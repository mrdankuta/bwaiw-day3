"""SQLite store: months plus expenses in one file (ticket: Monthly foundation)."""

from __future__ import annotations

import os
import sqlite3
import time

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS months (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    currency TEXT NOT NULL DEFAULT 'NGN',
    income_cents INTEGER NOT NULL DEFAULT 0,
    side_cents INTEGER NOT NULL DEFAULT 0,
    rollover_cents INTEGER NOT NULL DEFAULT 0,
    savings_goal_cents INTEGER NOT NULL DEFAULT 0,
    emergency_saved_cents INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month_id INTEGER NOT NULL REFERENCES months(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    fixed INTEGER NOT NULL DEFAULT 0,
    one_off INTEGER NOT NULL DEFAULT 0,
    debt INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS suggestions_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month_id INTEGER NOT NULL REFERENCES months(id) ON DELETE CASCADE,
    backend TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    model_version TEXT NOT NULL,
    prompt TEXT NOT NULL DEFAULT '',
    data_flow TEXT NOT NULL DEFAULT '',
    output TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
"""


def _migrate(conn: sqlite3.Connection) -> None:
    exp_cols = {r[1] for r in conn.execute("PRAGMA table_info(expenses)").fetchall()}
    if "debt" not in exp_cols:
        conn.execute("ALTER TABLE expenses ADD COLUMN debt INTEGER NOT NULL DEFAULT 0")
    month_cols = {r[1] for r in conn.execute("PRAGMA table_info(months)").fetchall()}
    if "savings_goal_cents" not in month_cols:
        conn.execute("ALTER TABLE months ADD COLUMN savings_goal_cents INTEGER NOT NULL DEFAULT 0")
    if "emergency_saved_cents" not in month_cols:
        conn.execute(
            "ALTER TABLE months ADD COLUMN emergency_saved_cents INTEGER NOT NULL DEFAULT 0"
        )
    log_cols = {r[1] for r in conn.execute("PRAGMA table_info(suggestions_log)").fetchall()}
    if log_cols and "prompt" not in log_cols:
        conn.execute("ALTER TABLE suggestions_log ADD COLUMN prompt TEXT NOT NULL DEFAULT ''")
    if log_cols and "data_flow" not in log_cols:
        conn.execute("ALTER TABLE suggestions_log ADD COLUMN data_flow TEXT NOT NULL DEFAULT ''")
    conn.commit()


def default_path() -> str:
    return os.environ.get("DATABASE_PATH", "data/app.db")


def connect(path: str | None = None) -> sqlite3.Connection:
    target = path or default_path()
    parent = os.path.dirname(target)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def save_month(
    conn: sqlite3.Connection,
    *,
    currency: str,
    income_cents: int,
    side_cents: int,
    rollover_cents: int,
    savings_goal_cents: int = 0,
    emergency_saved_cents: int = 0,
) -> int:
    cur = conn.execute(
        "INSERT INTO months (currency, income_cents, side_cents, rollover_cents,"
        " savings_goal_cents, emergency_saved_cents, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            currency,
            income_cents,
            side_cents,
            rollover_cents,
            savings_goal_cents,
            emergency_saved_cents,
            int(time.time()),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def add_expense(
    conn: sqlite3.Connection,
    *,
    month_id: int,
    name: str,
    category: str,
    amount_cents: int,
    fixed: bool = False,
    one_off: bool = False,
    debt: bool = False,
) -> int:
    if conn.execute("SELECT 1 FROM months WHERE id = ?", (month_id,)).fetchone() is None:
        raise KeyError(f"unknown month: {month_id}")
    cur = conn.execute(
        "INSERT INTO expenses (month_id, name, category, amount_cents, fixed, one_off, debt)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (month_id, name, category, amount_cents, int(fixed), int(one_off), int(debt)),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_month(conn: sqlite3.Connection, month_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM months WHERE id = ?", (month_id,)).fetchone()
    if row is None:
        return None
    expenses = conn.execute(
        "SELECT * FROM expenses WHERE month_id = ? ORDER BY id", (month_id,)
    ).fetchall()
    return {
        "id": row["id"],
        "currency": row["currency"],
        "income_cents": row["income_cents"],
        "side_cents": row["side_cents"],
        "rollover_cents": row["rollover_cents"],
        "savings_goal_cents": row["savings_goal_cents"],
        "emergency_saved_cents": row["emergency_saved_cents"],
        "expenses": [dict(e) for e in expenses],
    }


def list_months(conn: sqlite3.Connection) -> list[dict]:
    return [
        dict(r)
        for r in conn.execute(
            "SELECT id, currency, income_cents, side_cents, rollover_cents,"
            " savings_goal_cents, emergency_saved_cents"
            " FROM months ORDER BY id DESC"
        ).fetchall()
    ]


def save_advice(
    conn: sqlite3.Connection,
    *,
    month_id: int,
    backend: str,
    prompt_version: str,
    model_version: str,
    prompt: str,
    data_flow: str,
    output: str,
) -> int:
    cur = conn.execute(
        "INSERT INTO suggestions_log (month_id, backend, prompt_version,"
        " model_version, prompt, data_flow, output, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            month_id,
            backend,
            prompt_version,
            model_version,
            prompt,
            data_flow,
            output,
            int(time.time()),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def latest_advice(conn: sqlite3.Connection, month_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM suggestions_log WHERE month_id = ? ORDER BY id DESC LIMIT 1",
        (month_id,),
    ).fetchone()
    return dict(row) if row is not None else None
