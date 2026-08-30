# Setup

## 1. Bank alerts → email
Turn on **email** alerts for every purchase, lowest threshold the bank allows. This is the data feed; nothing else is needed.

| Bank | Where | Turn on |
|---|---|---|
| Chase | Profile & settings → Alerts → each card/account → **Transactions** | purchase / transaction over **$0** → email. Also **Payments → statement available** (usually on already) |
| Bank of America credit card | Alerts → card → | **Credit card charge over $0**, **Credit received**, (charge made online is fine too — duplicates are merged) |
| Bank of America checking | Alerts → checking | **Debit card charge made online, by phone, or mail** (BofA's per-swipe alert has a $100 minimum, so in-person debit swipes under $100 aren't captured) |

Emails from other bank senders (marketing, promos) are ignored by sender address.

## 2. Google app password
alertledger reads your Gmail over IMAP. Google requires an *app password* for that (your normal password won't work):
myaccount.google.com/apppasswords → name it `alertledger` → copy the 16 characters. Needs 2-Step Verification on. Revoke it there any time.

## 3. Install
```
git clone https://github.com/JoshBong/alertledger && cd alertledger && ./install.sh
```
The wizard asks for the Gmail address + app password and **tests the login before saving anything**, then which checking account Zelle mails belong to (last 4), then a port. It pulls the whole mailbox once (a few minutes — BofA alert history often goes back years), and registers a service:

- Raspberry Pi / Linux: systemd `alertledger` (starts on boot, restarts on failure). `journalctl -u alertledger -f` for logs.
- macOS: launchd `io.alertledger` (starts at login).

Then open `http://<host>:8080`. The service syncs every 60 minutes; the **Sync now** button pulls immediately.

Config lives in `~/.alertledger/config.json` (mode 600). `sync_interval_min` and `port` are editable there; restart the service after.

## 4. Viewing from anywhere
Don't expose the port to the internet. Install [Tailscale](https://tailscale.com) on the box and your phone/laptop — same URL works from any network, encrypted, no port-forwarding, free for personal use.

## Categories
`rules.toml` (copied from `rules.example.toml` on setup) maps merchant regexes → categories; `ignore = true` drops own-account payments from spend. Alerts carry no category from the bank, so this file is the categorizer.

## Day-to-day commands
```
./alertledger status                      service state, last sync, ledger totals, URL
./alertledger doctor                      python · config · Gmail login · database · service · port
./alertledger config                      show config (password masked)
./alertledger config set port 8090        also: sync_interval_min 30 · default_checking.Chase 1234   (restarts the service)
./alertledger config gmail                re-enter the Gmail login (tested before saving)
./alertledger update                      git pull → run tests → restart the service
./alertledger sync [--full]               pull now from the terminal
```
`./install.sh` is only for first install; `update` is the everyday one.

## Uninstall
`python3 alertledger.py uninstall` (sudo on Linux), delete `~/.alertledger`, revoke the app password.
