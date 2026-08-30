"""Fixtures are real (scrubbed) email bodies, flattened the way mail.flatten() produces them.
To add a bank: add fixtures here for every subject shape it sends, then make them pass.  python3 -m unittest -v"""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import parsers  # noqa: E402
from parsers import Email  # noqa: E402

D = date(2026, 8, 30)
CHASE, BOFA = "no.reply.alerts@chase.com", "onlinebanking@ealerts.bankofamerica.com"


def parse(subject, sender, body, received=D):
    parsers.configure({"Chase": "0946", "Bank of America": "1933"})
    return parsers.for_sender(sender).parse(Email(subject, sender, body, received))


class ChaseTests(unittest.TestCase):
    def test_statement(self):
        p = parse("Your credit card statement is available", CHASE,
                  "Statement ready Your credit card statement is available Account Chase Credit Card (...2637) Due date 09/18/2026 Minimum payment due $40.00 Statement balance $663.16 Auto-pay enabled")
        self.assertEqual((p.kind, p.last4, p.balance, p.due), ("statement", "2637", 663.16, date(2026, 9, 18)))

    def test_card_purchase_from_subject(self):
        p = parse("You made a $45.73 transaction with SQ *RAMEN ISHIDA", CHASE,
                  "Account Chase Sapphire Preferred (...2637) Date Aug 3, 2026 at 1:23 PM ET Merchant SQ *RAMEN ISHIDA Amount $45.73")
        self.assertEqual((p.kind, p.amount, p.merchant, p.last4, p.date), ("purchase", 45.73, "SQ *RAMEN ISHIDA", "2637", date(2026, 8, 3)))
        self.assertEqual(p.signed_amount, -45.73)

    def test_debit_purchase_merchant_in_body(self):
        p = parse("Your debit card transaction of $8.50", CHASE,
                  "Account Chase Secure Banking (...0946) Date Aug 30, 2026 Merchant BLUE BOTTLE COFFEE Amount $8.50")
        self.assertEqual((p.kind, p.merchant, p.last4), ("purchase", "BLUE BOTTLE COFFEE", "0946"))

    def test_zelle_received_is_income(self):
        p = parse("You received money with Zelle", CHASE,
                  "Zelle payment TYRONE THA sent you money Here are the details: Amount $16.00 Sent on Aug 29, 2026 Transaction number 30605351352 Memo burger")
        self.assertEqual((p.kind, p.amount, p.merchant, p.last4, p.date), ("zelle_in", 16.0, "Zelle from TYRONE THA", "0946", date(2026, 8, 29)))
        self.assertEqual(p.txn_type, "transfer")

    def test_noise_is_skipped_not_failed(self):
        for s in ("We've received your Chase Sapphire Preferred Visa payment", "Your latest statement is now available",
                  "You edited SheetLink's data access", "We're reviewing your transfer", "You received a new letter"):
            self.assertEqual(parse(s, CHASE, "x").kind, "skip", s)

    def test_unknown_subject_returns_none(self):
        self.assertIsNone(parse("Something Chase has never sent before", CHASE, "x"))


