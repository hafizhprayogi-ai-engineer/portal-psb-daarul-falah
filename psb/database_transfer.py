"""Pemindahan database tanpa mengubah sumber, dengan verifikasi setiap nilai."""

import json
import sqlite3
from pathlib import Path
from .mysql import MySQLConnection, initialize_mysql


def source_tables(source):
    return [
        row[0]
        for row in source.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


def migrate_sqlite(source_path, destination_url):
    source_path = Path(source_path).resolve(strict=True)
    source = sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    try:
        source.execute("BEGIN")
        if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Integritas SQLite tidak lulus; migrasi dibatalkan.")
        if source.execute("PRAGMA foreign_key_check").fetchone():
            raise RuntimeError("Relasi SQLite bermasalah; migrasi dibatalkan.")
        versions = {r[0] for r in source.execute("SELECT version FROM schema_migrations")}
        if versions not in ({1, 2}, {1, 2, 3}):
            raise RuntimeError("Versi SQLite tidak didukung untuk migrasi ini.")
        initialize_mysql(destination_url)
        dest = MySQLConnection(destination_url)
        try:
            tables = source_tables(source)
            counts = {}
            if (
                "drive_objects" not in tables
                and dest.execute("SELECT COUNT(*) AS n FROM drive_objects").fetchone()["n"]
            ):
                raise RuntimeError("Database tujuan sudah berisi data Drive; tidak akan ditimpa.")
            # Pemeriksaan kosong sebelum satu pun data dipindahkan.
            for table in tables:
                if table not in ("schema_migrations", "years", "sequences"):
                    if dest.execute(f"SELECT COUNT(*) AS n FROM `{table}`").fetchone()["n"]:
                        raise RuntimeError("Database tujuan sudah berisi data; tidak akan ditimpa.")
            # Ikuti urutan dependensi FK, bukan mematikan pemeriksaan relasi.
            remaining = set(tables)
            ordered = []
            while remaining:
                ready = sorted(
                    t
                    for t in remaining
                    if {r[2] for r in source.execute(f'PRAGMA foreign_key_list("{t}")')}
                    <= set(ordered)
                )
                if not ready:
                    raise RuntimeError("Relasi siklik tidak didukung.")
                ordered.extend(ready)
                remaining.difference_update(ready)
            dest.begin_write()
            try:
                for table in ordered:
                    columns = [r[1] for r in source.execute(f'PRAGMA table_info("{table}")')]
                    rows = source.execute(f'SELECT * FROM "{table}"').fetchall()
                    names = ",".join("`" + key + "`" for key in columns)
                    placeholders = ",".join("?" for _ in columns)
                    for row in rows:
                        sql = f"INSERT INTO `{table}` ({names}) VALUES({placeholders})"
                        if table in ("schema_migrations", "years", "sequences"):
                            sql += " ON DUPLICATE KEY UPDATE " + ",".join(
                                f"`{key}`=VALUES(`{key}`)" for key in columns
                            )
                        # SQL sudah mengutip nama key; gunakan raw cursor dengan parameter.
                        dest.raw.cursor().execute(sql.replace("?", "%s"), tuple(row))
                    actual = dest.raw.cursor()
                    if table == "schema_migrations":
                        actual.execute(
                            f"SELECT {names} FROM `{table}` WHERE version IN ("
                            + ",".join("%s" for _ in versions)
                            + ")",
                            tuple(sorted(versions)),
                        )
                    else:
                        actual.execute(f"SELECT {names} FROM `{table}`")
                    expected = sorted(json.dumps(list(r), ensure_ascii=False) for r in rows)
                    copied = sorted(
                        json.dumps([r[k] for k in columns], ensure_ascii=False)
                        for r in actual.fetchall()
                    )
                    if expected != copied:
                        raise RuntimeError(f"Verifikasi nilai gagal pada tabel {table}.")
                    counts[table] = len(rows)
                dest.commit()
            except BaseException:
                dest.rollback()
                raise
            return counts
        finally:
            dest.close()
    finally:
        source.close()


def backup_mysql(db, path):
    """Snapshot SQL konsisten, termasuk struktur, data, dan kolom generated."""
    cursor = db.raw.cursor()
    cursor.execute("SHOW FULL TABLES WHERE Table_type='BASE TABLE'")
    tables = [next(iter(row.values())) for row in cursor.fetchall()]
    with Path(path).open("w", encoding="utf-8", newline="\n") as output:
        output.write(
            "-- Cadangan PSB MySQL; impor ke database kosong.\nSET NAMES utf8mb4;\nSET SQL_MODE='NO_AUTO_VALUE_ON_ZERO';\nSET FOREIGN_KEY_CHECKS=0;\n"
        )
        for table in tables:
            cursor.execute(f"SHOW CREATE TABLE `{table}`")
            ddl = cursor.fetchone()["Create Table"]
            output.write(ddl + ";\n")
            cursor.execute(f"SHOW COLUMNS FROM `{table}`")
            columns = [r["Field"] for r in cursor.fetchall() if "GENERATED" not in r["Extra"]]
            names = ",".join("`" + key + "`" for key in columns)
            cursor.execute(f"SELECT {names} FROM `{table}`")
            for row in cursor.fetchall():
                values = ",".join(db.raw.escape(row[key]) for key in columns)
                output.write(f"INSERT INTO `{table}` ({names}) VALUES({values});\n")
        output.write("SET FOREIGN_KEY_CHECKS=1;\n")
