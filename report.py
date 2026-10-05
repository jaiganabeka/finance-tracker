"""Текстовые отчёты."""
from .money import format_money


def build_report(storage, month=None) -> str:
    income, expense = storage.totals(month)
    title = f"Отчёт за {month}" if month else "Отчёт за всё время"
    lines = [title, "=" * len(title)]
    lines.append(f"Доходы:  {format_money(income):>16}")
    lines.append(f"Расходы: {format_money(expense):>16}")
    lines.append(f"Баланс:  {format_money(income - expense):>16}")

    by_cat = storage.expenses_by_category(month)
    if by_cat:
        lines += ["", "Расходы по категориям:"]
        width = max(len(c) for c, _ in by_cat)
        for cat, total in by_cat:
            share = total * 100 / expense
            bar = "#" * max(1, round(share / 5))
            lines.append(f"  {cat:<{width}}  {format_money(total):>14}  {share:5.1f}%  {bar}")

    # лимиты месячные, поэтому показываем их только в отчёте за конкретный месяц
    budgets = storage.budgets() if month else {}
    if budgets:
        spent = dict(by_cat)
        lines += ["", "Бюджеты:"]
        width = max(len(c) for c in budgets)
        for cat, limit in budgets.items():
            used = spent.get(cat, 0)
            if used > limit:
                status = f"ПРЕВЫШЕН на {format_money(used - limit)}"
            else:
                status = f"осталось {format_money(limit - used)}"
            lines.append(f"  {cat:<{width}}  {format_money(used):>14} из {format_money(limit):>14}  {status}")
    return "\n".join(lines)
