#!/usr/bin/env python3
"""alertledger — bank alert emails → ledger → dashboard. One process: hourly sync + web UI.

  python3 alertledger.py setup       interactive: Gmail login (tested), accounts, port
  python3 alertledger.py sync        pull mail now (--full = whole mailbox)
  python3 alertledger.py serve       run forever: sync every N minutes + dashboard on :PORT
  python3 alertledger.py install     register `serve` as a system service (systemd / launchd) and start it
  python3 alertledger.py uninstall
"""
import argparse
import getpass
import json
import os
import plistlib
import subprocess
import sys
import threading
import time
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import config
import ledger
import mail
import parsers

HERE = Path(__file__).resolve().parent
SERVICE = "alertledger"


# ---------------------------------------------------------------- sync
def sync(con, cfg: dict, full: bool = False) -> dict:
    parsers.configure(cfg.get("default_checking", {}))
    since = None if full else date.today() - timedelta(days=14)
    counts = {"txn": 0, "statement": 0, "skip": 0, "unparsed": 0, "unknown_sender": 0}
    config.ensure_home()
    with open(config.FAILURES, "a") as failures:
        for e in mail.fetch(cfg["gmail_user"], cfg["gmail_app_password"], since):
            bank = parsers.for_sender(e.sender)
            if not bank:
                counts["unknown_sender"] += 1
                continue
            p = bank.parse(e)
            if p is None:
                counts["unparsed"] += 1
                failures.write(json.dumps({"bank": bank.name, "subject": e.subject, "date": e.received.isoformat(), "body": e.body[:1500]}) + "\n")
            elif p.kind == "skip":
                counts["skip"] += 1
            else:
                counts[ledger.record(con, bank.name, p, e.subject)] += 1
    ledger.set_meta(con, "last_sync", datetime.now().isoformat(timespec="seconds"))
    ledger.set_meta(con, "last_counts", json.dumps(counts))
    con.commit()
    return counts


# ---------------------------------------------------------------- serve
class Handler(BaseHTTPRequestHandler):
    con = None
    cfg = None
    lock = threading.Lock()

    def log_message(self, *a):
        pass

    def _send(self, body: bytes, ctype="text/html; charset=utf-8", code=200):
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            import dashboard
            self._send(dashboard.render(self.con).encode())
        elif self.path == "/api/status":
            self._send(json.dumps({"last_sync": ledger.get_meta(self.con, "last_sync"), "counts": json.loads(ledger.get_meta(self.con, "last_counts", "{}"))}).encode(), "application/json")
        else:
            self._send(b"not found", "text/plain", 404)

    def do_POST(self):
        if self.path == "/api/sync":
            with self.lock:
                try:
                    counts = sync(self.con, self.cfg)
                    self._send(json.dumps(counts).encode(), "application/json")
                except Exception as ex:  # surface the error to the button, don't kill the server
                    self._send(json.dumps({"error": str(ex)}).encode(), "application/json", 500)
        else:
            self._send(b"not found", "text/plain", 404)


