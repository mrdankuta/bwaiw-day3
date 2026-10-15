// Node tests for the client-side Advice module (ticket #22).
// Run: node --test web/app/test-advice.mjs
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  deterministicExplain,
  validateOutput,
  generateAdvice,
  PROMPT_VERSION,
} from './advice.js';

const PLAN = {
  available_cents: 1000000,
  total_expenses_cents: 400000,
  leftover_cents: 600000,
  savings_target_cents: 200000,
  needs_total_cents: 400000,
  wants_total_cents: 0,
  warnings: [
    { rule_id: 'rent-burden', message: 'Heuristic: rent burden at 40% of available (threshold 30%).' },
    { rule_id: 'housing-cap', message: 'Heuristic: housing over 28% of available.' },
  ],
  suggestions: ['Assign leftover 600000 minor units to Savings.'],
};

describe('deterministicExplain', () => {
  it('cites computed figures and stays within 3-5 lines', () => {
    const lines = deterministicExplain(PLAN, 'NGN');
    assert.ok(lines.length >= 3 && lines.length <= 5);
    assert.ok(lines[0].includes('1000000') && lines[0].includes('NGN'));
    assert.ok(lines.some((l) => l.includes('rent-burden')));
    assert.ok(lines.some((l) => l.includes('600000 minor units to Savings')));
  });

  it('pads quiet months to three lines', () => {
    const lines = deterministicExplain({ ...PLAN, warnings: [], suggestions: [] }, 'NGN');
    assert.equal(lines.length, 3);
  });
});

describe('validateOutput', () => {
  it('passes the module’s own output', () => {
    assert.deepEqual(validateOutput(deterministicExplain(PLAN, 'NGN').join('\n'), PLAN), []);
  });
  it('rejects uncomputed figures but ignores rule thresholds', () => {
    assert.deepEqual(validateOutput('Leftover 600000 is fine, not 12345.', PLAN),
      ['uncomputed figure cited: 12345']);
    assert.deepEqual(validateOutput('Rent at 40% with 3 months cover.', PLAN), []);
  });
  it('rejects blocklisted phrases', () => {
    const v = validateOutput('Guaranteed returns of 600000 await.', PLAN);
    assert.ok(v.some((x) => x.startsWith('blocklisted phrase')));
  });
});

describe('generateAdvice', () => {
  it('returns a logged bundle with versions', () => {
    const out = generateAdvice(PLAN, 'NGN', 'budget-engine-v1');
    assert.equal(out.backend, 'template-local');
    assert.equal(out.prompt_version, PROMPT_VERSION);
    assert.ok(out.prompt.includes('Educational only'));
    assert.ok(out.data_flow.includes('No fields left this machine'));
    assert.ok(out.data_flow.includes('budget-engine-v1'));
    assert.ok(out.lines.length >= 3 && out.lines.length <= 5);
  });
});
