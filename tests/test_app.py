"""Wizard + store tests: end-to-end behavior through HTTP and reopen."""

from fastapi.testclient import TestClient

from app import store
from app.main import app


def _client(tmp_path, monkeypatch):
    db = str(tmp_path / "app.db")
    monkeypatch.setenv("DATABASE_PATH", db)
    return TestClient(app), db


def test_wizard_income_to_plan_with_table(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)

    res = client.post(
        "/wizard/income",
        data={"currency": "NGN", "income_cents": "25000",
              "side_cents": "5000", "rollover_cents": "2000"},
        follow_redirects=False,
    )
    assert res.status_code == 303
    month_id = res.headers["location"].split("month_id=")[1]

    res = client.post(
        "/wizard/expenses",
        data={"month_id": month_id, "name": "Rent", "category": "Housing",
              "amount_cents": "10000"},
    )
    assert res.status_code == 200

    res = client.get(f"/wizard/plan?month_id={month_id}")
    assert res.status_code == 200
    assert "32000" in res.text  # available
    assert "10000" in res.text  # total
    assert "22000" in res.text  # leftover
    assert "Warnings" in res.text and "Suggestions" in res.text


def test_plan_shows_rent_warning(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    res = client.post(
        "/wizard/income",
        data={"currency": "NGN", "income_cents": "10000",
              "side_cents": "0", "rollover_cents": "0"},
        follow_redirects=False,
    )
    month_id = res.headers["location"].split("month_id=")[1]
    client.post(
        "/wizard/expenses",
        data={"month_id": month_id, "name": "Rent", "category": "Housing",
              "amount_cents": "4000", "fixed": "on"},
    )
    res = client.get(f"/wizard/plan?month_id={month_id}")
    assert "rent burden" in res.text.lower()


def test_store_survives_reopen(tmp_path, monkeypatch):
    client, db = _client(tmp_path, monkeypatch)
    res = client.post(
        "/wizard/income",
        data={"currency": "NGN", "income_cents": "100",
              "side_cents": "0", "rollover_cents": "0"},
        follow_redirects=False,
    )
    month_id = res.headers["location"].split("month_id=")[1]

    conn = store.connect(db)
    try:
        assert store.get_month(conn, int(month_id))["income_cents"] == 100
    finally:
        conn.close()


def test_unknown_month_is_404(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    assert client.get("/wizard/plan?month_id=9999").status_code == 404


def test_advice_generates_logs_and_renders(tmp_path, monkeypatch):
    from app import store as store_mod

    client, db = _client(tmp_path, monkeypatch)
    month_id = _make_month(client)
    client.post("/wizard/expenses",
                data={"month_id": month_id, "name": "Rent",
                      "category": "Housing", "amount_cents": "4000",
                      "fixed": "on"})
    res = client.post("/wizard/advice", data={"month_id": month_id})
    assert res.status_code == 200  # followed redirect to plan
    assert "Educational information only" in res.text  # banner
    assert "Generate advice" in res.text
    assert "No fields left this machine" in res.text  # data-flow log
    conn = store_mod.connect(db)
    try:
        logged = store_mod.latest_advice(conn, int(month_id))
    finally:
        conn.close()
    assert logged["prompt_version"] == "advice-v1"
    assert "Educational only" in logged["prompt"]
    assert "4000" in logged["output"]


def test_disclaimer_page(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    res = client.get("/disclaimer")
    assert "not financial" in res.text.lower()
    assert "non-discretionary" in res.text.lower()


def test_cloud_backend_without_consent_refused(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    month_id = _make_month(client)
    res = client.post("/wizard/advice",
                      data={"month_id": month_id, "backend": "ollama"})
    assert res.status_code == 422
    res = client.get(f"/wizard/plan?month_id={month_id}")
    assert "Data flow" not in res.text  # nothing logged, nothing sent


def test_decimal_amounts_rejected_and_large_exact(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    res = client.post("/wizard/income",
                      data={"currency": "NGN", "income_cents": "10.5",
                            "side_cents": "0", "rollover_cents": "0"})
    assert res.status_code == 422
    month_id = _make_month(client, income_cents="9007199254740993")
    res = client.get(f"/wizard/plan?month_id={month_id}")
    assert "9007199254740993" in res.text


def _make_month(client, **over):
    data = {"currency": "NGN", "income_cents": "10000", "side_cents": "0",
            "rollover_cents": "0", "savings_goal_cents": "0",
            "emergency_saved_cents": "0"}
    data.update(over)
    res = client.post("/wizard/income", data=data, follow_redirects=False)
    return res.headers["location"].split("month_id=")[1]


def test_goal_progress_and_emergency_cover(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    month_id = _make_month(client, savings_goal_cents="3000",
                           emergency_saved_cents="8000")
    client.post("/wizard/expenses",
                data={"month_id": month_id, "name": "Rent",
                      "category": "Housing", "amount_cents": "4000",
                      "fixed": "on"})
    res = client.get(f"/wizard/plan?month_id={month_id}")
    assert "Goal progress" in res.text
    assert "2.0" in res.text  # 8000 / 4000 essentials
    assert "Emergency cover" in res.text


def test_rollover_prefill_and_next_month_link(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    month_id = _make_month(client)
    client.post("/wizard/expenses",
                data={"month_id": month_id, "name": "Rent",
                      "category": "Housing", "amount_cents": "4000"})
    res = client.get(f"/wizard/plan?month_id={month_id}")
    assert "rollover_cents=6000" in res.text  # 10000 - 4000
    res = client.get("/wizard/income?rollover_cents=6000")
    assert "value='6000'" in res.text


def test_month_compare_and_debt_total(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    first = _make_month(client)
    client.post("/wizard/expenses",
                data={"month_id": first, "name": "Loan",
                      "category": "Other", "amount_cents": "2000",
                      "fixed": "on", "debt": "on"})
    res = client.get(f"/wizard/plan?month_id={first}")
    assert "Debt payments" in res.text
    second = _make_month(client)
    res = client.get("/months")
    assert "Available" in res.text and "Leftover" in res.text
    assert f"month_id={first}" in res.text and f"month_id={second}" in res.text
