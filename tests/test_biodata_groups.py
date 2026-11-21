import json
import pytest
from flask import g
from psb.biodata import BIO_GROUPS, BIO_FIELDS, bio_values, bio_group_status
from psb.db import one, execute, transaction, now
from psb.domain import participant, save_bio, RuleError, set_schedule, open_schedule, issue_document
from psb.files import document_lines, render_document
from conftest import login_as, post
from test_system import paid_participant, DATA, BIO, wednesday


def group_data(group):
    values = {**DATA, **BIO, "father_name": "Ayah Contoh", "mother_name": "Ibu Contoh", "email": ""}
    return {
        "bio_group": group,
        **{key: values.get(key, "") for key in BIO_GROUPS[group]["fields"] if key != "number"},
    }


def test_independent_group_saves_preserve_other_sections(ctx):
    with transaction():
        pid, _, _ = paid_participant()
        for group in ("alamat-kontak", "sekolah", "santri", "orang-tua"):
            save_bio(pid, group_data(group))
            p = participant(pid)
            stored = json.loads(p["bio"])
            assert stored["address"] == BIO["address"]
            assert not p["bio_complete"] or group == "orang-tua"
        assert participant(pid)["bio_complete"]
        stored = json.loads(participant(pid)["bio"])
        assert stored["nik"] == "0000000000000001"
        assert stored["postal_code"] == "00001" and stored["school_npsn"] == "00000001"
        assert stored["email"] == "" and participant(pid)["email"] == DATA["email"]
        assert all(bio_group_status(bio_values(participant(pid), stored), "MI").values())


@pytest.mark.parametrize(
    "group,key,value",
    [
        ("santri", "nik", "123"),
        ("santri", "kk_number", "a" * 16),
        ("santri", "nisn", "123456789"),
        ("orang-tua", "father_nik", "1" * 15),
        ("orang-tua", "mother_nik", "1" * 17),
        ("alamat-kontak", "postal_code", "123456"),
        ("sekolah", "school_npsn", "1234567"),
        ("alamat-kontak", "email", "bukan-email"),
    ],
)
def test_identifier_and_contact_validation(ctx, group, key, value):
    with transaction():
        pid, _, _ = paid_participant()
    with pytest.raises(RuleError):
        with transaction():
            save_bio(pid, {**group_data(group), key: value})
    assert json.loads(participant(pid)["bio"]) == {}


def test_mi_without_school_or_nisn_can_complete(ctx):
    with transaction():
        pid, _, _ = paid_participant()
        data = {**BIO, "school": "", "school_address": "", "school_npsn": "", "nisn": ""}
        save_bio(pid, data)
        assert participant(pid)["bio_complete"]
        mts, _, _ = paid_participant("MTS")
    with pytest.raises(RuleError):
        with transaction():
            save_bio(mts, data)


def test_unavailable_parent_requires_explanation(ctx):
    with transaction():
        pid, _, _ = paid_participant()
    fields = {
        **group_data("orang-tua"),
        "father_unavailable": "ya",
        "father_name": "",
        "father_nik": "",
        "father_education": "",
        "father_job": "",
    }
    with pytest.raises(RuleError):
        with transaction():
            save_bio(pid, fields)
    with transaction():
        save_bio(pid, {**fields, "father_note": "Data ayah tidak tersedia; wali adalah ibu."})
    stored = json.loads(participant(pid)["bio"])
    assert stored["father_note"] and stored["mother_name"] == "Ibu Contoh"


def setup_http(app):
    with app.app_context():
        g.user = one("SELECT * FROM users WHERE username='rangkap'")
        with transaction():
            pid, _, _ = paid_participant(account=True)
            other, _, _ = paid_participant(account=True)
        return pid, other, participant(pid)["number"]


def test_hub_subpages_and_role_isolation(app):
    pid, other, number = setup_http(app)
    c = app.test_client()
    login_as(app, c, number)
    hub = c.get(f"/peserta/{pid}/menu/biodata").get_data(as_text=True)
    assert "Data Orang Tua" in hub and "Sekolah Asal" in hub
    assert f'action="/peserta/{pid}/bio"' not in hub
    for group in BIO_GROUPS:
        assert c.get(f"/peserta/{pid}/menu/biodata/{group}").status_code == 200
        assert c.get(f"/peserta/{other}/menu/biodata/{group}").status_code == 403
        assert c.get("/layanan/biodata/" + group).status_code == 403
    login_as(app, c, "admin")
    assert c.get("/layanan/biodata/orang-tua").status_code == 200
    html = c.get(f"/peserta/{pid}/menu/biodata/santri").get_data(as_text=True)
    assert f'action="/peserta/{pid}/staff-bio"' not in html
    login_as(app, c, "bendahara")
    assert c.get(f"/peserta/{pid}/menu/biodata/santri").status_code == 403


