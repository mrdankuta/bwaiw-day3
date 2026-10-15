// Shared page chrome for the on-device app: topnav, educational-only
// guardrail strip, wizard stepper, footer. Pages call renderChrome with
// the active step and set <body data-active="...">.
const NAV = [
  ['income', 'Income', 'income.html'],
  ['expenses', 'Expenses', 'expenses.html'],
  ['plan', 'Plan', 'plan.html'],
  ['months', 'Past months', 'months.html'],
];

const DISCLAIMER_SHORT =
  'Educational information only, not financial advice. This planner suggests; it never moves money (non-discretionary).';

// Offline shell: every page importing this module registers the service
// worker (relative URL works both locally under /web/ and at the
// deployment root). Registration failure never blocks the page.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('sw.js').catch(() => {});
  });
}

export function renderChrome(active) {
  const links = NAV.map(([key, label, href]) =>
    `<a href="${href}"${key === active ? ' aria-current="page"' : ''}>${label}</a>`).join('');
  document.body.insertAdjacentHTML('afterbegin', `
    <header class="topnav"><div class="container topnav-inner">
      <a class="brand" href="index.html"><span class="brand-mark">₦</span><span>Monthly&nbsp;Planner</span></a>
      <nav aria-label="App navigation">${links}</nav>
      <a class="btn btn-primary" href="income.html">Plan this month</a>
    </div></header>
    <div class="guardrail"><div class="container">
      <span class="badge"><span class="badge-dot" style="background:var(--accent)"></span>Educational only</span>
      <span>${DISCLAIMER_SHORT} <a href="disclaimer.html">Full disclaimer</a></span>
    </div></div>`);
  document.body.insertAdjacentHTML('beforeend', `
    <footer class="pagefoot"><div class="container row-between">
      <span>Monthly Planner · deterministic budget engine · on-device SQLite store</span>
      <span class="meta">Computes first · explains second · moves nothing</span>
    </div></footer>`);
}

const STEP_LABELS = [['income', 'Income', 'income.html'], ['expenses', 'Expenses', 'expenses.html'], ['plan', 'Plan & Advice', 'plan.html']];

export function stepper(active) {
  const order = ['income', 'expenses', 'plan'];
  const idx = order.indexOf(active);
  return `<div class="steps">` + order.map((key, i) => {
    const n = i + 1;
    const label = STEP_LABELS[i][1];
    const href = STEP_LABELS[i][2];
    if (i < idx) return `<a class="step is-done" href="${href}"><span class="step-no">${n}</span>${label}</a>`;
    if (i === idx) return `<span class="step is-active"><span class="step-no">${n}</span>${label}</span>`;
    return `<span class="step"><span class="step-no">${n}</span>${label}</span>`;
  }).join('') + `</div>`;
}

export function wireFlags() {
  document.querySelectorAll('.flag input').forEach((cb) => {
    const label = cb.closest('.flag');
    const sync = () => label.classList.toggle('is-on', cb.checked);
    cb.addEventListener('change', sync);
    sync();
  });
}
