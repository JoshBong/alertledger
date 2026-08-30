#!/usr/bin/env python3
"""alertledger — bank alert emails → ledger → dashboard. One process: hourly sync + web UI.

  python3 alertledger.py setup       interactive: Gmail login (tested), accounts, port
  python3 alertledger.py sync        pull mail now (--full = whole mailbox)
  python3 alertledger.py import <account_id> <file.csv>   backfill from a bank CSV export (see status for account ids)
  python3 alertledger.py serve       run forever: sync every N minutes + dashboard on :PORT
  python3 alertledger.py install     register `serve` as a system service (systemd / launchd) and start it
  python3 alertledger.py uninstall
  python3 alertledger.py stop | start  pause / resume the installed service (registration stays)
  python3 alertledger.py status      service state, last sync, ledger totals, URL
  python3 alertledger.py doctor      check python, config, Gmail login, database, service, port
  python3 alertledger.py config      show config (password masked)
  python3 alertledger.py config set port 8090 | sync_interval_min 30 | default_checking.Chase 1234
  python3 alertledger.py config gmail        re-enter Gmail login (tested)
  python3 alertledger.py update      git pull, run tests, restart the service

`./alertledger <cmd>` is the same thing.
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


# ---------------------------------------------------------------- csv import
def import_csv(con, account_id_: str, text: str) -> dict:
    import csv
    import io
    acct = con.execute("SELECT * FROM accounts WHERE id=?", (account_id_,)).fetchone()
    if not acct:
        ids = [r["id"] for r in con.execute("SELECT id FROM accounts ORDER BY id")]
        raise ValueError(f"unknown account {account_id_!r}. known: {', '.join(ids) or 'none yet — sync first'}")
    bank = next((p for p in parsers._REGISTRY.values() if p.name == acct["institution"]), None)
    if not bank:
        raise ValueError(f"no parser for {acct['institution']}")
    rows = list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))
    if not rows:
        raise ValueError("empty file")
    counts = {"new": 0, "upgraded": 0, "dup": 0}
    for p in bank.csv_rows(rows[0], rows[1:]):
        counts[ledger.record_posted(con, bank.name, account_id_, p)] += 1
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
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache"); self.end_headers()
        self.wfile.write(body)

    WEB = HERE / "web"
    TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png"}

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._send((self.WEB / "index.html").read_bytes())
        elif path == "/api/data":
            import dashboard
            self._send(json.dumps(dashboard.data(self.con), separators=(",", ":")).encode(), "application/json")
        elif path.startswith("/static/"):
            f = (self.WEB / path[len("/static/"):]).resolve()
            if self.WEB.resolve() in f.parents and f.is_file():
                self._send(f.read_bytes(), self.TYPES.get(f.suffix, "application/octet-stream"))
            else:
                self._send(b"not found", "text/plain", 404)
        elif path == "/api/status":
            self._send(json.dumps({"last_sync": ledger.get_meta(self.con, "last_sync"), "counts": json.loads(ledger.get_meta(self.con, "last_counts", "{}"))}).encode(), "application/json")
        else:
            self._send(b"not found", "text/plain", 404)

    def do_POST(self):
        if self.path.startswith("/api/import"):
            from urllib.parse import parse_qs, urlparse
            acct = parse_qs(urlparse(self.path).query).get("account", [""])[0]
            body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8", errors="replace")
            with self.lock:
                try:
                    self._send(json.dumps(import_csv(self.con, acct, body)).encode(), "application/json")
                except Exception as ex:
                    self._send(json.dumps({"error": str(ex)}).encode(), "application/json", 400)
        elif self.path == "/api/sync":
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


# ---------------------------------------------------------------- status / doctor / config / update
def _service_state() -> str:
    if sys.platform == "darwin":
        out = subprocess.run(["launchctl", "list"], capture_output=True, text=True).stdout
        for line in out.splitlines():
            if line.endswith(f"io.{SERVICE}"):
                pid = line.split()[0]
                return f"launchd: running (pid {pid})" if pid != "-" else "launchd: loaded, not running"
        return "launchd: installed, stopped" if (Path.home() / "Library/LaunchAgents" / f"io.{SERVICE}.plist").exists() else "launchd: not installed"
    out = subprocess.run(["systemctl", "is-active", SERVICE], capture_output=True, text=True).stdout.strip()
    return f"systemd: {out or 'not installed'}"


def _restart_service():
    if sys.platform == "darwin":
        r = subprocess.run(["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/io.{SERVICE}"], capture_output=True, text=True)
    else:
        r = subprocess.run(["systemctl", "restart", SERVICE], capture_output=True, text=True)
    return r.returncode == 0


def stop():
    if sys.platform == "darwin":
        plist = Path.home() / "Library/LaunchAgents" / f"io.{SERVICE}.plist"
        if not plist.exists():
            raise SystemExit("not installed — nothing to stop")
        r = subprocess.run(["launchctl", "unload", str(plist)], capture_output=True, text=True)
    else:
        r = subprocess.run(["systemctl", "disable", "--now", SERVICE], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"nothing to stop: {r.stderr.strip() or 'not installed'}")
    for _ in range(20):
        if not _port_open(config.load()["port"]):
            break
        time.sleep(0.5)
    print("  ■ alertledger stopped — won't start at boot until ./alertledger start")


def start():
    if sys.platform == "darwin":
        plist = Path.home() / "Library/LaunchAgents" / f"io.{SERVICE}.plist"
        if not plist.exists():
            raise SystemExit("not installed — run ./alertledger install")
        r = subprocess.run(["launchctl", "load", str(plist)], capture_output=True, text=True)
        subprocess.run(["launchctl", "kickstart", f"gui/{os.getuid()}/io.{SERVICE}"], capture_output=True)  # load alone may not launch
    else:
        r = subprocess.run(["systemctl", "enable", "--now", SERVICE], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"failed: {r.stderr.strip()}")
    _announce(config.load()["port"])


def _lan_ip() -> str | None:
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("10.255.255.255", 1))
            return sock.getsockname()[0]
    except Exception:
        return None


def _announce(port: int, wait: int = 15):
    """Block until the server answers (or `wait` seconds), then print where it lives — or the log tail if it didn't come up."""
    import urllib.request
    for _ in range(wait * 2):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=1) as r:
                st = json.load(r)
            host = subprocess.run(["hostname"], capture_output=True, text=True).stdout.strip()
            ip = _lan_ip()
            ts = ip if ip and ip.startswith("100.") and 64 <= int(ip.split(".")[1]) <= 127 else None   # Tailscale CGNAT range
            print(f"""
  ✓ alertledger is up
    this machine   http://localhost:{port}
    on your LAN    http://{host}:{port}""" + (f"\n                   http://{ip}:{port}" if ip and not ts else "")
                  + (f"\n    via Tailscale  http://{ts}:{port}  (also http://{host.split('.')[0]}:{port} on the tailnet)" if ts else f"\n    via Tailscale  install it → http://<tailscale-name>:{port}") + f"""
    last sync      {st.get('last_sync') or 'never — first sync starts now'}
    logs           {config.HOME / 'serve.log' if sys.platform == 'darwin' else 'journalctl -u ' + SERVICE + ' -f'}
""")
            return True
        except Exception:
            time.sleep(0.5)
    print(f"\n  ✗ not answering on :{port} after {wait}s. Last log lines:")
    log = config.HOME / "serve.log"
    if log.exists():
        print("    " + "\n    ".join(log.read_text().splitlines()[-8:]))
    else:
        subprocess.run(["journalctl", "-u", SERVICE, "-n", "8", "--no-pager"])
    return False


