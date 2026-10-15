//! WASM binding for the canonical budget engine (spec #15, ticket #19).
//!
//! The single browser seam: a month-inputs JSON document in, a Plan
//! plus Warnings JSON document out. All math lives in `budget-engine`;
//! this crate is only the boundary. The module performs pure
//! computation and declares no network capability.

use wasm_bindgen::prelude::*;

/// Compute the monthly Plan for one month-inputs JSON document.
///
/// Returns the Plan document on success, or a JS error carrying the
/// same failure the core reports (invalid inputs, never partial math).
#[wasm_bindgen]
pub fn plan_month(inputs_json: &str) -> Result<String, JsValue> {
    budget_engine::plan_from_json(inputs_json).map_err(|e| JsValue::from_str(&e))
}

/// The canonical engine version behind this binding, for attributing
/// on-device computations alongside prompt and model versions.
#[wasm_bindgen]
pub fn engine_version() -> String {
    budget_engine::ENGINE_VERSION.to_string()
}

#[cfg(test)]
mod tests {
    // Host-side wiring check: the exact seam function the binding wraps
    // runs every shared fixture. (The #[wasm_bindgen] wrapper itself
    // only executes on wasm32; the real-boundary proof (JS -> WASM -> JS)
    // is web/engine/check-vectors.mjs against a wasm-pack build.)
    use super::*;

    fn vectors() -> serde_json::Value {
        let path = concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../fixtures/engine.json"
        );
        let text = std::fs::read_to_string(path).expect("read fixtures/engine.json");
        serde_json::from_str(&text).expect("parse fixtures/engine.json")
    }

    #[test]
    fn seam_runs_every_fixture() {
        let doc = vectors();
        let cases = doc["cases"].as_array().expect("cases array");
        assert!(!cases.is_empty());
        for case in cases {
            let id = case["id"].as_str().unwrap_or("?");
            let inputs = serde_json::to_string(&case["inputs"]).expect("encode inputs");
            let plan_json = budget_engine::plan_from_json(&inputs)
                .unwrap_or_else(|e| panic!("fixture {id} failed: {e}"));
            let plan: serde_json::Value =
                serde_json::from_str(&plan_json).expect("decode plan");
            let expected = &case["expected"];
            for key in [
                "available_cents",
                "total_expenses_cents",
                "leftover_cents",
                "savings_target_cents",
                "needs_total_cents",
                "wants_total_cents",
            ] {
                assert_eq!(plan[key], expected[key], "{id} {key}");
            }
            let rule_ids: Vec<&str> = plan["warnings"]
                .as_array()
                .expect("warnings array")
                .iter()
                .map(|w| w["rule_id"].as_str().expect("rule id"))
                .collect();
            let expected_ids: Vec<&str> = expected["warning_rule_ids"]
                .as_array()
                .expect("expected rule ids")
                .iter()
                .map(|v| v.as_str().expect("rule id"))
                .collect();
            assert_eq!(rule_ids, expected_ids, "{id} warnings");
        }
        for case in doc["error_cases"].as_array().expect("error_cases array") {
            let id = case["id"].as_str().unwrap_or("?");
            let inputs = serde_json::to_string(&case["inputs"]).expect("encode inputs");
            let ok = budget_engine::plan_from_json(&inputs).is_err();
            assert!(ok, "{id} unexpectedly succeeded");
        }
    }
}
