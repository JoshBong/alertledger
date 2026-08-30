"""SQLite store. accounts / transactions / statements / meta."""
import hashlib
import json
import sqlite3
from datetime import date

from parsers import Parsed

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (id TEXT PRIMARY KEY, institution TEXT, name TEXT, last_four TEXT);
CREATE TABLE IF NOT EXISTS transactions (
  id TEXT PRIMARY KEY, account_id TEXT NOT NULL, date TEXT NOT NULL, description TEXT, amount REAL NOT NULL,
  status TEXT, type TEXT, category TEXT, counterparty TEXT, raw TEXT, first_seen TEXT, last_seen TEXT);
CREATE TABLE IF NOT EXISTS statements (id TEXT PRIMARY KEY, account_id TEXT NOT NULL, statement_date TEXT NOT NULL, balance REAL NOT NULL, due_date TEXT);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS budgets (category TEXT PRIMARY KEY, amount REAL NOT NULL);
CREATE INDEX IF NOT EXISTS tx_date ON transactions(date);
"""


def connect(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def short(bank: str) -> str:
    return {"Bank of America": "BofA"}.get(bank, bank)


def account_id(bank: str, last4: str | None) -> str:
    return f"{bank.lower().replace(' ', '')}_{last4 or 'xxxx'}"


def ensure_account(con, bank: str, last4: str | None) -> str:
    aid = account_id(bank, last4)
    con.execute("INSERT OR IGNORE INTO accounts VALUES (?,?,?,?)", (aid, bank, f"{short(bank)} ••{last4 or '????'}", last4))
    return aid


def record_posted(con, bank: str, account_id_: str, p: Parsed) -> str:
    """CSV row → posted transaction. A pending alert row for the same amount within 3 days is replaced (alerts fire at
    authorization; the CSV is the bank's final word). Returns 'new' | 'upgraded' | 'dup'."""
    d = p.date.isoformat()
    amt = p.signed_amount
    tid = "csv_" + hashlib.sha1(f"{account_id_}|{d}|{amt:.2f}|{p.merchant.lower()}".encode()).hexdigest()[:20]
    if con.execute("SELECT 1 FROM transactions WHERE id=?", (tid,)).fetchone():
        return "dup"
    pend = con.execute("""SELECT id FROM transactions WHERE account_id=? AND status='pending' AND ABS(amount-?)<0.005
                          AND ABS(julianday(date)-julianday(?))<=3 LIMIT 1""", (account_id_, amt, d)).fetchone()
    if pend:
        con.execute("DELETE FROM transactions WHERE id=?", (pend["id"],))
    today = date.today().isoformat()
    con.execute("INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (tid, account_id_, d, p.merchant, amt, "posted", p.txn_type, p.category, p.merchant,
                 json.dumps({"kind": p.kind, "source": "csv"}), today, today))
    return "upgraded" if pend else "new"


def record(con, bank: str, p: Parsed, subject: str) -> str:
    """Write a Parsed to the ledger. Returns 'txn' | 'statement'."""
    aid = ensure_account(con, bank, p.last4)
    if p.kind == "statement":
        sd = p.date.isoformat()
        con.execute("INSERT INTO statements VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET balance=excluded.balance, due_date=excluded.due_date",
                    (f"{aid}:{sd}", aid, sd, p.balance, p.due.isoformat() if p.due else None))
        return "statement"
    d = p.date.isoformat()
    amt = p.signed_amount
    key = f"{bank}|{p.last4}|{d}|{amt:.2f}|{p.merchant.lower()}"
    tid = "mail_" + hashlib.sha1(key.encode()).hexdigest()[:20]
    today = date.today().isoformat()
    con.execute("""INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET last_seen=excluded.last_seen""",
                (tid, aid, d, p.merchant, amt, "pending", p.txn_type, None, p.merchant,
                 json.dumps({"subject": subject, "kind": p.kind}), today, today))
    return "txn"


def set_meta(con, key: str, value: str):
    con.execute("INSERT INTO meta VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def get_meta(con, key: str, default=None):
    r = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def budgets(con) -> dict:
    return {r["category"]: r["amount"] for r in con.execute("SELECT category, amount FROM budgets")}


def set_budget(con, category: str, amount: float | None):
    if amount is None or amount <= 0:
        con.execute("DELETE FROM budgets WHERE category=?", (category,))
    else:
        con.execute("INSERT INTO budgets VALUES (?,?) ON CONFLICT(category) DO UPDATE SET amount=excluded.amount", (category, float(amount)))
    con.commit()
