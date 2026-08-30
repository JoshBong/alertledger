import json
import os
from pathlib import Path

HOME = Path(os.environ.get("ALERTLEDGER_HOME", Path.home() / ".alertledger"))
CONFIG = HOME / "config.json"
DB = HOME / "ledger.db"
RULES = Path(__file__).parent / "rules.toml"   # your copy of rules.example.toml (gitignored)


def ensure_home():
    HOME.mkdir(mode=0o700, exist_ok=True)
    os.chmod(HOME, 0o700)


def load_config() -> dict:
    if not CONFIG.exists():
        raise SystemExit(f"missing {CONFIG} — create it: "
                         '{"gmail_user":"you@gmail.com","gmail_app_password":"xxxx xxxx xxxx xxxx","default_checking":{"Chase":"1234"}}')
    c = json.loads(CONFIG.read_text())
    for k in ("gmail_user", "gmail_app_password"):
        if not c.get(k):
            raise SystemExit(f"{CONFIG}: missing {k}")
    return c
