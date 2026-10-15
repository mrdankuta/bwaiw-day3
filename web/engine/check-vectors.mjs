// Boundary proof: feeds every shared fixture through the real compiled
// WASM binding (JS -> WASM -> JS) and diffs the Plan numbers plus ordered
// warning rule ids. Run after building:
//   wasm-pack build crates/budget-wasm --target nodejs --out-dir ../../web/engine/pkg
//   node web/engine/check-vectors.mjs [pkg-dir]
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const ROOT = path.resolve(import.meta.dirname, '..', '..');
const pkgDir = process.argv[2] ?? path.join(ROOT, 'web', 'engine', 'pkg');
const require = createRequire(import.meta.url);
const { plan_month, engine_version } = require(path.join(pkgDir, 'budget_wasm.js'));

const doc = JSON.parse(fs.readFileSync(path.join(ROOT, 'fixtures', 'engine.json'), 'utf8'));

const NUM_KEYS = [
  'available_cents',
  'total_expenses_cents',
  'leftover_cents',
  'savings_target_cents',
  'needs_total_cents',
  'wants_total_cents',
];

let failures = 0;
console.log(`engine: ${engine_version()}`);

for (const c of doc.cases) {
  const plan = JSON.parse(plan_month(JSON.stringify(c.inputs)));
  const problems = [];
  for (const k of NUM_KEYS) {
    if (plan[k] !== c.expected[k]) problems.push(`${k}: got ${plan[k]}, want ${c.expected[k]}`);
  }
  const got = plan.warnings.map((w) => w.rule_id);
  if (JSON.stringify(got) !== JSON.stringify(c.expected.warning_rule_ids)) {
    problems.push(`warnings: got [${got}], want [${c.expected.warning_rule_ids}]`);
  }
  if (JSON.stringify(plan.suggestions) !== JSON.stringify(c.expected.suggestions)) {
    problems.push('suggestions differ');
  }
  if (problems.length) {
    failures += 1;
    console.error(`FAIL ${c.id}: ${problems.join('; ')}`);
  }
}
for (const c of doc.error_cases) {
  let threw = false;
  try {
    plan_month(JSON.stringify(c.inputs));
  } catch {
    threw = true;
  }
  if (!threw) {
    failures += 1;
    console.error(`FAIL ${c.id}: expected an error, succeeded`);
  }
}

if (failures) {
  console.error(`${failures} fixture(s) failed through the WASM binding`);
  process.exit(1);
}
console.log(
  `${doc.cases.length} cases + ${doc.error_cases.length} error cases pass through the WASM binding`,
);
