-- MySQL 8.0.16+ / MariaDB 10.6+, InnoDB utf8mb4. Pasangan versi SQLite: 1 dan 2.

CREATE TABLE IF NOT EXISTS `schema_migrations` (
  `version` BIGINT PRIMARY KEY,
  `applied_at` LONGTEXT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `years` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `name` VARCHAR(191) NOT NULL,
  UNIQUE (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `settings` (
  `key` VARCHAR(191) PRIMARY KEY,
  `value` LONGTEXT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `sequences` (
  `level` VARCHAR(191) PRIMARY KEY,
  `value` BIGINT NOT NULL,
  CHECK(level IN ('MI','MTS','MA'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `applications` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `year_id` BIGINT NOT NULL DEFAULT 1,
  `reference` VARCHAR(191) NOT NULL,
  `tracking_hash` VARCHAR(191) NOT NULL,
  `level` LONGTEXT NOT NULL,
  `name` LONGTEXT NOT NULL,
  `birth_place` LONGTEXT NOT NULL,
  `birth_date` LONGTEXT NOT NULL,
  `phone` LONGTEXT NOT NULL,
  `email` LONGTEXT NOT NULL,
  `channel` LONGTEXT NOT NULL,
  `status` VARCHAR(255) NOT NULL DEFAULT 'Menunggu pembayaran',
  `created_at` LONGTEXT NOT NULL,
  UNIQUE (`tracking_hash`),
  UNIQUE (`reference`),
  FOREIGN KEY (`year_id`) REFERENCES `years` (`id`),
  CHECK(level IN ('MI','MTS','MA')),
  CHECK(channel IN ('online','langsung'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `rate_limits` (
  `key` VARCHAR(191) PRIMARY KEY,
  `count` BIGINT NOT NULL,
  `reset_at` LONGTEXT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `schedules` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `date` VARCHAR(191) NOT NULL,
  `status` VARCHAR(255) NOT NULL DEFAULT 'Terbuka',
  `reason` LONGTEXT,
  UNIQUE (`date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `participants` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `application_id` BIGINT NOT NULL,
  `number` VARCHAR(191) NOT NULL,
  `bio` LONGTEXT NOT NULL DEFAULT ('{}'),
  `bio_complete` BIGINT NOT NULL DEFAULT 0,
  `locked_at` LONGTEXT,
  `schedule_id` BIGINT,
  `attendance` VARCHAR(255) NOT NULL DEFAULT 'Belum dicatat',
  `draft_result` LONGTEXT,
  `published_result` LONGTEXT,
  `result_version` BIGINT NOT NULL DEFAULT 0,
  `financial_review` BIGINT NOT NULL DEFAULT 0,
  `completed` BIGINT NOT NULL DEFAULT 0,
  UNIQUE (`number`),
  UNIQUE (`application_id`),
  FOREIGN KEY (`schedule_id`) REFERENCES `schedules` (`id`),
  FOREIGN KEY (`application_id`) REFERENCES `applications` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `users` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `username` VARCHAR(191) COLLATE utf8mb4_general_ci NOT NULL,
  `password_hash` LONGTEXT NOT NULL,
  `participant_id` BIGINT,
  `roles` VARCHAR(255) NOT NULL DEFAULT '',
  `active` BIGINT NOT NULL DEFAULT 0,
  UNIQUE (`participant_id`),
  UNIQUE (`username`),
  FOREIGN KEY (`participant_id`) REFERENCES `participants` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `sessions` (
  `token_hash` VARCHAR(191) PRIMARY KEY,
  `user_id` BIGINT NOT NULL,
  `expires_at` LONGTEXT NOT NULL,
  FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `account_tokens` (
  `token_hash` VARCHAR(191) PRIMARY KEY,
  `user_id` BIGINT NOT NULL,
  `kind` LONGTEXT NOT NULL,
  `expires_at` LONGTEXT NOT NULL,
  `used_at` LONGTEXT,
  FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `uploads` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `application_id` BIGINT,
  `participant_id` BIGINT,
  `category` LONGTEXT NOT NULL,
  `filename` LONGTEXT NOT NULL,
  `storage_name` VARCHAR(191) NOT NULL,
  `mime` LONGTEXT NOT NULL,
  `size` BIGINT NOT NULL,
  `replaces` LONGTEXT,
  `reason` LONGTEXT,
  `status` VARCHAR(255) NOT NULL DEFAULT 'Menunggu pemeriksaan',
  `review_note` LONGTEXT,
  `reviewed_by` BIGINT,
  `created_at` LONGTEXT NOT NULL,
  UNIQUE (`storage_name`),
  FOREIGN KEY (`reviewed_by`) REFERENCES `users` (`id`),
  FOREIGN KEY (`participant_id`) REFERENCES `participants` (`id`),
  FOREIGN KEY (`application_id`) REFERENCES `applications` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `fee_versions` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `year_id` BIGINT NOT NULL DEFAULT 1,
  `level` LONGTEXT NOT NULL,
  `components` LONGTEXT NOT NULL,
  `total` BIGINT NOT NULL,
  `created_at` LONGTEXT NOT NULL,
  `created_by` BIGINT,
  FOREIGN KEY (`created_by`) REFERENCES `users` (`id`),
  FOREIGN KEY (`year_id`) REFERENCES `years` (`id`),
  CHECK(total>0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `invoices` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `participant_id` BIGINT NOT NULL,
  `fee_version_id` BIGINT NOT NULL,
  `components` LONGTEXT NOT NULL,
  `total` BIGINT NOT NULL,
  `created_at` LONGTEXT NOT NULL,
  UNIQUE (`participant_id`),
  FOREIGN KEY (`fee_version_id`) REFERENCES `fee_versions` (`id`),
  FOREIGN KEY (`participant_id`) REFERENCES `participants` (`id`),
  CHECK(total>0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `payments` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `application_id` BIGINT NOT NULL,
  `participant_id` BIGINT,
  `kind` LONGTEXT NOT NULL,
  `method` LONGTEXT NOT NULL,
  `amount` BIGINT NOT NULL,
  `status` LONGTEXT NOT NULL,
  `upload_id` BIGINT,
  `reason` LONGTEXT,
  `confirmed_by` BIGINT,
  `idempotency_key` VARCHAR(191) NOT NULL,
  `created_at` LONGTEXT NOT NULL,
  `confirmed_at` LONGTEXT,
  UNIQUE (`idempotency_key`),
  FOREIGN KEY (`confirmed_by`) REFERENCES `users` (`id`),
  FOREIGN KEY (`upload_id`) REFERENCES `uploads` (`id`),
  FOREIGN KEY (`participant_id`) REFERENCES `participants` (`id`),
  FOREIGN KEY (`application_id`) REFERENCES `applications` (`id`),
  CHECK(kind IN ('pendaftaran','daftar_ulang')),
  CHECK(method IN ('tunai','transfer')),
  CHECK(amount>=0),
  `approved_registration` BIGINT GENERATED ALWAYS AS (CASE WHEN kind='pendaftaran' AND status='Disahkan' THEN application_id ELSE NULL END) STORED,
  UNIQUE (`approved_registration`),
  `pending_application` BIGINT GENERATED ALWAYS AS (CASE WHEN status='Menunggu verifikasi' THEN application_id ELSE NULL END) STORED,
  `pending_kind` VARCHAR(191) GENERATED ALWAYS AS (CASE WHEN status='Menunggu verifikasi' THEN kind ELSE NULL END) STORED,
  UNIQUE (`pending_application`,`pending_kind`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `documents` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `participant_id` BIGINT NOT NULL,
  `kind` VARCHAR(191) NOT NULL,
  `version` BIGINT NOT NULL,
  `token` VARCHAR(191) NOT NULL,
  `valid` BIGINT NOT NULL DEFAULT 1,
  `snapshot` LONGTEXT NOT NULL,
  `payment_id` BIGINT,
  `created_at` LONGTEXT NOT NULL,
  UNIQUE (`participant_id`,`kind`,`version`),
  UNIQUE (`token`),
  FOREIGN KEY (`payment_id`) REFERENCES `payments` (`id`),
  FOREIGN KEY (`participant_id`) REFERENCES `participants` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `audit` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `actor_id` BIGINT,
  `entity` LONGTEXT NOT NULL,
  `entity_id` BIGINT,
  `action` LONGTEXT NOT NULL,
  `old_value` LONGTEXT,
  `new_value` LONGTEXT,
  `reason` LONGTEXT,
  `created_at` LONGTEXT NOT NULL,
  FOREIGN KEY (`actor_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `outbox` (
  `id` VARCHAR(191) PRIMARY KEY,
  `event_key` VARCHAR(191) NOT NULL,
  `participant_id` BIGINT,
  `application_id` BIGINT,
  `channel` VARCHAR(191) NOT NULL,
  `destination` LONGTEXT NOT NULL,
  `message` LONGTEXT NOT NULL,
  `payload` LONGTEXT NOT NULL,
  `status` VARCHAR(255) NOT NULL DEFAULT 'menunggu',
  `attempts` BIGINT NOT NULL DEFAULT 0,
  `next_attempt_at` LONGTEXT NOT NULL,
  `claimed_at` LONGTEXT,
  `delivery_id` LONGTEXT,
  `last_error` LONGTEXT,
  `created_at` LONGTEXT NOT NULL,
  UNIQUE (`event_key`,`channel`),
  FOREIGN KEY (`application_id`) REFERENCES `applications` (`id`),
  FOREIGN KEY (`participant_id`) REFERENCES `participants` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `delivery_attempts` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `event_id` VARCHAR(191) NOT NULL,
  `status` LONGTEXT NOT NULL,
  `detail` LONGTEXT,
  `created_at` LONGTEXT NOT NULL,
  FOREIGN KEY (`event_id`) REFERENCES `outbox` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `operations` (
  `key` VARCHAR(191) PRIMARY KEY,
  `actor_id` BIGINT,
  `created_at` LONGTEXT NOT NULL,
  FOREIGN KEY (`actor_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `delivery_claims` (
  `event_id` VARCHAR(191) NOT NULL,
  `attempt` BIGINT NOT NULL,
  `claimed_at` LONGTEXT NOT NULL,
  PRIMARY KEY (`event_id`,`attempt`),
  FOREIGN KEY (`event_id`) REFERENCES `outbox` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

INSERT INTO years VALUES(1,'2027/2028');

INSERT INTO sequences VALUES('MI',0),('MTS',0),('MA',0);

CREATE TABLE IF NOT EXISTS psb_write_lock (id BIGINT PRIMARY KEY) ENGINE=InnoDB;

INSERT INTO psb_write_lock VALUES(1);

INSERT INTO schema_migrations VALUES(1,'mysql-schema-v1'),(2,'mysql-schema-v1');
