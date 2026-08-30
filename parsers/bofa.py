"""Bank of America. Alerts come from onlinebanking@ealerts.bankofamerica.com.
Purchase bodies: `... Visa Signature ending in 1234 Amount: $54.98 Date: April 18, 2026 Where: FLIX This may have ...`"""
import re
from datetime import date

from . import BankParser, Email, Parsed


class BofA(BankParser):
    name = "Bank of America"
    senders = ("onlinebanking@ealerts.bankofamerica.com",)
    rules = [
        (r"credit card statement is available", "statement"),
        (r"credit received", "refund"),
        (r"credit card (?:charge|transaction|not present)|debit card (?:charge|transaction)|charge (?:over|made)", "purchase"),
        (r"^Zelle.* has been sent|^You sent \$", "zelle_out"),
        (r"sent you money|you received", "zelle_in"),
        (r"mobile check deposit", "deposit"),
        (r"statement is available|payment|zelle|apple pay|touch id|face id|fico|consent|insufficient|balance|"
         r"welcome|card is|virtual card|email address|receiving money|notifications|authorization code|"
         r"account information|recurring|year-end|delivery status|approved|request|security alert|notices|"
         r"shared your|wire", "skip"),
    ]

    def statement(self, e: Email):
        bal = self.amount(e.body, "Statement Balance")
        if bal is None:
            return None
        return Parsed("statement", last4=self.last4(e.body), date=self.date(e.body, e.received, "Statement Date"),
                      balance=bal, due=self.date(e.body, e.received, "due on"))

    def purchase(self, e: Email):
        amt = self.amount(e.body, "Amount")
        merchant = self.field(e.body, "Where")
        if amt is None or not merchant:
            return None
        return Parsed("purchase", amt, merchant, self.last4(e.body), self.date(e.body, e.received, "Date"))

    def refund(self, e: Email):
        amt = self.amount(e.body, "Amount")
        return Parsed("refund", amt, self.field(e.body, "Where") or "credit", self.last4(e.body),
                      self.date(e.body, e.received, "Date")) if amt else None

    def zelle_out(self, e: Email):
        amt = self.amount(e.subject)
        who = self.field(e.subject, "to", stop="has been sent") or "?"
        return Parsed("zelle_out", amt, "Zelle to " + who, self.last4(e.body), self.date(e.body, e.received)) if amt else None

    def zelle_in(self, e: Email):
        amt = self.amount(e.subject) or self.amount(e.body, "Amount")
        return Parsed("zelle_in", amt, "Zelle from " + (self.field(e.subject, "from") or "?"),
                      self.last4(e.body), self.date(e.body, e.received)) if amt else None

    def deposit(self, e: Email):
        amt = self.amount(e.body, "Check amount")
        return Parsed("deposit", amt, "Check deposit", self.last4(e.body),
                      self.date(e.body, e.received, "Credit posts on")) if amt else None

    # BofA → account → Download → CSV. File starts with a summary block, then: Date,Description,Amount,Running Bal.
    def csv_rows(self, header, rows):
        rows = list(rows)
        h = [c.strip().lower() for c in header]
        if "running bal." not in h and "running bal" not in h:
            # header may be further down after the preamble
            for n, r in enumerate(rows):
                if [c.strip().lower() for c in r][:3] == ["date", "description", "amount"]:
                    h, rows = [c.strip().lower() for c in r], rows[n + 1:]
                    break
            else:
                raise ValueError("not a BofA activity CSV (no Date,Description,Amount,Running Bal. header)")
        di, de, am = h.index("date"), h.index("description"), h.index("amount")
        for r in rows:
            if len(r) <= am or not r[am].strip():
                continue
            amt = float(r[am].replace(",", "").replace('"', ""))
            desc = r[de].strip()
            up = desc.upper()
            if "ONLINE PAYMENT" in up or "PAYMENT - THANK YOU" in up or "TRANSFER" in up and "ZELLE" not in up:
                continue
            if amt > 0:
                kind, merchant = ("zelle_in", "Zelle from " + up.split("FROM", 1)[-1].split(" CONF")[0].strip().title()) if "ZELLE" in up else ("deposit", desc)
            elif "ZELLE" in up:
                kind, merchant = "zelle_out", "Zelle to " + up.split(" TO ", 1)[-1].split(" CONF")[0].strip().title()
            else:
                kind, merchant = "purchase", desc
            yield Parsed(kind, abs(amt), merchant, None, self.date(r[di], None), posted=True)

    # BofA checking/savings eStatement PDFs (pdftotext -layout): "for December 13, 2025 to January 13, 2026",
    # sections "Deposits and other additions" / "Withdrawals and other subtractions" (+ "- continued") / "Service fees",
    # rows "MM/DD/YY  DESC  ±AMOUNT". Card eStatements use a different layout (not yet supported).
    PDF_ROW = re.compile(r"^\s*(\d{2})/(\d{2})/(\d{2})\s+(.+?)\s{2,}(-?[\d,]+\.\d{2})\s*$")
    OWN_ACCOUNT = re.compile(r"Online Banking transfer|Mobile Banking payment to CRD|payment to (?:CRD|ACCT#) ?\d{4}|transfer (?:to|from) (?:CHK|SAV|CRD)|"
                             r"DES:Ext Trnsfr|Fee Waiver", re.I)   # transfers between own accounts, card payments, $0 waiver lines

    def pdf_rows(self, text, filename=""):
        if not re.search(r"for [A-Z][a-z]+ \d{1,2}, \d{4} to [A-Z][a-z]+ \d{1,2}, \d{4}", text) or "Bank of America" not in text:
            raise ValueError("not a Bank of America eStatement")
        if "Withdrawals and other subtractions" not in text:
            raise ValueError("Bank of America card eStatements aren't supported yet (checking/savings are)")
        section = None
        for line in text.splitlines():
            u = line.strip()
            if u.startswith("Deposits and other additions"): section = "in"; continue
            if u.startswith("Withdrawals and other subtractions"): section = "out"; continue
            if u.startswith("Service fees"): section = "fee"; continue
            if u.startswith(("Total ", "Daily ledger balances", "Account summary")) and not u.startswith("Total deposits") : pass
            r = self.PDF_ROW.match(line)
            if not r or not section:
                continue
            desc, amt = re.sub(r"\s+", " ", r.group(4)).strip(), float(r.group(5).replace(",", ""))
            d = date(2000 + int(r.group(3)), int(r.group(1)), int(r.group(2)))
            up = desc.upper()
            if self.OWN_ACCOUNT.search(desc) or amt == 0:
                continue
            if section == "in":
                if up.startswith("ZELLE PAYMENT FROM"):
                    who = re.split(r" for \"| Conf#", desc[len("Zelle payment from "):], 1)[0]
                    yield Parsed("zelle_in", abs(amt), "Zelle from " + who.strip(), None, d, posted=True)
                elif "REFUND" in up or "CHECKCARD" in up or "PURCHASE" in up:
                    yield Parsed("refund", abs(amt), self._merchant(desc), None, d, posted=True)
                else:
                    yield Parsed("deposit", abs(amt), self._merchant(desc), None, d, posted=True)
                continue
            if up.startswith("ZELLE PAYMENT TO"):
                who = re.split(r" for \"| Conf#", desc[len("Zelle payment to "):], 1)[0]
                yield Parsed("zelle_out", abs(amt), "Zelle to " + who.strip(), None, d, posted=True)
            elif "ATM" in up and "WITHDRWL" in up:
                yield Parsed("purchase", abs(amt), "ATM withdrawal", None, d, posted=True)
            elif section == "fee":
                yield Parsed("purchase", abs(amt), "Fee: " + self._merchant(desc), None, d, posted=True)
            else:
                yield Parsed("purchase", abs(amt), self._merchant(desc), None, d, posted=True)

    @staticmethod
    def _merchant(desc: str) -> str:
        if re.match(r"BKOFAMERICA MOBILE .*DEPOSIT", desc, re.I):
            return "Mobile check deposit"
        m = re.sub(r"^(?:CHECKCARD|PURCHASE|PMNT SENT|PURCHASE REFUND)\s+\d{4}\s+", "", desc, flags=re.I)   # strip "CHECKCARD 1220 "
        m = re.sub(r"\s+\d{15,}.*$", "", m)                                                              # trailing reference numbers
        m = re.sub(r"\s+RECURRING$", "", m, flags=re.I)
        m = re.sub(r"\s+DES:.*$", "", m)                                                                   # ACH "DES:… ID:… INDN:…"
        m = re.sub(r"\s+(?:MOBILE|\*MOBILE)\s+[A-Z]{2}$", "", m)
        return m.strip()[:80]
