"""Aktifkan salinan Drive privat melalui persetujuan Google pada komputer operator."""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv, set_key
from filelock import FileLock, Timeout
from psb.app import create_app
from psb.db import all_rows
from psb.drive_sync import (
    DriveClient,
    DriveError,
    drive_credentials,
    participant_folder,
    sync_uploads,
)


def main():
    os.chdir(ROOT)
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("login", "setup", "sync", "status"))
    args = parser.parse_args()
    app = create_app()
    data = Path(app.config["DATA_DIR"])
    with FileLock(str(data / "google-drive.lock"), timeout=0):
        if args.command == "status":
            with app.app_context():
                rows = all_rows(
                    "SELECT state,COUNT(*) AS n FROM drive_objects WHERE upload_id IS NOT NULL GROUP BY state"
                )
                print(json.dumps({r["state"]: r["n"] for r in rows}))
            return
        credentials = drive_credentials(data, login=args.command == "login")
        client = DriveClient(credentials)
        try:
            if args.command in ("login", "setup"):
                client.request("GET", "about", params={"fields": "user(permissionId)"})
                with app.app_context():
                    participants = all_rows(
                        "SELECT p.id,p.number,a.name,a.level,a.year_id,y.name AS year_name FROM participants p JOIN applications a ON a.id=p.application_id JOIN years y ON y.id=a.year_id"
                    )
                    for p in participants:
                        participant_folder(client, p)
                    roots = all_rows(
                        "SELECT web_url FROM drive_objects WHERE participant_id IS NULL AND parent_id IS NULL AND state='ready'"
                    )
                set_key(ROOT / ".env", "GOOGLE_DRIVE_ENABLED", "true")
                print("Izin Drive berhasil. Folder privat per santri siap.")
                for root in roots:
                    if root["web_url"]:
                        print("Folder induk:", root["web_url"])
                print(
                    "Worker yang sudah berjalan akan menyalin versi berkas pada putaran berikutnya (sekitar 60 detik)."
                )
            else:
                with app.app_context():
                    print(json.dumps(sync_uploads(client), ensure_ascii=False))
        finally:
            client.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Koneksi Drive dihentikan.")
    except Timeout:
        print("Sinkronisasi Drive masih berjalan; coba lagi sebentar.")
        sys.exit(1)
    except DriveError as error:
        print("Belum selesai:", error)
        sys.exit(1)
    except Exception as error:
        print(
            f"Drive belum terhubung ({type(error).__name__}). Periksa Drive API, izin Google dan internet. Jangan bagikan isi token/JSON."
        )
        sys.exit(1)
