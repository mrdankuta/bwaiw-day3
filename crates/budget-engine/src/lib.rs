//! Canonical deterministic monthly budget engine (spec #15).
//!
//! Pure compute boundary: month inputs in integer minor units in, Plan
//! plus Warnings out. Owns every number: no I/O, no network access, no
//! floating point anywhere in the money path. This crate is the single
//! implementation of the budget math; the browser (WASM) and any other
//! host call it through the JSON-serializable types below.

use serde::{Deserialize, Serialize};

pub const ENGINE_VERSION: &str = "budget-engine-v1";

pub const EXPENSE_CATEGORIES: &[&str] = &[
    "Housing",
    "Food",
    "Transport",
    "Utilities",
    "Health",
    "Savings",
    "Other",
];

// Locked warning defaults: tunable configuration, labeled heuristics.
pub const RENT_WARN_PCT: i64 = 30;
pub const RENT_SEVERE_PCT: i64 = 50;
pub const HOUSING_CAP_PCT: i64 = 28;
pub const DEBT_CAP_PCT: i64 = 36;
pub const SAVINGS_FLOOR_PCT: i64 = 20;
pub const EMERGENCY_MONTHS: i64 = 3;

fn default_savings_pct() -> i64 {
    20
}
fn default_needs_cap_pct() -> i64 {
    50
}
fn default_wants_cap_pct() -> i64 {
    30
}

/// One Expense for the month (glossary terms).
#[derive(Debug, Clone, PartialEq, Deserialize, Serialize)]
pub struct ExpenseInput {
    pub name: String,
    pub category: String,
    pub amount_cents: i64,
    #[serde(default)]
    pub fixed: bool,
    #[serde(default)]
    pub one_off: bool,
    #[serde(default)]
    pub debt: bool,
}

/// Month inputs for the engine. All money in integer minor units;
/// percentages as integers; caps fully explicit at the boundary.
#[derive(Debug, Clone, PartialEq, Deserialize, Serialize)]
pub struct MonthInputs {
    pub income_cents: i64,
    #[serde(default)]
    pub side_cents: i64,
    #[serde(default)]
    pub rollover_cents: i64,
    #[serde(default)]
    pub expenses: Vec<ExpenseInput>,
    #[serde(default = "default_savings_pct")]
    pub savings_pct: i64,
    #[serde(default = "default_needs_cap_pct")]
    pub needs_cap_pct: i64,
    #[serde(default = "default_wants_cap_pct")]
    pub wants_cap_pct: i64,
    #[serde(default)]
    pub emergency_cents: Option<i64>,
}

/// A rule breach surfaced from the Plan (glossary: Warning).
#[derive(Debug, Clone, PartialEq, Deserialize, Serialize)]
pub struct Warning {
    pub rule_id: String,
    pub message: String,
}

/// Deterministic monthly Plan numbers (glossary: Plan).
#[derive(Debug, Clone, PartialEq, Deserialize, Serialize)]
pub struct PlanResult {
    pub available_cents: i64,
    pub total_expenses_cents: i64,
    pub leftover_cents: i64,
    pub savings_target_cents: i64,
    pub needs_total_cents: i64,
    pub wants_total_cents: i64,
    pub warnings: Vec<Warning>,
    pub suggestions: Vec<String>,
}

fn require_minor_units(label: &str, value: i64) -> Result<i64, String> {
    if value < 0 {
        return Err(format!("{label} must be >= 0"));
    }
    Ok(value)
}

