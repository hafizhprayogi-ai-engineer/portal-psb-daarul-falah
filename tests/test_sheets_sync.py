import json

import pytest

from psb.sheets_sync import (
    SheetsClient,
    SheetsError,
    map_headers,
    plan_sheet,
    participant_values,
    credentials_for,
    snapshot_participants,
)
from psb.db import transaction
from test_system import paid_participant

HEADERS = [
    "NO PENDAFTARAN",
    "NAMA SISWA",
    "NISN",
    "JENIS KELAMIN",
    "TTL",
    "NIS LOKAL",
    "NIK",
    "NO. KK",
    "NAMA AYAH",
    "NIK",
    "PENDIDIKAN",
    "PEKERJAAN",
    "NAMA IBU",
    "NIK",
    "PENDIDIKAN",
    "PEKERJAAN",
]


def example(level="MI"):
    return dict(
        number=level + "-01",
        name="=Nama Contoh",
        level=level,
        birth_place="Kota Contoh",
        birth_date="2015-04-12",
        phone="081234567890",
        email="contoh@example.test",
        bio=json.dumps(
            dict(
                schema_version=2,
                nisn="0000000001",
                nik="0000000000000001",
                kk_number="0000000000000002",
                father_name="Ayah",
                father_nik="0000000000000003",
                mother_name="Ibu",
                mother_nik="0000000000000004",
            )
        ),
        bio_complete=1,
        completed=0,
        published_result=None,
    )


def test_template_mapping_keeps_three_distinct_niks_and_manual_column():
    mapped = map_headers(HEADERS)
    assert mapped[7] == "nik" and mapped[10] == "father_nik" and mapped[14] == "mother_nik"
    assert mapped[11] == "father_education" and mapped[15] == "mother_education"
    assert 6 not in mapped
    plan = plan_sheet("MI", HEADERS, [["MI-01"]], [example()])
    cells = {item["range"]: item["values"][0][0] for item in plan["updates"]}
    assert cells["'MI'!C2"] == "0000000001"
    assert cells["'MI'!G2"] == "0000000000000001"
    assert cells["'MI'!J2"] == "0000000000000003"
    assert cells["'MI'!N2"] == "0000000000000004"
    assert "'MI'!F2" not in cells and not plan["additions"]
    assert cells["'MI'!E2"] == "Kota Contoh, 12/04/2015"


def test_ambiguous_headers_and_duplicate_numbers_stop_before_write():
    with pytest.raises(SheetsError, match="ganda/ambigu"):
        map_headers(["NO PENDAFTARAN", "NAMA SISWA", "NIK", "NIK"])
    with pytest.raises(SheetsError, match="Baris 1"):
        map_headers(["Nama", "NISN"])
    with pytest.raises(SheetsError, match="ganda"):
        plan_sheet("MI", HEADERS, [["MI-01"], ["MI-01"]], [example()])


def test_npsn_sekolah_header_syncs_school_id_without_touching_local_nis():
    participant = example("MA")
    bio = json.loads(participant["bio"])
    bio["school_npsn"] = "00000042"
    participant["bio"] = json.dumps(bio)
    headers = ["NO PENDAFTARAN", "NAMA SISWA", "NIS LOKAL", "NPSN SEKOLAH"]
    plan = plan_sheet("MA", headers, [["MA-01"]], [participant])
    cells = {item["range"]: item["values"][0][0] for item in plan["updates"]}
    assert cells["'MA'!D2"] == "00000042"
    assert "'MA'!C2" not in cells
    assert plan["unmapped"] == ["NIS LOKAL"]


class FakeSheets(SheetsClient):
    def __init__(self):
        self.calls = []
        self.numbers = {level: [] for level in ("MI", "MTS", "MA")}
        self.fail_append_once = False
        self.bad_header = None

    def metadata(self):
        return {
            "sheets": [
                {
                    "properties": {
                        "title": level,
                        "gridProperties": {"rowCount": 100, "columnCount": 26},
                    }
                }
                for level in self.numbers
            ]
        }

    def values(self, title, cell_range):
        if cell_range.startswith("A1:"):
            return [["NAMA SISWA"]] if title == self.bad_header else [HEADERS]
        return [[number] for number in self.numbers[title]]

    def request(self, method, suffix="", **kwargs):
        self.calls.append((method, suffix, kwargs))
        if suffix.endswith(":append"):
            for level in self.numbers:
                if f"%27{level}%27" in suffix:
                    self.numbers[level].append(kwargs["json"]["values"][0][0])
            if self.fail_append_once:
                self.fail_append_once = False
                raise SheetsError("Timeout setelah data diterima Google.")
        return {}


def test_preview_is_read_only_and_levels_are_separated():
    client = FakeSheets()
    result = client.sync([example("MI"), example("MTS")], apply=False)
    assert [r["peserta"] for r in result] == [1, 1, 0] and not client.calls
    client.sync([example("MI"), example("MTS")], apply=True)
    assert client.numbers == {"MI": ["MI-01"], "MTS": ["MTS-01"], "MA": []}
    for _, _, args in client.calls:
        assert args["params"]["valueInputOption"] == "RAW"
        assert args["json"]["values"][0][1] == "=Nama Contoh"
        assert args["json"]["values"][0][5] is None


def test_all_tabs_validated_before_first_write():
    client = FakeSheets()
    client.bad_header = "MA"
    with pytest.raises(SheetsError):
        client.sync([example()], apply=True)
    assert not client.calls


def test_ambiguous_append_timeout_rechecks_numbers_on_retry():
    client = FakeSheets()
    client.fail_append_once = True
    with pytest.raises(SheetsError):
        client.sync([example()], apply=True)
    client.sync([example()], apply=True)
    assert client.numbers["MI"] == ["MI-01"]
    assert len([c for c in client.calls if c[1].endswith(":append")]) == 1
    assert client.calls[-1][2]["json"]["valueInputOption"] == "RAW"


def test_snapshot_excludes_account_and_public_tokens(ctx):
    with transaction():
        paid_participant(account=True)
    rows = snapshot_participants()
    assert len(rows) == 1
    assert not ({"password_hash", "tracking_hash", "token", "secret"} & set(rows[0]))
    assert participant_values(rows[0])["number"] == rows[0]["number"]


def test_oauth_login_uses_pkce_and_loopback_and_saves_private_token(tmp_path, monkeypatch):
    from google_auth_oauthlib.flow import InstalledAppFlow

    settings = {
        "installed": {
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test",
            "client_secret": "test-only",
        }
    }
    (tmp_path / "google-oauth-client.json").write_text(json.dumps(settings))
    captured = {}

    class FakeToken:
        def to_json(self):
            return '{"token":"test-only"}'

    class FakeFlow:
        def run_local_server(self, **kwargs):
            captured.update(kwargs)
            return FakeToken()

    def factory(config, scopes, **kwargs):
        captured.update(kwargs)
        return FakeFlow()

    monkeypatch.setattr(InstalledAppFlow, "from_client_config", factory)
    credentials_for(tmp_path, login=True)
    assert captured["autogenerate_code_verifier"] is True
    assert captured["host"] == "127.0.0.1" and captured["port"] == 0
    assert captured["timeout_seconds"] == 600
    assert captured["access_type"] == "offline"
    assert (tmp_path / "google-sheets-token.json").is_file()
