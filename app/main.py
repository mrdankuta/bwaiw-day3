"""Stepped wizard web app: Income -> Expenses -> Plan (ticket: Monthly foundation)."""

from __future__ import annotations

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from . import store
from .advice import (
    DISCLAIMER_SHORT,
    MODEL_VERSION_DEFAULT,
    PROMPT_VERSION,
    build_prompt,
    validate_output,
)
from .engine import EXPENSE_CATEGORIES, ExpenseInput, PlanResult, compute_plan
from .llm import (
    KNOWN_BACKENDS,
    LOCAL_BACKEND,
    base_url,
    default_backend,
    generate as llm_generate,
)

app = FastAPI(title="Monthly Planner")


def _page(title: str, body: str) -> str:
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{title}</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:720px;margin:24px auto;padding:0 16px}"
        "table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:8px;text-align:left}"
        "input,select{padding:6px;margin:2px 0}label{display:block;margin:8px 0}</style>"
        f"</head><body><p><small>{DISCLAIMER_SHORT} "
        "<a href='/disclaimer'>Full disclaimer</a></small></p>"
        f"<h1>{title}</h1>{body}</body></html>"
    )


def _parse_cents(raw: str, label: str) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=f"{label} must be an integer")
    if value < 0:
        raise HTTPException(status_code=422, detail=f"{label} must be >= 0")
    return value


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _page(
        "Monthly Planner",
        "<p>Plan this month in three steps.</p>"
        "<p><a href='/wizard/income'>Start: step 1 Income</a> · "
        "<a href='/months'>Past months</a></p>",
    )


@app.get("/wizard/income", response_class=HTMLResponse)
def income_form(currency: str = "NGN", rollover_cents: str = "0") -> str:
    try:
        pre_roll = int(rollover_cents) if int(rollover_cents) >= 0 else 0
    except (TypeError, ValueError):
        pre_roll = 0
    return _page(
        "Step 1: Income",
        "<form method='post' action='/wizard/income'>"
        f"<label>Currency code <input name='currency' value='{currency}' maxlength='8'></label>"
        "<label>Recurring Income (minor units) <input name='income_cents' value='250000'></label>"
        "<label>Other Inflows (minor units) <input name='side_cents' value='50000'></label>"
        f"<label>Savings Rollover (minor units) <input name='rollover_cents' value='{pre_roll}'></label>"
        "<label>Monthly Savings Goal (minor units, 0 = none) <input name='savings_goal_cents' value='0'></label>"
        "<label>Emergency Fund saved (minor units) <input name='emergency_saved_cents' value='0'></label>"
        "<button type='submit'>Continue to Expenses</button></form>",
    )


@app.post("/wizard/income")
def income_submit(
    currency: str = Form("NGN"),
    income_cents: str = Form("0"),
    side_cents: str = Form("0"),
    rollover_cents: str = Form("0"),
    savings_goal_cents: str = Form("0"),
    emergency_saved_cents: str = Form("0"),
) -> RedirectResponse:
    code = (currency or "NGN").strip().upper()[:8] or "NGN"
    conn = store.connect()
    try:
        month_id = store.save_month(
            conn,
            currency=code,
            income_cents=_parse_cents(income_cents, "income"),
            side_cents=_parse_cents(side_cents, "side inflows"),
            rollover_cents=_parse_cents(rollover_cents, "rollover"),
            savings_goal_cents=_parse_cents(savings_goal_cents, "savings goal"),
            emergency_saved_cents=_parse_cents(emergency_saved_cents, "emergency saved"),
        )
    finally:
        conn.close()
    return RedirectResponse(
        f"/wizard/expenses?month_id={month_id}", status_code=303
    )


@app.get("/wizard/expenses", response_class=HTMLResponse)
def expenses_form(month_id: int) -> str:
    conn = store.connect()
    try:
        month = store.get_month(conn, month_id)
    finally:
        conn.close()
    if month is None:
        raise HTTPException(status_code=404, detail="unknown month")
    options = "".join(f"<option>{c}</option>" for c in EXPENSE_CATEGORIES)
    rows = "".join(
        f"<tr><td>{e['name']}</td><td>{e['category']}</td>"
        f"<td>{e['amount_cents']}</td></tr>"
        for e in month["expenses"]
    )
    return _page(
        "Step 2: Expenses",
        f"<p>Month {month_id} ({month['currency']}). Add one Expense at a time.</p>"
        "<form method='post' action='/wizard/expenses'>"
        f"<input type='hidden' name='month_id' value='{month_id}'>"
        "<label>Name <input name='name'></label>"
        f"<label>Category <select name='category'>{options}</select></label>"
        "<label>Amount (minor units) <input name='amount_cents'></label>"
        "<label><input type='checkbox' name='fixed'> Fixed expense</label>"
        "<label><input type='checkbox' name='one_off'> One-off expense</label>"
        "<label><input type='checkbox' name='debt'> Debt payment minimum</label>"
        "<button type='submit'>Add expense</button></form>"
        f"<table><tr><th>Name</th><th>Category</th><th>Amount</th></tr>{rows}</table>"
        f"<p><a href='/wizard/plan?month_id={month_id}'>Continue to Plan</a></p>",
    )


