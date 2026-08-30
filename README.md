# alertledger

Your bank already emails you every purchase. alertledger turns those alerts into a ledger and a dashboard — no aggregator,
no bank credentials, no CSV exports. Runs on a Raspberry Pi (or anything with Python 3.11+), view it from your phone.

Built after Teller shut down (July 2026) and left individuals with no free bank API. Alert emails are the one feed banks
give you for free.

```
bank purchase alert ──► Gmail ──► alertledger (one process: hourly IMAP pull + web UI) ──► http://pi:8080
statement-ready mail ──┘                                                                   └─ ~/.alertledger/ledger.db
```

- **Install:** `git clone https://github.com/JoshBong/alertledger && cd alertledger && ./install.sh` → [docs/setup.md](docs/setup.md)
- **Banks:** Chase, Bank of America. Adding one is a ~40-line subclass → [docs/parsers.md](docs/parsers.md)
- **Dashboard:** monthly spend by card, categories, recurring charges (the subscriptions you forgot), per-statement
  checksum (how much the alerts missed vs. the bank's balance), searchable transactions, **Sync now**.
- **Zero dependencies.** Python stdlib only; SQLite on disk; one file of HTML.

Caveats: alerts fire at authorization, so amounts can drift when they post (tips) — the checksum shows the drift. No history
before you turned alerts on (except what your bank already emailed). Two identical purchases on the same day at the same
merchant collapse into one row.
