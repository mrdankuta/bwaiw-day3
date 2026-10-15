// On-device engine wrapper: loads the compiled WASM once, exposes the
// single seam (month-inputs in minor units -> Plan document). Amounts
// entered in whole currency units are converted x100 to integer minor
// units at this boundary, so the engine only ever sees integers.
import init, { plan_month, engine_version } from '../engine/pkg-web/budget_wasm.js';

let ready = null;

export function engineReady() {
  if (!ready) ready = init();
  return ready;
}

export function engineVersion() {
  return engine_version();
}

export async function planMonth(inputs) {
  await engineReady();
  return JSON.parse(plan_month(JSON.stringify(inputs)));
}

export function monthInputsForEngine(month, split = {}) {
  return {
    income_cents: month.income_cents,
    side_cents: month.side_cents,
    rollover_cents: month.rollover_cents,
    expenses: month.expenses.map((e) => ({
      name: e.name,
      category: e.category,
      amount_cents: e.amount_cents,
      fixed: e.fixed,
      one_off: e.one_off,
      debt: e.debt,
    })),
    savings_pct: split.savings_pct ?? 20,
    needs_cap_pct: split.needs_cap_pct ?? 50,
    wants_cap_pct: split.wants_cap_pct ?? 30,
    emergency_cents: month.emergency_saved_cents,
  };
}

// Whole-unit entry (e.g. Naira) -> integer minor units (e.g. kobo).
export function unitsToMinorUnits(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n < 0 || !Number.isInteger(n)) {
    throw new Error('amounts must be whole non-negative numbers');
  }
  return Math.round(n * 100);
}

export function minorUnitsToUnits(cents) {
  return Math.round(cents / 100);
}

export function fmtMoney(cents, currency = 'NGN') {
  try {
    return new Intl.NumberFormat('en-NG', {
      style: 'currency', currency, minimumFractionDigits: 2,
    }).format(cents / 100);
  } catch {
    return `${(cents / 100).toFixed(2)} ${currency}`;
  }
}

export function fmtMoneyShort(cents, currency = 'NGN') {
  return fmtMoney(cents, currency).replace(/\.00$/, '');
}

export function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}