class BofATests(unittest.TestCase):
    def test_statement(self):
        p = parse("Your credit card statement is available", BOFA,
                  "Account Customized Cash Rewards Visa Signature - 4139 Statement Date July 27, 2026 Total Minimum Payment Due $35.00 Statement Balance $144.99 VIEW STATEMENT Your minimum payment of $35.00 is due on August 24, 2026.")
        self.assertEqual((p.kind, p.last4, p.date, p.balance, p.due), ("statement", "4139", date(2026, 7, 27), 144.99, date(2026, 8, 24)))

    def test_purchase_not_present(self):
        p = parse("Credit card not present during this transaction", BOFA,
                  "Credit card not present during this transaction Customized Cash Rewards Visa Signature ending in 4139 Amount: $54.98 Date: April 18, 2026 Where: FLIX This may have occurred for a purchase you made online, by phone, mail or when a merchant manually enters your card information. View details")
        self.assertEqual((p.kind, p.amount, p.merchant, p.last4, p.date), ("purchase", 54.98, "FLIX", "4139", date(2026, 4, 18)))

    def test_purchase_abroad_strips_location(self):
        p = parse("Credit card transaction outside the 50 U.S. states", BOFA,
                  "Customized Cash Rewards Visa Signature ending in 4139 Amount: $13.81 Date: May 23, 2025 Where: PEAK TRAMWAYS CO LTD Location: Country not provided View details")
        self.assertEqual(p.merchant, "PEAK TRAMWAYS CO LTD")

    def test_charge_over_threshold_dedupes_with_not_present(self):
        a = parse("Credit card charge over your alert limit", BOFA, "Visa Signature ending in 4139 Amount: $21.24 Date: August 13, 2026 Where: GOOGLE *GOOGLE ONE View details")
        b = parse("Credit card not present during this transaction", BOFA, "Visa Signature ending in 4139 Amount: $21.24 Date: August 13, 2026 Where: GOOGLE *GOOGLE ONE This may have occurred")
        self.assertEqual((a.kind, a.amount, a.merchant, a.date), (b.kind, b.amount, b.merchant, b.date))

    def test_refund(self):
        p = parse("Credit received on credit card", BOFA, "Visa Signature ending in 4139 Amount: $12.00 Date: August 29, 2026 Where: AMAZON")
        self.assertEqual((p.kind, p.signed_amount), ("refund", 12.0))

    def test_zelle_sent_new_format(self):
        p = parse("Zelle payment of $75.00 to CONNECTICUT TAEKWONDO ACADEMY LLC has been sent", BOFA,
                  "Zelle payment of $75.00 to CONNECTICUT TAEKWONDO ACADEMY LLC has been sent Sent from account ending in 1933 To 203-252-4939 Confirmation yueig8wz4")
        self.assertEqual((p.kind, p.amount, p.merchant, p.last4), ("zelle_out", 75.0, "Zelle to CONNECTICUT TAEKWONDO ACADEMY LLC", "1933"))

    def test_zelle_sent_old_format(self):
        p = parse("You sent $165.95 to Kevin gu", BOFA, "You sent $165.95 to Kevin gu sent from account ending in 1933 to 774.534.0481 Message: Itzy tickets View balance")
        self.assertEqual((p.kind, p.amount, p.merchant), ("zelle_out", 165.95, "Zelle to Kevin gu"))

    def test_check_deposit_is_income(self):
        p = parse("We received your mobile check deposit", BOFA,
                  "We received your mobile check deposit Check amount: $76.66 To: Adv SafeBalance Banking 1933 Credit posts on: June 09, 2021 Available now: $0.00 Confirmation #: 3708730541")
        self.assertEqual((p.kind, p.amount, p.last4, p.date, p.txn_type), ("deposit", 76.66, "1933", date(2021, 6, 9), "transfer"))

    def test_noise_is_skipped(self):
        for s in ("Your account may have insufficient funds", "Confirmation of your consent to share your account information with Plaid",
                  "Your card is ready to use in Apple Pay", "Reminder: Review Your FICO(R) Score", "Your statement is available",
                  "hope x accepted your $2.90 Zelle payment", "Your credit card year-end summary is available"):
            self.assertEqual(parse(s, BOFA, "x").kind, "skip", s)


class RegistryTests(unittest.TestCase):
    def test_sender_routing(self):
        self.assertEqual(parsers.for_sender("Chase <no.reply.alerts@chase.com>").name, "Chase")
        self.assertEqual(parsers.for_sender(BOFA).name, "Bank of America")
        self.assertIsNone(parsers.for_sender("promo@mcmap.chase.com"))


if __name__ == "__main__":
    unittest.main()


class CsvTests(unittest.TestCase):
    def rows(self, text):
        import csv, io
        r = list(csv.reader(io.StringIO(text)))
        return r[0], r[1:]

    def test_chase_card_csv(self):
        h, rows = self.rows("Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n"
                            "08/03/2026,08/04/2026,SQ *RAMEN ISHIDA,Food & Drink,Sale,-45.73,\n"
                            "08/10/2026,08/11/2026,AMAZON.COM,Shopping,Return,12.00,\n"
                            "08/18/2026,08/18/2026,AUTOMATIC PAYMENT - THANK,,Payment,663.16,\n")
        out = list(parsers.for_sender(CHASE).csv_rows(h, rows))
        self.assertEqual([(p.kind, p.amount, p.merchant, p.category, p.posted) for p in out],
                         [("purchase", 45.73, "SQ *RAMEN ISHIDA", "Food & Drink", True), ("refund", 12.0, "AMAZON.COM", "Shopping", True)])
        self.assertEqual(out[0].date, date(2026, 8, 4))

    def test_chase_checking_csv(self):
        h, rows = self.rows("Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #\n"
                            "DEBIT,08/05/2026,BLUE BOTTLE COFFEE NEW YORK NY,-8.50,DEBIT_CARD,991.50,\n"
                            "CREDIT,08/06/2026,Zelle payment from TYRONE THA 30605351352,16.00,QUICKPAY_CREDIT,1007.50,\n"
                            "DEBIT,08/07/2026,Payment to Chase card ending in 2637,-663.16,ACCT_XFER,344.34,\n")
        out = list(parsers.for_sender(CHASE).csv_rows(h, rows))
        self.assertEqual([(p.kind, p.amount) for p in out], [("purchase", 8.5), ("deposit", 16.0)])

    def test_bofa_csv_with_preamble(self):
        text = ('Description,,Summary Amt.\nBeginning balance as of 07/01/2026,,"1,000.00"\n,,\n'
                "Date,Description,Amount,Running Bal.\n"
                '07/17/2026,"Zelle payment to CONNECTICUT TAEKWONDO ACADEMY LLC Conf# yueig8wz4",-75.00,"925.00"\n'
                '07/20/2026,"CHECKCARD 0719 STARBUCKS 800-782-7282 WA",-6.45,"918.55"\n'
                '07/25/2026,"Online Banking transfer to SAV 4727",-100.00,"818.55"\n')
        h, rows = self.rows(text)
        out = list(parsers.for_sender(BOFA).csv_rows(h, rows))
        self.assertEqual([(p.kind, p.amount, p.merchant) for p in out],
                         [("zelle_out", 75.0, "Zelle to Connecticut Taekwondo Academy Llc"), ("purchase", 6.45, "CHECKCARD 0719 STARBUCKS 800-782-7282 WA")])

    def test_wrong_csv_raises(self):
        with self.assertRaises(ValueError):
            list(parsers.for_sender(CHASE).csv_rows(["a", "b"], [["1", "2"]]))


