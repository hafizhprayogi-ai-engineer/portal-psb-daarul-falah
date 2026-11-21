CREATE TABLE IF NOT EXISTS drive_objects (
 item_key VARCHAR(191) PRIMARY KEY,
 drive_id VARCHAR(191) UNIQUE NOT NULL,
 upload_id BIGINT UNIQUE,
 participant_id BIGINT,
 parent_id VARCHAR(191),
 checksum VARCHAR(64),
 state VARCHAR(32) NOT NULL DEFAULT 'pending',
 web_url LONGTEXT,
 updated_at VARCHAR(40) NOT NULL,
 FOREIGN KEY(upload_id) REFERENCES uploads(id),
 FOREIGN KEY(participant_id) REFERENCES participants(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
INSERT INTO schema_migrations VALUES(3,'drive-objects-v3');