def _port_open(port: int) -> bool:
    import socket
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def status():
    cfg = config.load()
    con = ledger.connect(str(config.DB))
    n_tx, n_st = con.execute("SELECT COUNT(*) FROM transactions").fetchone()[0], con.execute("SELECT COUNT(*) FROM statements").fetchone()[0]
    accts = [r["name"] for r in con.execute("SELECT name FROM accounts ORDER BY name")]
    host = subprocess.run(["hostname"], capture_output=True, text=True).stdout.strip()
    print(f"service    {_service_state()}")
    print(f"dashboard  http://{host}:{cfg['port']}  ({'listening' if _port_open(cfg['port']) else 'port closed'})")
    print(f"last sync  {ledger.get_meta(con, 'last_sync') or 'never'}  {ledger.get_meta(con, 'last_counts', '')}")
    print(f"ledger     {n_tx} transactions · {n_st} statements · accounts: {', '.join(accts) or 'none'}")
    print(f"interval   every {cfg['sync_interval_min']} min · gmail {cfg['gmail_user']} · config {config.CONFIG}")


def doctor():
    ok = lambda c, m: print(("  ✓ " if c else "  ✗ ") + m) or c
    good = True
    good &= ok(sys.version_info >= (3, 11), f"python {sys.version.split()[0]} (need ≥ 3.11)")
    good &= ok(config.CONFIG.exists(), f"config {config.CONFIG}")
    if not config.CONFIG.exists():
        print("    run: ./alertledger setup"); return
    cfg = config.load()
    good &= ok((config.CONFIG.stat().st_mode & 0o077) == 0, "config permissions 600")
    try:
        mail.login(cfg["gmail_user"], cfg["gmail_app_password"]).logout(); good &= ok(True, f"gmail login as {cfg['gmail_user']}")
    except Exception as ex:
        good &= ok(False, f"gmail login: {ex}  → ./alertledger config gmail")
    try:
        ledger.connect(str(config.DB)).execute("SELECT 1"); good &= ok(True, f"database {config.DB}")
    except Exception as ex:
        good &= ok(False, f"database: {ex}")
    good &= ok((HERE / "rules.toml").exists(), "rules.toml (categories)")
    st = _service_state(); good &= ok("running" in st or "active" == st.split()[-1], st)
    good &= ok(_port_open(cfg["port"]), f"port {cfg['port']} listening")
    print("all good" if good else "fix the ✗ lines above")