def test_failed_save_keeps_inputs_and_number_cannot_change(app):
    pid, _, number = setup_http(app)
    c = app.test_client()
    login_as(app, c, number)
    payload = {
        **group_data("santri"),
        "nik": "123",
        "name": "Nama Fiktif Baru",
        "illness_history": "Catatan uji, bukan data nyata",
    }
    response = post(c, f"/peserta/{pid}/bio", payload)
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "Nama Fiktif Baru" in html and "Catatan uji, bukan data nyata" in html
    assert f'value="{number}"' in html
    result = post(c, f"/peserta/{pid}/bio", {**group_data("santri"), "number": "MI-999"})
    assert result.status_code == 400
    with app.app_context():
        assert participant(pid)["name"] == DATA["name"]


def test_post_redirect_and_no_cross_group_updates(app):
    pid, _, number = setup_http(app)
    c = app.test_client()
    login_as(app, c, number)
    result = post(
        c, f"/peserta/{pid}/bio", {**group_data("alamat-kontak"), "nik": "9999999999999999"}
    )
    assert result.location == f"/peserta/{pid}/menu/biodata/alamat-kontak"
    with app.app_context():
        stored = json.loads(participant(pid)["bio"])
        assert "nik" not in stored
        assert stored["email"] == "" and participant(pid)["email"] == DATA["email"]


def test_lock_staff_reason_and_old_documents(ctx):
    with transaction():
        pid, _, _ = paid_participant()
        save_bio(pid, BIO)
        open_schedule(wednesday())
        set_schedule(pid, one("SELECT id FROM schedules")["id"])
        execute("UPDATE participants SET locked_at=? WHERE id=?", (now(), pid))
        card = issue_document(pid, "kartu")
        form = issue_document(pid, "formulir")
    with pytest.raises(RuleError):
        with transaction():
            save_bio(pid, group_data("santri"))
    with pytest.raises(RuleError):
        with transaction():
            save_bio(pid, group_data("santri"), staff=True)
    with transaction():
        save_bio(
            pid,
            {**group_data("santri"), "nik": "0000000000000099"},
            staff=True,
            reason="Perbaikan berdasarkan dokumen contoh",
        )
    assert one("SELECT valid FROM documents WHERE id=?", (card,))["valid"] == 0
    assert one("SELECT valid FROM documents WHERE id=?", (form,))["valid"] == 0
    assert (
        one("SELECT COUNT(*) AS n FROM audit WHERE reason='Perbaikan berdasarkan dokumen contoh'")[
            "n"
        ]
        == 1
    )


def test_form_pdf_contains_new_biodata(ctx):
    with transaction():
        pid, _, _ = paid_participant()
        save_bio(pid, BIO)
        doc_id = issue_document(pid, "formulir")
    doc = one("SELECT * FROM documents WHERE id=?", (doc_id,))
    _, _, lines = document_lines(doc)
    values = dict(lines)
    assert (
        values["NIK santri"] == BIO["nik"]
        and values["Pendidikan terakhir ibu"] == BIO["mother_education"]
    )
    assert values["Riwayat penyakit anak"] == "Tidak ada"
    assert render_document(doc).read().startswith(b"%PDF")


def test_legacy_biodata_is_preserved_and_needs_additional_fields(ctx):
    with transaction():
        pid, _, _ = paid_participant()
        old = {
            "father": "Ayah Lama",
            "mother": "Ibu Lama",
            "address": "Alamat lama",
            "gender": "Putra",
        }
        execute("UPDATE participants SET bio=?,bio_complete=1 WHERE id=?", (json.dumps(old), pid))
    p = participant(pid)
    assert not p["bio_complete"]
    assert bio_values(p, json.loads(p["bio"]))["father_name"] == "Ayah Lama"
    assert json.loads(p["bio"]) == old
