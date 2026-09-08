# Setup

## 1. Bank alerts → email
Turn on **email** alerts for every purchase, lowest threshold the bank allows. This is the data feed; nothing else is needed.

| Bank | Where | Turn on |
|---|---|---|
| Chase | Profile & settings → Alerts → each card/account → **Transactions** | purchase / transaction over **$0** → email. Also **Payments → statement available** (usually on already) |
| Bank of America credit card | Alerts → card → | **Credit card charge over $0**, **Credit received**, (charge made online is fine too — duplicates are merged) |
| Bank of America checking | Alerts → checking | **Debit card charge made online, by phone, or mail** (BofA's per-swipe alert has a $100 minimum, so in-person debit swipes under $100 aren't captured) |

| Venmo | nothing to set up | payment emails (`You paid…`, `… paid you`) are on by default |

Emails from other bank senders (marketing, promos) are ignored by sender address. Bank-side `VENMO` rows (funding pulls, cash-outs) are treated as transfers so Venmo spend is counted once, from Venmo's own emails.

## 2. Google app password
budgetmail reads your Gmail over IMAP. Google requires an *app password* for that (your normal password won't work):
myaccount.google.com/apppasswords → name it `budgetmail` → copy the 16 characters. Needs 2-Step Verification on. Revoke it there any time.

## 3. Install
```
git clone https://github.com/JoshBong/budgetmail && cd budgetmail && ./install.sh
```
The wizard asks for the Gmail address + app password and **tests the login before saving anything**, then which checking account Zelle mails belong to (last 4), then a port. It pulls the whole mailbox once (a few minutes — BofA alert history often goes back years), and registers a service:

- Raspberry Pi / Linux: systemd `budgetmail` (starts on boot, restarts on failure). `journalctl -u budgetmail -f` for logs.
- macOS: launchd `io.budgetmail` (starts at login).

Then open `http://<host>:8080`. The service syncs every 60 minutes; the **Sync now** button pulls immediately.

Config lives in `~/.budgetmail/config.json` (mode 600). `sync_interval_min` and `port` are editable there; restart the service after.

## 4. Viewing from anywhere
Don't expose the port to the internet. Install [Tailscale](https://tailscale.com) on the box and your phone/laptop — same URL works from any network, encrypted, no port-forwarding, free for personal use.

## Backfill from statements / exports
Alerts only exist from the day you turned them on. For history, drop the bank's files on the Data tab (or
`./budgetmail import file1.pdf file2.csv …`):

| Bank | File | Account detection |
|---|---|---|
| Chase | statement **PDF** (`20260821-statements-2637-.pdf`) — card or checking | from the filename |
| Chase | activity **CSV** (`Chase2637_Activity_….CSV`) | from the filename |
| Bank of America | activity CSV | picked in the UI / `--account` (file doesn't say) |

Imported rows are the bank's *posted* data: they replace pending alert rows for the same charge, carry the bank's category
where it provides one, and card statements also record the closing balance. **The same file twice is ignored** (file hash),
and identical rows from overlapping files dedupe.

PDF import needs `pdftotext` (poppler): macOS `brew install poppler`, Raspberry Pi / Debian `sudo apt install poppler-utils`.
Without it, CSV import still works.

## Budgets
On the Spending tab, each category card has **+ budget**. Set a monthly amount (or take the 3-month average it suggests).
The card then shows a bar of spent-vs-budget with a tick at "where you should be today", the projected month-end pace, and
the donut shows total spent vs total budgeted. No rollover; budgets are the same every month until you change them.
Stored in the database (`budgets` table).

## Categories
The fixed set is in `categories.py`: Food & Dining · Groceries · Shopping · Travel · Transport · Bills & Subscriptions · Health · People · Other.
`rules.toml` (copied from `rules.example.toml` on setup) maps merchant regexes into them; `ignore = true` drops own-account payments from spend. The Spending tab shows how many transactions fell into Other, so you know when to add a rule.

## Day-to-day commands
```
./budgetmail stop / start                pause or resume the service (keeps it installed)
./budgetmail status                      service state, last sync, ledger totals, URL
./budgetmail doctor                      python · config · Gmail login · database · service · port
./budgetmail config                      show config (password masked)
./budgetmail config set port 8090        also: sync_interval_min 30 · default_checking.Chase 1234   (restarts the service)
./budgetmail config gmail                re-enter the Gmail login (tested before saving)
./budgetmail update                      git pull → run tests → restart the service
./budgetmail sync [--full]               pull now from the terminal
```
`./install.sh` is only for first install; `update` is the everyday one.

## Uninstall
`python3 budgetmail.py uninstall` (sudo on Linux), delete `~/.budgetmail`, revoke the app password.
