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
- **Sources:** Chase, Bank of America, Venmo. Adding one is a ~40-line subclass → [docs/parsers.md](docs/parsers.md)
- **Dashboard:** phone-first, four tabs — **Spending** (one month, donut by category or account, tap to drill), **Transactions**
  (filter/search), **Trends** (12 months, recurring charges, category month-over-month), **Data** (sync, accounts, CSV import, checksum).
- **Backfill:** drag in Chase statement PDFs or bank CSV exports; posted rows replace the alert-time ones, the same file twice is ignored.
- **Budgets:** per category, with a "where you should be today" tick and month-end pace.
- **Zero dependencies.** Python stdlib only; SQLite on disk. (PDF import shells out to `pdftotext` if installed.)

## Commands
```
./install.sh                      first install: setup wizard → first pull → register the service
./alertledger status              service state · last sync · ledger totals · URL
./alertledger stop | start        pause / resume the service (stays installed)
./alertledger update              git pull → run tests → restart
./alertledger doctor              check python · config · Gmail login · database · service · port
./alertledger config              show config (password masked)
./alertledger config set port 8090            also: sync_interval_min 30 · default_checking.Chase 1234
./alertledger config gmail        re-enter the Gmail login (tested before saving)
./alertledger sync [--full]       pull mail now from the terminal (--full = whole mailbox)
./alertledger import <files…>     backfill from statement PDFs / CSV exports (account auto-detected)
./alertledger backup | restore <zip>   move everything to another machine (Data tab has a download button too)
./alertledger serve               run in the foreground (what the service runs)
./alertledger install | uninstall register / remove the service (systemd on Linux, launchd on macOS)
```

Caveats: alerts fire at authorization, so amounts can drift when they post (tips) — the checksum shows the drift. No history
before you turned alerts on (except what your bank already emailed). Two identical purchases on the same day at the same
merchant collapse into one row.
