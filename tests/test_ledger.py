"""record() must distinguish a genuinely new row from a re-seen alert (sync re-reads 14 days of mail every cycle);
/api/events fires only on the former.  python3 -m unittest -v"""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ledger  # noqa: E402
from parsers import Parsed  # noqa: E402

import alertledger  # noqa: E402

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
        alertledger.publish({"new_txns": 1})               # no subscribers: must not raise
        import queue
        q = queue.Queue()
        with alertledger._sub_lock:
            alertledger._subscribers.append(q)
        try:
            alertledger.publish({"new_txns": 2})
            self.assertEqual(q.get(timeout=1), '{"new_txns":2}')
        finally:
            with alertledger._sub_lock:
                alertledger._subscribers.remove(q)


if __name__ == "__main__":
    unittest.main()
