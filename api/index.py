"""Pintu masuk Vercel (serverless) untuk Portal PSB - khusus demonstrasi.

Di Vercel hanya /tmp yang dapat ditulis dan isinya tidak permanen.
Gunakan DATABASE_URL (MySQL cloud) agar data tidak hilang.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATA_DIR", "/tmp/psb")
os.environ.setdefault("COOKIE_SECURE", "true")
os.environ.setdefault("TRUST_PROXY", "true")

from psb.app import create_app  # noqa: E402

app = create_app()
