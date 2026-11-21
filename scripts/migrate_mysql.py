"""Pindahkan SQLite ke MySQL lokal; password diminta tanpa ditampilkan."""

import getpass
import os
import re
import secrets
import shutil
import socket
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pymysql
from dotenv import dotenv_values, set_key
from psb.database_transfer import migrate_sqlite


def main():
    config = dotenv_values(ROOT / ".env")
    if config.get("DATABASE_URL"):
        raise RuntimeError(
            "DATABASE_URL sudah diisi. Migrasi tidak akan diulang atau menimpa database."
        )
    with socket.socket() as probe:
        probe.settimeout(1)
        if probe.connect_ex(("127.0.0.1", int(config.get("PORT") or 5000))) == 0:
            raise RuntimeError(
                "Hentikan server aplikasi dan worker dahulu, lalu jalankan kembali skrip ini."
            )
    data = Path(config.get("DATA_DIR") or ROOT / "instance")
    if not data.is_absolute():
        data = ROOT / data
    source_path = data / "psb.sqlite3"
    if not source_path.is_file():
        raise RuntimeError("Database SQLite sumber tidak ditemukan.")
    host = input("Host MySQL [127.0.0.1]: ").strip() or "127.0.0.1"
    if host not in ("127.0.0.1", "localhost"):
        raise RuntimeError(
            "Skrip ini khusus MySQL di komputer yang sama. Server jarak jauh memerlukan konfigurasi TLS tersendiri."
        )
    port = int(input("Port MySQL [3306]: ").strip() or "3306")
    database = input("Database BARU [psb_daarulfalah]: ").strip() or "psb_daarulfalah"
    if not re.fullmatch(r"[A-Za-z0-9_]{1,60}", database):
        raise RuntimeError("Nama database tidak valid.")
    username = input("Username administrator MySQL [root]: ").strip() or "root"
    password = getpass.getpass("Password MySQL (tidak ditampilkan): ")
    admin = pymysql.connect(
        host=host,
        port=port,
        user=username,
        password=password,
        charset="utf8mb4",
        autocommit=True,
        connect_timeout=10,
    )
    # Sumber tidak diubah. Kunci SQLite mencegah worker lama menulis saat disalin.
    source = sqlite3.connect(source_path, timeout=30, isolation_level=None)
    try:
        cursor = admin.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin"
        )
        cursor.execute(f"SHOW TABLES FROM `{database}`")
        if cursor.fetchone():
            raise RuntimeError(
                "Database tujuan tidak kosong. Pilih nama database baru; data tidak ditimpa."
            )
        source.execute("BEGIN IMMEDIATE")
        backup = data / "backups" / ("sebelum-mysql-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
        backup.mkdir(parents=True)
        with (
            sqlite3.connect(source_path) as reader,
            sqlite3.connect(backup / "psb.sqlite3") as copied,
        ):
            reader.backup(copied)
        if (data / "private").exists():
            shutil.copytree(data / "private", backup / "private")
        if (ROOT / ".env").exists():
            shutil.copy2(ROOT / ".env", backup / "env-sebelumnya.txt")
        runtime_user = "psb_" + secrets.token_hex(5)
        runtime_password = secrets.token_urlsafe(32)
        cursor.execute("CREATE USER %s@%s IDENTIFIED BY %s", (runtime_user, host, runtime_password))
        cursor.execute(
            f"GRANT SELECT,INSERT,UPDATE,DELETE,CREATE,ALTER,INDEX,REFERENCES ON `{database}`.* TO %s@%s",
            (runtime_user, host),
        )
        url = f'mysql://{quote(runtime_user, safe="")}:{quote(runtime_password, safe="")}@{host}:{port}/{database}'
        counts = migrate_sqlite(backup / "psb.sqlite3", url)
        # Konfigurasi berubah hanya setelah semua tabel dan nilai cocok.
        set_key(ROOT / ".env", "DATABASE_URL", url)
        print("Migrasi berhasil; seluruh nilai telah diverifikasi.")
        print("Database di phpMyAdmin:", database)
        print("Jumlah tabel tersalin:", len(counts))
        print("Cadangan SQLite, file privat dan konfigurasi lama:", backup)
        print("Jalankan kembali server aplikasi. Password login wali/petugas tetap sama.")
    finally:
        source.rollback()
        source.close()
        admin.close()


if __name__ == "__main__":
    os.chdir(ROOT)
    try:
        main()
    except (pymysql.MySQLError, RuntimeError, ValueError) as error:
        # Hindari traceback yang dapat memuat kredensial koneksi.
        print("Migrasi belum selesai:", error)
        sys.exit(1)
