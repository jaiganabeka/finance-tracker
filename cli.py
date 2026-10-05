"""Интерфейс командной строки."""
import argparse
import csv
import os
import sys
from pathlib import Path

from .money import current_month, format_money, parse_amount
from .report import build_report
from .storage import Storage

DEFAULT_DB = Path.home() / ".finance_tracker" / "finance.db"

KIND_ALIASES = {"income": "income", "доход": "income", "expense": "expense", "расход": "expense"}
KIND_RU = {"income": "доход", "expense": "расход"}


def _kind(value: str) -> str:
    try:
        return KIND_ALIASES[value.lower()]
    except KeyError:
        raise argparse.ArgumentTypeError("используйте income/expense (или доход/расход)") from None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="finance_tracker", description="Учёт личных финансов")
    p.add_argument("--db", default=os.environ.get("FINANCE_DB", str(DEFAULT_DB)),
                   help="путь к файлу базы данных (по умолчанию ~/.finance_tracker/finance.db)")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="добавить операцию")
    a.add_argument("kind", type=_kind, help="income/expense или доход/расход")
    a.add_argument("amount", help="сумма, например 4500 или 4500.50")
    a.add_argument("-c", "--category", default="Прочее")
    a.add_argument("-n", "--note", default="")
    a.add_argument("-d", "--date", help="ГГГГ-ММ-ДД (по умолчанию сегодня)")

    ls = sub.add_parser("list", help="список операций")
    ls.add_argument("-m", "--month", help="фильтр по месяцу ГГГГ-ММ")

    de = sub.add_parser("delete", help="удалить операцию по id")
    de.add_argument("id", type=int)

    r = sub.add_parser("report", help="отчёт за месяц")
    r.add_argument("-m", "--month", help="ГГГГ-ММ (по умолчанию текущий месяц)")
    r.add_argument("--all", action="store_true", help="отчёт за всё время")

    b = sub.add_parser("budget", help="месячные лимиты расходов по категориям")
    bsub = b.add_subparsers(dest="budget_cmd", required=True)
    bs = bsub.add_parser("set", help="установить лимит")
    bs.add_argument("category")
    bs.add_argument("amount")
    bsub.add_parser("list", help="показать лимиты")

    e = sub.add_parser("export", help="выгрузить все операции в CSV")
    e.add_argument("path")
    return p


def _print_transactions(txs) -> None:
    if not txs:
        print("Операций нет")
        return
    print(f"{'ID':>4}  {'Дата':<10}  {'Тип':<6}  {'Категория':<18}  {'Сумма':>16}  Заметка")
    for t in txs:
        sign = "+" if t.kind == "income" else "-"
        print(f"{t.id:>4}  {t.date:<10}  {KIND_RU[t.kind]:<6}  {t.category:<18}  "
              f"{sign + format_money(t.amount):>16}  {t.note}")


def run(args, storage: Storage) -> None:
    if args.cmd == "add":
        tx_id = storage.add(args.kind, parse_amount(args.amount), args.category, args.note, args.date)
        print(f"Добавлено (id {tx_id})")
    elif args.cmd == "list":
        _print_transactions(storage.list(args.month))
    elif args.cmd == "delete":
        print("Удалено" if storage.delete(args.id) else f"Операции с id {args.id} нет")
    elif args.cmd == "report":
        month = None if args.all else (args.month or current_month())
        print(build_report(storage, month))
    elif args.cmd == "budget":
        if args.budget_cmd == "set":
            storage.set_budget(args.category, parse_amount(args.amount))
            print("Лимит сохранён")
        else:
            budgets = storage.budgets()
            if not budgets:
                print("Лимитов нет")
            for cat, limit in budgets.items():
                print(f"{cat:<18} {format_money(limit)} в месяц")
    elif args.cmd == "export":
        with open(args.path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["id", "date", "kind", "category", "amount", "note"])
            for t in storage.list():
                w.writerow([t.id, t.date, t.kind, t.category, f"{t.amount / 100:.2f}", t.note])
        print(f"Выгружено в {args.path}")


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    storage = Storage(args.db)
    try:
        run(args, storage)
    except ValueError as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 1
    finally:
        storage.close()
    return 0
