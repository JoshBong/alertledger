"""Chase. Alerts come from no.reply.alerts@chase.com. Bodies are `label value` pairs."""
import re

from . import BankParser, Email, Parsed


class Chase(BankParser):
    name = "Chase"
    senders = ("no.reply.alerts@chase.com",)
    rules = [
        (r"credit card statement is available", "statement"),
        (r"transaction with|debit card transaction of", "purchase"),
        (r"refund|credit (?:was )?posted", "refund"),
        (r"received money with Zelle", "zelle_in"),
        (r"sent money with Zelle|^You sent", "zelle_out"),
        (r"daily account summary", "skip"),          # TODO: parse posted transactions once a real one is seen
        (r"statement is now available|payment|letter|credit summary|zelle|transfer|external bank|approved|"
         r"account is open|data access|sharing data|security|sign.?in|password|alert|paperless|notifications|"
         r"digital wallet|external account|check deposit|welcome|identity|credit journey", "skip"),
    ]

    def statement(self, e: Email):
        bal = self.amount(e.body, "Statement balance")
        if bal is None:
            return None
        return Parsed("statement", last4=self.last4(e.body, e.subject), date=e.received, balance=bal,
                      due=self.date(e.body, e.received, "Due date"))

    def purchase(self, e: Email):
        amt = self.amount(e.subject) or self.amount(e.body, "Amount")
        merchant = self.field(e.subject, "transaction with") or self.field(e.body, "Merchant")
        if amt is None or not merchant:
            return None
        return Parsed("purchase", amt, merchant, self.last4(e.body, e.subject), self.date(e.body, e.received, "Date"))

    def refund(self, e: Email):
        amt = self.amount(e.subject) or self.amount(e.body, "Amount")
        merchant = self.field(e.body, "Merchant") or "refund"
        return Parsed("refund", amt, merchant, self.last4(e.body, e.subject), self.date(e.body, e.received)) if amt else None

    def zelle_in(self, e: Email):
        amt = self.amount(e.body, "Amount")
        m = re.search(r"(?:Zelle payment\s+)?([A-Z][A-Za-z0-9 .'\-]{1,40}?) sent you money", e.body)
        return Parsed("zelle_in", amt, "Zelle from " + (m.group(1).strip() if m else "?"),
                      self.last4(e.body), self.date(e.body, e.received, "Sent on")) if amt else None

    def zelle_out(self, e: Email):
        amt = self.amount(e.subject) or self.amount(e.body, "Amount")
        who = self.field(e.subject, "to") or self.field(e.body, "To") or "?"
        return Parsed("zelle_out", amt, "Zelle to " + who, self.last4(e.body), self.date(e.body, e.received)) if amt else None

    # Chase → account → "Download activity" → CSV. Two layouts:
    #   card:     Transaction Date,Post Date,Description,Category,Type,Amount,Memo
    #   checking: Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #
    def csv_rows(self, header, rows):
        h = [c.strip().lower() for c in header]
        if "transaction date" in h and "category" in h:
            i = {k: h.index(k) for k in ("transaction date", "post date", "description", "category", "type", "amount")}
            for r in rows:
                if len(r) <= i["amount"] or not r[i["amount"]]:
                    continue
                amt = float(r[i["amount"]])
                typ = r[i["type"]].strip().lower()
                if typ == "payment":
                    continue                                            # own-account payment, not spend
                kind = "refund" if amt > 0 else "purchase"
                yield Parsed(kind, abs(amt), r[i["description"]].strip(), None, self.date(r[i["post date"]] or r[i["transaction date"]], None),
                             category=r[i["category"]].strip() or None, posted=True)
        elif "details" in h and "posting date" in h:
            i = {k: h.index(k) for k in ("details", "posting date", "description", "amount", "type")}
            for r in rows:
                if len(r) <= i["type"] or not r[i["amount"]]:
                    continue
                amt = float(r[i["amount"]])
                typ = r[i["type"]].strip().upper()
                desc = r[i["description"]].strip()
                if typ in ("ACCT_XFER", "LOAN_PMT") or "PAYMENT TO CHASE CARD" in desc.upper():
                    continue                                            # transfers between own accounts
                if amt > 0:
                    kind, merchant = "deposit", ("Zelle from " + desc.split("FROM", 1)[-1].strip() if "ZELLE" in desc.upper() else desc)
                elif "ZELLE" in desc.upper():
                    kind, merchant = "zelle_out", "Zelle to " + desc.split(" TO ", 1)[-1].split(" ")[0] if " TO " in desc.upper() else desc
                else:
                    kind, merchant = "purchase", desc
                yield Parsed(kind, abs(amt), merchant, None, self.date(r[i["posting date"]], None), posted=True)
        else:
            raise ValueError("not a Chase activity CSV (expected card or checking headers)")
