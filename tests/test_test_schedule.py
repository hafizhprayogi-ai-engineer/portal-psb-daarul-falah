from datetime import date, timedelta

import pytest
from flask import g

from conftest import login_as
from test_system import paid_participant, BIO, wednesday
from psb.db import transaction, one
from psb.domain import open_schedule, set_schedule, save_bio
from psb.sheets_sync import (
    snapshot_participants,
    participant_values,
    TEST_HEADERS,
    TEST_SHEET,
    plan_sheet,
    SheetsError,
)
from test_sheets_sync import FakeSheets, example, HEADERS


def setup_roster(app):
    with app.app_context():
        g.user = one("SELECT * FROM users WHERE username='rangkap'")
        with transaction():
            first, _, _ = paid_participant(account=True)
            second, _, _ = paid_participant(level="MA")
            save_bio(first, BIO)
            save_bio(second, BIO)
            first_date = wednesday()
            open_schedule(first_date)
            open_schedule(
                (
                    date.fromisoformat(first_date) + timedelta(days=7)
                ).isoformat()
            )
            first_sid = one("SELECT id FROM schedules ORDER BY date LIMIT 1")["id"]
            second_sid = one("SELECT id FROM schedules ORDER BY date DESC LIMIT 1")["id"]
            set_schedule(first, first_sid)
        return first, second, first_sid, second_sid


def test_roster_permissions_filter_and_participant_isolation(app):
    first, second, sid, _ = setup_roster(app)
    client = app.test_client()
    assert client.get(f"/jadwal/{sid}").status_code == 302
    for username in ("admin", "berkas"):
        login_as(app, client, username)
        response = client.get(f"/jadwal/{sid}")
        assert (
            response.status_code == 200
            and b"MI-01" in response.data
            and b"MA-01" not in response.data
        )
        assert b"MI-01" not in client.get(f"/jadwal/{sid}?level=MA").data
        assert client.get("/jadwal/999999").status_code == 404
    for username in ("bendahara", "MI-01"):
        login_as(app, client, username)
        assert client.get(f"/jadwal/{sid}").status_code == 403


def test_sheet_snapshot_tracks_choice_move_and_unselected(app):
    first, second, sid, target = setup_roster(app)
    with app.app_context():
        rows = snapshot_participants()
        mi = next(p for p in rows if p["id"] == first)
        ma = next(p for p in rows if p["id"] == second)
        assert participant_values(mi)["schedule_choice"] == "Sudah memilih"
        assert participant_values(ma)["schedule_choice"] == "Belum memilih"
        assert participant_values(ma)["test_date"] == ""
        previous = mi["test_date"]
        g.user = one("SELECT * FROM users WHERE username='berkas'")
        with transaction():
            set_schedule(first, target, staff=True, reason="Pemindahan contoh untuk pengujian")
        mi = next(p for p in snapshot_participants() if p["id"] == first)
        assert mi["test_date"] != previous
        plan = plan_sheet(TEST_SHEET, TEST_HEADERS, [["MI-01"], ["MA-01"]], [mi, ma])
        cells = {item["range"]: item["values"][0][0] for item in plan["updates"]}
        assert cells["'Jadwal Tes'!D2"] == mi["test_date"]
        assert cells["'Jadwal Tes'!F3"] == "Belum memilih"
        assert not plan["additions"]


class FakeWithSchedule(FakeSheets):
    def metadata(self):
        data = super().metadata()
        for i, sheet in enumerate(data["sheets"]):
            sheet["properties"]["sheetId"] = i + 1
        data["sheets"].append(
            {
                "properties": {
                    "sheetId": 4,
                    "title": TEST_SHEET,
                    "gridProperties": {"rowCount": 1000, "columnCount": 8},
                }
            }
        )
        return data

    def values(self, title, cell_range):
        if title == TEST_SHEET:
            return [TEST_HEADERS] if cell_range.startswith("A1:") else [["MI-01"]]
        return super().values(title, cell_range)


def test_schedule_tab_is_synced_and_existing_sheet_not_recreated():
    client = FakeWithSchedule()
    assert client.setup_test_sheet() == 4 and not client.calls
    client.numbers["MI"] = ["MI-01"]
    result = client.sync([example()], apply=True)
    assert result[-1]["tab"] == TEST_SHEET and result[-1]["peserta"] == 1
    updates = [
        r
        for _, suffix, args in client.calls
        if suffix == "/values:batchUpdate"
        for r in args["json"]["data"]
    ]
    assert any(
        r["range"] == "'Jadwal Tes'!F2" and r["values"] == [["Belum memilih"]] for r in updates
    )


def test_setup_preserves_existing_conflicting_sheet():
    client = FakeWithSchedule()
    client.values = lambda *args: [["Kolom manual yang tidak sesuai"]]
    with pytest.raises(SheetsError, match="tidak ditimpa"):
        client.setup_test_sheet()
    assert not client.calls


def test_setup_creates_only_new_schedule_sheet_atomically():
    client = FakeSheets()
    original_metadata = client.metadata

    def metadata():
        data = original_metadata()
        for i, sheet in enumerate(data["sheets"]):
            sheet["properties"]["sheetId"] = i + 1
        return data

    client.metadata = metadata
    client.setup_test_sheet()
    assert len(client.calls) == 1
    _, suffix, args = client.calls[0]
    assert suffix == ":batchUpdate"
    requests = args["json"]["requests"]
    assert requests[0]["addSheet"]["properties"]["title"] == TEST_SHEET
    assert not any("deleteSheet" in r for r in requests)
