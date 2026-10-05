"""Хранилище на SQLite (встроенный модуль sqlite3, ничего устанавливать не нужно)."""
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .money import check_month, parse_date

KINDS = ("income", "expense")

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    date     TEXT    NOT NULL,
    kind     TEXT    NOT NULL CHECK (kind IN ('income', 'expense')),
    category TEXT    NOT NULL,
    amount   INTEGER NOT NULL CHECK (amount > 0),
    note     TEXT    NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS budgets (
    category     TEXT PRIMARY KEY,
    limit_amount INTEGER NOT NULL CHECK (limit_amount > 0)
);
"""


@dataclass(frozen=True)
class Transaction:
    id: int
    date: str
    kind: str
    category: str
    amount: int
    note: str


def normalize_category(name: str) -> str:
    name = (name or "").strip()
    if not name:
        raise ValueError("Категория не может быть пустой")
    return name.capitalize()


class Storage:
    def __init__(self, path=":memory:"):
        if str(path) != ":memory:":
            Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
            path = str(Path(path).expanduser())
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # --- операции ---
    def add(self, kind: str, amount: int, category: str, note: str = "", on=None) -> int:
        if kind not in KINDS:
            raise ValueError(f"Тип операции должен быть один из {KINDS}")
        if amount <= 0:
            raise ValueError("Сумма должна быть больше нуля")
        cur = self.conn.execute(
            "INSERT INTO transactions (date, kind, category, amount, note) VALUES (?, ?, ?, ?, ?)",
            (parse_date(on), kind, normalize_category(category), amount, note.strip()),
        )
        self.conn.commit()
        return cur.lastrowid

    def list(self, month=None) -> list:
        sql, params = "SELECT * FROM transactions", ()
        if month:
            sql += " WHERE substr(date, 1, 7) = ?"
            params = (check_month(month),)
        sql += " ORDER BY date, id"
        return [Transaction(**dict(r)) for r in self.conn.execute(sql, params)]

    def delete(self, tx_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        self.conn.commit()
        return cur.rowcount > 0

    # --- итоги ---
    def totals(self, month=None) -> tuple:
        """Возвращает (доходы, расходы) в минимальных единицах."""
        where, params = "", ()
        if month:
            where, params = " AND substr(date, 1, 7) = ?", (check_month(month),)
        out = {}
        for kind in KINDS:
            row = self.conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE kind = ?" + where,
                (kind,) + params,
            ).fetchone()
            out[kind] = row[0]
        return out["income"], out["expense"]

    def expenses_by_category(self, month=None) -> list:
        sql = "SELECT category, SUM(amount) AS total FROM transactions WHERE kind = 'expense'"
        params = ()
        if month:
            sql += " AND substr(date, 1, 7) = ?"
            params = (check_month(month),)
        sql += " GROUP BY category ORDER BY total DESC, category"
        return [(r["category"], r["total"]) for r in self.conn.execute(sql, params)]

    # --- бюджеты (месячные лимиты по категориям) ---
    def set_budget(self, category: str, limit_amount: int) -> None:
        if limit_amount <= 0:
            raise ValueError("Лимит должен быть больше нуля")
        self.conn.execute(
            "INSERT INTO budgets (category, limit_amount) VALUES (?, ?) "
            "ON CONFLICT(category) DO UPDATE SET limit_amount = excluded.limit_amount",
            (normalize_category(category), limit_amount),
        )
        self.conn.commit()

    def budgets(self) -> dict:
        rows = self.conn.execute("SELECT category, limit_amount FROM budgets ORDER BY category")
        return {r["category"]: r["limit_amount"] for r in rows}