def show_config(argv):
    cfg = config.load()
    if not argv:
        masked = {**cfg, "gmail_app_password": "•" * 12 + cfg["gmail_app_password"][-4:]}
        print(json.dumps(masked, indent=2, ensure_ascii=False)); return
    if argv[0] == "gmail":
        user = input(f"Gmail address [{cfg['gmail_user']}]: ").strip() or cfg["gmail_user"]
        pw = getpass.getpass("App password (hidden): ").strip() or cfg["gmail_app_password"]
        mail.login(user, pw).logout(); print("login ok")
        config.save({**cfg, "gmail_user": user, "gmail_app_password": pw})
    elif argv[0] == "set" and len(argv) == 3:
        key, val = argv[1], argv[2]
        if key.startswith("default_checking."):
            cfg.setdefault("default_checking", {})[key.split(".", 1)[1]] = val
        elif key in ("port", "sync_interval_min"):
            cfg[key] = int(val)
        else:
            raise SystemExit(f"unknown key {key}. settable: port, sync_interval_min, default_checking.<Bank>")
        config.save(cfg); print(f"{key} = {val}")
    else:
        raise SystemExit("usage: config | config gmail | config set <key> <value>")
    if _restart_service():
        print("service restarted")
    else:
        print("service not running — start with ./alertledger install (or serve)")


def update():
    print("git pull…", flush=True)
    r = subprocess.run(["git", "-C", str(HERE), "pull", "--ff-only"], capture_output=True, text=True)
    print("  " + (r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip()))
    if r.returncode != 0:
        raise SystemExit("pull failed — resolve in the repo and rerun")
    t = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"], cwd=HERE, capture_output=True, text=True)
    print("  tests: " + ("ok" if t.returncode == 0 else "FAILED\n" + t.stderr))
    if t.returncode != 0:
        raise SystemExit("not restarting a broken build")
    print("  service: " + ("restarted" if _restart_service() else "not installed — run ./alertledger install"))


# ---------------------------------------------------------------- install
def install():
    py, script = sys.executable, str(HERE / "alertledger.py")
    if sys.platform == "darwin":
        plist = Path.home() / "Library/LaunchAgents" / f"io.{SERVICE}.plist"
        plist.write_bytes(plistlib.dumps({"Label": f"io.{SERVICE}", "ProgramArguments": [py, script, "serve"], "RunAtLoad": True, "KeepAlive": True,
                                          "StandardOutPath": str(config.HOME / "serve.log"), "StandardErrorPath": str(config.HOME / "serve.log")}))
        subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
        subprocess.run(["launchctl", "load", str(plist)], check=True)
        subprocess.run(["launchctl", "kickstart", f"gui/{os.getuid()}/io.{SERVICE}"], capture_output=True)
        print(f"launchd: {plist} (starts at login, restarts if it dies)")
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
        print(f"systemd: {SERVICE} enabled (starts at boot, restarts on failure)")
    _announce(config.load()["port"])


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
    ap.add_argument("cmd", choices=["setup", "sync", "serve", "install", "uninstall", "start", "stop", "status", "doctor", "config", "update", "import"])
    ap.add_argument("--full", action="store_true")
    ap.add_argument("rest", nargs="*")
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
    elif a.cmd == "uninstall":
        uninstall()
    elif a.cmd == "start":
        start()
    elif a.cmd == "stop":
        stop()
    elif a.cmd == "status":
        status()
    elif a.cmd == "doctor":
        doctor()
    elif a.cmd == "config":
        show_config(a.rest)
    elif a.cmd == "update":
        update()
    elif a.cmd == "import":
        if len(a.rest) != 2:
            raise SystemExit("usage: import <account_id> <file.csv>")
        print(import_csv(ledger.connect(str(config.DB)), a.rest[0], Path(a.rest[1]).read_text(errors="replace")))
