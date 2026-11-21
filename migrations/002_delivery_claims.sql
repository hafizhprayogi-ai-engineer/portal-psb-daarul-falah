CREATE TABLE IF NOT EXISTS delivery_claims (
 event_id TEXT NOT NULL REFERENCES outbox(id),
 attempt INTEGER NOT NULL,
 claimed_at TEXT NOT NULL,
 PRIMARY KEY(event_id, attempt)
);
INSERT OR IGNORE INTO schema_migrations VALUES(2,datetime('now'));
