"""Deterministic budget engine (ticket: Monthly foundation).

Pure compute boundary: month inputs in integer minor units in,
Plan numbers out. Owns every number; no LLM, no I/O, no rounding.
Warning rules and allocation percentages belong to a later ticket.
"""

from dataclasses import dataclass

EXPENSE_CATEGORIES = (
    "Housing",
    "Food",
    "Transport",
    "Utilities",
    "Health",
    "Savings",
    "Other",
)


@dataclass(frozen=True)
class ExpenseInput:
    """One Expense for the month (glossary terms)."""

    name: str
    category: str
    amount_cents: int
    fixed: bool = False
    one_off: bool = False
    debt: bool = False


@dataclass(frozen=True)
class Warning:
    """A rule breach surfaced from the Plan (glossary: Warning)."""

    rule_id: str
    message: str


@dataclass(frozen=True)
class PlanResult:
    """Deterministic monthly Plan numbers (glossary: Plan)."""

    available_cents: int
    total_expenses_cents: int
    leftover_cents: int
    savings_target_cents: int = 0
    needs_total_cents: int = 0
    wants_total_cents: int = 0
    warnings: tuple[Warning, ...] = ()
    suggestions: tuple[str, ...] = ()


# Locked warning defaults (tunable configuration, labeled heuristics).
RENT_WARN_PCT = 30
RENT_SEVERE_PCT = 50
HOUSING_CAP_PCT = 28
DEBT_CAP_PCT = 36
SAVINGS_FLOOR_PCT = 20
EMERGENCY_MONTHS = 3


def _require_minor_units(label: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer number of minor units")
    if value < 0:
        raise ValueError(f"{label} must be >= 0")
    return value


def compute_plan(
    *,
    income_cents: int,
    side_cents: int = 0,
    rollover_cents: int = 0,
    expenses: tuple[ExpenseInput, ...] | list[ExpenseInput] = (),
    savings_pct: int = 20,
    needs_cap_pct: int = 50,
    wants_cap_pct: int = 30,
    rent_warn_pct: int = RENT_WARN_PCT,
    rent_severe_pct: int = RENT_SEVERE_PCT,
    housing_cap_pct: int = HOUSING_CAP_PCT,
    debt_cap_pct: int = DEBT_CAP_PCT,
    savings_floor_pct: int = SAVINGS_FLOOR_PCT,
    emergency_months: int = EMERGENCY_MONTHS,
    emergency_cents: int | None = None,
) -> PlanResult:
    """Compute available, allocation, leftover, warnings, and suggestions.

    Savings-first: the savings target is carved from available first,
    Needs (Fixed Expenses plus Debt Payments) are capped next, Wants
    (variable non-debt) take the remainder. Thresholds are tunable
    configuration; every warning is labeled a heuristic.
    """
    income_cents = _require_minor_units("income_cents", income_cents)
    side_cents = _require_minor_units("side_cents", side_cents)
    rollover_cents = _require_minor_units("rollover_cents", rollover_cents)
    for label, pct in (
        ("savings_pct", savings_pct),
        ("needs_cap_pct", needs_cap_pct),
        ("wants_cap_pct", wants_cap_pct),
    ):
        if isinstance(pct, bool) or not isinstance(pct, int) or pct < 0:
            raise ValueError(f"{label} must be an integer >= 0")

    total = 0
    needs = 0
    wants = 0
    rent = 0
    housing = 0
    debt_total = 0
    for exp in expenses:
        if not exp.name or not exp.name.strip():
            raise ValueError("expense name must be non-empty")
        if exp.category not in EXPENSE_CATEGORIES:
            raise ValueError(f"unknown expense category: {exp.category!r}")
        _require_minor_units(f"expense {exp.name!r}", exp.amount_cents)
        total += exp.amount_cents
        if exp.fixed or exp.debt:
            needs += exp.amount_cents
        else:
            wants += exp.amount_cents
        if exp.category == "Housing":
            rent += exp.amount_cents
            housing += exp.amount_cents
        elif exp.category == "Utilities":
            housing += exp.amount_cents
        if exp.debt:
            debt_total += exp.amount_cents

    available = income_cents + side_cents + rollover_cents
    leftover = available - total
    savings_target = available * savings_pct // 100

    warnings: list[Warning] = []
    if available > 0:
        if rent * 100 >= rent_severe_pct * available:
            warnings.append(
                Warning(
                    "rent-severe",
                    f"Heuristic: rent severe at {rent * 100 // available}%"
                    f" of available (threshold {rent_severe_pct}%).",
                )
            )
        elif rent * 100 >= rent_warn_pct * available:
            warnings.append(
                Warning(
                    "rent-burden",
                    f"Heuristic: rent burden at {rent * 100 // available}%"
                    f" of available (threshold {rent_warn_pct}%).",
                )
            )
        if housing * 100 > housing_cap_pct * available:
            warnings.append(
                Warning(
                    "housing-cap",
                    "Heuristic: housing over "
                    f"{housing_cap_pct}% of available.",
                )
            )
        if debt_total * 100 > debt_cap_pct * available:
            warnings.append(
                Warning(
                    "debt-cap",
                    f"Heuristic: all-debt over {debt_cap_pct}% of available.",
                )
            )
        if leftover * 100 < savings_floor_pct * available:
            warnings.append(
                Warning(
                    "savings-floor",
                    f"Heuristic: savings under {savings_floor_pct}% of available.",
                )
            )
        if emergency_cents is not None and needs > 0:
            if emergency_cents * 1 < emergency_months * needs:
                warnings.append(
                    Warning(
                        "emergency-cover",
                        f"Heuristic: emergency cover under {emergency_months}"
                        " months of essentials.",
                    )
                )
    if leftover < 0:
        warnings.append(
            Warning(
                "shortfall",
                f"Heuristic: overspent by {-leftover} minor units.",
            )
        )

    suggestions: list[str] = []
    if leftover < 0:
        cut = min(wants, -leftover)
        if cut > 0:
            suggestions.append(
                f"Cut Wants by {cut} minor units first (variable non-debt)."
            )
            if -leftover > wants:
                suggestions.append("Then review Needs: fixed and debt minimums.")
        else:
            suggestions.append("Review Needs: fixed and debt minimums.")
    elif leftover > 0:
        suggestions.append(
            f"Assign leftover {leftover} minor units to Savings."
        )

    return PlanResult(
        available_cents=available,
        total_expenses_cents=total,
        leftover_cents=leftover,
        savings_target_cents=savings_target,
        needs_total_cents=needs,
        wants_total_cents=wants,
        warnings=tuple(warnings),
        suggestions=tuple(suggestions),
    )
