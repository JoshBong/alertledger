"""record() must distinguish a genuinely new row from a re-seen alert (sync re-reads 14 days of mail every cycle);
/api/events fires only on the former.  python3 -m unittest -v"""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ledger  # noqa: E402
from parsers import Parsed  # noqa: E402

import budgetmail  # noqa: E402

D = date(2026, 9, 4)


def purchase(amount=45.73, merchant="SQ *RAMEN ISHIDA"):
    return Parsed(kind="purchase", amount=amount, merchant=merchant, last4="2637", date=D)


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.con = ledger.connect(":memory:")

    def test_new_then_reseen(self):
        self.assertEqual(ledger.record(self.con, "Chase", purchase(), "subj"), "txn_new")
        self.assertEqual(ledger.record(self.con, "Chase", purchase(), "subj"), "txn")

    def test_posted_twin_is_not_new(self):
        aid = ledger.ensure_account(self.con, "Chase", "2637")
        ledger.record_posted(self.con, "Chase", aid, Parsed(kind="purchase", amount=45.73, merchant="SQ *RAMEN ISHIDA", last4="2637", date=D, posted=True))
        self.assertEqual(ledger.record(self.con, "Chase", purchase(), "subj"), "txn")

    def test_statement_unchanged(self):
        p = Parsed(kind="statement", last4="2637", date=D, balance=663.16)
        self.assertEqual(ledger.record(self.con, "Chase", p, "subj"), "statement")


class PublishTests(unittest.TestCase):
    def test_publish_reaches_subscriber_and_noops_without(self):
        budgetmail.publish({"new_txns": 1})               # no subscribers: must not raise
        import queue
        q = queue.Queue()
        with budgetmail._sub_lock:
            budgetmail._subscribers.append(q)
        try:
            budgetmail.publish({"new_txns": 2})
            self.assertEqual(q.get(timeout=1), '{"new_txns":2}')
        finally:
            with budgetmail._sub_lock:
                budgetmail._subscribers.remove(q)


class RecategorizeTests(unittest.TestCase):
    """Dragging a transaction into another category: precedence, the merchant scope, and undo."""

    def setUp(self):
        self.con = ledger.connect(":memory:")
        for i, (merch, cat) in enumerate([("SQ *RAMEN ISHIDA", None), ("SQ *RAMEN ISHIDA #4471", None), ("NETFLIX.COM", None)]):
            ledger.record(self.con, "Chase", Parsed(kind="purchase", amount=10 + i, merchant=merch, last4="2637", date=D), "s")
        self.rows = {r["description"]: r["id"] for r in self.con.execute("SELECT id, description FROM transactions")}

    def cat(self, desc):
        import report
        r = self.con.execute("SELECT * FROM transactions WHERE description=?", (desc,)).fetchone()
        return report.Classifier(self.con).of(r)

    def test_rules_are_the_baseline(self):
        self.assertEqual(self.cat("SQ *RAMEN ISHIDA")[0], "Food & Dining")          # rules.toml: SQ \*
        self.assertEqual(self.cat("NETFLIX.COM")[0], "Bills & Subscriptions")

    def test_one_row_override_beats_the_rules_and_pins_it(self):
        r = budgetmail.recategorize(self.con, self.rows["NETFLIX.COM"], "Shopping", "one")
        self.assertEqual(r["changed"], 1)
        self.assertEqual(self.cat("NETFLIX.COM"), ("Shopping", False, True))
        budgetmail.revert_recategorize(self.con, r["revert"])                       # undo → back to the rule
        self.assertEqual(self.cat("NETFLIX.COM"), ("Bills & Subscriptions", False, False))

    def test_merchant_scope_moves_the_whole_merchant(self):
        r = budgetmail.recategorize(self.con, self.rows["SQ *RAMEN ISHIDA"], "People", "merchant")
        self.assertEqual(r["changed"], 2)                                           # store number stripped: both rows
        self.assertEqual(self.cat("SQ *RAMEN ISHIDA")[0], "People")
        self.assertEqual(self.cat("SQ *RAMEN ISHIDA #4471")[0], "People")
        self.assertEqual(self.cat("NETFLIX.COM")[0], "Bills & Subscriptions")       # and nothing else
        budgetmail.revert_recategorize(self.con, r["revert"])
        self.assertEqual(self.cat("SQ *RAMEN ISHIDA")[0], "Food & Dining")

    def test_merchant_scope_subsumes_and_restores_row_overrides(self):
        one = self.rows["SQ *RAMEN ISHIDA"]
        budgetmail.recategorize(self.con, one, "Travel", "one")
        r = budgetmail.recategorize(self.con, one, "People", "merchant")
        self.assertEqual(self.cat("SQ *RAMEN ISHIDA")[0], "People")                 # the rule wins, not the stale override
        budgetmail.revert_recategorize(self.con, r["revert"])
        self.assertEqual(self.cat("SQ *RAMEN ISHIDA")[0], "Travel")                 # undo puts the override back

    def test_unknown_transaction(self):
        with self.assertRaises(KeyError):
            budgetmail.recategorize(self.con, "nope", "Shopping", "one")

    def test_a_pinned_transfer_counts_as_spend(self):
        import dashboard, report
        tid = self.rows["NETFLIX.COM"]
        self.con.execute("UPDATE transactions SET type='transfer' WHERE id=?", (tid,))
        budgetmail.recategorize(self.con, tid, "Shopping", "one")
        tx = {t["id"]: t for t in dashboard.collect(self.con, report.Classifier(self.con))[0]}
        self.assertTrue(tx[tid]["pinned"])
        self.assertFalse(tx[tid]["ignore"])


if __name__ == "__main__":
    unittest.main()
