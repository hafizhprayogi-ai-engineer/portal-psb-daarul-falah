"""Adaptor MySQL/MariaDB; SQL bisnis tetap memakai parameter, bukan interpolasi."""

import re
from decimal import Decimal
from urllib.parse import urlsplit, unquote

import pymysql


def integer_decimal(value):
    number = Decimal(value)
    if number != number.to_integral_value():
        raise ValueError("Nilai database harus berupa integer rupiah.")
    return int(number)


def connection_options(url):
    parsed = urlsplit(url)
    if parsed.scheme not in ("mysql", "mysql+pymysql", "mariadb"):
        raise ValueError("DATABASE_URL harus memakai mysql:// atau mariadb://.")
    if parsed.query or parsed.fragment:
        raise ValueError(
            "Parameter tambahan DATABASE_URL belum didukung; jangan menganggap TLS sudah dikonfigurasi melalui URL."
        )
    database = unquote(parsed.path.lstrip("/"))
    if not re.fullmatch(r"[A-Za-z0-9_]+", database):
        raise ValueError("Nama database hanya boleh huruf, angka dan garis bawah.")
    return dict(
        host=parsed.hostname or "127.0.0.1",
        port=parsed.port or 3306,
        user=unquote(parsed.username or ""),
        password=unquote(parsed.password or ""),
        database=database,
        charset="utf8mb4",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
        read_timeout=60,
        write_timeout=60,
        conv={
            **pymysql.converters.conversions,
            pymysql.constants.FIELD_TYPE.NEWDECIMAL: integer_decimal,
        },
    )


def translate_sql(sql):
    """Terjemahkan subset SQL aplikasi; jangan ubah literal atau nilai parameter."""
    sql = re.sub(
        r"date\(([at]\.created_at),'\+7 hours'\)",
        r"DATE_FORMAT(DATE_ADD(CAST(REPLACE(LEFT(\1,19),'T',' ') AS DATETIME), INTERVAL 7 HOUR),'%Y-%m-%d')",
        sql,
    )
    ignore_table = None
    if sql.startswith("INSERT OR IGNORE INTO "):
        ignore_table = sql.split()[4].split("(")[0]
        sql = sql.replace("INSERT OR IGNORE INTO", "INSERT INTO", 1)
    replace_table = None
    if sql.startswith("INSERT OR REPLACE INTO "):
        replace_table = sql.split()[4].split("(")[0]
        sql = sql.replace("INSERT OR REPLACE INTO", "INSERT INTO", 1)
    tokens = re.findall(
        r"`[^`]*`|'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|[A-Za-z_][A-Za-z_0-9]*|\?|.", sql, re.S
    )
    output = []
    for token in tokens:
        if token == "?":
            output.append("%s")
        elif token.lower() == "key":
            output.append("`key`")
        else:
            output.append(token.replace("%", "%%"))
    sql = "".join(output)
    if ignore_table:
        primary = {"outbox": "id", "delivery_claims": "event_id"}[ignore_table]
        sql += f" ON DUPLICATE KEY UPDATE `{primary}`=`{primary}`"
    if replace_table:
        columns = {"settings": ("value",), "rate_limits": ("count", "reset_at")}[replace_table]
        sql += " ON DUPLICATE KEY UPDATE " + ",".join(f"`{key}`=VALUES(`{key}`)" for key in columns)
    return sql


class MySQLConnection:
    def __init__(self, url):
        self.raw = pymysql.connect(**connection_options(url))
        self.raw.cursor().execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
        self.raw.cursor().execute(
            "SET SESSION sql_mode='STRICT_ALL_TABLES,NO_AUTO_VALUE_ON_ZERO,NO_ENGINE_SUBSTITUTION'"
        )

    def execute(self, sql, args=()):
        cursor = self.raw.cursor()
        cursor.execute(translate_sql(sql), args)
        return cursor

    def begin_write(self):
        self.raw.begin()
        # Setara dengan satu penulis BEGIN IMMEDIATE SQLite. Kunci terlepas pada
        # commit/rollback dan tetap melindungi alur nomor, uang serta outbox.
        try:
            row = self.execute("SELECT id FROM psb_write_lock WHERE id=1 FOR UPDATE").fetchone()
            if not row:
                raise RuntimeError("Kunci transaksi database tidak tersedia.")
        except BaseException:
            self.raw.rollback()
            raise

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()


def initialize_mysql(url):
    from pathlib import Path

    db = MySQLConnection(url)
    try:
        cursor = db.raw.cursor()
        cursor.execute(
            "SELECT GET_LOCK(CONCAT(LEFT(DATABASE(),40), ':psb-schema'), 30) AS acquired"
        )
        if cursor.fetchone()["acquired"] != 1:
            raise RuntimeError("Migrasi database sedang berjalan. Coba lagi.")
        try:
            cursor.execute("SHOW TABLES LIKE 'schema_migrations'")
            if cursor.fetchone():
                cursor.execute("SELECT version FROM schema_migrations")
                versions = {row["version"] for row in cursor.fetchall()}
                if versions == {1, 2, 3}:
                    return
                if versions == {1, 2}:
                    path = Path(__file__).parent.parent / "migrations/mysql/003_drive_objects.sql"
                    for statement in path.read_text(encoding="utf-8").split(";"):
                        if statement.strip():
                            cursor.execute(statement)
                    return
                raise RuntimeError(
                    "Skema MySQL belum lengkap atau versinya tidak didukung. Gunakan database kosong baru."
                )
            cursor.execute("SHOW TABLES")
            if cursor.fetchone():
                raise RuntimeError("Database tujuan harus kosong; tabel lain tidak akan ditimpa.")
            # DDL MySQL autocommit; kegagalan awal memerlukan database kosong baru.
            schema = Path(__file__).parent.parent / "migrations/mysql/001_schema.sql"
            for statement in schema.read_text(encoding="utf-8").split(";"):
                if statement.strip():
                    cursor.execute(statement)
            path = schema.parent / "003_drive_objects.sql"
            for statement in path.read_text(encoding="utf-8").split(";"):
                if statement.strip():
                    cursor.execute(statement)
        finally:
            cursor.execute("SELECT RELEASE_LOCK(CONCAT(LEFT(DATABASE(),40), ':psb-schema'))")
    finally:
        db.close()
