"""Advice seam tests: explainer cites computed figures; validator gates."""

from app.advice import (
    PROMPT_VERSION,
    build_prompt,
    deterministic_explain,
    validate_output,
)
from app.engine import ExpenseInput, compute_plan


def _plan(**kw):
    args = dict(income_cents=100_00, expenses=[
        ExpenseInput(name="Rent", category="Housing", amount_cents=40_00, fixed=True),
    ])
    args.update(kw)
    return compute_plan(**args)


def test_explainer_cites_figures_three_to_five():
    plan = _plan()
    lines = deterministic_explain(plan, "NGN")
    assert 3 <= len(lines) <= 5
    assert not validate_output("\n".join(lines), plan)


def test_prompt_pins_rules_and_version():
    assert PROMPT_VERSION in ("advice-v1", PROMPT_VERSION)
    text = build_prompt(_plan(), "NGN")
    assert "Educational only" in text
    assert "4000" in text  # computed rent figure present


def test_validator_blocks_uncomputed_figure():
    plan = _plan()
    assert any(
        "uncomputed" in v
        for v in validate_output("You will have 99999 left.", plan)
    )


def test_validator_blocks_blocklisted_claims():
    plan = _plan()
    assert validate_output("This is guaranteed returns.", plan)
    assert validate_output("We are your fiduciary.", plan)