class ChasePdfTests(unittest.TestCase):
    CARD = """    Previous Balance                                                            $831.90
    New Balance                                                                 $663.16
    Opening/Closing Date                                          07/22/26 - 08/21/26
PAYMENTS AND OTHER CREDITS
  08/18                    AUTOMATIC PAYMENT - THANK YOU                                                                            -831.90
  08/10                    AMAZON.COM REFUND                                                                                        -12.00
PURCHASE
  07/22                    TST*SEOUL SALON New York NY                                                                                99.00
  05/28                    SKEJOOL SUNGSOO SEOUL                                                                                     29.01
  05/29                    WON
  43,300 X 0.000669976 (EXCHG RATE)
  08/15                    SHANGHAI MONG NEW YORK NY                                                                                  60.00
INTEREST CHARGES
"""
    CHECKING = """                                       July 25, 2026 through August 26, 2026
           TRANSACTION DETAIL
                                                  Beginning Balance                                                                                                $938.25
             07/27                              Recurring Card Purchase 07/26 Apple.Com/Bill 866-712-7753 CA Card 6066                       -9.99                  928.26
             07/29                              Online Transfer 30184458620 From Adv Safebalance Banking                                  2,000.00                 2,928.26
             08/19                              Chase Credit Crd Autopay                  PPD ID: 4760039224                               -831.90                 2,096.36
             08/21                              Zelle Payment From Reuben Miranda 30503184858                                               54.00                  2,150.36
             08/24                              Zelle Payment To Zhitong Liu Jpm99CU4Mju2                                                   -47.50                 2,102.86
                                                  Ending Balance                                                                                              $2,092.87
"""

    def test_card_statement(self):
        rows = list(parsers.for_sender(CHASE).pdf_rows(self.CARD, "20260821-statements-2637-.pdf"))
        kinds = [(p.kind, p.amount, p.merchant[:16], p.date) for p in rows]
        self.assertIn(("refund", 12.0, "AMAZON.COM REFUN", date(2026, 8, 10)), kinds)
        self.assertIn(("purchase", 99.0, "TST*SEOUL SALON ", date(2026, 7, 22)), kinds)
        self.assertNotIn("WON", [p.merchant for p in rows])                        # FX continuation lines skipped
        self.assertFalse(any("PAYMENT" in p.merchant for p in rows))                # autopay is not spend
        st = [p for p in rows if p.kind == "statement"][0]
        self.assertEqual((st.balance, st.date), (663.16, date(2026, 8, 21)))
        self.assertEqual([p for p in rows if p.merchant.startswith("SKEJOOL")][0].date.year, 2026)   # out-of-window date still gets a sane year

    def test_checking_statement(self):
        rows = list(parsers.for_sender(CHASE).pdf_rows(self.CHECKING, "20260826-statements-0946-.pdf"))
        self.assertEqual([(p.kind, p.amount, p.merchant) for p in rows],
                         [("purchase", 9.99, "Apple.Com/Bill 866-712-7753 CA"), ("zelle_in", 54.0, "Zelle from Reuben Miranda"), ("zelle_out", 47.5, "Zelle to Zhitong Liu")])
        self.assertEqual(rows[0].date, date(2026, 7, 27))

    def test_not_chase(self):
        with self.assertRaises(ValueError):
            list(parsers.for_sender(CHASE).pdf_rows("Bank of America statement", "x.pdf"))
