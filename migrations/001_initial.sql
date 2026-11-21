PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS years(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
INSERT OR IGNORE INTO years VALUES(1,'2027/2028');
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sequences(level TEXT PRIMARY KEY CHECK(level IN ('MI','MTS','MA')), value INTEGER NOT NULL);
INSERT OR IGNORE INTO sequences VALUES('MI',0),('MTS',0),('MA',0);
CREATE TABLE IF NOT EXISTS applications(
 id INTEGER PRIMARY KEY, year_id INTEGER NOT NULL DEFAULT 1 REFERENCES years(id), reference TEXT UNIQUE NOT NULL,
 tracking_hash TEXT UNIQUE NOT NULL, level TEXT NOT NULL CHECK(level IN ('MI','MTS','MA')),
 name TEXT NOT NULL, birth_place TEXT NOT NULL, birth_date TEXT NOT NULL, phone TEXT NOT NULL, email TEXT NOT NULL,
 channel TEXT NOT NULL CHECK(channel IN ('online','langsung')), status TEXT NOT NULL DEFAULT 'Menunggu pembayaran', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS participants(
 id INTEGER PRIMARY KEY, application_id INTEGER UNIQUE NOT NULL REFERENCES applications(id), number TEXT UNIQUE NOT NULL,
 bio TEXT NOT NULL DEFAULT '{}', bio_complete INTEGER NOT NULL DEFAULT 0, locked_at TEXT, schedule_id INTEGER REFERENCES schedules(id),
 attendance TEXT NOT NULL DEFAULT 'Belum dicatat', draft_result TEXT, published_result TEXT, result_version INTEGER NOT NULL DEFAULT 0,
 financial_review INTEGER NOT NULL DEFAULT 0, completed INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS users(
 id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL COLLATE NOCASE, password_hash TEXT NOT NULL,
 participant_id INTEGER UNIQUE REFERENCES participants(id), roles TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS account_tokens(token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), kind TEXT NOT NULL, expires_at TEXT NOT NULL, used_at TEXT);
CREATE TABLE IF NOT EXISTS rate_limits(key TEXT PRIMARY KEY, count INTEGER NOT NULL, reset_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS schedules(id INTEGER PRIMARY KEY, date TEXT UNIQUE NOT NULL, status TEXT NOT NULL DEFAULT 'Terbuka', reason TEXT);
CREATE TABLE IF NOT EXISTS uploads(
 id INTEGER PRIMARY KEY, application_id INTEGER REFERENCES applications(id), participant_id INTEGER REFERENCES participants(id),
 category TEXT NOT NULL, filename TEXT NOT NULL, storage_name TEXT NOT NULL UNIQUE, mime TEXT NOT NULL, size INTEGER NOT NULL,
 replaces TEXT, reason TEXT, status TEXT NOT NULL DEFAULT 'Menunggu pemeriksaan', review_note TEXT, reviewed_by INTEGER REFERENCES users(id), created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS fee_versions(
 id INTEGER PRIMARY KEY, year_id INTEGER NOT NULL DEFAULT 1 REFERENCES years(id), level TEXT NOT NULL, components TEXT NOT NULL,
 total INTEGER NOT NULL CHECK(total>0), created_at TEXT NOT NULL, created_by INTEGER REFERENCES users(id));
CREATE TABLE IF NOT EXISTS invoices(
 id INTEGER PRIMARY KEY, participant_id INTEGER UNIQUE NOT NULL REFERENCES participants(id), fee_version_id INTEGER NOT NULL REFERENCES fee_versions(id),
 components TEXT NOT NULL, total INTEGER NOT NULL CHECK(total>0), created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS payments(
 id INTEGER PRIMARY KEY, application_id INTEGER NOT NULL REFERENCES applications(id), participant_id INTEGER REFERENCES participants(id),
 kind TEXT NOT NULL CHECK(kind IN ('pendaftaran','daftar_ulang')), method TEXT NOT NULL CHECK(method IN ('tunai','transfer')),
 amount INTEGER NOT NULL CHECK(amount>=0), status TEXT NOT NULL, upload_id INTEGER REFERENCES uploads(id),
 reason TEXT, confirmed_by INTEGER REFERENCES users(id), idempotency_key TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL, confirmed_at TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS one_registration_payment ON payments(application_id) WHERE kind='pendaftaran' AND status='Disahkan';
CREATE UNIQUE INDEX IF NOT EXISTS one_pending_payment ON payments(application_id,kind) WHERE status='Menunggu verifikasi';
CREATE TABLE IF NOT EXISTS documents(
 id INTEGER PRIMARY KEY, participant_id INTEGER NOT NULL REFERENCES participants(id), kind TEXT NOT NULL,
 version INTEGER NOT NULL, token TEXT UNIQUE NOT NULL, valid INTEGER NOT NULL DEFAULT 1, snapshot TEXT NOT NULL,
 payment_id INTEGER REFERENCES payments(id), created_at TEXT NOT NULL,
 UNIQUE(participant_id,kind,version));
CREATE TABLE IF NOT EXISTS audit(
 id INTEGER PRIMARY KEY, actor_id INTEGER REFERENCES users(id), entity TEXT NOT NULL, entity_id INTEGER,
 action TEXT NOT NULL, old_value TEXT, new_value TEXT, reason TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS outbox(
 id TEXT PRIMARY KEY, event_key TEXT NOT NULL, participant_id INTEGER REFERENCES participants(id), application_id INTEGER REFERENCES applications(id),
 channel TEXT NOT NULL, destination TEXT NOT NULL, message TEXT NOT NULL, payload TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'menunggu', attempts INTEGER NOT NULL DEFAULT 0, next_attempt_at TEXT NOT NULL,
 claimed_at TEXT, delivery_id TEXT, last_error TEXT, created_at TEXT NOT NULL, UNIQUE(event_key,channel));
CREATE TABLE IF NOT EXISTS delivery_attempts(id INTEGER PRIMARY KEY, event_id TEXT NOT NULL REFERENCES outbox(id), status TEXT NOT NULL, detail TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS operations(key TEXT PRIMARY KEY, actor_id INTEGER REFERENCES users(id), created_at TEXT NOT NULL);
INSERT OR IGNORE INTO schema_migrations VALUES(1,datetime('now'));
