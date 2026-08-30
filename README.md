# alertledger

Your bank already emails you every purchase. alertledger turns those alerts into a ledger — no aggregator, no bank
credentials, no monthly CSV pulls. Gmail → IMAP → SQLite → three reports. Python 3.11+, stdlib only.

Built after Teller shut down (July 2026) and left US individuals with no free bank API. Alerts are the one feed banks
give you for free, forever.

```
bank purchase alert ──► Gmail ──► sync.py (IMAP, search by sender) ──► ledger.db ──► report.py
                                                                          ▲
statement-ready mail ─────────────────────────────────────────────────────┘  (monthly checksum)
```

## Supported
| Bank | Email | Becomes |
|---|---|---|
| Chase | card / debit purchase alert | spend row |
| Chase | Zelle received | income row (excluded from spend) |
| Chase | credit card statement available | statement balance (checksum) |
| Bank of America | credit card charge / online charge / credit received | spend or refund row (double alerts dedupe) |
| Bank of America | Zelle sent | spend row |
| Bank of America | credit card statement available | statement balance (checksum) |

Statement and Zelle parsers are verified against real emails; purchase-alert parsers are written from the documented
subject lines and are confirmed as real alerts arrive (Aug 2026). Unrecognised mails from those senders go to `~/.alertledger/parse_failures.jsonl` — nothing is dropped silently.
Other banks: add a sender to `SENDERS`, a name to `BANKS`, and (if needed) a regex to `MERCHANT`/`LAST4`. PRs welcome.

## Setup
1. **Turn on email alerts at your bank, lowest threshold.** Chase: Alerts → Transactions → purchase over `$0`.
   BofA credit: "Credit card charge over `$0`" + "Credit received". BofA checking only offers per-swipe alerts ≥$100;
   use "Debit card charge made online, by phone, or mail" (any amount) and accept the gap.
2. *(optional)* Gmail filter `from:(no.reply.alerts@chase.com OR onlinebanking@ealerts.bankofamerica.com)` → skip inbox,
   label it. The importer searches All Mail by sender, so this is only for inbox hygiene.
3. Google **app password** (2-Step Verification → App passwords).
4. `~/.alertledger/config.json` (chmod 600):
   ```json
   {"gmail_user": "you@gmail.com", "gmail_app_password": "xxxx xxxx xxxx xxxx",
    "default_checking": {"Chase": "1234", "Bank of America": "5678"}}
   ```
   `default_checking` = last-4 of the checking account Zelle mails belong to when they don't say.
5. `cp rules.example.toml rules.toml` and edit — alerts carry no bank category, so this is your categorizer.
6. `python3 sync.py --full` once, then `python3 sync.py --install-launchd` (macOS, daily 08:00, last 14 days). Linux: cron it.

## Reports
```
python3 report.py recurring                 # monthly-cadence charges across all cards (subscriptions you forgot)
python3 report.py breakdown --month 2026-08 # category × card;  --all = month over month
python3 report.py txns --month 2026-08 --grep google
python3 report.py checksum                  # statement balance vs our charges per cycle → how much the alerts missed
```

## Caveats
- Alerts fire at authorization; posted amounts can differ (tips). Rows stay `status=pending`. `checksum` shows the drift.
- `checksum` assumes autopay pays each statement in full.
- Two identical (bank, card, date, amount, merchant) purchases collapse into one row.
- No history before you enabled alerts. Backfill from a CSV export if you care.
