import json
import os
from pathlib import Path

HOME = Path(os.environ.get("ALERTLEDGER_HOME", Path.home() / ".alertledger"))
CONFIG = HOME / "config.json"
DB = HOME / "ledger.db"
FAILURES = HOME / "parse_failures.jsonl"
RULES = Path(__file__).parent / "rules.toml"
DEFAULTS = {"port": 8080, "sync_interval_min": 60, "default_checking": {}}


def ensure_home():
    HOME.mkdir(mode=0o700, exist_ok=True)
    os.chmod(HOME, 0o700)


def load() -> dict:
    if not CONFIG.exists():
        raise SystemExit(f"no config at {CONFIG} — run: python3 alertledger.py setup")
    c = {**DEFAULTS, **json.loads(CONFIG.read_text())}
    for k in ("gmail_user", "gmail_app_password"):
        if not c.get(k):
            raise SystemExit(f"{CONFIG}: missing {k} — run: python3 alertledger.py setup")
    return c


def save(c: dict):
    ensure_home()
    CONFIG.write_text(json.dumps(c, indent=2))
    os.chmod(CONFIG, 0o600)
