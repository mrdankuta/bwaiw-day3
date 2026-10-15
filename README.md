# Monthly Planner

Live at https://monthly-planner-4sn.pages.dev/ (Cloudflare Pages).

Plan the month before it spends you. A single-user monthly budget
planner that runs entirely on your device: deterministic budget math
in WebAssembly, months in on-device SQLite, advice from a validated
local template. No server, no account, nothing leaves your machine.

## Quick start

Build the shippable app with one command, then serve the repo root
with any static server and open `/web/index.html`:

```sh
./web/build.sh
npx serve .          # then open /web/index.html
```

## Verify

```sh
cargo test --workspace                       # Rust core + binding wiring
node --test web/store/test-store.mjs         # on-device store logic + schema
node --test web/app/test-advice.mjs          # template explainer + validator
node web/engine/check-vectors.mjs            # every fixture through real WASM
```

## How it works

Three steps, guided: **Income** (recurring income, inflows, savings
rollover, goal, emergency fund) → **Expenses** (categorized, with
fixed / one-off / debt-payment flags) → **Plan & Advice** (available
minus expenses equals leftover, locked-rule warnings, validated
suggestions, next-month rollover).

- `crates/budget-engine/` — canonical deterministic engine (Rust)
- `crates/budget-wasm/` — browser binding (month JSON in, Plan JSON out)
- `fixtures/engine.json` — shared conformance vectors every port runs
- `web/` — static app (ClickHouse design system), on-device store,
  vendored SQLite runtime; see `web/README.md`
- `scripts/export-months.mjs` — one-shot import from the retired
  server database (see `web/months.html`)

Money is integer minor units throughout; amounts enter as whole
currency units and are stored x100. One currency per month, no
conversion. Educational information only — the planner suggests, it
never moves money.
