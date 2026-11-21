"""Login, periksa rencana, atau salin biodata ke Google Sheets."""

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from dotenv import dotenv_values
from filelock import FileLock, Timeout
from psb.sheets_sync import SheetsClient, SheetsError, credentials_for, snapshot_participants


def load_credentials(data_dir, login=False, watch=False):
    from google.auth.exceptions import TransportError
    from requests.exceptions import RequestException

    while True:
        try:
            return credentials_for(data_dir, login=login)
        except (TransportError, RequestException):
            if not watch:
                raise
            print(
                "Internet belum siap untuk login tersimpan. Dicoba kembali dalam 60 detik.",
                flush=True,
            )
            time.sleep(60)


def sync_drive_if_enabled(app, data_dir):
    if dotenv_values(ROOT / ".env").get("GOOGLE_DRIVE_ENABLED", "").lower() != "true":
        return
    from psb.drive_sync import DriveClient, DriveError, drive_credentials, sync_uploads

    try:
        with FileLock(str(data_dir / "google-drive.lock"), timeout=0):
            client = DriveClient(drive_credentials(data_dir))
            try:
                with app.app_context():
                    result = sync_uploads(client)
                print("Salinan Drive privat:", json.dumps(result), flush=True)
            finally:
                client.close()
    except Timeout:
        pass
    except (DriveError, SheetsError) as error:
        print("Salinan Drive belum selesai:", error, flush=True)
    except Exception as error:
        print(
            f"Salinan Drive belum selesai ({type(error).__name__}); file utama tetap tersimpan. Coba lagi pada putaran berikutnya.",
            flush=True,
        )


def main():
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("login", "preview", "sync", "setup-tests"))
    parser.add_argument(
        "--watch", action="store_true", help="Ulangi setiap 60 detik; biarkan terminal terbuka."
    )
    args = parser.parse_args()
    os.chdir(ROOT)
    data_dir = Path(os.getenv("DATA_DIR") or ROOT / "instance").resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    spreadsheet_id = os.getenv("GOOGLE_SHEETS_ID", "").strip()
    if not spreadsheet_id:
        raise SheetsError("GOOGLE_SHEETS_ID belum diisi di .env lokal.")
    if args.watch and args.command != "sync":
        raise SheetsError("--watch hanya tersedia untuk perintah sync.")
    with FileLock(str(data_dir / "google-sheets.lock"), timeout=0):
        credentials = load_credentials(data_dir, login=args.command == "login", watch=args.watch)
        client = SheetsClient(credentials, spreadsheet_id)
        try:
            if args.command == "setup-tests":
                client.setup_test_sheet()
                print("Tab Jadwal Tes siap; tab MI/MTS/MA tetap dipertahankan.")
                return
            if args.command == "login":
                metadata = client.metadata()
                titles = [s["properties"]["title"] for s in metadata["sheets"]]
                print("Login dan akses baca spreadsheet berhasil. Tab:", ", ".join(titles))
                print("Belum menulis data. Berikutnya jalankan perintah preview.")
                return
            from psb.app import create_app

            app = create_app()
            while True:
                try:
                    with app.app_context():
                        participants = snapshot_participants()
                    result = client.sync(participants, apply=args.command == "sync")
                    print(
                        "Sinkronisasi selesai."
                        if args.command == "sync"
                        else "Rencana saja; belum ada penulisan."
                    )
                    print(json.dumps(result, ensure_ascii=False), flush=True)
                    if args.command == "sync":
                        sync_drive_if_enabled(app, data_dir)
                except SheetsError as error:
                    print("Sinkronisasi belum selesai:", error, flush=True)
                    if not args.watch:
                        raise
                except Exception:
                    # Jangan bocorkan payload biodata, token, atau URL database melalui traceback.
                    if not args.watch:
                        raise
                    print(
                        "Koneksi gagal; data aplikasi tetap tersimpan. Percobaan berikutnya dalam 60 detik.",
                        flush=True,
                    )
                if not args.watch:
                    break
                time.sleep(60)
        finally:
            client.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Sinkronisasi dihentikan.")
    except Timeout:
        print(
            "Proses koneksi/sinkronisasi Sheets lain masih berjalan. Tutup proses tersebut dahulu."
        )
        sys.exit(1)
    except SheetsError as error:
        print("Belum selesai:", error)
        sys.exit(1)
    except Exception as error:
        print(
            f"Koneksi belum berhasil ({type(error).__name__}). Periksa internet, login Google, dan layanan database. Jangan membagikan token/JSON."
        )
        sys.exit(1)
