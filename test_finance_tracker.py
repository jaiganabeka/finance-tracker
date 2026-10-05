import contextlib
import csv
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from finance_tracker.cli import main
from finance_tracker.money import check_month, format_money, parse_amount, parse_date
from finance_tracker.report import build_report
from finance_tracker.storage import Storage


class TestMoney(unittest.TestCase):
    def test_parse_amount(self):
        self.assertEqual(parse_amount("4500"), 450000)
        self.assertEqual(parse_amount("4500,50"), 450050)
        self.assertEqual(parse_amount("0.1"), 10)
        self.assertEqual(parse_amount("1 000"), 100000)

    def test_parse_amount_invalid(self):
        for bad in ["abc", "0", "-5", "1.234", "nan", "inf", ""]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    parse_amount(bad)

    def test_no_float_errors(self):
        self.assertEqual(parse_amount("0.1") + parse_amount("0.2"), parse_amount("0.3"))

    def test_format_money(self):
        self.assertEqual(format_money(450050), "4 500.50 тг")
        self.assertEqual(format_money(0), "0.00 тг")
        self.assertEqual(format_money(-123456789), "-1 234 567.89 тг")

    def test_dates(self):
        self.assertEqual(parse_date("2026-10-05"), "2026-10-05")
        with self.assertRaises(ValueError):
            parse_date("05.10.2026")
        with self.assertRaises(ValueError):
            check_month("2026-13")


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.s = Storage()
        self.s.add("income", 35000000, "зарплата", on="2026-10-01")
        self.s.add("expense", 1200000, "еда", on="2026-10-03")
        self.s.add("expense", 800000, "Еда", on="2026-10-10")
        self.s.add("expense", 500000, "транспорт", on="2026-10-12")
        self.s.add("expense", 999900, "еда", on="2026-09-20")

    def test_categories_are_normalized(self):
        cats = {t.category for t in self.s.list()}
        self.assertEqual(cats, {"Зарплата", "Еда", "Транспорт"})

    def test_month_filter(self):
        self.assertEqual(len(self.s.list("2026-10")), 4)
        self.assertEqual(len(self.s.list("2026-09")), 1)
        self.assertEqual(len(self.s.list()), 5)

    def test_totals(self):
        self.assertEqual(self.s.totals("2026-10"), (35000000, 2500000))

    def test_expenses_by_category_sorted(self):
        self.assertEqual(self.s.expenses_by_category("2026-10"),
                         [("Еда", 2000000), ("Транспорт", 500000)])

    def test_delete(self):
        first = self.s.list()[0].id
        self.assertTrue(self.s.delete(first))
        self.assertFalse(self.s.delete(first))

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            self.s.add("expense", 0, "Еда")
        with self.assertRaises(ValueError):
            self.s.add("gift", 100, "Еда")
        with self.assertRaises(ValueError):
            self.s.add("expense", 100, "  ")

    def test_budget_upsert(self):
        self.s.set_budget("еда", 1000000)
        self.s.set_budget("Еда", 1500000)
        self.assertEqual(self.s.budgets(), {"Еда": 1500000})


class TestReport(unittest.TestCase):
    def test_budget_exceeded_is_flagged(self):
        s = Storage()
        s.add("expense", 2000000, "Еда", on="2026-10-03")
        s.set_budget("Еда", 1500000)
        s.set_budget("Транспорт", 500000)
        text = build_report(s, "2026-10")
        self.assertIn("ПРЕВЫШЕН на 5 000.00 тг", text)
        self.assertIn("осталось 5 000.00 тг", text)

    def test_empty_report(self):
        text = build_report(Storage(), "2026-10")
        self.assertIn("Баланс:", text)
        self.assertIn("0.00 тг", text)


class TestCli(unittest.TestCase):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--db", self.db, *argv])
        return code, out.getvalue(), err.getvalue()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_list_report(self):
        self.assertEqual(self.run_cli("add", "доход", "350000", "-c", "Зарплата", "-d", "2026-10-01")[0], 0)
        self.assertEqual(self.run_cli("add", "expense", "4500.50", "-c", "Еда", "-d", "2026-10-02")[0], 0)
        _, out, _ = self.run_cli("list", "-m", "2026-10")
        self.assertIn("Зарплата", out)
        self.assertIn("-4 500.50 тг", out)
        _, out, _ = self.run_cli("report", "-m", "2026-10")
        self.assertIn("345 499.50 тг", out)

    def test_error_returns_code_1(self):
        code, _, err = self.run_cli("add", "expense", "-5")
        self.assertEqual(code, 1)
        self.assertIn("Ошибка", err)

    def test_export_csv(self):
        self.run_cli("add", "expense", "100", "-c", "Еда", "-n", "обед", "-d", "2026-10-02")
        path = str(Path(self.tmp.name) / "out.csv")
        self.run_cli("export", path)
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(rows[0]["amount"], "100.00")
        self.assertEqual(rows[0]["note"], "обед")


if __name__ == "__main__":
    unittest.main()
