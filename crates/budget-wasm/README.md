# budget-wasm

WASM binding for the canonical budget engine (ticket #19). One browser
seam: month-inputs JSON in (`plan_month`), Plan plus Warnings JSON out,
plus `engine_version` for attribution. Pure computation; the module
declares no network capability.

## Verify

- Host wiring: `cargo test -p budget-wasm` (every shared fixture
  through the exact seam function the binding wraps).
- Real boundary (JS -> WASM -> JS):
  `wasm-pack build crates/budget-wasm --target nodejs --out-dir web/engine/pkg`
  then `node web/engine/check-vectors.mjs` (all fixtures diffed).
- The `pkg/` build output is generated and git-ignored; CI rebuilds it.
