import json
import sqlite3
from datetime import date

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
  id TEXT PRIMARY KEY, enrollment_id TEXT, institution TEXT, name TEXT,
  type TEXT, subtype TEXT, last_four TEXT, status TEXT, currency TEXT
);
CREATE TABLE IF NOT EXISTS transactions (
  id TEXT PRIMARY KEY, account_id TEXT NOT NULL, date TEXT NOT NULL,
  description TEXT, amount REAL NOT NULL, status TEXT, type TEXT,
  running_balance REAL, category TEXT, counterparty TEXT, raw TEXT,
  first_seen TEXT, last_seen TEXT
);
CREATE TABLE IF NOT EXISTS statements (
  id TEXT PRIMARY KEY, account_id TEXT NOT NULL, statement_date TEXT NOT NULL, balance REAL NOT NULL, due_date TEXT
);
CREATE INDEX IF NOT EXISTS tx_date ON transactions(date);
CREATE INDEX IF NOT EXISTS tx_account ON transactions(account_id);
"""


def connect(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def upsert_account(con, a: dict):
    con.execute(
        """INSERT INTO accounts VALUES (?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET enrollment_id=excluded.enrollment_id, institution=excluded.institution,
             name=excluded.name, type=excluded.type, subtype=excluded.subtype, last_four=excluded.last_four,
             status=excluded.status, currency=excluded.currency""",
        (a["id"], a.get("enrollment_id"), (a.get("institution") or {}).get("name"), a.get("name"),
         a.get("type"), a.get("subtype"), a.get("last_four"), a.get("status"), a.get("currency")),
    )


def upsert_transaction(con, t: dict, today: str | None = None):
    today = today or date.today().isoformat()
    d = t.get("details") or {}
    cp = (d.get("counterparty") or {}).get("name")
    rb = t.get("running_balance")
    con.execute(
        """INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET date=excluded.date, description=excluded.description,
             amount=excluded.amount, status=excluded.status, type=excluded.type,
             running_balance=excluded.running_balance, category=excluded.category,
             counterparty=excluded.counterparty, raw=excluded.raw, last_seen=excluded.last_seen""",
        (t["id"], t["account_id"], t["date"], t.get("description"), float(t["amount"]), t.get("status"),
         t.get("type"), float(rb) if rb is not None else None, d.get("category"), cp,
         json.dumps(t, separators=(",", ":")), today, today),
    )


def drop_stale_pending(con, account_id: str, since: str, seen_ids: set[str]) -> int:
    """Pending rows in the pulled window that the bank no longer reports (they re-id on posting)."""
    rows = con.execute("SELECT id FROM transactions WHERE account_id=? AND status='pending' AND date>=?",
                       (account_id, since)).fetchall()
    stale = [r["id"] for r in rows if r["id"] not in seen_ids]
    if stale:
        con.executemany("DELETE FROM transactions WHERE id=?", [(i,) for i in stale])
    return len(stale)


def upsert_statement(con, account_id: str, statement_date: str, balance: float, due_date: str | None):
    con.execute("""INSERT INTO statements VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET balance=excluded.balance,
                   due_date=excluded.due_date""", (f"{account_id}:{statement_date}", account_id, statement_date, balance, due_date))
