# Research: web stack + persistence + privacy for personal finance MVP
Ticket: #4 (part of wayfinder map #1) | Branch: `research/stack-persistence-privacy`
Context: personal single-user web app, manual entry first, no bank sync, advisor-only
(deterministic budget math + LLM explanation layer).

## 1. Minimal web stacks (solo-dev speed)

| Option | Shape | Pros | Cons | Best when |
|---|---|---|---|---|
| A. Single-file Python: Flask or FastAPI + SQLite + Jinja/HTMX | One process, server-rendered HTML, JSON API only if needed | Fastest to MVP for Python dev; no build step; `sqlite3` stdlib (Flask) / easy Pydantic validation (FastAPI); trivial Docker; backup = copy one file | Less polished interactive UI vs React; PWA/offline is manual | Solo dev, Python-comfortable, prioritize shipping math + forms |
| B. JS full-stack: Next.js App Router + SQLite (`better-sqlite3` / `node:sqlite`) + Drizzle + Tailwind | One app serves UI + API routes + PWA shell | One language end-to-end; mobile-first PWA + installable; FTS5 search, file-in-process DB; single-container deploy | Heavier toolchain (Node, build, native module `serverExternalPackages`); hot-reload singleton + `PRAGMA journal_mode=WAL` gotchas | Want polished/mobile UI, JS-comfortable, PWA matters |
| C. (rejected for MVP) Split SPA + separate API + hosted services | e.g. Vite SPA + FastAPI + Supabase Auth | Scales to multi-user later | 2 deploys, auth, CORS, billing — overkill for 1 user | Not MVP |

Trade-off summary: A wins on fewest moving parts and fastest deterministic-math
iteration; B wins if UI polish/PWA is the differentiator. Both are single-process +
single-file DB patterns proven for personal apps (one process, no Redis/cron;
SQLite table as job queue; `DATA_DIR` holds db + backups).

## 2. Persistence: local file/SQLite vs hosted DB

Rule of thumb (from source survey): if a single process writes, SQLite in the same
container wins; if multiple writers/instances/edge writes, use hosted Postgres.

| Option | Cost / ops | Pros | Cons |
|---|---|---|---|
| SQLite file next to app (`./data/app.db`, WAL, auto-migrate, gitignore `*.db*`) | $0 extra; backup = `VACUUM INTO` / nightly copy / Litestream to R2/S3 | Zero infra; µs reads (no network); trivial local dev = copy file; easy later migration via Drizzle/Kysely portable SQL | Single-writer serializes; no multi-instance; file must live on persistent volume (not ephemeral serverless FS); don't write from outside app while open |
| Turso (managed libSQL/SQLite) | Free 5 GB / 500M rows-read; paid from ~$5–6/mo; reads counted as rows scanned | Keeps SQLite SQL; embedded replicas = local reads | Row-scan billing punishes missing indexes; still single primary for writes |
| Supabase (hosted Postgres + auth/storage) | Free 500 MB, 2 projects, pauses after ~7d idle; Pro $25/mo (daily backups) | Full platform when you need auth/realtime; standard `postgres://` = portable | Idle pause bad for rarely-used personal app; paying for unused platform if only DB needed |
| Neon (hosted Postgres) | Free 0.5 GB + 100 CU-hrs; usage-based paid; scale-to-zero, branches | Branch = safe migration testing; good "only Postgres" choice | Cold starts; suspends on limit until next month |
| Cloudflare D1 (SQLite on Workers) | Free 5M rows-read/day, 5 GB; paid $5/mo; 10 GB cap | Zero-server if app already on Workers | Workers-only binding; platform-shaped code; cap unrais rable |

Recommendation: **SQLite file on persistent volume, WAL on, migrations auto-run at
boot, nightly file backup.** No hosted DB for MVP — monthly plans + history are
KBs/month, single writer, no concurrency need. Keep SQL portable (Drizzle/Kysely)
so a later move to Postgres is a data migration, not a rewrite. Add `npm`/`make`
`backup` + `restore` scripts from day one.

Minimal schema sketch: `months(id, yyyy_mm, income_cents, …)`,
`expenses(id, month_id, category, amount_cents, fixed/variable, note)`,
`plans(id, month_id, method, payload_json)`, `suggestions_log(id, month_id, text, created_at)`.

