"""Gmail over IMAP: search All Mail by the registered bank senders, yield flattened Emails."""
import email
import email.utils
import imaplib
import re
from datetime import date
from email.header import decode_header, make_header
from html import unescape
from typing import Iterator

from parsers import Email, all_senders

MAILBOX = "[Gmail]/All Mail"


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
    s = s.replace("\xa0", " ").replace("|", " ").replace("®", "").replace("℠", "")
    s = re.sub(r"\[\]\([^)]*\)", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def login(user: str, app_password: str) -> imaplib.IMAP4_SSL:
    M = imaplib.IMAP4_SSL("imap.gmail.com")
    M.login(user, app_password)
    return M


def fetch(user: str, app_password: str, since: date | None) -> Iterator[Email]:
    M = login(user, app_password)
    if M.select(f'"{MAILBOX}"', readonly=True)[0] != "OK":
        raise RuntimeError(f"cannot open {MAILBOX}")
    senders = all_senders()
    crit = "OR " * (len(senders) - 1) + " ".join(f'FROM "{s}"' for s in senders)
    if since:
        crit += f' SINCE {since.strftime("%d-%b-%Y")}'
    _, data = M.search(None, f"({crit})")
    for i in data[0].split():
        _, d = M.fetch(i, "(RFC822)")
        msg = email.message_from_bytes(d[0][1])
        try:
            received = email.utils.parsedate_to_datetime(msg["Date"]).date()
        except Exception:
            received = date.today()
        yield Email(norm(str(make_header(decode_header(msg.get("Subject", ""))))), msg.get("From", ""), flatten(msg), received)
    M.logout()
