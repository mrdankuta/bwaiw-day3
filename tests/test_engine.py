"""Engine seam tests: external behavior only (inputs in, Plan JSON out)."""

import pytest

from app.engine import ExpenseInput, compute_plan


def _exp(name="Rent", category="Housing", amount=100_00, **kw):
    return ExpenseInput(name=name, category=category, amount_cents=amount, **kw)


def test_available_total_leftover():
    plan = compute_plan(
        income_cents=250_00,
        side_cents=50_00,
        rollover_cents=20_00,
        expenses=[_exp(amount=100_00), _exp("Feeding", "Food", 60_00)],
    )
    assert plan.available_cents == 320_00
    assert plan.total_expenses_cents == 160_00
    assert plan.leftover_cents == 160_00


def test_empty_month_leaves_everything():
    plan = compute_plan(income_cents=100_00)
    assert (plan.available_cents, plan.total_expenses_cents, plan.leftover_cents) == (
        100_00,
        0,
        100_00,
    )


def test_one_off_counts_in_month_but_is_flagged():
    plan = compute_plan(
        income_cents=300_00,
        expenses=[_exp("Repair", "Other", 30_00, one_off=True)],
    )
    assert plan.total_expenses_cents == 30_00
    assert plan.leftover_cents == 270_00


def test_shortfall_goes_negative():
    plan = compute_plan(income_cents=100_00, expenses=[_exp(amount=150_00)])
    assert plan.leftover_cents == -50_00


@pytest.mark.parametrize("field", ["income_cents", "side_cents", "rollover_cents"])
def test_negative_inputs_rejected(field):
    with pytest.raises(ValueError):
        compute_plan(**{"income_cents": 0, field: -1})


def test_unknown_category_rejected():
    with pytest.raises(ValueError, match="unknown expense category"):
        compute_plan(income_cents=10, expenses=[_exp(category="Yachts")])


def test_floats_rejected_not_rounded():
    with pytest.raises(ValueError, match="minor units"):
        compute_plan(income_cents=10.5)  # type: ignore[arg-type]


def test_savings_target_carved_first_and_adjustable():
    base = dict(income_cents=100_00, expenses=[])
    assert compute_plan(**base).savings_target_cents == 20_00
    assert compute_plan(**base, savings_pct=30).savings_target_cents == 30_00


def test_needs_wants_split():
    plan = compute_plan(
        income_cents=100_00,
        expenses=[
            _exp("Rent", "Housing", 40_00, fixed=True),
            _exp("Loan", "Other", 10_00, fixed=True, debt=True),
            _exp("Eating out", "Food", 20_00),
        ],
    )
    assert plan.needs_total_cents == 50_00
    assert plan.wants_total_cents == 20_00


def test_rent_boundaries():
    assert "rent-burden" in [
        w.rule_id
        for w in compute_plan(
            income_cents=100_00, expenses=[_exp("Rent", "Housing", 30_00, fixed=True)]
        ).warnings
    ]
    assert "rent-severe" in [
        w.rule_id
        for w in compute_plan(
            income_cents=100_00, expenses=[_exp("Rent", "Housing", 50_00, fixed=True)]
        ).warnings
    ]


def test_housing_debt_savings_emergency_boundaries():
    over_housing = compute_plan(
        income_cents=100_00,
        expenses=[_exp("Rent", "Housing", 20_00, fixed=True),
                  _exp("Power", "Utilities", 9_00, fixed=True)],
    )
    assert "housing-cap" in [w.rule_id for w in over_housing.warnings]
    over_debt = compute_plan(
        income_cents=100_00,
        expenses=[_exp("Loan", "Other", 37_00, fixed=True, debt=True)],
    )
    assert "debt-cap" in [w.rule_id for w in over_debt.warnings]
    thin = compute_plan(
        income_cents=100_00, expenses=[_exp("Rent", "Housing", 85_00, fixed=True)]
    )
    assert "savings-floor" in [w.rule_id for w in thin.warnings]
    low_cover = compute_plan(
        income_cents=100_00,
        expenses=[_exp("Rent", "Housing", 40_00, fixed=True)],
        emergency_cents=50_00,
    )
    assert "emergency-cover" in [w.rule_id for w in low_cover.warnings]
    ok_cover = compute_plan(
        income_cents=100_00,
        expenses=[_exp("Rent", "Housing", 40_00, fixed=True)],
        emergency_cents=120_00,
    )
    assert "emergency-cover" not in [w.rule_id for w in ok_cover.warnings]


def test_shortfall_suggests_wants_first_and_surplus_to_savings():
    over = compute_plan(
        income_cents=100_00,
        expenses=[_exp("Rent", "Housing", 60_00, fixed=True),
                  _exp("Fun", "Food", 60_00)],
    )
    assert "shortfall" in [w.rule_id for w in over.warnings]
    assert any("Wants" in s for s in over.suggestions)
    under = compute_plan(income_cents=100_00, expenses=[_exp("Rent", "Housing", 40_00, fixed=True)])
    assert any("Savings" in s for s in under.suggestions)
