// Pure month-grain mapping: database rows <-> month objects, plus the
// versioned export/import document. No browser or SQL imports, so this
// module runs unchanged in Node tests and in the browser store.

export const EXPORT_VERSION = 1;

export const EXPENSE_CATEGORIES = Object.freeze([
  'Housing',
  'Food',
  'Transport',
  'Utilities',
  'Health',
  'Savings',
  'Other',
]);

const INT_FIELDS = Object.freeze([
  'income_cents',
  'side_cents',
  'rollover_cents',
  'savings_goal_cents',
  'emergency_saved_cents',
]);

function isMinorUnits(value) {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0;
}

export function monthFromRows(monthRow, expenseRows) {
  return {
    id: monthRow.id,
    currency: monthRow.currency,
    income_cents: monthRow.income_cents,
    side_cents: monthRow.side_cents,
    rollover_cents: monthRow.rollover_cents,
    savings_goal_cents: monthRow.savings_goal_cents,
    emergency_saved_cents: monthRow.emergency_saved_cents,
    expenses: expenseRows.map((e) => ({
      id: e.id,
      name: e.name,
      category: e.category,
      amount_cents: e.amount_cents,
      fixed: Boolean(e.fixed),
      one_off: Boolean(e.one_off),
      debt: Boolean(e.debt),
    })),
  };
}

export function validateMonthInput(input) {
  if (typeof input.currency !== 'string' || !input.currency.trim()) {
    throw new Error('currency is required');
  }
  for (const field of INT_FIELDS) {
    if (!isMinorUnits(input[field])) {
      throw new Error(`${field} must be an integer number of minor units`);
    }
  }
  const expenses = input.expenses ?? [];
  if (!Array.isArray(expenses)) throw new Error('expenses must be an array');
  for (const e of expenses) {
    if (typeof e.name !== 'string' || !e.name.trim()) {
      throw new Error('expense name must be non-empty');
    }
    if (!EXPENSE_CATEGORIES.includes(e.category)) {
      throw new Error(`unknown expense category: ${JSON.stringify(e.category)}`);
    }
    if (!isMinorUnits(e.amount_cents)) {
      throw new Error(`expense ${JSON.stringify(e.name)} must be an integer number of minor units`);
    }
  }
  return true;
}

// The migration vehicle: the same month-inputs shape the engine consumes,
// plus currency and the advice log. Exported JSON doubles as the one-shot
// server-to-device migration format.
export function exportMonth(month, adviceEntries = []) {
  return {
    version: EXPORT_VERSION,
    month: {
      currency: month.currency,
      income_cents: month.income_cents,
      side_cents: month.side_cents,
      rollover_cents: month.rollover_cents,
      savings_goal_cents: month.savings_goal_cents,
      emergency_saved_cents: month.emergency_saved_cents,
      expenses: month.expenses.map((e) => ({
        name: e.name,
        category: e.category,
        amount_cents: e.amount_cents,
        fixed: Boolean(e.fixed),
        one_off: Boolean(e.one_off),
        debt: Boolean(e.debt),
      })),
    },
    advice: adviceEntries.map((a) => ({
      backend: a.backend,
      prompt_version: a.prompt_version,
      model_version: a.model_version,
      prompt: a.prompt,
      data_flow: a.data_flow,
      output: a.output,
    })),
  };
}

export function importMonthDoc(doc) {
  if (!doc || doc.version !== EXPORT_VERSION || !doc.month) {
    throw new Error(`unsupported export version: ${doc?.version}`);
  }
  const month = { ...doc.month, expenses: doc.month.expenses ?? [] };
  validateMonthInput(month);
  const advice = Array.isArray(doc.advice) ? doc.advice : [];
  for (const a of advice) {
    if (typeof a.output !== 'string') throw new Error('advice output must be text');
  }
  return { month, advice };
}
