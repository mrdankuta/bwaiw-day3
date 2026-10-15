-- On-device month grain. Mirrors the server store: one month row plus its
-- expenses, plus the suggestions log. Single user, single device.
CREATE TABLE IF NOT EXISTS months (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    currency TEXT NOT NULL DEFAULT 'NGN',
    income_cents INTEGER NOT NULL DEFAULT 0,
    side_cents INTEGER NOT NULL DEFAULT 0,
    rollover_cents INTEGER NOT NULL DEFAULT 0,
    savings_goal_cents INTEGER NOT NULL DEFAULT 0,
    emergency_saved_cents INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month_id INTEGER NOT NULL REFERENCES months(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    fixed INTEGER NOT NULL DEFAULT 0,
    one_off INTEGER NOT NULL DEFAULT 0,
    debt INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS suggestions_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month_id INTEGER NOT NULL REFERENCES months(id) ON DELETE CASCADE,
    backend TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    model_version TEXT NOT NULL,
    prompt TEXT NOT NULL DEFAULT '',
    data_flow TEXT NOT NULL DEFAULT '',
    output TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
