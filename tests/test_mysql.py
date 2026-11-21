"""Pengujian MySQL nyata opsional; tidak mengakses database operasional."""

import hashlib
import secrets
from urllib.parse import urlsplit, urlunsplit

import pymysql
import pytest
from flask import g
from werkzeug.security import generate_password_hash

from psb.app import create_app
from psb.db import execute, one, transaction, get_db
from psb.domain import save_bio
from psb.mysql import translate_sql, connection_options
from psb.database_transfer import migrate_sqlite, backup_mysql
from conftest import PASSWORD, login_as
from test_system import paid_participant, BIO


def test_parameter_translation_and_literal_protection():
    result = translate_sql("SELECT key FROM settings WHERE key=? AND value LIKE '%?key%'")
    assert result == "SELECT `key` FROM settings WHERE `key`=%s AND value LIKE '%%?key%%'"
    assert "ON DUPLICATE KEY UPDATE" in translate_sql("INSERT OR IGNORE INTO outbox(id) VALUES(?)")
    assert "DELETE" not in translate_sql("INSERT OR REPLACE INTO settings VALUES(?,?)")
    with pytest.raises(ValueError):
        connection_options("mysql://user@localhost/unsafe-name")


def test_migration_from_sqlite_version_two(mysql_database, tmp_path):
    if not mysql_database:
        pytest.skip("PSB_TEST_MYSQL_URL tidak diisi.")
    import sqlite3
    from pathlib import Path

    source = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(source)
    root = Path(__file__).resolve().parents[1]
    for path in sorted((root / "migrations").glob("*.sql"))[:2]:
        connection.executescript(path.read_text(encoding="utf-8"))
    connection.close()
    counts = migrate_sqlite(source, mysql_database)
    assert counts["schema_migrations"] == 2
    connection = pymysql.connect(**connection_options(mysql_database))
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT version FROM schema_migrations")
        assert {r["version"] for r in cursor.fetchall()} == {1, 2, 3}
    finally:
        connection.close()


def test_mysql_schema_upgrade_from_v2_preserves_existing_settings(mysql_database):
    if not mysql_database:
        pytest.skip("PSB_TEST_MYSQL_URL tidak diisi.")
    from pathlib import Path
    from psb.mysql import initialize_mysql

    connection = pymysql.connect(**connection_options(mysql_database))
    try:
        cursor = connection.cursor()
        schema = Path(__file__).resolve().parents[1] / "migrations/mysql/001_schema.sql"
        for statement in schema.read_text(encoding="utf-8").split(";"):
            if statement.strip():
                cursor.execute(statement)
        cursor.execute(
            "INSERT INTO settings (`key`,value) VALUES('upgrade-test','tetap tersimpan')"
        )
        initialize_mysql(mysql_database)
        initialize_mysql(mysql_database)
        cursor.execute("SELECT version FROM schema_migrations")
        assert {r["version"] for r in cursor.fetchall()} == {1, 2, 3}
        cursor.execute("SELECT value FROM settings WHERE `key`='upgrade-test'")
        assert cursor.fetchone()["value"] == "tetap tersimpan"
    finally:
        connection.close()


