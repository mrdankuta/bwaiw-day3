# Research: LLM budgeting advice patterns + guardrails (issue #3)

Map: issue #1 (Agentic Financial Planner MVP — personal single-user, manual entry, zero-based + 50/30/20, deterministic math + LLM explanation, advisor-only).
Scope: what the spec needs to copy/paste — prompt pattern, disclaimer, warning thresholds, never-claims. Not legal advice; MVP must have a human-readable disclaimer and stay educational-only.

## 1. Prompt pattern: budget-math-first + LLM-explains

Industry consensus is **never let the LLM do the arithmetic**. Compute deterministically, then give the LLM the computed JSON to explain.

- **Deterministic engine owns all numbers.** Totals, 50/30/20 splits, zero-based assignment (`income − assigned = 0`), ratios (rent/income, savings rate, DTI). LLM input = structured JSON of those results; LLM must echo, not recompute. Origin's AI advisor pairs "LLM reasoning layer with deterministic computational engines… Monte Carlo simulation, not a language model estimation" plus "138 automated checks… numerical accuracy, suitability, disclosure" (useorigin.com breakdown of Origin AI Advisor).
- **Post-generation verify-and-repair, not prompt-only self-correction.** BiasMix-Finance (arXiv 2608.28646, Aug 2026) pattern: (i) strict JSON allocation schema, (ii) validate against numeric caps, (iii) deterministically project to nearest feasible portfolio via convex program. First-pass LLM drafts violated ≥1 cap in 67.2% pooled cases; projection reduced final violations to 0%. Same compose works for budgeting caps (rent %, savings floor): LLM proposes wording, code enforces numbers.
- **Neuro-symbolic canonicalizer-vs-solver split.** Moxia (arXiv 2606.00671): LLM rewrites NL → narrow task schema, deterministic CAS pipeline derives every answer, abstain is first-class. Budgeting analogue: LLM classifies/cleans manual entries → code sums and assigns; LLM never emits a balance.
- **Personal-finance LLM recipe.** FinNLP 2025 "Synthesizing Behaviorally-Grounded Reasoning Chains" (Perfios): modular chain-of-thought + LLM-jury validation, factual grounding is the bottleneck → add retrieval for regulatory info + calculation verification; "system is for educational use only — not fiduciary… prompts/filters forbid unsafe guidance (e.g. 'guaranteed returns')"; plan rule-based compliance layer + DPO alignment.
- **System validation, not just model score.** arXiv 2607.28840 "Benchmarks Are Not Validation": validate retrieval, grounding, guardrail respect, tool-call safety, escalation, stability across model/prompt/tool changes. Treat prompt-template/tool-schema/guardrail edits as controlled changes with regression tests.

**Actionable prompt skeleton for spec:**
```
system: You are a budgeting explainer, not an adviser. Educational only.
  Rules: use ONLY the provided computed JSON; never recompute or invent
  numbers; cite each figure; 3–5 suggestions tied to computed gaps;
  include disclaimer; refuse: guaranteed returns, specific securities,
  tax/legal verdicts, fiduciary claims. Output strict JSON schema.
  Temperature low. Log prompt+output.
user: { computed: { income, needs/wants/savings actual vs target,
  ratios, warnings[] }, user_goal }
```

## 2. Disclaimers + guardrails for personal advisor-only MVP

Copy the standard educational-only formula used by shipping budgeting apps:

- BudgetPlan AI: "AI-generated financial information for educational purposes only. Not a substitute for professional financial advice… not a registered investment advisor" (budgetplanai.com/about).
- Perry AI: "educational and insights tool… does not constitute financial advice… no guarantees about accuracy… consult qualified professionals… solely responsible" (theperryai.com/get-started).
- SavvyMoney (Jul 2026): "informational and educational purposes only… not a registered investment adviser, broker-dealer… AI responses can be incomplete, outdated, or inaccurate. Do not rely on them as sole basis" (mysavvymoney.com/legal/disclaimer).
- WealthPlanrAI pricing page one-liner (good minimal banner): "Educational platform only. Not financial advice. Not an investment adviser, broker-dealer, or insurance producer… does not create an advisor-client relationship."
- ROI (App Store): "not a financial advisor… general guidance, not personalized advice. Always do your own research."
- Origin (SEC-registered, for contrast — we are NOT this): "personalized, non-discretionary guidance… may occasionally contain errors. Users responsible… encouraged to consult human advisor" (BusinessWire Sep 2025). Non-discretionary = no authority to act; client decides. Our MVP should state the same non-discretionary posture explicitly.

Regulatory backdrop (why the above wording matters):
- FINRA Regulatory Notice 24-09 (Jun 2024) + 2026 Oversight Report: GenAI rules are technology-neutral — communications must still be fair/balanced, no false/misleading; firms need pre-deployment testing, output logs/model tracking, governance + change management, vendor diligence, books-and-records capture. MVP action: log prompts/outputs, version prompt template, never claim testing you didn't do.
- SEC AI-washing enforcement (GAO-25-107197): ≥8 AI-related actions 2023–24 for false/misleading AI claims; ~30 advisers examined, most lacked AI policies. SEC/FINRA/NASAA Jan 2024 joint alert on AI investment fraud. MVP action: don't say "SEC-approved", "fiduciary", "guaranteed", or inflate AI capability.
- Privacy posture for spec: "manual entry only, no bank sync; user data not used for model training; single-user" — mirrors M1 Advisor disclosure ("not used to train AI models") and avoids Plaid-scope liabilities.

