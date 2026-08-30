"""Ingest bank alert emails into budget.db over IMAP (server-side search by sender; no Gmail filter required).

Handles: purchase alerts (Chase + BofA) → transactions (status=pending, auth-time amounts)
         Zelle sent → spend row; Zelle received → income row (type=transfer, excluded from spend reports)
         statement-ready mails → statements table (monthly checksum: our net charges vs bank's statement balance)
Anything from the banks that isn't recognised → ~/.budget/parse_failures.jsonl, never silently dropped.
"""
import email
import email.utils
import hashlib
import imaplib
import json
import re
from datetime import date, datetime
from email.header import decode_header, make_header
from html import unescape

import config
import db

MAILBOX = "[Gmail]/All Mail"
SENDERS = ["no.reply.alerts@chase.com", "onlinebanking@ealerts.bankofamerica.com"]
BANKS = {"chase.com": "Chase", "bankofamerica.com": "Bank of America"}
_DEFAULT_CHECKING: dict = {}   # bank → last4, from config "default_checking"; Zelle mails don't always name the account

AMT = r"\$\s?([0-9,]+\.\d{2})"
LAST4 = [re.compile(r"\(\s*\.{3}\s*(\d{4})\s*\)"),                    # Chase "(...1234)"
         re.compile(r"ending (?:in|with)\s*:?\s*(?:\*+|x+)?(\d{4})", re.I),   # BofA "ending in 1234"
         re.compile(r"(?:Signature|Card|Banking|Savings|Checking)\s*-\s*(\d{4})\b", re.I)]   # BofA "Visa Signature - 1234"
DATES = [(re.compile(r"\b([A-Z][a-z]{2,8} \d{1,2}, \d{4})"), ("%b %d, %Y", "%B %d, %Y")),
         (re.compile(r"\b(\d{2}/\d{2}/\d{4})"), ("%m/%d/%Y",))]
VALUE_END = r"(?=\s+(?:Amount|When|Date|Card|Account|Sent|To|Merchant|Where|Transaction|Memo|View|If|Confirmation)\b|\s*\$|$)"
MERCHANT = [re.compile(r"transaction with (.+?)" + VALUE_END, re.I),                  # Chase card subject/body
            re.compile(r"\b(?:Merchant|Where|Description|Payee)\s*:?\s+(.+?)" + VALUE_END, re.I),
            re.compile(r"payment of " + AMT + r" to (.+?) has been sent", re.I),        # BofA Zelle sent (group 2)
            re.compile(r"\bTo\s*:?\s+([A-Z][A-Z0-9 &'.\-]{2,60}?)" + VALUE_END)]         # Chase Zelle sent "To NAME"
IGNORE = re.compile(r"payment (?:is scheduled|has been applied|received)|received your .* payment|automatic payment|"
                    r"new letter|credit summary|welcome to zelle|zelle recipient|deleted from zelle|password|sign.?in|"
                    r"security|data access|sharing data|statement is now available|your statement is available", re.I)
STATEMENT = re.compile(r"credit card statement is available", re.I)
ZELLE_SENT = re.compile(r"zelle.*(?:has been sent|you sent)|you sent money", re.I)
ZELLE_RECV = re.compile(r"received money|sent you money", re.I)
REFUND = re.compile(r"refund|credit (?:received|posted|to your)|was credited|return", re.I)


def flatten(msg) -> str:
    parts = []
    for p in msg.walk():
        ct = p.get_content_type()
        if ct in ("text/plain", "text/html") and p.get_content_disposition() is None:
            raw = p.get_payload(decode=True) or b""
            s = raw.decode(p.get_content_charset() or "utf-8", errors="replace")
            if ct == "text/html":
                s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
                s = re.sub(r"<[^>]+>", " ", s)
            parts.append(unescape(s))
    return norm("\n".join(parts))


def norm(s: str) -> str:
    s = s.replace("\xa0", " ").replace("|", " ").replace("®", "")
    s = re.sub(r"\[\]\([^)]*\)", " ", s)          # markdown-ish link residue
    return re.sub(r"\s+", " ", s).strip()


def find_date(text: str, default: date) -> date:
    for rx, fmts in DATES:
        for m in rx.finditer(text):
            for f in fmts:
                try:
                    return datetime.strptime(m.group(1), f).date()
                except ValueError:
                    continue
    return default


def find_last4(*texts):
    for t in texts:
        for rx in LAST4:
            m = rx.search(t)
            if m:
                return m.group(1)
    return None


def find_merchant(*texts):
    for t in texts:
        for rx in MERCHANT:
            m = rx.search(t)
            if m:
                return re.sub(r"\s+", " ", m.group(m.lastindex)).strip(" .:")[:80]
    return None


def labeled_amount(text: str, label: str):
    m = re.search(label + r"\s*:?\s*" + AMT, text, re.I)
    return float(m.group(1).replace(",", "")) if m else None