@app.post("/wizard/expenses")
def expenses_submit(
    month_id: int = Form(...),
    name: str = Form(...),
    category: str = Form(...),
    amount_cents: str = Form(...),
    fixed: str | None = Form(None),
    one_off: str | None = Form(None),
    debt: str | None = Form(None),
) -> RedirectResponse:
    if not name.strip():
        raise HTTPException(status_code=422, detail="expense name is required")
    if category not in EXPENSE_CATEGORIES:
        raise HTTPException(status_code=422, detail="unknown category")
    conn = store.connect()
    try:
        store.add_expense(
            conn,
            month_id=month_id,
            name=name.strip(),
            category=category,
            amount_cents=_parse_cents(amount_cents, "amount"),
            fixed=fixed is not None,
            one_off=one_off is not None,
            debt=debt is not None,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown month")
    finally:
        conn.close()
    return RedirectResponse(
        f"/wizard/expenses?month_id={month_id}", status_code=303
    )


def _month_plan(
    month: dict,
    savings_pct: int = 20,
    needs_cap_pct: int = 50,
    wants_cap_pct: int = 30,
) -> PlanResult:
    """Assemble engine inputs for one stored month (single assembly point)."""
    return compute_plan(
        income_cents=month["income_cents"],
        side_cents=month["side_cents"],
        rollover_cents=month["rollover_cents"],
        savings_pct=savings_pct,
        needs_cap_pct=needs_cap_pct,
        wants_cap_pct=wants_cap_pct,
        emergency_cents=month["emergency_saved_cents"],
        expenses=[
            ExpenseInput(
                name=e["name"],
                category=e["category"],
                amount_cents=e["amount_cents"],
                fixed=bool(e["fixed"]),
                one_off=bool(e["one_off"]),
                debt=bool(e["debt"]),
            )
            for e in month["expenses"]
        ],
    )


@app.get("/wizard/plan", response_class=HTMLResponse)
def plan_view(
    month_id: int, savings_pct: int = 20, needs_cap_pct: int = 50,
    wants_cap_pct: int = 30,
) -> str:
    conn = store.connect()
    try:
        month = store.get_month(conn, month_id)
    finally:
        conn.close()
    if month is None:
        raise HTTPException(status_code=404, detail="unknown month")
    try:
        plan = _month_plan(
            month,
            savings_pct=savings_pct,
            needs_cap_pct=needs_cap_pct,
            wants_cap_pct=wants_cap_pct,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    warn_html = "".join(f"<li>{w.message}</li>" for w in plan.warnings)
    sugg_html = "".join(f"<li>{s}</li>" for s in plan.suggestions)
    debt_total = sum(e["amount_cents"] for e in month["expenses"] if e["debt"])
    goal = month["savings_goal_cents"]
    goal_html = (
        f"<tr><td>Savings Goal</td><td>{goal}</td></tr>"
        f"<tr><td>Goal progress (leftover vs goal)</td>"
        f"<td>{plan.leftover_cents} / {goal}</td></tr>"
        if goal > 0
        else ""
    )
    essentials = plan.needs_total_cents
    emergency_months = (
        f"{month['emergency_saved_cents'] / essentials:.1f}"
        if essentials > 0
        else "n/a"
    )
    next_rollover = max(plan.leftover_cents, 0)
    conn2 = store.connect()
    try:
        logged = store.latest_advice(conn2, month_id)
    finally:
        conn2.close()
    if logged is None:
        advice_html = "<p>No advice generated yet.</p>"
    else:
        items = "".join(f"<li>{line}</li>" for line in logged["output"].splitlines() if line.strip())
        advice_html = (
            f"<ol>{items}</ol><p><small>Backend {logged['backend']} · "
            f"prompt {logged['prompt_version']} · model {logged['model_version']}</small></p>"
            f"<p><small>Data flow: {logged.get('data_flow') or 'not recorded'}</small></p>"
        )
    return _page(
        "Step 3: Plan",
        f"<p>Month {month_id} ({month['currency']})</p>"
        "<table><tr><th>Line</th><th>Amount (minor units)</th></tr>"
        f"<tr><td>Available</td><td>{plan.available_cents}</td></tr>"
        f"<tr><td>Total expenses</td><td>{plan.total_expenses_cents}</td></tr>"
        f"<tr><td>Leftover to savings</td><td>{plan.leftover_cents}</td></tr>"
        f"<tr><td>Savings target (20%)</td><td>{plan.savings_target_cents}</td></tr>"
        f"<tr><td>Needs (fixed + debt)</td><td>{plan.needs_total_cents}</td></tr>"
        f"<tr><td>Wants (variable)</td><td>{plan.wants_total_cents}</td></tr>"
        f"<tr><td>Debt payments</td><td>{debt_total}</td></tr>"
        f"<tr><td>Emergency cover (months)</td><td>{emergency_months}</td></tr>"
        f"{goal_html}"
        "</table>"
        f"<h2>Warnings</h2><ul>{warn_html or '<li>None</li>'}</ul>"
        f"<h2>Suggestions</h2><ul>{sugg_html or '<li>None</li>'}</ul>"
        f"<h2>Adjust split</h2><form method='get' action='/wizard/plan'>"
        f"<input type='hidden' name='month_id' value='{month_id}'>"
        f"<label>Savings % <input name='savings_pct' value='{savings_pct}'></label>"
        f"<label>Needs cap % <input name='needs_cap_pct' value='{needs_cap_pct}'></label>"
        f"<label>Wants cap % <input name='wants_cap_pct' value='{wants_cap_pct}'></label>"
        "<button type='submit'>Recompute</button></form>"
        f"<h2>Advice</h2>{advice_html}"
        f"<form method='post' action='/wizard/advice'>"
        f"<input type='hidden' name='month_id' value='{month_id}'>"
        f"<label>Backend <select name='backend'>"
        + "".join(
            f"<option value='{b}'{' selected' if b == default_backend() else ''}>{b}</option>"
            for b in KNOWN_BACKENDS
        )
        + "</select></label>"
        "<label><input type='checkbox' name='allow_cloud'>"
        " I consent to sending computed aggregates off-machine for this request</label>"
        "<button type='submit'>Generate advice</button></form>"
        f"<p><a href='/wizard/income?currency={month['currency']}"
        f"&rollover_cents={next_rollover}'>Start next month with rollover</a></p>"
        "<p><a href='/months'>Past months</a></p>",
    )


@app.post("/wizard/advice")
def advice_generate(
    month_id: int = Form(...),
    backend: str = Form("template-local"),
    allow_cloud: str | None = Form(None),
) -> RedirectResponse:
    conn = store.connect()
    try:
        month = store.get_month(conn, month_id)
        if month is None:
            raise HTTPException(status_code=404, detail="unknown month")
        plan = _month_plan(month)
        prompt = build_prompt(plan, month["currency"])
        try:
            lines, data_flow = llm_generate(
                backend,
                prompt,
                plan,
                month["currency"],
                allow_cloud=allow_cloud is not None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except PermissionError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except ConnectionError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        text = "\n".join(lines)
        violations = validate_output(text, plan)
        if violations:
            raise HTTPException(status_code=422, detail="; ".join(violations))
        store.save_advice(
            conn,
            month_id=month_id,
            backend=backend,
            prompt_version=PROMPT_VERSION,
            model_version=base_url()
            if backend != LOCAL_BACKEND
            else MODEL_VERSION_DEFAULT,
            prompt=prompt,
            data_flow=data_flow,
            output=text,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    finally:
        conn.close()
    return RedirectResponse(f"/wizard/plan?month_id={month_id}", status_code=303)


@app.get("/disclaimer", response_class=HTMLResponse)
def disclaimer() -> str:
    return _page(
        "Disclaimer",
        "<p>This planner provides educational information only. It is not"
        " financial, tax, or legal advice, and it creates no adviser-client"
        " relationship. It is not a registered investment adviser,"
        " broker-dealer, or fiduciary.</p>"
        "<p>Figures shown come from deterministic computation over the amounts"
        " you entered manually; nothing here is bank-verified. This planner"
        " suggests; it never moves money (non-discretionary): it cannot pay"
        " bills or transfer funds. Consult a qualified professional before"
        " acting.</p>",
    )


@app.get("/months", response_class=HTMLResponse)
def months_list() -> str:
    conn = store.connect()
    try:
        months = [store.get_month(conn, m["id"]) for m in store.list_months(conn)]
    finally:
        conn.close()
    rows = ""
    for m in months:
        plan = _month_plan(m)
        rows += (
            f"<tr><td><a href='/wizard/plan?month_id={m['id']}'>{m['id']}</a></td>"
            f"<td>{m['currency']}</td>"
            f"<td>{plan.available_cents}</td>"
            f"<td>{plan.total_expenses_cents}</td>"
            f"<td>{plan.leftover_cents}</td></tr>"
        )
    return _page(
        "Past months",
        "<table><tr><th>Month</th><th>Currency</th><th>Available</th>"
        "<th>Total</th><th>Leftover</th></tr>"
        f"{rows}</table>"
        "<p>Single currency per month; no conversion.</p>"
        "<p><a href='/wizard/income'>Start a new month</a></p>",
    )
