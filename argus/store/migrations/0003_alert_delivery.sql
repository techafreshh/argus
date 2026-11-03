-- Operator notification channels and the per-attempt delivery ledger.
-- channels.watch_id NULL means the channel is global (receives every approval).
CREATE TABLE IF NOT EXISTS channels (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL DEFAULT 'webhook',
    target TEXT NOT NULL,
    secret TEXT NOT NULL DEFAULT '',
    watch_id TEXT REFERENCES watches(id),
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL
);

-- deliveries is a ledger: channel_id is intentionally NOT a foreign key so
-- deleting a channel can never rewrite delivery history. alert_id is NULL
-- for channel test-fires (no alert involved).
CREATE TABLE IF NOT EXISTS deliveries (
    id TEXT PRIMARY KEY,
    alert_id TEXT REFERENCES alerts(id),
    channel_id TEXT NOT NULL,
    status TEXT NOT NULL,
    http_status INTEGER,
    error TEXT NOT NULL DEFAULT '',
    attempts INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
