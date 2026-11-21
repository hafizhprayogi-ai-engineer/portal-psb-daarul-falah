"""Peluncur saat login Windows; tidak meminta password dan tidak membuka browser."""

import argparse
import json
import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psutil
from dotenv import dotenv_values
from filelock import FileLock, Timeout


def project_processes(root=ROOT):
    result = {"server": [], "sheets": [], "notifications": []}
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if not (process.info["name"] or "").lower().startswith(("python", "pythonw")):
                continue
            args = process.info["cmdline"] or []
            if Path(process.cwd()).resolve() != root.resolve():
                continue
            scripts = [Path(arg).as_posix().replace("\\", "/") for arg in args[1:]]
            if "run.py" in scripts or (root / "run.py").as_posix() in scripts:
                result["server"].append(process.info["pid"])
            if (
                (
                    "scripts/google_sheets.py" in scripts
                    or (root / "scripts/google_sheets.py").as_posix() in scripts
                )
                and "sync" in args
                and "--watch" in args
            ):
                result["sheets"].append(process.info["pid"])
            if (
                (
                    "scripts/notification_worker.py" in scripts
                    or (root / "scripts/notification_worker.py").as_posix() in scripts
                )
                and "--watch" in args
            ):
                result["notifications"].append(process.info["pid"])
        except (psutil.Error, OSError):
            continue
    return result


def database_ready(config, data_dir):
    try:
        if config.get("DATABASE_URL"):
            import pymysql
            from psb.mysql import connection_options

            options = connection_options(config["DATABASE_URL"])
            options.update(connect_timeout=3, read_timeout=3, write_timeout=3)
            connection = pymysql.connect(**options)
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
            finally:
                connection.close()
        else:
            import sqlite3

            path = (data_dir / "psb.sqlite3").resolve(strict=True)
            connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=3)
            try:
                connection.execute("SELECT 1").fetchone()
            finally:
                connection.close()
        return True
    except Exception:
        return False


def port_busy(port):
    with socket.socket() as connection:
        connection.settimeout(1)
        return connection.connect_ex(("127.0.0.1", port)) == 0


def health_ready(port):
    try:
        with urlopen(f"http://127.0.0.1:{port}/health", timeout=3) as response:
            return response.status == 200 and json.load(response).get("status") == "ok"
    except Exception:
        return False


def stop_project_services():
    """Hentikan hanya server dan worker yang terdeteksi berasal dari proyek ini."""
    targets = []
    for pids in project_processes().values():
        targets.extend(pids)
    processes = []
    for pid in sorted(set(targets)):
        try:
            process = psutil.Process(pid)
            process.terminate()
            processes.append(process)
        except psutil.Error:
            continue
    for process in processes:
        try:
            process.wait(timeout=8)
        except psutil.Error:
            continue


def wait_for(check, timeout, interval=5):
    deadline = time.monotonic() + timeout
    while True:
        if check():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(interval)


def launch(kind, data_dir, config):
    commands = {
        "server": (["run.py"], "server"),
        "sheets": (["scripts/google_sheets.py", "sync", "--watch"], "sheets-sync"),
        "notifications": (["scripts/notification_worker.py", "--watch"], "notifications"),
    }
    args, prefix = commands[kind]
    # Sesi lama tidak boleh menimpa .env baru melalui environment yang diwariskan.
    environment = os.environ.copy()
    environment.update({key: value for key, value in config.items() if value is not None})
    with (
        (data_dir / f"{prefix}.stdout.log").open("a", encoding="utf-8") as stdout,
        (data_dir / f"{prefix}.stderr.log").open("a", encoding="utf-8") as stderr,
    ):
        process = subprocess.Popen(
            [str(ROOT / ".venv/Scripts/python.exe"), "-u", *args],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            env=environment,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    (data_dir / f"{prefix}.pid").write_text(str(process.pid), encoding="ascii")
    return process


def start_services(config, data_dir):
    port = int(config.get("PORT") or 5000)
    logging.info("Menunggu database siap (maksimal 10 menit).")
    if not wait_for(lambda: database_ready(config, data_dir), timeout=600, interval=10):
        logging.error(
            "Database belum siap. Pastikan layanan MySQL aktif, lalu jalankan peluncur kembali."
        )
        return 1
    processes = project_processes()
    if processes["server"]:
        logging.info("Proses server PSB sudah ada; tidak membuat server tambahan.")
    elif port_busy(port):
        logging.error("Port aplikasi dipakai proses lain. Proses lain tidak dihentikan.")
        return 1
    else:
        launch("server", data_dir, config)
        logging.info("Server PSB dimulai.")
    if not wait_for(lambda: health_ready(port), timeout=60):
        logging.error("Health portal belum berhasil. Periksa server.stderr.log.")
        return 1
    if project_processes().get("notifications"):
        logging.info("Worker notifikasi sudah berjalan; tidak membuat proses tambahan.")
    else:
        process = launch("notifications", data_dir, config)
        time.sleep(2)
        if process is not None and process.poll() is None:
            logging.info("Worker notifikasi berjalan di latar belakang setiap 30 detik.")
        else:
            logging.warning("Worker notifikasi belum bertahan; periksa notifications.stderr.log.")
    # Worker yang sudah ada diteruskan; filelock worker juga melindungi start bersamaan.
    if project_processes().get("sheets"):
        logging.info("Sinkronisasi Sheets sudah berjalan; tidak membuat worker tambahan.")
        return 0
    if not config.get("GOOGLE_SHEETS_ID") or not (data_dir / "google-sheets-token.json").is_file():
        logging.warning(
            "Portal aktif. Sheets belum login/diatur; jalankan google_sheets.py login secara manual."
        )
        return 0
    # Login/refresh dapat gagal saat Wi-Fi belum siap. Ulangi terbatas tanpa membuka browser.
    for attempt in range(1, 21):
        if project_processes()["sheets"]:
            return 0
        process = launch("sheets", data_dir, config)
        time.sleep(8)
        if process.poll() is None:
            logging.info("Worker Sheets berjalan di latar belakang setiap 60 detik.")
            return 0
        logging.warning(
            "Worker Sheets belum bertahan; percobaan %s/20. Periksa sheets-sync.stdout.log.",
            attempt,
        )
        time.sleep(20)
    logging.error("Worker Sheets belum siap; mungkin perlu login Google ulang. Portal tetap aktif.")
    return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--restart", action="store_true", help="Muat ulang .env dan mulai ulang portal/worker.")
    args = parser.parse_args()
    config = dotenv_values(ROOT / ".env")
    data_dir = Path(config.get("DATA_DIR") or ROOT / "instance")
    if not data_dir.is_absolute():
        data_dir = ROOT / data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    if args.status:
        print(
            json.dumps(
                {
                    "processes": project_processes(),
                    "database_ready": database_ready(config, data_dir),
                    "portal_ready": health_ready(int(config.get("PORT") or 5000)),
                }
            )
        )
        return 0
    if args.restart:
        stop_project_services()
    logging.basicConfig(
        filename=data_dir / "startup-portal.log",
        encoding="utf-8",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    os.chdir(ROOT)
    try:
        with FileLock(str(data_dir / "startup-portal.lock"), timeout=0):
            logging.info("Peluncuran otomatis dimulai.")
            return start_services(config, data_dir)
    except Timeout:
        logging.info("Peluncur lain masih berjalan; proses tambahan diabaikan.")
        return 0
    except Exception as error:
        logging.error(
            "Peluncur belum berhasil (%s). Detail rahasia tidak dicetak.", type(error).__name__
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
