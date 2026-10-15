// Node verification for the on-device store ticket (#17).
// Covers what is verifiable without a browser: schema.sql executes,
// the grain mapping round-trips through real SQL identically, and the
// export/import document validates. The wa-sqlite binding itself
// (OPFS/IndexedDB VFS wiring in store.js) is verified in a real browser
// via harness.html. Run: node --test web/store/test-store.mjs
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import {
  monthFromRows,
  validateMonthInput,
  exportMonth,
  importMonthDoc,
} from './grain.js';

const DIR = import.meta.dirname;
const SCHEMA = fs.readFileSync(path.join(DIR, 'schema.sql'), 'utf8');
const STORE_SRC = fs.readFileSync(path.join(DIR, 'store.js'), 'utf8');

const SAMPLE = {
  currency: 'NGN',
  income_cents: 10000,
  side_cents: 500,
  rollover_cents: 2000,
  savings_goal_cents: 3000,
  emergency_saved_cents: 8000,
  expenses: [
    { name: 'Rent', category: 'Housing', amount_cents: 4000, fixed: true, one_off: false, debt: false },
    { name: 'Loan', category: 'Other', amount_cents: 2000, fixed: false, one_off: false, debt: true },
  ],
};

function openDb() {
  const db = new DatabaseSync(':memory:');
  db.exec(SCHEMA);
  return db;
}

function insertMonth(db, input) {
  const r = db
    .prepare(`INSERT INTO months (currency, income_cents, side_cents, rollover_cents,
      savings_goal_cents, emergency_saved_cents, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)`)
    .run(input.currency, input.income_cents, input.side_cents, input.rollover_cents,
      input.savings_goal_cents, input.emergency_saved_cents, 0);
  const id = Number(r.lastInsertRowid);
  const ins = db.prepare(`INSERT INTO expenses
    (month_id, name, category, amount_cents, fixed, one_off, debt) VALUES (?, ?, ?, ?, ?, ?, ?)`);
  for (const e of input.expenses) {
    ins.run(id, e.name, e.category, e.amount_cents,
      e.fixed ? 1 : 0, e.one_off ? 1 : 0, e.debt ? 1 : 0);
  }
  return id;
}

describe('schema.sql', () => {
  it('creates the server grain: months, expenses, suggestions_log', () => {
    const db = openDb();
    const tables = db
      .prepare("SELECT name FROM sqlite_master WHERE type = 'table' AND name != 'sqlite_sequence' ORDER BY name")
      .all().map((r) => r.name);
    assert.deepEqual(tables, ['expenses', 'months', 'suggestions_log']);
    for (const t of ['months', 'expenses', 'suggestions_log']) {
      const cols = db.prepare(`PRAGMA table_info(${t})`).all().map((r) => r.name);
      assert.ok(cols.includes('id'), `${t} has id`);
    }
    db.close();
  });

  it('store.js references every table (no schema drift)', () => {
    for (const t of ['months', 'expenses', 'suggestions_log']) {
      assert.ok(STORE_SRC.includes(t), `store.js mentions ${t}`);
    }
  });
});

describe('grain round-trip through real SQL', () => {
  it('reads back byte-identical at the grain boundary', () => {
    const db = openDb();
    const id = insertMonth(db, SAMPLE);
    const monthRow = db.prepare('SELECT * FROM months WHERE id = ?').get(id);
    const expenseRows = db.prepare('SELECT * FROM expenses WHERE month_id = ? ORDER BY id').all(id);
    const back = monthFromRows(monthRow, expenseRows);
    assert.equal(back.currency, 'NGN');
    assert.equal(back.income_cents, 10000);
    assert.equal(back.expenses.length, 2);
    assert.equal(back.expenses[0].fixed, true);
    assert.equal(back.expenses[0].one_off, false);
    assert.equal(back.expenses[1].debt, true);
    assert.deepEqual(
      back.expenses.map(({ id, ...e }) => e),
      SAMPLE.expenses,
    );
    db.close();
  });
});

describe('validation', () => {
  it('accepts a well-formed month', () => {
    assert.equal(validateMonthInput(SAMPLE), true);
  });
  for (const [label, mutate, match] of [
    ['empty currency', { currency: '  ' }, /currency/],
    ['negative income', { income_cents: -1 }, /income_cents/],
    ['float amount', { expenses: [{ ...SAMPLE.expenses[0], amount_cents: 10.5 }] }, /minor units/],
    ['empty name', { expenses: [{ ...SAMPLE.expenses[0], name: '' }] }, /non-empty/],
    ['unknown category', { expenses: [{ ...SAMPLE.expenses[0], category: 'Yachts' }] }, /unknown expense category/],
  ]) {
    it(`rejects ${label}`, () => {
      assert.throws(() => validateMonthInput({ ...SAMPLE, ...mutate }), match);
    });
  }
});

describe('export/import document', () => {
  it('round-trips to an identical grain', () => {
    const db = openDb();
    const id = insertMonth(db, SAMPLE);
    db.prepare(`INSERT INTO suggestions_log (month_id, backend, prompt_version, model_version,
      prompt, data_flow, output, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`)
      .run(id, 'template-local', 'advice-v1', 'template-local-v1', 'p', 'local', 'line one', 0);
    const month = monthFromRows(
      db.prepare('SELECT * FROM months WHERE id = ?').get(id),
      db.prepare('SELECT * FROM expenses WHERE month_id = ? ORDER BY id').all(id),
    );
    const advice = db.prepare('SELECT backend, prompt_version, model_version, prompt, data_flow, output FROM suggestions_log WHERE month_id = ? ORDER BY id').all(id);
    const doc = exportMonth(month, advice);
    assert.equal(doc.version, 1);
    const { month: back, advice: backAdvice } = importMonthDoc(JSON.parse(JSON.stringify(doc)));
    assert.deepEqual(
      { ...back, expenses: back.expenses },
      { ...SAMPLE },
    );
    assert.equal(backAdvice.length, 1);
    assert.equal(backAdvice[0].output, 'line one');
    db.close();
  });

  it('rejects unknown versions and bad advice', () => {
    assert.throws(() => importMonthDoc({ version: 999, month: SAMPLE }), /unsupported export version/);
    const doc = exportMonth({ ...SAMPLE, id: 1, expenses: SAMPLE.expenses }, [{ output: 42 }]);
    assert.throws(() => importMonthDoc(doc), /advice output/);
  });
});
