//! Conformance suite: every shared fixture in `fixtures/engine.json`
//! runs against the Rust core. Numbers and ordered warning rule ids
//! must match exactly; suggestion strings match exactly here (the
//! Python suite pins the same strings; ports document any wording
//! variance in fixtures/README.md).

use budget_engine::{compute_plan, ExpenseInput, MonthInputs};
use serde_json::Value;

fn vectors() -> Value {
    let path = concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../fixtures/engine.json"
    );
    let text = std::fs::read_to_string(path).expect("read fixtures/engine.json");
    serde_json::from_str(&text).expect("parse fixtures/engine.json")
}

fn month_inputs(v: &Value) -> MonthInputs {
    let get_i64 = |key: &str| {
        v.get(key)
            .and_then(Value::as_i64)
            .unwrap_or_else(|| panic!("fixture inputs.{key} must be an integer"))
    };
    MonthInputs {
        income_cents: get_i64("income_cents"),
        side_cents: get_i64("side_cents"),
        rollover_cents: get_i64("rollover_cents"),
        expenses: v
            .get("expenses")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default()
            .iter()
            .map(|e| ExpenseInput {
                name: e.get("name").and_then(Value::as_str).unwrap_or("").to_string(),
                category: e
                    .get("category")
                    .and_then(Value::as_str)
                    .unwrap_or("")
                    .to_string(),
                amount_cents: e
                    .get("amount_cents")
                    .and_then(Value::as_i64)
                    .expect("expense amount_cents must be an integer"),
                fixed: e.get("fixed").and_then(Value::as_bool).unwrap_or(false),
                one_off: e.get("one_off").and_then(Value::as_bool).unwrap_or(false),
                debt: e.get("debt").and_then(Value::as_bool).unwrap_or(false),
            })
            .collect(),
        savings_pct: get_i64("savings_pct"),
        needs_cap_pct: get_i64("needs_cap_pct"),
        wants_cap_pct: get_i64("wants_cap_pct"),
        emergency_cents: v.get("emergency_cents").and_then(Value::as_i64),
    }
}

#[test]
fn success_vectors() {
    let doc = vectors();
    let cases = doc.get("cases").and_then(Value::as_array).expect("cases array");
    assert!(!cases.is_empty(), "no fixture cases found");
    for case in cases {
        let id = case.get("id").and_then(Value::as_str).unwrap_or("?");
        let plan = compute_plan(&month_inputs(&case["inputs"]))
            .unwrap_or_else(|e| panic!("fixture {id} unexpectedly failed: {e}"));
        let expected = &case["expected"];
        let num = |key: &str| {
            expected
                .get(key)
                .and_then(Value::as_i64)
                .unwrap_or_else(|| panic!("fixture {id} expected.{key} must be an integer"))
        };
        assert_eq!(plan.available_cents, num("available_cents"), "{id} available");
        assert_eq!(plan.total_expenses_cents, num("total_expenses_cents"), "{id} total");
        assert_eq!(plan.leftover_cents, num("leftover_cents"), "{id} leftover");
        assert_eq!(plan.savings_target_cents, num("savings_target_cents"), "{id} target");
        assert_eq!(plan.needs_total_cents, num("needs_total_cents"), "{id} needs");
        assert_eq!(plan.wants_total_cents, num("wants_total_cents"), "{id} wants");
        let rule_ids: Vec<&str> = plan.warnings.iter().map(|w| w.rule_id.as_str()).collect();
        let expected_ids: Vec<&str> = expected
            .get("warning_rule_ids")
            .and_then(Value::as_array)
            .expect("warning_rule_ids array")
            .iter()
            .map(|v| v.as_str().expect("rule id string"))
            .collect();
        assert_eq!(rule_ids, expected_ids, "{id} warnings");
        let suggestions: Vec<&str> = plan.suggestions.iter().map(String::as_str).collect();
        let expected_suggestions: Vec<&str> = expected
            .get("suggestions")
            .and_then(Value::as_array)
            .expect("suggestions array")
            .iter()
            .map(|v| v.as_str().expect("suggestion string"))
            .collect();
        assert_eq!(suggestions, expected_suggestions, "{id} suggestions");
    }
}

#[test]
fn error_vectors() {
    let doc = vectors();
    let cases = doc
        .get("error_cases")
        .and_then(Value::as_array)
        .expect("error_cases array");
    assert!(!cases.is_empty(), "no fixture error cases found");
    for case in cases {
        let id = case.get("id").and_then(Value::as_str).unwrap_or("?");
        let err = compute_plan(&month_inputs(&case["inputs"]))
            .err()
            .unwrap_or_else(|| panic!("fixture {id} unexpectedly succeeded"));
        let needle = case
            .get("error_match")
            .and_then(Value::as_str)
            .expect("error_match string");
        assert!(
            err.contains(needle),
            "{id} error {err:?} does not contain {needle:?}"
        );
    }
}