def serve(cfg: dict):
    con = ledger.connect(str(config.DB))
    Handler.con, Handler.cfg = con, cfg
    interval = max(5, int(cfg.get("sync_interval_min", 60))) * 60

    def loop():
        while True:
            with Handler.lock:
                try:
                    c = sync(con, cfg)
                    print(datetime.now().strftime("%H:%M"), "sync", c, flush=True)
                except Exception as ex:
                    print(datetime.now().strftime("%H:%M"), "sync failed:", ex, flush=True)
            time.sleep(interval)

    threading.Thread(target=loop, daemon=True).start()
    port = int(cfg.get("port", 8080))
    print(f"alertledger on http://0.0.0.0:{port}  (sync every {interval // 60} min)", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


# ---------------------------------------------------------------- setup
def setup():
    cur = {}
    if config.CONFIG.exists():
        cur = json.loads(config.CONFIG.read_text())
    print("alertledger setup — Gmail is read over IMAP with an app password (myaccount.google.com/apppasswords)\n")
    user = input(f"Gmail address [{cur.get('gmail_user', '')}]: ").strip() or cur.get("gmail_user", "")
    pw = getpass.getpass("App password (hidden, 16 chars): ").strip() or cur.get("gmail_app_password", "")
    print("testing login…", end=" ", flush=True)
    try:
        mail.login(user, pw).logout()
        print("ok")
    except Exception as ex:
        raise SystemExit(f"FAILED: {ex}\nCheck the address, that 2-Step Verification is on, and that the app password is fresh.")
    dc = dict(cur.get("default_checking", {}))
    print("\nZelle/deposit emails don't always name the account. For each bank, the last 4 of the checking account they belong to (blank to skip):")
    for name in ("Chase", "Bank of America"):
        v = input(f"  {name} checking last-4 [{dc.get(name, '')}]: ").strip() or dc.get(name)
        if v:
            dc[name] = v
    port = input(f"Dashboard port [{cur.get('port', 8080)}]: ").strip() or cur.get("port", 8080)
    config.save({**cur, "gmail_user": user, "gmail_app_password": pw, "default_checking": dc, "port": int(port),
                 "sync_interval_min": int(cur.get("sync_interval_min", 60))})
    if not (HERE / "rules.toml").exists():
        (HERE / "rules.toml").write_text((HERE / "rules.example.toml").read_text())
    print(f"\nsaved {config.CONFIG}. Next: python3 alertledger.py sync --full   (first pull, a few minutes)")


# ---------------------------------------------------------------- install
def install():
    py, script = sys.executable, str(HERE / "alertledger.py")
    if sys.platform == "darwin":
        plist = Path.home() / "Library/LaunchAgents" / f"io.{SERVICE}.plist"
        plist.write_bytes(plistlib.dumps({"Label": f"io.{SERVICE}", "ProgramArguments": [py, script, "serve"], "RunAtLoad": True, "KeepAlive": True,
                                          "StandardOutPath": str(config.HOME / "serve.log"), "StandardErrorPath": str(config.HOME / "serve.log")}))
        subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
        subprocess.run(["launchctl", "load", str(plist)], check=True)
        print(f"launchd: {plist} loaded (starts at login, restarts if it dies). log: {config.HOME / 'serve.log'}")
    else:
        unit = f"""[Unit]
Description=alertledger
After=network-online.target

[Service]
ExecStart={py} {script} serve
Restart=always
RestartSec=10
User={os.environ.get('SUDO_USER') or getpass.getuser()}
Environment=ALERTLEDGER_HOME={config.HOME}

[Install]
WantedBy=multi-user.target
"""
        path = Path(f"/etc/systemd/system/{SERVICE}.service")
        try:
            path.write_text(unit)
        except PermissionError:
            raise SystemExit(f"need root to write {path}: rerun with  sudo -E {py} {script} install")
        for c in (["systemctl", "daemon-reload"], ["systemctl", "enable", "--now", SERVICE]):
            subprocess.run(c, check=True)
        print(f"systemd: {SERVICE} enabled + started. status: systemctl status {SERVICE} · logs: journalctl -u {SERVICE} -f")
    print(f"dashboard: http://{subprocess.run(['hostname'], capture_output=True, text=True).stdout.strip()}:{config.load().get('port', 8080)}")


def uninstall():
    if sys.platform == "darwin":
        plist = Path.home() / "Library/LaunchAgents" / f"io.{SERVICE}.plist"
        subprocess.run(["launchctl", "unload", str(plist)], capture_output=True); plist.unlink(missing_ok=True)
    else:
        subprocess.run(["systemctl", "disable", "--now", SERVICE], capture_output=True)
        Path(f"/etc/systemd/system/{SERVICE}.service").unlink(missing_ok=True)
        subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
    print("removed")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["setup", "sync", "serve", "install", "uninstall"])
    ap.add_argument("--full", action="store_true")
    a = ap.parse_args()
    if a.cmd == "setup":
        setup()
    elif a.cmd == "sync":
        c = sync(ledger.connect(str(config.DB)), config.load(), a.full)
        print(c, "" if not c["unparsed"] else f"→ {config.FAILURES}")
    elif a.cmd == "serve":
        serve(config.load())
    elif a.cmd == "install":
        install()
    else:
        uninstall()
