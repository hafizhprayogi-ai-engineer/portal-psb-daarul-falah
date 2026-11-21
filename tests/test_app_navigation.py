import pytest
from flask import g
from psb.db import one, execute, transaction
from psb.domain import participant, save_bio, publish_result
from psb.interface import admission_progress
from conftest import login_as, post
from test_system import paid_participant, BIO, passed, accepted_files


def setup_participants(app):
    with app.app_context():
        g.user = one("SELECT * FROM users WHERE username='rangkap'")
        with transaction():
            pid, _, _ = paid_participant(account=True)
            other, _, _ = paid_participant(account=True)
        return pid, other, participant(pid)["number"]


def test_wali_dashboard_has_menu_instead_of_forms(app):
    pid, other, number = setup_participants(app)
    c = app.test_client()
    login_as(app, c, number)
    html = c.get(f"/peserta/{pid}").get_data(as_text=True)
    assert "1/6" in html and "Menu utama" in html
    assert f"/peserta/{pid}/menu/biodata" in html
    assert f'action="/peserta/{pid}/bio"' not in html
    for section in (
        "biodata",
        "jadwal",
        "hasil",
        "berkas",
        "pembayaran",
        "dokumen",
        "notifikasi",
        "bantuan",
        "progres",
    ):
        page = c.get(f"/peserta/{pid}/menu/{section}")
        assert page.status_code == 200, section
        assert c.get(f"/peserta/{other}/menu/{section}").status_code == 403
    bio = c.get(f"/peserta/{pid}/menu/biodata/santri").get_data(as_text=True)
    assert f'action="/peserta/{pid}/bio"' in bio
    assert 'id="hasil"' not in bio and 'id="berkas"' not in bio
    assert c.get(f"/peserta/{pid}/menu/absensi").status_code == 403
    assert c.get(f"/peserta/{pid}/menu/tidak-ada").status_code == 404


def test_save_returns_to_selected_menu(app):
    pid, _, number = setup_participants(app)
    c = app.test_client()
    login_as(app, c, number)
    result = post(c, f"/peserta/{pid}/bio", BIO)
    assert result.status_code == 302 and result.location == f"/peserta/{pid}/menu/biodata"
    assert "2/6" in c.get(f"/peserta/{pid}").get_data(as_text=True)


@pytest.mark.parametrize(
    "username,allowed,denied",
    [
        (
            "admin",
            [
                "/pengaturan",
                "/pengaturan/lembaga",
                "/pengaturan/biaya",
                "/pengaturan/petugas",
                "/keuangan/verifikasi",
                "/keuangan/riwayat",
                "/pekerjaan",
                "/layanan/hasil",
            ],
            ["/keuangan/pendaftaran", "/keuangan/daftar-ulang"],
        ),
        (
            "bendahara",
            [
                "/keuangan",
                "/keuangan/pendaftaran",
                "/keuangan/daftar-ulang",
                "/keuangan/verifikasi",
                "/keuangan/riwayat",
                "/pekerjaan",
            ],
            ["/pengaturan/petugas", "/layanan/hasil", "/layanan/berkas"],
        ),
        (
            "berkas",
            [
                "/layanan/biodata",
                "/layanan/berkas",
                "/layanan/hasil",
                "/layanan/dokumen",
                "/pekerjaan",
            ],
            ["/keuangan/verifikasi", "/pengaturan/biaya"],
        ),
        (
            "rangkap",
            [
                "/keuangan/pendaftaran",
                "/keuangan/daftar-ulang",
                "/layanan/hasil",
                "/pengaturan/petugas",
            ],
            [],
        ),
    ],
)
def test_staff_menu_pages_follow_roles(app, username, allowed, denied):
    c = app.test_client()
    login_as(app, c, username)
    assert c.get("/dashboard").status_code == 200
    for path in allowed:
        assert c.get(path).status_code == 200, path
    for path in denied:
        assert c.get(path).status_code == 403, path


def test_admin_read_only_selection_and_new_finance_paths(app):
    pid, _, _ = setup_participants(app)
    c = app.test_client()
    login_as(app, c, "admin")
    html = c.get(f"/peserta/{pid}/menu/hasil").get_data(as_text=True)
    assert f'action="/peserta/{pid}/draft"' not in html
    assert post(c, f"/peserta/{pid}/draft", {"result": "Lulus"}).status_code == 403
    assert (
        post(c, "/keuangan/verifikasi", {"action": "approve", "payment_id": 1}).status_code == 403
    )


def test_progress_updates_when_result_is_corrected(ctx):
    with transaction():
        pid, _, _ = paid_participant()
        save_bio(pid, BIO)
        passed(pid)
        accepted_files(pid)
        p = participant(pid)
        assert admission_progress(p, True)["count"] == 4
        publish_result(pid, "Tidak lulus", "Hasil dikoreksi", True)
        progress = admission_progress(participant(pid), True)
        assert progress["count"] == 2 and progress["next_section"] == "hasil"


def test_paid_with_missing_documents_counts_payment_independently(ctx):
    from psb.domain import balance
    p = {'id': 999, 'published_result':'Lulus', 'bio_complete':1,
         'schedule_id':1,'locked_at':'2026-11-20','completed':0}
    paid={'invoice':{'total':1000000},'remaining':0}
    progress=admission_progress(p,False,paid)
    assert progress['count']==5 and progress['next_section']=='berkas'
    assert progress['steps'][-1]['done']
    assert not progress['steps'][-2]['done']
    unpaid=admission_progress(p,False,{'invoice':{'total':1000000},'remaining':500000})
    assert unpaid['count']==4
    unset=admission_progress(p,False,{'invoice':None,'remaining':None})
    assert unset['count']==4
    assert admission_progress(p,True,paid)['count']==6


def test_three_roles_display_as_ketua_psb_without_granting_admin_finance(app):
    c=app.test_client()
    login_as(app,c,'rangkap')
    assert 'Ketua PSB' in c.get('/dashboard').get_data(as_text=True)
    assert c.get('/keuangan/daftar-ulang').status_code==200
    assert c.get('/pengaturan/petugas').status_code==200
    assert c.get('/layanan/berkas').status_code==200
    login_as(app,c,'admin')
    assert 'Ketua PSB' not in c.get('/dashboard').get_data(as_text=True)
    assert c.get('/keuangan/daftar-ulang').status_code==403
