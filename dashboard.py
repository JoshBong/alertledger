"""Data layer for the dashboard: shapes ledger rows into the JSON that web/ renders. No HTML here."""
import json
from datetime import date, timedelta

import categories
import config
import ledger
import report


def short(inst):
    return ledger.short(inst)


def collect(con, rules):
    tx = []
    for r in con.execute("SELECT t.*, a.institution, a.last_four FROM transactions t JOIN accounts a ON a.id=t.account_id ORDER BY t.date DESC, t.id"):
        cat, ignore = report.classify(r, rules)
        tx.append({"id": r["id"], "date": r["date"], "acct": r["account_id"], "card": ledger.account_label(r["institution"], r["last_four"]),
                   "merchant": r["description"], "amount": round(r["amount"], 2), "cat": cat, "type": r["type"],
                   "ignore": ignore, "status": r["status"]})
    accounts = [{"id": r["id"], "name": r["name"]} for r in con.execute("SELECT id, name FROM accounts ORDER BY name")]
    return tx, accounts


def recurring(con, rules):
    from collections import defaultdict
    from datetime import datetime
    groups = defaultdict(list)
    for row, cat in report.spend_rows(con, rules):
        groups[report.merchant_key(row)].append((datetime.fromisoformat(row["date"]).date(), -row["amount"], ledger.account_label(row["institution"], row["last_four"]), cat))
    out = []
    for k, items in groups.items():
        items.sort(); hits = set()
        for (d0, a0, *_), (d1, a1, *_) in zip(items, items[1:]):
            if 26 <= (d1 - d0).days <= 35 and abs(a1 - a0) <= max(1.0, 0.05 * a0):
                hits.update({(d0, a0), (d1, a1)})
        if len(hits) >= 2:
            out.append({"merchant": k, "amount": items[-1][1], "last": items[-1][0].isoformat(), "hits": len(hits), "card": items[-1][2], "cat": items[-1][3]})
    return sorted(out, key=lambda r: -r["amount"])


def checksum(con):
    rows = con.execute("SELECT s.*, a.institution, a.last_four FROM statements s JOIN accounts a ON a.id=s.account_id ORDER BY s.account_id, s.statement_date").fetchall()
    prev, out = {}, []
    for r in rows:
        p = prev.get(r["account_id"]); prev[r["account_id"]] = r
        since = p["statement_date"] if p else (date.fromisoformat(r["statement_date"]) - timedelta(days=31)).isoformat()
        ours = con.execute("SELECT COALESCE(SUM(-amount),0) FROM transactions WHERE account_id=? AND date>? AND date<=? AND type NOT IN ('transfer')",
                           (r["account_id"], since, r["statement_date"])).fetchone()[0]
        out.append({"card": ledger.account_label(r["institution"], r["last_four"]), "date": r["statement_date"], "bank": r["balance"], "ours": ours, "gap": r["balance"] - ours})
    return sorted(out, key=lambda r: r["date"], reverse=True)


def failures():
    p = config.FAILURES
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines()[-50:]:
        try:
            j = json.loads(line); out.append({"bank": j.get("bank"), "subject": j.get("subject"), "date": j.get("date")})
        except Exception:
            pass
    return out[::-1]


def data(con) -> dict:
    """Everything the UI needs, as JSON. The UI (web/) does all aggregation client-side."""
    rules = report.load_rules()
    tx, accounts = collect(con, rules)
    return {"tx": tx, "accounts": accounts, "categories": categories.CATEGORIES, "recurring": recurring(con, rules), "checksum": checksum(con),
            "budgets": ledger.budgets(con), "failures": failures(), "last_sync": ledger.get_meta(con, "last_sync"), "last_counts": json.loads(ledger.get_meta(con, "last_counts", "{}"))}


if __name__ == "__main__":
    print(json.dumps(data(ledger.connect(str(config.DB))), indent=1))
