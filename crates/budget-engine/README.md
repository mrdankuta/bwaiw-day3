# budget-engine

Canonical deterministic monthly budget engine (spec #15): month inputs
in integer minor units in, Plan plus Warnings out. Pure compute — no
I/O, no network access, no floating point in the money path.

- `cargo test` runs the shared conformance fixtures
  (`fixtures/engine.json`) against this core.
- `cargo run --example plan` reads a month-inputs JSON document on
  stdin and prints the Plan document — the exact seam the WASM
  binding exposes to the browser.
