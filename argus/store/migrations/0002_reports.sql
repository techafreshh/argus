CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    watch_id TEXT NOT NULL REFERENCES watches(id),
    alert_id TEXT NOT NULL,
    headline TEXT NOT NULL,
    card_json TEXT NOT NULL,
    data_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
