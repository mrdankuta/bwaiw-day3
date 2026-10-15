# On-device app (spec #15)

Static pages, on-device compute (WASM) and storage (browser SQLite).
No server, no build step for the pages themselves.

## Layout

- `index.html`, `income.html`, `expenses.html` (+ `plan.html`,
  `months.html`, `disclaimer.html` in later tickets)
- `app/` — `app.css` (ClickHouse design system, extracted verbatim
  from the monthly-planner UX prototype), `chrome.js` (shared
  topnav/guardrail/stepper/footer), `engine.js` (WASM init, the single
  engine seam, whole-units to minor-units at the boundary, Naira
  formatting like the prototype)
- `engine/` — `check-vectors.mjs` plus the compiled bindings:
  `pkg/` (Node.js target, for the automated check, git-ignored),
  `pkg-web/` (browser target, loaded by `engine.js`, git-ignored)
- `store/` — the on-device month store (see its README)
- `vendor/` — vendored `wa-sqlite` runtime (offline-first)

## Build and verify

- `wasm-pack build crates/budget-wasm --target nodejs --out-dir web/engine/pkg`
  then `node web/engine/check-vectors.mjs`
- `wasm-pack build crates/budget-wasm --target web --out-dir web/engine/pkg-web`
  then serve the repo root (`npx serve .`) and open
  `/web/index.html`. Amounts are entered in whole currency units and
  stored x100 as integer minor units; the engine only ever sees integers.
- Only external requests are Google Fonts (progressive enhancement);
  everything that computes or stores is same-origin and cached, so the
  app plans fully offline once loaded.
