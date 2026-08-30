"""Bank of America. Alerts come from onlinebanking@ealerts.bankofamerica.com.
Purchase bodies: `... Visa Signature ending in 1234 Amount: $54.98 Date: April 18, 2026 Where: FLIX This may have ...`"""
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
