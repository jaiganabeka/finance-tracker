"""Работа с деньгами и датами.

Суммы хранятся целым числом в минимальных единицах (тиыны, 1 тг = 100 тиын).
Так нет ошибок округления, которые бывают у float (0.1 + 0.2 != 0.3).
"""
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def parse_amount(text) -> int:
    """'4500' -> 450000, '4500,50' -> 450050. Сумма должна быть > 0, до 2 знаков после запятой."""
    try:
        value = Decimal(str(text).strip().replace(" ", "").replace(",", "."))
    except InvalidOperation:
        raise ValueError(f"Некорректная сумма: {text!r}") from None
    if not value.is_finite():
        raise ValueError(f"Некорректная сумма: {text!r}")
    if value <= 0:
        raise ValueError("Сумма должна быть больше нуля")
    if value.as_tuple().exponent < -2:
        raise ValueError("Не более двух знаков после запятой")
    return int(value * 100)


def format_money(minor: int) -> str:
    """450050 -> '4 500.50 тг'."""
    sign = "-" if minor < 0 else ""
    minor = abs(minor)
    whole = f"{minor // 100:,}".replace(",", " ")
    return f"{sign}{whole}.{minor % 100:02d} тг"


def parse_date(text=None) -> str:
    """Возвращает дату в формате ГГГГ-ММ-ДД. Без аргумента — сегодняшняя."""
    if not text:
        return date.today().isoformat()
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise ValueError(f"Дата должна быть в формате ГГГГ-ММ-ДД: {text!r}") from None


def check_month(text: str) -> str:
    if not _MONTH_RE.match(text):
        raise ValueError(f"Месяц должен быть в формате ГГГГ-ММ, например 2026-10: {text!r}")
    return text


def current_month() -> str:
    return date.today().strftime("%Y-%m")
