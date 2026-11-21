"""Pemeriksaan HTTP server lokal menggunakan akun demo yang dibuat manage.py."""

import http.cookiejar
import argparse
import re
import urllib.parse
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5000")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    credentials = (root / "instance" / "akun-demo.txt").read_text(encoding="utf-8")
    password_line = next(
        line for line in credentials.splitlines() if line.startswith("Password seluruh akun: ")
    )
    password = password_line.split(": ", 1)[1]
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    base_url = args.base_url.rstrip("/")
    with opener.open(base_url + "/login", timeout=10) as response:
        html = response.read().decode("utf-8")
    csrf = re.search(r'name="csrf" value="([^"]+)"', html).group(1)
    body = urllib.parse.urlencode(
        {"csrf": csrf, "username": "admin.demo", "password": password}
    ).encode()
    with opener.open(base_url + "/login", data=body, timeout=10) as response:
        assert response.url.endswith("/dashboard"), "Login belum mencapai dashboard."
        assert "Ringkasan penerimaan" in response.read().decode("utf-8")
    for path in (
        "/health",
        "/peserta",
        "/keuangan",
        "/pengaturan",
        "/aktivitas",
        "/laporan/pendaftaran.xlsx",
    ):
        with opener.open(base_url + path, timeout=10) as response:
            assert response.status == 200
            print(f"{path} HTTP {response.status}")
    print("Login dan halaman utama melalui server Waitress berhasil diperiksa.")


if __name__ == "__main__":
    main()
