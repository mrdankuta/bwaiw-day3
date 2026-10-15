// On-device month store on browser SQLite (wa-sqlite, vendored).
//
// Storage choice: OPFS (OriginPrivateFileSystemVFS, synchronous build)
// where sync access handles exist, otherwise IndexedDB
// (IDBBatchAtomicVFS, asynchronous build) which works everywhere.
// Single user, single device. Mirror of the server store's grain.
import SyncModuleFactory from '../vendor/wa-sqlite/dist/wa-sqlite.mjs';
import AsyncModuleFactory from '../vendor/wa-sqlite/dist/wa-sqlite-async.mjs';
import { Factory } from '../vendor/wa-sqlite/src/sqlite-api.js';
import { OriginPrivateFileSystemVFS } from '../vendor/wa-sqlite/src/examples/OriginPrivateFileSystemVFS.js';
import { IDBBatchAtomicVFS } from '../vendor/wa-sqlite/src/examples/IDBBatchAtomicVFS.js';
import { monthFromRows, validateMonthInput, exportMonth, importMonthDoc } from './grain.js';

export { exportMonth, importMonthDoc };

const DB_FILENAME = 'monthly-planner.db';
const IDB_NAME = 'monthly-planner-idb';

function vendorUrl(filename) {
  return new URL(`../vendor/wa-sqlite/dist/${filename}`, import.meta.url).href;
}

async function supportsOPFS() {
  try {
    if (!navigator.storage?.getDirectory) return false;
    const root = await navigator.storage.getDirectory();
    const probe = await root.getFileHandle('__planner_probe', { create: true });
    const ok = typeof probe.createSyncAccessHandle === 'function';
    await root.removeEntry('__planner_probe');
    return ok;
  } catch {
    return false;
  }
}

async function all(sqlite3, db, sql, params = []) {
  const { rows, columns } = await sqlite3.execWithParams(
    db, sql, params.length ? params : undefined);
  return rows.map((values) =>
    Object.fromEntries(values.map((value, i) => [columns[i], value])));
}

async function run(sqlite3, db, sql, params = []) {
  await sqlite3.run(db, sql, params.length ? params : undefined);
  const rows = await all(sqlite3, db, 'SELECT last_insert_rowid() AS id');
  return rows[0].id;
}

export async function openStore() {
  const useOPFS = await supportsOPFS();
  const factory = useOPFS ? SyncModuleFactory : AsyncModuleFactory;
  const wasm = useOPFS ? 'wa-sqlite.wasm' : 'wa-sqlite-async.wasm';
  const sqlite3 = Factory(
    await factory({ locateFile: (name) => (name.endsWith('.wasm') ? vendorUrl(wasm) : name) }),
  );
  const vfs = useOPFS ? new OriginPrivateFileSystemVFS() : new IDBBatchAtomicVFS(IDB_NAME);
  sqlite3.vfs_register(vfs, true);
  const db = await sqlite3.open_v2(DB_FILENAME);
  const schema = await (await fetch(new URL('./schema.sql', import.meta.url))).text();
  await sqlite3.exec(db, schema);
  return new MonthStore(sqlite3, db, useOPFS ? 'opfs' : 'indexeddb');
}

export class MonthStore {
  constructor(sqlite3, db, backend) {
    this.sqlite3 = sqlite3;
    this.db = db;
    this.backend = backend; // 'opfs' | 'indexeddb'
  }

  async close() {
    await this.sqlite3.close(this.db);
  }

  async saveMonth(input) {
    validateMonthInput(input);
    const now = Math.floor(Date.now() / 1000);
    const id = await run(
      this.sqlite3, this.db,
      `INSERT INTO months (currency, income_cents, side_cents, rollover_cents,
        savings_goal_cents, emergency_saved_cents, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
      [input.currency.trim().toUpperCase().slice(0, 8) || 'NGN',
       input.income_cents, input.side_cents, input.rollover_cents,
       input.savings_goal_cents, input.emergency_saved_cents, now],
    );
    for (const e of input.expenses ?? []) {
      await this.addExpense(id, e);
    }
    return id;
  }

  async addExpense(monthId, expense) {
    const months = await all(this.sqlite3, this.db, 'SELECT 1 AS ok FROM months WHERE id = ?', [monthId]);
    if (!months.length) throw new Error(`unknown month: ${monthId}`);
    validateMonthInput({
      currency: 'NGN', income_cents: 0, side_cents: 0, rollover_cents: 0,
      savings_goal_cents: 0, emergency_saved_cents: 0, expenses: [expense],
    });
    return run(
      this.sqlite3, this.db,
      `INSERT INTO expenses (month_id, name, category, amount_cents, fixed, one_off, debt)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
      [monthId, expense.name.trim(), expense.category, expense.amount_cents,
       expense.fixed ? 1 : 0, expense.one_off ? 1 : 0, expense.debt ? 1 : 0],
    );
  }

  async deleteExpense(expenseId) {
    await this.sqlite3.run(this.db, 'DELETE FROM expenses WHERE id = ?', [expenseId]);
    return this.sqlite3.changes(this.db) > 0;
  }

  async getMonth(monthId) {
    const months = await all(this.sqlite3, this.db, 'SELECT * FROM months WHERE id = ?', [monthId]);
    if (!months.length) return null;
    const expenses = await all(
      this.sqlite3, this.db, 'SELECT * FROM expenses WHERE month_id = ? ORDER BY id', [monthId]);
    return monthFromRows(months[0], expenses);
  }

  async listMonths() {
    const months = await all(this.sqlite3, this.db,
      'SELECT id, currency FROM months ORDER BY id DESC');
    return months.map((m) => ({ id: m.id, currency: m.currency }));
  }

  async saveAdvice({ monthId, backend, prompt_version, model_version, prompt, data_flow, output }) {
    const now = Math.floor(Date.now() / 1000);
    return run(
      this.sqlite3, this.db,
      `INSERT INTO suggestions_log (month_id, backend, prompt_version, model_version,
        prompt, data_flow, output, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      [monthId, backend, prompt_version, model_version, prompt, data_flow, output, now],
    );
  }

  async latestAdvice(monthId) {
    const rows = await all(this.sqlite3, this.db,
      'SELECT * FROM suggestions_log WHERE month_id = ? ORDER BY id DESC LIMIT 1', [monthId]);
    return rows[0] ?? null;
  }

  async exportMonth(monthId) {
    const month = await this.getMonth(monthId);
    if (!month) throw new Error(`unknown month: ${monthId}`);
    const advice = await all(this.sqlite3, this.db,
      'SELECT backend, prompt_version, model_version, prompt, data_flow, output FROM suggestions_log WHERE month_id = ? ORDER BY id',
      [monthId]);
    return exportMonth(month, advice);
  }

  async importMonthDoc(doc) {
    const { month, advice } = importMonthDoc(doc);
    const id = await this.saveMonth(month);
    for (const a of advice) {
      await this.saveAdvice({ monthId: id, ...a });
    }
    return id;
  }
}
