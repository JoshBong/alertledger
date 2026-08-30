# Email parsers

Each bank is a class in `parsers/<bank>.py`. `parsers/__init__.py` has the base class and the helpers; `parsers/chase.py` and
`parsers/bofa.py` are the two shipped examples. Subclassing `BankParser` registers the bank automatically — nothing else to wire.

## Anatomy of a bank
```python
from . import BankParser, Email, Parsed

class Chase(BankParser):
    name = "Chase"                                   # display name; key for default_checking in config
    senders = ("no.reply.alerts@chase.com",)         # exact From addresses. Everything else from the bank is ignored
    rules = [                                        # subject regex → handler method. First match wins, top to bottom
        (r"credit card statement is available", "statement"),
        (r"transaction with|debit card transaction of", "purchase"),
        (r"received money with Zelle", "zelle_in"),
        (r"payment|letter|security", "skip"),        # known noise → skip (never logged)
    ]                                                # no rule matches → returned as unparsed → parse_failures.jsonl

    def purchase(self, e: Email):
        amt = self.amount(e.subject) or self.amount(e.body, "Amount")
        merchant = self.field(e.subject, "transaction with") or self.field(e.body, "Merchant")
        if amt is None or not merchant:
            return None                              # "I recognised the subject but couldn't read it" → logged
        return Parsed("purchase", amt, merchant, self.last4(e.body, e.subject), self.date(e.body, e.received, "Date"))
```

`Email` = `subject`, `sender`, `body` (HTML flattened to one whitespace-normalised line, pipes/tables removed), `received` (date).

`Parsed(kind, amount, merchant, last4, date, balance, due)` — `kind` is one of
`purchase` · `refund` · `zelle_out` · `zelle_in` · `deposit` · `statement` · `skip`. Amount is always positive; the sign
and the "is this spend or income" decision come from `kind`.

## Helpers on the base class
| helper | does |
|---|---|
| `amount(text, label=None)` | first `$1,234.56`; with `label`, the amount right after that label (`"Amount"`, `"Statement balance"`) |
| `field(text, label, stop=None)` | text after `label` up to the next boilerplate word (`Amount`, `Date`, `Where`, `Location`, `This may have`, …) or a `$`. Override `stop` for one-offs |
| `last4(*texts)` | `(...1234)`, `ending in 1234`, `Visa Signature - 1234`; falls back to the bank's `default_checking` from config |
| `date(text, default, label=None)` | `Aug 3, 2026` / `August 3, 2026` / `08/03/2026`; with `label`, only the date after that label |

## Adding a bank
1. Enable the bank's email alerts and let a few arrive. Run `python3 alertledger.py sync`; they land in
   `~/.alertledger/parse_failures.jsonl` as unknown-sender or unparsed, **with the flattened body** — that's your spec.
2. Create `parsers/<bank>.py` with `name`, `senders`, `rules`, and a handler per subject shape. Import it at the bottom of
   `parsers/__init__.py`.
3. Copy each real body into `tests/test_parsers.py` (scrub your card digits) and assert the fields. `python3 -m unittest -v`.
4. Re-run `sync --full`. Dedup is by `(bank, last4, date, amount, merchant)`, so a bank that sends two alerts for one
   purchase (BofA does) produces one row as long as the handlers agree on those five.

Rule of thumb: **one handler per email shape, explicit `skip` for known noise, `None` for anything you can't read.**
Silence is the bug; the failures file is the feature.

## CSV imports (`csv_rows`)
Each bank can also read its own activity-export CSV so users can backfill history and get the bank's *posted* amounts:

```python
    def csv_rows(self, header, rows):          # header: list[str]; rows: list[list[str]]
        h = [c.strip().lower() for c in header]
        if "transaction date" in h and "category" in h:   # sniff the layout — banks ship one per account type
            ...
            yield Parsed("purchase", abs(amt), desc, None, self.date(post_date, None), category=bank_cat, posted=True)
        else:
            raise ValueError("not a <Bank> activity CSV")
```
The account is chosen by the user at import time (`./alertledger import chase_2637 file.csv` or the Data tab), because bank
CSVs are per account and don't name it. `posted=True` rows replace any pending alert row with the same amount within
3 days, and their `category` (if the bank supplies one) is mapped through `categories.BANK_MAP`.
Skip the bank's own-account payments/transfers in `csv_rows` — they aren't spending.
