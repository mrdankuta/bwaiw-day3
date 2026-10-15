// One-shot server-to-device migration (ticket #23). Reads the retired
// server's SQLite file directly and writes versioned export documents
// (the engine's own month-inputs shape plus the advice log) that
// months.html imports into the on-device store. Pure Node, no Python.
//
// Usage: node scripts/export-months.mjs [server-db-path] [out-dir]
// Defaults: data/app.db -> ./migration-exports/
import fs from 'node:fs';
import path from 'node:path';
import { DatabaseSync } from 'node:sqlite';

const dbPath = process.argv[2] ?? path.join(import.meta.dirname, '..', 'data', 'app.db');
const outDir = process.argv[3] ?? path.join(import.meta.dirname, '..', 'migration-exports');

if (!fs.existsSync(dbPath)) {
  console.error(`server database not found: ${dbPath}`);
  process.exit(1);
}
const db = new DatabaseSync(dbPath, { readOnly: true });
const months = db.prepare('SELECT * FROM months ORDER BY id').all();
if (!months.length) {
  console.log('no months to export');
  process.exit(0);
}
fs.mkdirSync(outDir, { recursive: true });
for (const m of months) {
  const expenses = db.prepare('SELECT * FROM expenses WHERE month_id = ? ORDER BY id').all(m.id);
  const advice = db
    .prepare('SELECT backend, prompt_version, model_version, prompt, data_flow, output FROM suggestions_log WHERE month_id = ? ORDER BY id')
    .all(m.id);
  const doc = {
    version: 1,
    month: {
      currency: m.currency,
      income_cents: m.income_cents,
      side_cents: m.side_cents,
      rollover_cents: m.rollover_cents,
      savings_goal_cents: m.savings_goal_cents,
      emergency_saved_cents: m.emergency_saved_cents,
      expenses: expenses.map((e) => ({
        name: e.name,
        category: e.category,
        amount_cents: e.amount_cents,
        fixed: Boolean(e.fixed),
        one_off: Boolean(e.one_off),
        debt: Boolean(e.debt),
      })),
    },
    advice: advice.map((a) => ({ ...a })),
  };
  const file = path.join(outDir, `month-${m.id}.json`);
  fs.writeFileSync(file, JSON.stringify(doc, null, 2) + '\n');
  console.log(`month ${m.id}: ${expenses.length} expenses, ${advice.length} advice -> ${file}`);
}
db.close();
