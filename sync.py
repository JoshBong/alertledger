"""Ingest bank alert emails into ~/.alertledger/ledger.db. Daily via launchd."""
import argparse
import plistlib
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import config
import db
import mail_import
import dashboard

LAUNCHD_LABEL = "io.alertledger.sync"


def run(full: bool = False):
    cfg = config.load_config()
    con = db.connect(str(config.DB))
    since = None if full else date.today() - timedelta(days=14)
    c = mail_import.run(cfg, con, since)
    print(f"transactions {c['txn']} · statements {c['statement']} · skipped {c['skip']} · unparsed {c['fail']}"
          + (f" → {config.HOME / 'parse_failures.jsonl'}" if c['fail'] else ""))
    print("dashboard →", dashboard.build(con))


def uninstall_launchd():
    plist = Path.home() / "Library/LaunchAgents" / f"{LAUNCHD_LABEL}.plist"
    subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
    plist.unlink(missing_ok=True)
    print("removed", plist)


def install_cron(hour: int = 8):
    """Linux / Raspberry Pi: append a daily crontab line (idempotent)."""
    line = f"0 {hour} * * * {sys.executable} {Path(__file__).resolve()} >> {config.HOME / 'sync.log'} 2>&1"
    cur = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    if "alertledger" in cur or str(Path(__file__).resolve()) in cur:
        print("cron entry already present"); return
    subprocess.run(["crontab", "-"], input=cur.rstrip("\n") + f"\n# alertledger daily sync\n{line}\n", text=True, check=True)
    print("installed cron:", line)


def install_launchd(hour: int = 8):
    plist = Path.home() / "Library/LaunchAgents" / f"{LAUNCHD_LABEL}.plist"
    log = config.HOME / "sync.log"
    plist.write_bytes(plistlib.dumps({
        "Label": LAUNCHD_LABEL,
        "ProgramArguments": [sys.executable, str(Path(__file__).resolve())],
        "StartCalendarInterval": {"Hour": hour, "Minute": 0},
        "StandardOutPath": str(log), "StandardErrorPath": str(log),
        "RunAtLoad": False,
    }))
    subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
    subprocess.run(["launchctl", "load", str(plist)], check=True)
    print(f"installed {plist} — daily {hour:02d}:00, log → {log}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--full", action="store_true", help="re-scan the whole label (default: last 14 days)")
    p.add_argument("--install-launchd", action="store_true", help="macOS: daily 08:00 job")
    p.add_argument("--uninstall-launchd", action="store_true")
    p.add_argument("--install-cron", action="store_true", help="Linux/Pi: daily 08:00 crontab line")
    a = p.parse_args()
    if a.install_launchd: install_launchd()
    elif a.uninstall_launchd: uninstall_launchd()
    elif a.install_cron: install_cron()
    else: run(full=a.full)
