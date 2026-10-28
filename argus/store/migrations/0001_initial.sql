CREATE TABLE IF NOT EXISTS watches (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    region_json TEXT NOT NULL,
    question TEXT NOT NULL,
    template TEXT NOT NULL,
    cadence TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS acquisitions (
    id TEXT PRIMARY KEY,
    watch_id TEXT NOT NULL REFERENCES watches(id),
    sensor TEXT NOT NULL,
    aoi_json TEXT NOT NULL,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    comparison_json TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS receipts (
    id TEXT PRIMARY KEY,
    watch_id TEXT NOT NULL REFERENCES watches(id),
    acquisition_id TEXT REFERENCES acquisitions(id),
    tool TEXT NOT NULL,
    params_json TEXT NOT NULL,
    source_url TEXT NOT NULL,
    data_hash TEXT NOT NULL,
    plot_path TEXT NOT NULL,
    token_usage INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    watch_id TEXT NOT NULL REFERENCES watches(id),
    report_id TEXT,
    title TEXT NOT NULL,
    confidence REAL NOT NULL,
    status TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    decided_at TEXT
);

CREATE TABLE IF NOT EXISTS predictions (
    id TEXT PRIMARY KEY,
    watch_id TEXT NOT NULL REFERENCES watches(id),
    analog_json TEXT,
    expectation_json TEXT NOT NULL,
    outcome TEXT,
    status TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    evaluated_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meta_spend (
    id TEXT PRIMARY KEY,
    operation TEXT NOT NULL,
    model TEXT NOT NULL,
    tokens_in INTEGER NOT NULL,
    tokens_out INTEGER NOT NULL,
    cost_credits REAL NOT NULL,
    created_at TEXT NOT NULL
);
