"""Reports over ~/.budget/budget.db.
  report.py recurring            monthly-cadence charges across all cards
  report.py breakdown [--month YYYY-MM] [--all]   category × card
  report.py txns [--month YYYY-MM] [--category X] [--grep RE]
  report.py checksum             per statement: bank's statement balance vs our net charges (alert coverage check)
"""
import argparse
import re
import tomllib
from collections import defaultdict
from datetime import date, datetime, timedelta

import config
import db

SKIP_TYPES = {"payment", "transfer"}  # own-account movements, not spend


def load_rules():
    if not config.RULES.exists():
        return []
    rules = tomllib.loads(config.RULES.read_text()).get("rule", [])
    for r in rules:
        r["_re"] = re.compile(r["pattern"], re.I)
    return rules


def classify(row, rules):
    """→ (category, ignore)"""
    for r in rules:
        if r["_re"].search(row["description"] or "") or r["_re"].search(row["counterparty"] or ""):
            return r.get("category") or row["category"] or "uncategorized", bool(r.get("ignore"))
    return row["category"] or "uncategorized", (row["type"] in SKIP_TYPES)


def spend_rows(con, rules, month=None):
    q = "SELECT t.*, a.institution, a.name AS acct, a.last_four FROM transactions t JOIN accounts a ON a.id=t.account_id WHERE t.amount<0"
    args = []
    if month:
        q += " AND t.date LIKE ?"; args.append(month + "%")
    for row in con.execute(q + " ORDER BY t.date", args):
        cat, ignore = classify(row, rules)
        if not ignore:
            yield row, cat


def merchant_key(row):
    s = (row["counterparty"] or row["description"] or "").lower()
    s = re.sub(r"[#*]\s*\w+|\d{2}/\d{2}|\s+\d+$", "", s)          # strip store numbers, dates, trailing ids
    return re.sub(r"\s+", " ", s).strip()[:40]


def recurring(con, rules):
    groups = defaultdict(list)
    for row, cat in spend_rows(con, rules):
        groups[merchant_key(row)].append((datetime.fromisoformat(row["date"]).date(), -row["amount"], row["last_four"], cat))
    found = []
    for k, items in groups.items():
        items.sort()
        hits = []
        for (d0, a0, *_), (d1, a1, *_) in zip(items, items[1:]):
            gap = (d1 - d0).days
            if 26 <= gap <= 35 and abs(a1 - a0) <= max(1.0, 0.05 * a0):
                hits.append((d0, a0)); hits.append((d1, a1))
        if len(set(hits)) >= 2:
            last = items[-1]
            found.append((last[1], k, last[0], last[2], last[3], len(set(hits))))
    found.sort(reverse=True)
    print(f"{'$/mo':>8}  {'merchant':<40} {'last':<11} card  cat              hits")
    for amt, k, d, card, cat, n in found:
        print(f"{amt:>8.2f}  {k:<40} {d}  ••{card}  {cat:<16} {n}")
    print(f"{sum(f[0] for f in found):>8.2f}  total recurring / month")


def breakdown(con, rules, month, all_months=False):
    table = defaultdict(lambda: defaultdict(float))
    cols = set()
    for row, cat in spend_rows(con, rules, None if all_months else month):
        col = row["date"][:7] if all_months else f"••{row['last_four']}"
        table[cat][col] += -row["amount"]; cols.add(col)
    cols = sorted(cols)
    w = max([len(c) for c in table] + [8])
    print(f"{'category':<{w}}  " + "  ".join(f"{c:>10}" for c in cols) + f"  {'total':>10}")
    grand = defaultdict(float)
    for cat, vals in sorted(table.items(), key=lambda kv: -sum(kv[1].values())):
        tot = sum(vals.values())
        print(f"{cat:<{w}}  " + "  ".join(f"{vals.get(c, 0):>10.2f}" for c in cols) + f"  {tot:>10.2f}")
        for c in cols: grand[c] += vals.get(c, 0)
    print(f"{'total':<{w}}  " + "  ".join(f"{grand[c]:>10.2f}" for c in cols) + f"  {sum(grand.values()):>10.2f}")


def txns(con, rules, month, category, grep):
    pat = re.compile(grep, re.I) if grep else None
    for row, cat in spend_rows(con, rules, month):
        if category and cat != category: continue
        if pat and not (pat.search(row["description"] or "") or pat.search(row["counterparty"] or "")): continue
        print(f"{row['date']}  {-row['amount']:>9.2f}  ••{row['last_four']}  {cat:<16} {row['description']}")


def checksum(con):
    """Per card statement: bank's statement balance vs our charges in that cycle.
    Assumes autopay pays the previous statement in full (true for Josh's cards), so new balance == cycle charges − refunds.
    Gap > $1 = alerts we missed or auth-vs-post drift (tips)."""
    rows = con.execute("""SELECT s.*, a.institution, a.last_four FROM statements s JOIN accounts a ON a.id=s.account_id
                          ORDER BY s.account_id, s.statement_date""").fetchall()
    prev = {}
    print(f"{'card':<22} {'stmt date':<11} {'bank':>10} {'ours':>10} {'gap':>9}")
    for r in rows:
        p = prev.get(r["account_id"])
        prev[r["account_id"]] = r
        since = p["statement_date"] if p else (date.fromisoformat(r["statement_date"]) - timedelta(days=31)).isoformat()
        ours = con.execute("""SELECT COALESCE(SUM(-amount),0) FROM transactions WHERE account_id=? AND date>? AND date<=?
                              AND type NOT IN ('transfer')""", (r["account_id"], since, r["statement_date"])).fetchone()[0]
        gap = r["balance"] - ours
        flag = "" if abs(gap) < 1 else "  ← check"
        print(f"{r['institution'] + ' ••' + (r['last_four'] or '????'):<22} {r['statement_date']:<11} {r['balance']:>10.2f} {ours:>10.2f} {gap:>9.2f}{flag}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["recurring", "breakdown", "txns", "checksum"])
    p.add_argument("--month", default=date.today().strftime("%Y-%m"))
    p.add_argument("--all", action="store_true")
    p.add_argument("--category")
    p.add_argument("--grep")
    a = p.parse_args()
    con = db.connect(str(config.DB))
    rules = load_rules()
    {"recurring": lambda: recurring(con, rules),
     "breakdown": lambda: breakdown(con, rules, a.month, a.all),
     "txns": lambda: txns(con, rules, a.month, a.category, a.grep),
     "checksum": lambda: checksum(con)}[a.cmd]()