/// Compute available, allocation, leftover, warnings, and suggestions.
///
/// Savings-first: the savings target is carved from available first,
/// Needs (Fixed Expenses plus Debt Payments) are capped next, Wants
/// (variable non-debt) take the remainder. Thresholds are tunable
/// configuration; every warning is labeled a heuristic.
pub fn compute_plan(inputs: &MonthInputs) -> Result<PlanResult, String> {
    let income = require_minor_units("income_cents", inputs.income_cents)?;
    let side = require_minor_units("side_cents", inputs.side_cents)?;
    let rollover = require_minor_units("rollover_cents", inputs.rollover_cents)?;
    for (label, pct) in [
        ("savings_pct", inputs.savings_pct),
        ("needs_cap_pct", inputs.needs_cap_pct),
        ("wants_cap_pct", inputs.wants_cap_pct),
    ] {
        if pct < 0 {
            return Err(format!("{label} must be an integer >= 0"));
        }
    }

    let mut total: i64 = 0;
    let mut needs: i64 = 0;
    let mut wants: i64 = 0;
    let mut rent: i64 = 0;
    let mut housing: i64 = 0;
    let mut debt_total: i64 = 0;
    for exp in &inputs.expenses {
        if exp.name.trim().is_empty() {
            return Err("expense name must be non-empty".to_string());
        }
        if !EXPENSE_CATEGORIES.contains(&exp.category.as_str()) {
            return Err(format!("unknown expense category: {:?}", exp.category));
        }
        require_minor_units(&format!("expense {:?}", exp.name), exp.amount_cents)?;
        total += exp.amount_cents;
        if exp.fixed || exp.debt {
            needs += exp.amount_cents;
        } else {
            wants += exp.amount_cents;
        }
        if exp.category == "Housing" {
            rent += exp.amount_cents;
            housing += exp.amount_cents;
        } else if exp.category == "Utilities" {
            housing += exp.amount_cents;
        }
        if exp.debt {
            debt_total += exp.amount_cents;
        }
    }

    let available = income + side + rollover;
    let leftover = available - total;
    // Operands are non-negative, so truncation matches the floor division
    // the money path requires.
    let savings_target = available * inputs.savings_pct / 100;

    let mut warnings: Vec<Warning> = Vec::new();
    if available > 0 {
        let rent_pct = rent * 100 / available;
        if rent_pct >= RENT_SEVERE_PCT {
            warnings.push(Warning {
                rule_id: "rent-severe".to_string(),
                message: format!(
                    "Heuristic: rent severe at {rent_pct}% of available (threshold {RENT_SEVERE_PCT}%)."
                ),
            });
        } else if rent_pct >= RENT_WARN_PCT {
            warnings.push(Warning {
                rule_id: "rent-burden".to_string(),
                message: format!(
                    "Heuristic: rent burden at {rent_pct}% of available (threshold {RENT_WARN_PCT}%)."
                ),
            });
        }
        if housing * 100 > HOUSING_CAP_PCT * available {
            warnings.push(Warning {
                rule_id: "housing-cap".to_string(),
                message: format!("Heuristic: housing over {HOUSING_CAP_PCT}% of available."),
            });
        }
        if debt_total * 100 > DEBT_CAP_PCT * available {
            warnings.push(Warning {
                rule_id: "debt-cap".to_string(),
                message: format!("Heuristic: all-debt over {DEBT_CAP_PCT}% of available."),
            });
        }
        if leftover * 100 < SAVINGS_FLOOR_PCT * available {
            warnings.push(Warning {
                rule_id: "savings-floor".to_string(),
                message: format!("Heuristic: savings under {SAVINGS_FLOOR_PCT}% of available."),
            });
        }
        if let Some(emergency) = inputs.emergency_cents {
            if needs > 0 && emergency < EMERGENCY_MONTHS * needs {
                warnings.push(Warning {
                    rule_id: "emergency-cover".to_string(),
                    message: format!(
                        "Heuristic: emergency cover under {EMERGENCY_MONTHS} months of essentials."
                    ),
                });
            }
        }
    }
    if leftover < 0 {
        warnings.push(Warning {
            rule_id: "shortfall".to_string(),
            message: format!("Heuristic: overspent by {} minor units.", -leftover),
        });
    }

    let mut suggestions: Vec<String> = Vec::new();
    if leftover < 0 {
        let cut = wants.min(-leftover);
        if cut > 0 {
            suggestions.push(format!(
                "Cut Wants by {cut} minor units first (variable non-debt)."
            ));
            if -leftover > wants {
                suggestions.push("Then review Needs: fixed and debt minimums.".to_string());
            }
        } else {
            suggestions.push("Review Needs: fixed and debt minimums.".to_string());
        }
    } else if leftover > 0 {
        suggestions.push(format!(
            "Assign leftover {leftover} minor units to Savings."
        ));
    }

    Ok(PlanResult {
        available_cents: available,
        total_expenses_cents: total,
        leftover_cents: leftover,
        savings_target_cents: savings_target,
        needs_total_cents: needs,
        wants_total_cents: wants,
        warnings,
        suggestions,
    })
}

/// JSON boundary convenience: month-inputs document in, Plan document out.
/// This is the exact seam the WASM binding exposes to the browser.
pub fn plan_from_json(inputs_json: &str) -> Result<String, String> {
    let inputs: MonthInputs =
        serde_json::from_str(inputs_json).map_err(|e| format!("invalid month inputs: {e}"))?;
    let plan = compute_plan(&inputs)?;
    serde_json::to_string(&plan).map_err(|e| format!("cannot encode plan: {e}"))
}
