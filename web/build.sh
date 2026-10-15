#!/usr/bin/env bash
# Build the shippable app: both WASM targets for the canonical engine.
# Needs: cargo with the wasm32-unknown-unknown target, wasm-pack, node.
set -euo pipefail
cd "$(dirname "$0")/.."
wasm-pack build crates/budget-wasm --target nodejs --out-dir ../../web/engine/pkg
wasm-pack build crates/budget-wasm --target web --out-dir ../../web/engine/pkg-web
node web/engine/check-vectors.mjs
node --test web/store/test-store.mjs web/app/test-advice.mjs
cargo test --workspace
echo "build ok: open /web/index.html from any static server"
