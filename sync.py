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

LAUNCHD_LABEL = "io.alertledger.sync"


def run(full: bool = False):
    cfg = config.load_config()
    con = db.connect(str(config.DB))
    since = None if full else date.today() - timedelta(days=14)
    c = mail_import.run(cfg, con, since)
    print(f"transactions {c['txn']} · statements {c['statement']} · skipped {c['skip']} · unparsed {c['fail']}"
          + (f" → {config.HOME / 'parse_failures.jsonl'}" if c['fail'] else ""))


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
    p.add_argument("--install-launchd", action="store_true")
    a = p.parse_args()
    install_launchd() if a.install_launchd else run(full=a.full)
