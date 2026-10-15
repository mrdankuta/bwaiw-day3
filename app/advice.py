"""Advice explainer plus validator (ticket: LLM advice and guardrails).

Math-first posture: the engine owns every number. The explainer only
verbalizes the computed Plan plus Warnings JSON. The default backend is
a deterministic template stand-in for the local model; an Ollama-style
HTTP backend can be selected by configuration (wired in privacy ticket).
The validator runs before render, whatever the backend.
"""

from __future__ import annotations

import re

from .engine import PlanResult

PROMPT_VERSION = "advice-v1"
MODEL_VERSION_DEFAULT = "template-local-v1"

BLOCKLIST = (
    "guarantee",
    "fiduciary",
    "registered investment",
    "registered adviser",
    "sec-approved",
    "risk-free",
    "will earn",
    "guaranteed returns",
)

DISCLAIMER_SHORT = (
    "Educational information only, not financial advice. "
    "This planner suggests; it never moves money (non-discretionary)."
)


def build_prompt(plan: PlanResult, currency: str) -> str:
    lines = [
        "You are a budgeting explainer, not an adviser. Educational only.",
        "Rules: use ONLY the computed figures below; never recompute or invent",
        "numbers; cite each figure; give 3-5 suggestions tied to the gaps;",
        "refuse guaranteed returns, specific securities, tax or legal verdicts,",
        "and fiduciary claims. Low temperature. Output plain suggestions.",
        f"Computed: available={plan.available_cents} total={plan.total_expenses_cents}",
        f"leftover={plan.leftover_cents} savings_target={plan.savings_target_cents}",
        f"needs={plan.needs_total_cents} wants={plan.wants_total_cents}",
        f"currency={currency}",
    ]
    for warning in plan.warnings:
        lines.append(f"warning {warning.rule_id}: {warning.message}")
    return "\n".join(lines)


def deterministic_explain(plan: PlanResult, currency: str) -> list[str]:
    """Template stand-in for the local model: cites computed figures only."""
    out = [
        f"Available {plan.available_cents} against expenses"
        f" {plan.total_expenses_cents} leaves {plan.leftover_cents} ({currency}).",
        f"Protect the savings carve-out of {plan.savings_target_cents} before Wants"
        f" (Needs {plan.needs_total_cents}, Wants {plan.wants_total_cents}).",
    ]
    for warning in plan.warnings:
        out.append(f"Act on warning {warning.rule_id}: {warning.message}")
        if len(out) >= 5:
            break
    for suggestion in plan.suggestions:
        if len(out) >= 5:
            break
        if suggestion not in out:
            out.append(suggestion)
    while len(out) < 3:
        out.append("No further gaps detected; hold the current allocation.")
    return out[:5]


def validate_output(text: str, plan: PlanResult) -> list[str]:
    """Return a list of violations; empty means the output may render."""
    violations: list[str] = []
    known = {
        plan.available_cents,
        plan.total_expenses_cents,
        plan.leftover_cents,
        plan.savings_target_cents,
        plan.needs_total_cents,
        plan.wants_total_cents,
    }
    for match in re.finditer(r"(-?\d[\d,]*)(%| months?)?", text):
        raw, suffix = match.groups()
        if suffix:
            continue  # thresholds cite labeled rules, not money figures
        if int(raw.replace(",", "")) not in known:
            violations.append(f"uncomputed figure cited: {raw}")
    lowered = text.lower()
    for banned in BLOCKLIST:
        if banned in lowered:
            violations.append(f"blocklisted phrase: {banned}")
    return violations
