"""Salinan biodata ke Sheets, satu arah dan terpisah dari transaksi wali."""

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import quote

from .biodata import bio_values
from .db import all_rows

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
TEST_SHEET = "Jadwal Tes"
TEST_HEADERS = [
    "NO PENDAFTARAN",
    "NAMA SISWA",
    "JENJANG",
    "TANGGAL TES",
    "JAM TES (WIB)",
    "STATUS PEMILIHAN",
    "STATUS TANGGAL",
    "KEHADIRAN",
]


class SheetsError(RuntimeError):
    pass


def normalize(value):
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def column_name(index):
    result = ""
    while index:
        index, part = divmod(index - 1, 26)
        result = chr(65 + part) + result
    return result


def sheet_prefix(name):
    return "'" + name.replace("'", "''") + "'!"


def map_headers(headers):
    aliases = {
        "NOPPENDAFTARAN": "number",
        "NOPENDAFTARAN": "number",
        "NOMORPENDAFTARAN": "number",
        "NAMASISWA": "name",
        "NAMASANTRI": "name",
        "NAMALENGKAP": "name",
        "NAMALENGKAPPENDAFTAR": "name",
        "NISN": "nisn",
        "JENISKELAMIN": "gender",
        "JK": "gender",
        "TTL": "ttl",
        "TEMPATTANGGALLAHIR": "ttl",
        "TEMPATLAHIR": "birth_place",
        "TANGGALLAHIR": "birth_date",
        "NIKSANTRI": "nik",
        "NIKSISWA": "nik",
        "NOKK": "kk_number",
        "NOMORKK": "kk_number",
        "NAMAAYAH": "father_name",
        "NIKAYAH": "father_nik",
        "NAMAIBU": "mother_name",
        "NIKIBU": "mother_nik",
        "ALAMAT": "address",
        "ALAMATRUMAH": "address",
        "KODEPOS": "postal_code",
        "SEKOLAHASAL": "school",
        "ASALSEKOLAH": "school",
        "ALAMATSEKOLAHASAL": "school_address",
        "ALAMATSEKOLAH": "school_address",
        "NPSN": "school_npsn",
        "NPSNSEKOLAH": "school_npsn",
        "NPSNSEKOLAHASAL": "school_npsn",
        "JENJANG": "level",
        "TANGGALTES": "test_date",
        "JAMTESWIB": "test_hours",
        "STATUSPEMILIHAN": "schedule_choice",
        "STATUSTANGGAL": "schedule_status",
        "KEHADIRAN": "attendance",
        "RIWAYATPENYAKIT": "illness_history",
        "RIWAYATPENYAKITANAK": "illness_history",
        "NOTELPWA": "phone",
        "NOTELP": "phone",
        "NOWA": "phone",
        "NOMORWHATSAPP": "phone",
        "EMAIL": "email",
        "EMAILOPSIONAL": "email",
        "NAMAWALI": "guardian",
        "PENDIDIKANTERAKHIRAYAH": "father_education",
        "PENDIDIKANAYAH": "father_education",
        "PENDIDIKANTERAKHIRIBU": "mother_education",
        "PENDIDIKANIBU": "mother_education",
        "PEKERJAANAYAH": "father_job",
        "PEKERJAANIBU": "mother_job",
        "STATUSBIODATA": "bio_status",
        "HASILSELEKSI": "published_result",
        "STATUSDAFTARULANG": "completion",
    }
    mapped = {}
    parent = None
    for index, header in enumerate(headers, 1):
        name = normalize(header)
        if name == "NAMAAYAH":
            parent = "father"
        elif name == "NAMAIBU":
            parent = "mother"
        key = aliases.get(name)
        if re.fullmatch(r"NIK[0-9]*", name):
            key = parent + "_nik" if parent else "nik"
        if re.fullmatch(r"PENDIDIKAN(?:TERAKHIR)?[0-9]*", name) and parent:
            key = parent + "_education"
        if re.fullmatch(r"PEKERJAAN[0-9]*", name) and parent:
            key = parent + "_job"
        if key:
            if key in mapped.values():
                raise SheetsError(
                    "Kolom biodata ganda/ambigu; gunakan judul lengkap untuk ayah dan ibu."
                )
            mapped[index] = key
    if "number" not in mapped.values() or "name" not in mapped.values():
        raise SheetsError("Baris 1 harus memiliki NO PENDAFTARAN dan NAMA SISWA/NAMA LENGKAP.")
    return mapped


