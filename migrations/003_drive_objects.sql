CREATE TABLE IF NOT EXISTS drive_objects (
 item_key TEXT PRIMARY KEY,
 drive_id TEXT UNIQUE NOT NULL,
 upload_id INTEGER UNIQUE REFERENCES uploads(id),
 participant_id INTEGER REFERENCES participants(id),
 parent_id TEXT,
 checksum TEXT,
 state TEXT NOT NULL DEFAULT 'pending',
 web_url TEXT,
 updated_at TEXT NOT NULL
);
INSERT OR IGNORE INTO schema_migrations VALUES(3,datetime('now'));
