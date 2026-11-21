"""Memproses antrean email/notifikasi secara berkala tanpa membuka jendela terminal."""

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from filelock import FileLock, Timeout


def run_once():
    from psb.app import create_app
    from psb.notifications import process_outbox

    app = create_app()
    with app.app_context():
        return process_outbox(app)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", action="store_true", help="Proses antrean setiap 30 detik.")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    data_dir = Path(os.getenv("DATA_DIR") or ROOT / "instance").resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    with FileLock(str(data_dir / "notification-worker.lock"), timeout=0):
        while True:
            try:
                processed = run_once()
                if processed:
                    print(f"Antrean notifikasi diproses: {processed}", flush=True)
            except Exception as error:
                # Jangan mencetak alamat tujuan, isi pesan, password SMTP, atau token.
                print(
                    f"Worker notifikasi belum selesai ({type(error).__name__}); mencoba lagi nanti.",
                    flush=True,
                )
            if not args.watch:
                return
            time.sleep(30)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Timeout:
        print("Worker notifikasi lain sudah berjalan.")