def test_mysql_migration_backup_restore_and_login(mysql_database, tmp_path):
    if not mysql_database:
        pytest.skip("PSB_TEST_MYSQL_URL tidak diisi.")
    source_path = tmp_path / "source.sqlite3"
    source_app = create_app(
        dict(
            TESTING=True,
            SECRET_KEY="test-only",
            DATA_DIR=str(tmp_path),
            DATABASE=str(source_path),
            DATABASE_URL="",
            UPLOAD_DIR=str(tmp_path / "private"),
            BASE_URL="http://localhost",
        )
    )
    with source_app.app_context():
        with transaction():
            execute(
                "INSERT INTO users(username,password_hash,roles,active) VALUES(?,?,'admin,bendahara,pemberkasan',1)",
                ("rangkap", generate_password_hash(PASSWORD)),
            )
            g.user = one("SELECT * FROM users WHERE username='rangkap'")
            pid, _, _ = paid_participant(account=True)
            save_bio(pid, {**BIO, "name": "Contoh O'Nama; 100% 🏫", "nik": "0000000000000001"})
            token = one("SELECT token FROM documents")["token"]
            hashed = one("SELECT password_hash FROM users WHERE username='rangkap'")[
                "password_hash"
            ]
    before = hashlib.sha256(source_path.read_bytes()).hexdigest()
    counts = migrate_sqlite(source_path, mysql_database)
    assert counts["participants"] == 1 and counts["payments"] == 1 and counts["audit"] > 0
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == before
    app = create_app(
        dict(
            TESTING=True,
            SECRET_KEY="test-only",
            DATA_DIR=str(tmp_path),
            DATABASE_URL=mysql_database,
            UPLOAD_DIR=str(tmp_path / "private"),
            BASE_URL="http://localhost",
            NOTIFICATION_MODE="simulation",
        )
    )
    dump = tmp_path / "mysql.sql"
    with app.app_context():
        assert (
            one("SELECT password_hash FROM users WHERE username='rangkap'")["password_hash"]
            == hashed
        )
        with transaction():
            backup_mysql(get_db(), dump)
    client = app.test_client()
    login_as(app, client, "rangkap")
    assert client.get("/dashboard").status_code == 200
    assert client.get(f"/peserta/{pid}/menu/biodata/santri").status_code == 200
    assert client.get("/verifikasi/" + token).status_code == 200
    with pytest.raises(RuntimeError, match="sudah berisi"):
        migrate_sqlite(source_path, mysql_database)
    options = connection_options(mysql_database)
    options.pop("database")
    options["client_flag"] = pymysql.constants.CLIENT.MULTI_STATEMENTS
    admin = pymysql.connect(**options)
    restored_name = "psb_test_restore_" + secrets.token_hex(8)
    try:
        cursor = admin.cursor()
        cursor.execute(
            f"CREATE DATABASE `{restored_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin"
        )
        admin.select_db(restored_name)
        cursor.execute(dump.read_text(encoding="utf-8"))
        while cursor.nextset():
            pass
        cursor.execute("SELECT COUNT(*) AS n FROM participants")
        assert cursor.fetchone()["n"] == 1
        cursor.execute("SELECT name FROM applications")
        assert cursor.fetchone()["name"] == "Contoh O'Nama; 100% 🏫"
        restored_url = urlunsplit(urlsplit(mysql_database)._replace(path="/" + restored_name))
        restored = create_app(
            dict(
                TESTING=True,
                SECRET_KEY="test-only",
                DATA_DIR=str(tmp_path),
                DATABASE_URL=restored_url,
                UPLOAD_DIR=str(tmp_path / "private"),
            )
        )
        assert restored.test_client().get("/verifikasi/" + token).status_code == 200
    finally:
        admin.cursor().execute(f"DROP DATABASE IF EXISTS `{restored_name}`")
        admin.close()


def test_mysql_conditional_unique_constraints(ctx):
    if not ctx.config.get("DATABASE_URL"):
        pytest.skip("Batasan generated column khusus MySQL.")
    with transaction():
        pid, aid, _ = paid_participant()
        payment = one("SELECT * FROM payments WHERE participant_id=?", (pid,))
    with pytest.raises(pymysql.IntegrityError):
        with transaction():
            execute(
                "INSERT INTO payments(application_id,kind,method,amount,status,idempotency_key,created_at) VALUES(?,'pendaftaran','tunai',200000,'Disahkan',?,?)",
                (payment["application_id"], secrets.token_hex(16), payment["created_at"]),
            )


def test_interactive_migration_uses_dedicated_account(mysql_database, tmp_path, monkeypatch):
    if not mysql_database:
        pytest.skip("PSB_TEST_MYSQL_URL tidak diisi.")
    import importlib.util
    from pathlib import Path
    from dotenv import dotenv_values

    options = connection_options(mysql_database)
    if options["host"] != "127.0.0.1":
        pytest.skip("Skrip interaktif lokal diuji pada loopback.")
    data = tmp_path / "instance"
    create_app(
        dict(
            TESTING=True,
            SECRET_KEY="test",
            DATABASE=str(data / "psb.sqlite3"),
            DATABASE_URL="",
            DATA_DIR=str(data),
            UPLOAD_DIR=str(data / "private"),
        )
    )
    (tmp_path / ".env").write_text("DATA_DIR=instance\nPORT=59998\n", encoding="utf-8")
    spec = importlib.util.spec_from_file_location(
        "migration_cli_test", Path(__file__).resolve().parents[1] / "scripts/migrate_mysql.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    inputs = iter(["127.0.0.1", str(options["port"]), options["database"], options["user"]])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))
    monkeypatch.setattr(module.getpass, "getpass", lambda prompt: options["password"])
    module.main()
    config = dotenv_values(tmp_path / ".env")
    runtime = connection_options(config["DATABASE_URL"])
    assert runtime["user"].startswith("psb_") and runtime["user"] != options["user"]
    runtime_app = create_app(
        dict(
            TESTING=True,
            SECRET_KEY="test",
            DATABASE_URL=config["DATABASE_URL"],
            DATA_DIR=str(data),
            UPLOAD_DIR=str(data / "private"),
        )
    )
    assert runtime_app.test_client().get("/health").status_code == 200
    assert list((data / "backups").glob("*/psb.sqlite3"))
    connection = pymysql.connect(**options)
    try:
        connection.cursor().execute("DROP USER %s@%s", (runtime["user"], runtime["host"]))
    finally:
        connection.close()