def parse(subject: str, sender: str, body: str, received: date) -> dict | None:
    """→ {"kind": "txn"|"statement"|"skip", ...} or None (= unrecognised)."""
    bank = next((b for k, b in BANKS.items() if k in sender), None)
    if not bank:
        return None
    subject = norm(subject)
    if STATEMENT.search(subject):
        bal = labeled_amount(body, "Statement balance")
        if bal is None:
            return None
        sd = re.search(r"Statement Date\s*:?\s*([A-Z][a-z]+ \d{1,2}, \d{4})", body)
        due = re.search(r"(?:Due date|due on)\s*:?\s*([A-Za-z0-9/, ]+?\d{4})", body)
        return {"kind": "statement", "bank": bank, "last4": find_last4(body, subject),
                "statement_date": (find_date(sd.group(1), received) if sd else received).isoformat(),
                "balance": bal, "due_date": find_date(due.group(1), received).isoformat() if due else None}
    if IGNORE.search(subject):
        return {"kind": "skip"}
    m = re.search(AMT, subject) or re.search(r"Amount\s*:?\s*" + AMT, body) or re.search(AMT, body)
    if not m:
        return None
    amount = float(m.group(1).replace(",", ""))
    last4 = find_last4(subject, body) or _DEFAULT_CHECKING.get(bank)
    merchant = find_merchant(subject, body)
    if ZELLE_RECV.search(subject):
        who = re.search(r"([A-Z][A-Z0-9 .'\-]{2,40}?) sent you money", body)
        return {"kind": "txn", "bank": bank, "last4": last4, "date": find_date(body, received).isoformat(),
                "amount": amount, "merchant": "Zelle from " + (who.group(1).strip() if who else "?"), "type": "transfer", "subject": subject}
    if ZELLE_SENT.search(subject):
        return {"kind": "txn", "bank": bank, "last4": last4, "date": find_date(body, received).isoformat(),
                "amount": -amount, "merchant": "Zelle to " + (merchant or "?"), "type": "zelle", "subject": subject}
    if not merchant:
        return None
    sign = 1 if REFUND.search(subject) else -1
    return {"kind": "txn", "bank": bank, "last4": last4, "date": find_date(body, received).isoformat(),
            "amount": sign * amount, "merchant": merchant, "type": "card_payment", "subject": subject}


def account_id(bank: str, last4: str | None) -> str:
    return f"{bank.lower().replace(' ', '')}_{last4 or 'xxxx'}"


def txn_row(p: dict) -> dict:
    key = f"{p['bank']}|{p['last4']}|{p['date']}|{p['amount']:.2f}|{p['merchant'].lower()}"
    return {"id": "mail_" + hashlib.sha1(key.encode()).hexdigest()[:20], "account_id": account_id(p["bank"], p["last4"]),
            "date": p["date"], "description": p["merchant"], "amount": str(p["amount"]), "status": "pending",
            "type": p["type"], "running_balance": None,
            "details": {"category": None, "counterparty": {"name": p["merchant"]}, "source": "email", "subject": p["subject"]}}


def ensure_account(con, bank, last4):
    db.upsert_account(con, {"id": account_id(bank, last4), "enrollment_id": "email", "institution": {"name": bank},
                            "name": f"{bank} ••{last4 or '????'}", "type": None, "subtype": None, "last_four": last4,
                            "status": "open", "currency": "USD"})


def ingest(con, subject, sender, body, received) -> str:
    p = parse(subject, sender, body, received)
    if p is None:
        return "fail"
    if p["kind"] == "skip":
        return "skip"
    ensure_account(con, p["bank"], p["last4"])
    if p["kind"] == "statement":
        db.upsert_statement(con, account_id(p["bank"], p["last4"]), p["statement_date"], p["balance"], p["due_date"])
        return "statement"
    db.upsert_transaction(con, txn_row(p))
    return "txn"


def run(cfg: dict, con, since: date | None = None) -> dict:
    _DEFAULT_CHECKING.update(cfg.get("default_checking", {}))
    M = imaplib.IMAP4_SSL("imap.gmail.com")
    M.login(cfg["gmail_user"], cfg["gmail_app_password"])
    if M.select(f'"{MAILBOX}"', readonly=True)[0] != "OK":
        raise SystemExit(f"IMAP: cannot open {MAILBOX!r}")
    crit = "OR " * (len(SENDERS) - 1) + " ".join(f'FROM "{s}"' for s in SENDERS)
    if since:
        crit += f' SINCE {since.strftime("%d-%b-%Y")}'
    _, data = M.search(None, f"({crit})")
    counts = {"txn": 0, "statement": 0, "skip": 0, "fail": 0}
    with open(config.HOME / "parse_failures.jsonl", "a") as failures:
        for i in data[0].split():
            _, d = M.fetch(i, "(RFC822)")
            msg = email.message_from_bytes(d[0][1])
            subject = str(make_header(decode_header(msg.get("Subject", ""))))
            sender = msg.get("From", "")
            try:
                received = email.utils.parsedate_to_datetime(msg["Date"]).date()
            except Exception:
                received = date.today()
            body = flatten(msg)
            r = ingest(con, subject, sender, body, received)
            counts[r] += 1
            if r == "fail":
                failures.write(json.dumps({"subject": subject, "from": sender, "date": received.isoformat(), "body": body[:1500]}) + "\n")
    con.commit()
    M.logout()
    return counts
