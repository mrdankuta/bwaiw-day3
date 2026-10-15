"""Privacy seam tests: consent gating, no-egress default, migrations."""

import sqlite3

import pytest

from app import llm, store
from app.advice import validate_output
from app.engine import ExpenseInput, compute_plan


def _plan():
    return compute_plan(
        income_cents=100_00,
        expenses=[ExpenseInput(name="Rent", category="Housing",
                               amount_cents=40_00, fixed=True)],
    )


def test_local_backend_sends_nothing_off_machine():
    lines, flow = llm.generate("template-local", "prompt", _plan(), "NGN")
    assert lines
    assert not validate_output("\n".join(lines), _plan())
    assert "No fields left this machine" in flow


def test_unknown_backend_rejected():
    with pytest.raises(ValueError, match="unknown backend"):
        llm.generate("megacloud", "prompt", _plan(), "NGN")


def test_http_backend_needs_consent():
    with pytest.raises(PermissionError, match="consent"):
        llm.generate("ollama", "prompt", _plan(), "NGN")


def test_legacy_db_migrates_on_boot(tmp_path):
    db = str(tmp_path / "legacy.db")
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE months (id INTEGER PRIMARY KEY, currency TEXT,"
                 " income_cents INTEGER, side_cents INTEGER, rollover_cents INTEGER)")
    conn.execute("INSERT INTO months VALUES (1, 'NGN', 100, 0, 0)")
    conn.execute("CREATE TABLE expenses (id INTEGER PRIMARY KEY, month_id INTEGER,"
                 " name TEXT, category TEXT, amount_cents INTEGER,"
                 " fixed INTEGER, one_off INTEGER)")
    conn.commit()
    conn.close()
    conn = store.connect(db)
    try:
        month = store.get_month(conn, 1)
        assert month["savings_goal_cents"] == 0
        assert month["emergency_saved_cents"] == 0
    finally:
        conn.close()


def test_backup_restore_round_trip(tmp_path):
    from scripts import backup as backup_mod
    from scripts import restore as restore_mod

    db = str(tmp_path / "app.db")
    conn = store.connect(db)
    mid = store.save_month(conn, currency="NGN", income_cents=100,
                           side_cents=0, rollover_cents=0)
    conn.close()
    dest = backup_mod.backup(db, str(tmp_path / "backups"))
    wiped = str(tmp_path / "restored.db")
    restore_mod.restore(dest, wiped)
    conn = store.connect(wiped)
    try:
        assert store.get_month(conn, mid)["income_cents"] == 100
    finally:
        conn.close()
    with pytest.raises(FileExistsError):
        restore_mod.restore(dest, wiped)