## 3. LLM provider + privacy posture

| Path | What leaves machine | Cost (Apr 2026 ref) | Latency / quality |
|---|---|---|---|
| Local-only (Ollama / llama.cpp, GGUF Q4, 3B–8B on laptop) | Nothing (after model download) | $0/token; HW sunk (3B ≈ 2 GB; 8B-Q4 ≈ 5 GB) | TTFT 200–400 ms on-device (no net); ~14–24 tok/s for 7B-Q4 on M1/M4; weaker on hard reasoning/agentic chains, fine for explain/summarize/classify |
| API (GPT-4o / Claude Sonnet / Haiku / 4o-mini via HTTPS) | Prompt + amounts/categories sent to provider; retained per DPA (e.g. 30d default) | GPT-4o $2.50/$10 per 1M in/out; Sonnet $3/$15; mini/Haiku ~$0.15–0.25/$0.60–1.25; MVP volume = cents/mo | TTFT ~180–800 ms; frontier quality on triage/reasoning (e.g. 92% vs 85–88% local in one fintech eval) |
| Hybrid (recommended) | Only non-sensitive or summarized data to API; raw amounts stay local unless user opts in | API pennies at MVP; self-host break-even only at ~$200–300/mo bill or >10–100K tok/day sustained | Best of both; same OpenAI-compatible `base_url` swap (`localhost:11434` ↔ `api.openai.com`) |

Privacy design for advisor-only MVP:
1. Deterministic math (zero-based, 50/30/20) runs in code — never ask LLM for arithmetic.
2. Default **local-only** (Ollama): explanation/suggestions from categorized totals, no raw export.
3. API is opt-in per request with explicit consent + data-flow log (which fields left machine).
4. Document field-level flow (for future ISO/FINMA-style rigor): `month totals → local`; `prompt text → API only if consented`.
5. Provider-agnostic client (`OPENAI_BASE_URL` env) + LiteLLM-style gateway so local ↔ cloud is one env change.

## Recommendation (one path)

**A + SQLite-file + hybrid-LLM with local default:**
`FastAPI (or Flask) + SQLite (WAL, single file) + server-rendered forms + Ollama
via OpenAI-compatible client; optional cloud API behind explicit opt-in flag.`
Ship `backup`/`restore` scripts, `DATABASE_PATH` env, portable SQL.

Why: fewest services (one process, one file, zero DB bill), fastest solo iteration
on budget math, strongest privacy story (nothing leaves machine by default), and
reversible — SQLite→Postgres and local→API are both afternoon migrations when a
real constraint fires. Choose B (Next.js + SQLite) instead only if polished
mobile PWA is the MVP differentiator and dev is JS-first.

## Sources (primary / first-party where possible)
- Next.js + SQLite single-user patterns: domiciledb README (Next 16, Drizzle, better-sqlite3, WAL, DATA_DIR); afile build log (Next 15, better-sqlite3, FTS5, $6 droplet, `cp` backup); Detweiler PWA+SQLite+Tailscale guide; abhishekchaudhary.com SQLite-vs-Postgres solo-founder (WAL, single-writer rule); dreaming.press decision framework (WAL/Litestream/Turso vs Neon/Supabase).
- DB pricing/quotas: flaviocopes.com DB hosting comparison (Supabase/Neon/Turso/D1/Railway/Fly/DO caps); Ortega Supabase-vs-Neon-vs-Turso-vs-SQLite (single-writer rule, pause/suspend/row-scan caveats); Achron "where data lives" (localStorage vs SQLite vs Postgres homes).
- LLM local-vs-API: CACM on-prem economics (llama.cpp/Ollama vs vLLM, bandwidth-bound, break-even 50–100M tok/mo for 70B); Forfis Swiss-fintech pilot (180–400 ms API vs 50–150 ms local, 92% vs 85–88%, residency decides); apidog local-vs-API (pricing table, break-even ~70K tok/day vs GPT-4o, OpenAI-compatible swap); toolsura/gridex hybrids (sensitivity/confidence routing, LiteLLM/RouteLLM, start-cloud-route-local).
