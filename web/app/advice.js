// Client-side Advice (ticket #22): deterministic template explainer
// plus cite-numbers-only validator. Pure module — no browser or network
// imports — so Node tests exercise the exact code the page runs.
//
// Math-first posture, mirroring the retired server: the engine owns
// every number; this module only verbalizes the computed Plan plus
// Warnings. There is no cloud or off-machine path here.

export const PROMPT_VERSION = 'advice-v1';
export const MODEL_VERSION_DEFAULT = 'template-local-v1';
export const LOCAL_BACKEND = 'template-local';

export const BLOCKLIST = Object.freeze([
  'guarantee',
  'fiduciary',
  'registered investment',
  'registered adviser',
  'sec-approved',
  'risk-free',
  'will earn',
  'guaranteed returns',
]);

export function buildPrompt(plan, currency) {
  const lines = [
    'You are a budgeting explainer, not an adviser. Educational only.',
    'Rules: use ONLY the computed figures below; never recompute or invent',
    'numbers; cite each figure; give 3-5 suggestions tied to the gaps;',
    'refuse guaranteed returns, specific securities, tax or legal verdicts,',
    'and fiduciary claims. Low temperature. Output plain suggestions.',
    `Computed: available=${plan.available_cents} total=${plan.total_expenses_cents}`,
    `leftover=${plan.leftover_cents} savings_target=${plan.savings_target_cents}`,
    `needs=${plan.needs_total_cents} wants=${plan.wants_total_cents}`,
    `currency=${currency}`,
  ];
  for (const w of plan.warnings) lines.push(`warning ${w.rule_id}: ${w.message}`);
  return lines.join('\n');
}

export function deterministicExplain(plan, currency) {
  const out = [
    `Available ${plan.available_cents} against expenses` +
      ` ${plan.total_expenses_cents} leaves ${plan.leftover_cents} (${currency}).`,
    `Protect the savings carve-out of ${plan.savings_target_cents} before Wants` +
      ` (Needs ${plan.needs_total_cents}, Wants ${plan.wants_total_cents}).`,
  ];
  for (const w of plan.warnings) {
    out.push(`Act on warning ${w.rule_id}: ${w.message}`);
    if (out.length >= 5) break;
  }
  for (const s of plan.suggestions) {
    if (out.length >= 5) break;
    if (!out.includes(s)) out.push(s);
  }
  while (out.length < 3) out.push('No further gaps detected; hold the current allocation.');
  return out.slice(0, 5);
}

export function validateOutput(text, plan) {
  const violations = [];
  const known = new Set([
    plan.available_cents,
    plan.total_expenses_cents,
    plan.leftover_cents,
    plan.savings_target_cents,
    plan.needs_total_cents,
    plan.wants_total_cents,
  ]);
  for (const m of text.matchAll(/(-?\d[\d,]*)(%| months?)?/g)) {
    if (m[2]) continue; // thresholds cite labeled rules, not money figures
    if (!known.has(Number(m[1].replace(/,/g, '')))) {
      violations.push(`uncomputed figure cited: ${m[1]}`);
    }
  }
  const lowered = text.toLowerCase();
  for (const banned of BLOCKLIST) {
    if (lowered.includes(banned)) violations.push(`blocklisted phrase: ${banned}`);
  }
  return violations;
}

export function generateAdvice(plan, currency, engineVersion) {
  const lines = deterministicExplain(plan, currency);
  const text = lines.join('\n');
  const violations = validateOutput(text, plan);
  if (violations.length) throw new Error(violations.join('; '));
  return {
    lines,
    text,
    backend: LOCAL_BACKEND,
    prompt_version: PROMPT_VERSION,
    model_version: MODEL_VERSION_DEFAULT,
    prompt: buildPrompt(plan, currency),
    // Engine version travels in the data-flow note: no schema change,
    // attribution preserved alongside prompt and model versions.
    data_flow: `No fields left this machine (local template backend) · engine ${engineVersion}.`,
  };
}