def participant_values(row):
    from .domain import service_hours

    values = bio_values(row, json.loads(row["bio"]))
    complete = bool(row["bio_complete"]) and bool(
        row.get("locked_at") or values.get("schema_version") == 2
    )
    try:
        birthday = date.fromisoformat(row["birth_date"]).strftime("%d/%m/%Y")
    except ValueError:
        birthday = row["birth_date"]
    values.update(
        level=row["level"],
        test_date=row.get("test_date") or "",
        test_hours=service_hours(row["test_date"]) if row.get("test_date") else "",
        schedule_choice="Sudah memilih" if row.get("schedule_id") else "Belum memilih",
        schedule_status=row.get("schedule_status") or "",
        attendance=row.get("attendance") or "Belum dicatat",
        ttl=f"{row['birth_place']}, {birthday}",
        bio_status="Lengkap" if complete else "Belum lengkap",
        published_result=row["published_result"] or "Menunggu hasil",
        completion="Selesai" if row["completed"] else "Belum selesai",
    )
    return values


def snapshot_participants():
    # Hanya peserta yang sudah mendapat nomor; tidak mengekspor token/password/file privat.
    return [
        dict(row)
        for row in all_rows(
            "SELECT p.*,a.name,a.birth_place,a.birth_date,a.phone,a.email,a.level,s.date AS test_date,s.status AS schedule_status "
            "FROM participants p JOIN applications a ON a.id=p.application_id LEFT JOIN schedules s ON s.id=p.schedule_id ORDER BY p.id"
        )
    ]


def plan_sheet(title, headers, existing_numbers, participants):
    mapped = map_headers(headers)
    number_column = next(col for col, key in mapped.items() if key == "number")
    existing = {}
    for row_index, cells in enumerate(existing_numbers, 2):
        number = str(cells[0]).strip() if cells else ""
        if number:
            if number in existing:
                raise SheetsError(
                    f"Nomor pendaftaran ganda di tab {title}; rapikan sebelum sinkronisasi."
                )
            existing[number] = row_index
    updates, additions = [], []
    for participant in participants:
        data = participant_values(participant)
        number = data["number"]
        if not number:
            raise SheetsError("Peserta belum memiliki nomor pendaftaran.")
        if number in existing:
            for column, key in mapped.items():
                updates.append(
                    {
                        "range": sheet_prefix(title) + f"{column_name(column)}{existing[number]}",
                        "values": [[str(data.get(key) or "")]],
                    }
                )
        else:
            # null melewati kolom manual seperti NIS LOKAL; bukan menghapus nilainya.
            values = [None] * len(headers)
            for column, key in mapped.items():
                values[column - 1] = str(data.get(key) or "")
            additions.append(values)
    return {
        "updates": updates,
        "additions": additions,
        "number_column": number_column,
        "mapped": mapped,
        "unmapped": [h for i, h in enumerate(headers, 1) if h and i not in mapped],
    }


def save_token(path, credentials):
    path = Path(path)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(credentials.to_json(), encoding="utf-8")
    temporary.replace(path)