**MVP guardrail checklist (spec-ready):** educational-only banner + full disclaimer page; non-discretionary / advisor-only statement ("suggests, never moves money"); no autonomous payments; structured-output schema + numeric validator before render; blocklist (guarantee, fiduciary, registered, "will return X%"); low temperature; human-in-loop confirm for categories; prompt/output logging; vendor/model version pinned.

## 3. Warning-rule examples (deterministic, tunable)

All code-computed; LLM only verbalizes. Thresholds are heuristics, not law — label as such in UI.

| Warning | Rule (default, tunable) | Source |
|---|---|---|
| Rent burden | rent+utilities > 30% gross income → warn; > 50% → severe | HUD cost-burden definition (Brooke Amend. 1969, raised 25%→30% in 1981); HUD User; Fed FEDS Notes 2017-12-22: >30% burdened, >50% severely |
| Mortgage / 28-36 | housing ≤ 28% gross, all debt ≤ 36% gross | Bankrate 28/36 explainer; CFPB Your Money Your Goals DTI tool: mortgage 28–35%, all-debt ≤36% homeowners, 15–20% renters (rent excl.) |
| 50/30/20 drift | needs >50%, wants >30%, savings+debt-pay <20% take-home → flag each | CFPB "Analyzing budgets" worksheet; Experian Apr 2026; Investopedia; SoFi — all: 50% needs max / 30% wants max / ≥20% savings+debt; bends in HCOL, framework not rigid |
| Savings floor | savings rate <20% → nudge; emergency fund <3× monthly essentials → warn | 20% from 50/30/20; 3–6 mo emergency-fund standard (CFPB toolkit convention — confirm exact CFPB page at spec time) |
| Shortfall / zero-based | `assigned − income > 0` → overspend; `income − assigned > 0` → unassigned ("give every dollar a job") | Zero-based definition; AI Budgie "plan vs actual / left-to-spend" is the UX analogue |

Spec note: store thresholds in config (not prompts) so BiasMix-style validator can enforce them; LLM receives `warnings[]` with triggered rule IDs and must not invent new ratios.

## 4. What must NEVER be claimed

- No guaranteed/predicted returns ("will earn X%", "beat the market", "risk-free"). Past performance ≠ future results. (FinNLP paper explicitly forbids "guaranteed returns"; Northbridge disclaimer template.)
- No regulated-advice posture: don't claim to be a registered adviser, broker-dealer, fiduciary, CFP, or "SEC-approved"; don't create advisor-client relationship. (SEC examination + AI-washing actions; FINRA fair/balanced comms.)
- No definitive tax/legal/benefits verdicts; no specific security buy/sell/hold instructions in MVP. Route to "consult a qualified professional."
- No invented math: LLM must not restate totals differently from computed JSON, estimate bank balances, or claim bank-verified data (manual-entry MVP has no verification — say so, cf. AI Fund terms: "users responsible for accuracy… does not connect to banks").
- No autonomy claims: never imply it can pay bills/move money. Advisor-only, non-discretionary.

## Sources (primary-first)

- Origin AI Advisor launch (BusinessWire/Yahoo, Sep 2025) — multi-agent + deterministic engines + 138 checks; non-discretionary disclosure.
- BiasMix-Finance, arXiv:2608.28646 — post-generation KYC guardrail pipeline; 67.2%→0% violations.
- Moxia, arXiv:2606.00671 — canonicalizer-vs-solver, abstain-first.
- Theerthala (Perfios), FinNLP 2025 — personal-finance CoT + jury; educational-only + compliance layer.
- "Benchmarks Are Not Validation", arXiv:2607.28840 — system-level validation.
- FINRA Notice 24-09; FINRA 2026 Oversight Report summary (Financial Commission Dec 2025); GAO-25-107197; SEC AI Roundtable remarks Mar 2025.
- HUD 30%/50% burden (24 CFR, HUD User, Fed FEDS Notes); CFPB DTI calculator tool (36% / 15–20% / 28–35%); CFPB 50-30-20 worksheet; Experian/Investopedia/SoFi 50/30/20.
- Disclaimer wording: budgetplanai.com/about, theperryai.com/get-started, mysavvymoney.com/legal/disclaimer, wealthplanrai.com/pricing, ROI App Store, naturalui.com/roi/terms.

## Spec handoff (5 items)

1. Architect as `compute (TS/Python, tested) → validate → LLM explain (strict JSON, low temp) → validator → render + disclaimer`.
2. System prompt hard-codes educational-only + cite-numbers-only + blocklist; thresholds live in config.
3. Default warnings: rent>30/50%, housing 28%, all-debt 36%, savings<20%, emergency<3mo, zero-based shortfall — all tunable, all labeled heuristics.
4. Ship banner + disclaimer page (WealthPlanrAI one-liner + SavvyMoney full text as models); log prompt/output/version; non-discretionary statement.
5. Regression tests: golden computed fixtures; LLM must echo numbers; violation-injection test (biased draft → validator still blocks Romain/Guarantee/fiduciary language).
