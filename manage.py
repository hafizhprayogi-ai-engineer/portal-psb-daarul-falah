"""Perintah pemeliharaan lokal; kredensial tidak disimpan di repositori."""

import argparse
import getpass
import json
import secrets
import shutil
import sqlite3
from pathlib import Path
from flask import g
from werkzeug.security import generate_password_hash
from psb.app import create_app
from psb.db import execute, one, all_rows, transaction, now, get_db
from psb.domain import new_application, create_payment, approve_payment
from psb.notifications import queue_reminders, process_outbox


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=["init", "admin", "demo", "worker", "reminders", "backup", "notifications"],
    )
    parser.add_argument("--username", default="admin")
    parser.add_argument("--output", default="backups")
    args = parser.parse_args()
    app = create_app()
    with app.app_context():
        g.user = None
        if args.command == "init":
            print(
                "Migrasi selesai. Backend:",
                "MySQL/MariaDB" if app.config.get("DATABASE_URL") else "SQLite",
            )
        elif args.command == "admin":
            pwd = getpass.getpass("Kata sandi Admin Utama (minimal 12 karakter): ")
            if len(pwd) < 12:
                raise SystemExit("Kata sandi terlalu pendek.")
            with transaction():
                execute(
                    "INSERT INTO users(username,password_hash,roles,active) VALUES(?,?,'admin',1)",
                    (args.username, generate_password_hash(pwd)),
                )
            print("Admin dibuat. Tambahkan peran transaksi secara eksplisit bila diperlukan.")
        elif args.command == "demo":
            if one("SELECT id FROM users LIMIT 1"):
                raise SystemExit("Demo hanya untuk database kosong. Gunakan DATA_DIR terpisah.")
            password = secrets.token_urlsafe(16)
            credentials = []
            with transaction():
                for name, roles in [
                    ("admin.demo", "admin"),
                    ("bendahara.demo", "bendahara"),
                    ("berkas.demo", "pemberkasan"),
                    ("rangkap.demo", "admin,bendahara,pemberkasan"),
                ]:
                    execute(
                        "INSERT INTO users(username,password_hash,roles,active) VALUES(?,?,?,1)",
                        (name, generate_password_hash(password), roles),
                    )
                    credentials.append(name)
                g.user = one("SELECT * FROM users WHERE username='bendahara.demo'")
                execute("INSERT INTO settings VALUES('demo','ya')")
                for level, name in [
                    ("MI", "Santri Contoh A"),
                    ("MTS", "Santri Contoh B"),
                    ("MA", "Santri Contoh C"),
                ]:
                    aid, _ = new_application(
                        {
                            "level": level,
                            "name": name,
                            "birth_place": "Kota Contoh",
                            "birth_date": "2015-04-12",
                            "phone": "6280000000000",
                            "email": "wali@example.test",
                        },
                        "langsung",
                    )
                    pay = create_payment(aid, "pendaftaran", "tunai", 200000, secrets.token_hex(16))
                    pid = approve_payment(pay)
                    p = one("SELECT * FROM participants WHERE id=?", (pid,))
                    execute(
                        "INSERT INTO users(username,password_hash,participant_id,active) VALUES(?,?,?,1)",
                        (p["number"], generate_password_hash(password), pid),
                    )
                    credentials.append(p["number"])
            path = Path(app.config["DATA_DIR"]) / "akun-demo.txt"
            path.write_text(
                "HANYA DATA FIKTIF LOKAL\nPassword seluruh akun: "
                + password
                + "\n\n"
                + "\n".join(credentials),
                encoding="utf-8",
            )
            print("Data demo dibuat. Kredensial acak tersimpan lokal:", path)
        elif args.command == "worker":
            print("Kejadian diproses:", process_outbox(app))
        elif args.command == "reminders":
            queue_reminders()
            print("Pengingat yang memenuhi jadwal ditambahkan.")
        elif args.command == "notifications":
            for row in all_rows(
                "SELECT channel,status,message FROM outbox ORDER BY created_at DESC LIMIT 30"
            ):
                print(f"[{row['channel']} / {row['status']}] {row['message']}")
        elif args.command == "backup":
            target = Path(args.output) / now().replace(":", "-")
            target.mkdir(parents=True)
            # Kunci penulis juga menghindari snapshot metadata yang tak cocok dengan unggahan.
            with transaction():
                if app.config.get("DATABASE_URL"):
                    from psb.database_transfer import backup_mysql

                    backup_mysql(get_db(), target / "psb.sql")
                else:
                    source = sqlite3.connect(app.config["DATABASE"])
                    dest = sqlite3.connect(target / "psb.sqlite3")
                    source.backup(dest)
                    source.close()
                    dest.close()
                shutil.copytree(app.config["UPLOAD_DIR"], target / "private")
            print("Cadangan selesai:", target)


if __name__ == "__main__":
    main()