def credentials_for(data_dir, login=False, scopes=None, token_filename="google-sheets-token.json"):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow

    data_dir = Path(data_dir)
    token = data_dir / token_filename
    scopes = scopes or SCOPES
    if login:
        client = data_dir / "google-oauth-client.json"
        if not client.is_file():
            raise SheetsError("Simpan google-oauth-client.json di direktori instance dahulu.")
        config = json.loads(client.read_text(encoding="utf-8-sig"))
        installed = config.get("installed", {})
        if (
            installed.get("auth_uri") != "https://accounts.google.com/o/oauth2/auth"
            or installed.get("token_uri") != "https://oauth2.googleapis.com/token"
        ):
            raise SheetsError("Konfigurasi OAuth Desktop Google tidak sesuai.")
        flow = InstalledAppFlow.from_client_config(config, scopes, autogenerate_code_verifier=True)
        credentials = flow.run_local_server(
            host="127.0.0.1",
            port=0,
            timeout_seconds=600,
            authorization_prompt_message="Buka alamat berikut untuk mengizinkan koneksi Google:\n{url}",
            success_message="Koneksi Google berhasil. Anda boleh menutup tab ini.",
            access_type="offline",
            prompt="consent",
        )
        save_token(token, credentials)
        return credentials
    if not token.is_file():
        raise SheetsError("Login belum dilakukan untuk koneksi Google ini.")
    credentials = Credentials.from_authorized_user_file(token, scopes)
    if not credentials.valid:
        if not credentials.refresh_token:
            raise SheetsError("Izin Google perlu diperbarui. Jalankan perintah login kembali.")
        credentials.refresh(Request())
        save_token(token, credentials)
    return credentials


class SheetsClient:
    def __init__(self, credentials, spreadsheet_id):
        from google.auth.transport.requests import AuthorizedSession

        if not re.fullmatch(r"[A-Za-z0-9_-]{20,}", spreadsheet_id):
            raise SheetsError("ID spreadsheet tidak valid.")
        self.session = AuthorizedSession(credentials)
        self.base = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"

    def request(self, method, suffix="", **kwargs):
        response = self.session.request(method, self.base + suffix, timeout=45, **kwargs)
        if not response.ok:
            messages = {
                401: "Izin login kedaluwarsa; jalankan login kembali.",
                403: "Google menolak akses. Periksa Sheets API, izin akun, serta Test users.",
                404: "Spreadsheet/tab tidak ditemukan atau akun tidak memiliki akses.",
                429: "Batas permintaan Google tercapai. Coba lagi nanti.",
            }
            raise SheetsError(
                messages.get(
                    response.status_code, f"Google Sheets gagal (HTTP {response.status_code})."
                )
            )
        return response.json()

    def metadata(self):
        return self.request("GET", params={"fields": "spreadsheetId,sheets.properties"})

    def values(self, title, cell_range):
        target = quote(sheet_prefix(title) + cell_range, safe="")
        return self.request(
            "GET", "/values/" + target, params={"valueRenderOption": "FORMATTED_VALUE"}
        ).get("values", [])

    def setup_test_sheet(self):
        metadata = self.metadata()
        existing = next(
            (s["properties"] for s in metadata["sheets"] if s["properties"]["title"] == TEST_SHEET),
            None,
        )
        if existing:
            rows = self.values(TEST_SHEET, "A1:H1")
            if not rows or rows[0] != TEST_HEADERS:
                raise SheetsError("Tab Jadwal Tes sudah ada dengan kolom berbeda; tidak ditimpa.")
            return existing["sheetId"]
        import secrets

        sheet_id = secrets.randbelow(2000000000) + 1
        used = {s["properties"]["sheetId"] for s in metadata["sheets"]}
        while sheet_id in used:
            sheet_id = secrets.randbelow(2000000000) + 1
        header_range = dict(
            sheetId=sheet_id, startRowIndex=0, endRowIndex=1, startColumnIndex=0, endColumnIndex=8
        )
        requests = [
            {
                "addSheet": {
                    "properties": {
                        "sheetId": sheet_id,
                        "title": TEST_SHEET,
                        "gridProperties": {"rowCount": 1000, "columnCount": 8, "frozenRowCount": 1},
                    }
                }
            },
            {
                "updateCells": {
                    "range": header_range,
                    "rows": [
                        {
                            "values": [
                                {
                                    "userEnteredValue": {"stringValue": value},
                                    "userEnteredFormat": {
                                        "backgroundColor": {
                                            "red": 0.08,
                                            "green": 0.32,
                                            "blue": 0.24,
                                        },
                                        "textFormat": {
                                            "bold": True,
                                            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                                        },
                                        "wrapStrategy": "WRAP",
                                        "verticalAlignment": "MIDDLE",
                                    },
                                }
                                for value in TEST_HEADERS
                            ]
                        }
                    ],
                    "fields": "userEnteredValue,userEnteredFormat",
                }
            },
            {
                "setBasicFilter": {
                    "filter": {
                        "range": dict(
                            sheetId=sheet_id,
                            startRowIndex=0,
                            endRowIndex=1000,
                            startColumnIndex=0,
                            endColumnIndex=8,
                        )
                    }
                }
            },
            {
                "repeatCell": {
                    "range": dict(
                        sheetId=sheet_id,
                        startRowIndex=1,
                        endRowIndex=1000,
                        startColumnIndex=0,
                        endColumnIndex=8,
                    ),
                    "cell": {
                        "userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}
                    },
                    "fields": "userEnteredFormat.wrapStrategy,userEnteredFormat.verticalAlignment",
                }
            },
            {
                "updateDimensionProperties": {
                    "range": dict(sheetId=sheet_id, dimension="ROWS", startIndex=0, endIndex=1),
                    "properties": {"pixelSize": 48},
                    "fields": "pixelSize",
                }
            },
        ]
        for i, width in enumerate((155, 240, 85, 130, 190, 165, 140, 135)):
            requests.append(
                {
                    "updateDimensionProperties": {
                        "range": dict(
                            sheetId=sheet_id, dimension="COLUMNS", startIndex=i, endIndex=i + 1
                        ),
                        "properties": {"pixelSize": width},
                        "fields": "pixelSize",
                    }
                }
            )
        self.request("POST", ":batchUpdate", json={"requests": requests})
        return sheet_id

    def sync(self, participants, apply=False):
        metadata = self.metadata()
        sheets = {sheet["properties"]["title"]: sheet["properties"] for sheet in metadata["sheets"]}
        if not all(level in sheets for level in ("MI", "MTS", "MA")):
            raise SheetsError(
                "Spreadsheet harus memiliki tab MI, MTS, dan MA dengan nama yang sama persis."
            )
        plans = []
        for level in ["MI", "MTS", "MA"] + ([TEST_SHEET] if TEST_SHEET in sheets else []):
            properties = sheets[level]
            if properties.get("sheetType", "GRID") != "GRID":
                raise SheetsError("Jenis tab belum didukung.")
            if (
                properties["gridProperties"]["columnCount"] > 64
                or properties["gridProperties"]["rowCount"] > 20000
            ):
                raise SheetsError(
                    "Ukuran tab melebihi batas pemeriksaan aman (64 kolom/20.000 baris)."
                )
            header_rows = self.values(
                level, "A1:" + column_name(properties["gridProperties"]["columnCount"]) + "1"
            )
            headers = header_rows[0] if header_rows else []
            if level == TEST_SHEET and headers != TEST_HEADERS:
                raise SheetsError(
                    "Kolom Jadwal Tes berubah. Pulihkan delapan kolom rekap sebelum sinkronisasi."
                )
            mapping = map_headers(headers)
            column = column_name(next(col for col, key in mapping.items() if key == "number"))
            last = max(2, properties["gridProperties"]["rowCount"])
            numbers = self.values(level, f"{column}2:{column}{last}")
            selected = (
                participants
                if level == TEST_SHEET
                else [p for p in participants if p["level"] == level]
            )
            plan = plan_sheet(level, headers, numbers, selected)
            plans.append((level, headers, selected, plan))
        # Validasi SEMUA tab sebelum penulisan pertama.
        for level, headers, selected, plan in plans:
            if apply:
                for offset in range(0, len(plan["updates"]), 400):
                    self.request(
                        "POST",
                        "/values:batchUpdate",
                        json={
                            "valueInputOption": "RAW",
                            "data": plan["updates"][offset : offset + 400],
                        },
                    )
                # Jika timeout, hentikan; putaran berikutnya membaca ulang nomor sebelum append.
                for values in plan["additions"]:
                    target = quote(sheet_prefix(level) + f"A1:{column_name(len(headers))}", safe="")
                    self.request(
                        "POST",
                        "/values/" + target + ":append",
                        params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
                        json={"values": [values]},
                    )
        return [
            {
                "tab": level,
                "peserta": len(selected),
                "baris_baru": len(plan["additions"]),
                "kolom_dibiarkan": plan["unmapped"],
            }
            for level, _, selected, plan in plans
        ]

    def close(self):
        self.session.close()
