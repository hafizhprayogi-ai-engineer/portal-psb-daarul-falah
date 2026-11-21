import io
import json
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta, datetime, timezone
import pytest
from flask import g
from werkzeug.security import generate_password_hash
from psb.db import one, all_rows, execute, transaction, now
from psb.domain import *
from psb.files import save_upload
from psb.notifications import queue_reminders, process_outbox
from conftest import PASSWORD, login_as, post

DATA = {
    "level": "MI",
    "name": "Anak Fiktif",
    "birth_place": "Kota Contoh",
    "birth_date": "2015-04-12",
    "phone": "081234567890",
    "email": "wali@example.test",
}
BIO = {
    "nisn": "0000000001",
    "nik": "0000000000000001",
    "kk_number": "0000000000000002",
    "illness_history": "Tidak ada",
    "father_nik": "0000000000000003",
    "father_education": "SMA / MA / SMK",
    "father_job": "Petani contoh",
    "mother_nik": "0000000000000004",
    "mother_education": "SMA / MA / SMK",
    "mother_job": "Pedagang contoh",
    "postal_code": "00001",
    "school_address": "Alamat sekolah fiktif",
    "school_npsn": "00000001",
    "gender": "Putra",
    "address": "Alamat Fiktif",
    "school": "Sekolah Contoh",
    "father": "Ayah Contoh, petani",
    "mother": "Ibu Contoh, pedagang",
    "guardian": "Ayah Contoh",
    "phone": "081234567890",
}
PDF = b"%PDF-1.4\n1 0 obj <<>> endobj\n%%EOF"


def paid_participant(level="MI", account=False):
    aid, token = new_application({**DATA, "level": level}, "langsung")
    payment = create_payment(aid, "pendaftaran", "tunai", 200000, secrets.token_hex(20))
    pid = approve_payment(payment)
    if account:
        p = participant(pid)
        execute(
            "INSERT INTO users(username,password_hash,participant_id,active) VALUES(?,?,?,1)",
            (p["number"], generate_password_hash(PASSWORD), pid),
        )
    return pid, aid, token


def passed(pid, total=1000000):
    p = participant(pid)
    execute(
        "INSERT INTO fee_versions(level,components,total,created_at) VALUES(?,?,?,?)",
        (p["level"], json.dumps([{"name": "Biaya contoh", "amount": total}]), total, now()),
    )
    execute("UPDATE participants SET draft_result='Lulus' WHERE id=?", (pid,))
    publish_result(pid, "Lulus")


def accepted_files(pid, level="MI"):
    for cat in required_docs(level):
        execute(
            "INSERT INTO uploads(participant_id,category,filename,storage_name,mime,size,status,created_at) VALUES(?,?,?,?,?,1,'Diterima',?)",
            (pid, cat, "contoh.pdf", secrets.token_hex(20), "application/pdf", now()),
        )


def wednesday():
    d = today() + timedelta(days=1)
    while d.weekday() != 2:
        d += timedelta(days=1)
    return d.isoformat()


def test_no_number_before_approval_and_shared_contacts(ctx):
    with transaction():
        aid, _ = new_application(DATA, "online")
        assert one("SELECT COUNT(*) AS n FROM participants")["n"] == 0
        p1, _, _ = paid_participant()
        p2, _, _ = paid_participant()
        p3, _, _ = paid_participant("MTS")
    assert [participant(x)["number"] for x in (p1, p2, p3)] == ["MI-01", "MI-02", "MTS-01"]
    assert participant(p1)["email"] == participant(p2)["email"]


def test_sequence_past_99_and_idempotent_approval(ctx):
    with transaction():
        execute("UPDATE sequences SET value=99 WHERE level='MI'")
        pid, aid, _ = paid_participant()
        pay = one("SELECT * FROM payments WHERE application_id=?", (aid,))
        assert approve_payment(pay["id"]) == pid
    assert participant(pid)["number"] == "MI-100"
    assert one("SELECT COUNT(*) AS n FROM documents WHERE kind='kuitansi'")["n"] == 1


def test_concurrent_numbers(app):
    with app.app_context():
        with transaction():
            pay_ids = []
            for i in range(6):
                aid, _ = new_application(DATA, "langsung")
                pay_ids.append(
                    create_payment(aid, "pendaftaran", "tunai", 200000, secrets.token_hex(20))
                )

    def approve(pay_id):
        with app.app_context():
            g.user = one("SELECT * FROM users WHERE username='bendahara'")
            with transaction():
                return approve_payment(pay_id)

    with ThreadPoolExecutor(max_workers=6) as pool:
        ids = list(pool.map(approve, pay_ids))
    with app.app_context():
        assert len(set(ids)) == 6
        assert len({x["number"] for x in all_rows("SELECT number FROM participants")}) == 6


def test_registration_matching_activation_and_reused_token(app):
    with app.app_context():
        g.user = one("SELECT * FROM users WHERE username='bendahara'")
        with transaction():
            pid, _, _ = paid_participant()
        number = participant(pid)["number"]
    c = app.test_client()
    bad = post(
        c,
        "/daftar-akun",
        {
            **DATA,
            "number": number,
            "birth_place": "Keliru",
            "password": PASSWORD,
            "confirm": PASSWORD,
        },
    )
    assert bad.status_code == 400
    assert (
        post(
            c, "/daftar-akun", {**DATA, "number": number, "password": PASSWORD, "confirm": PASSWORD}
        ).status_code
        == 302
    )
    assert post(c, "/login", {"username": number, "password": PASSWORD}).status_code == 400
    with app.app_context():
        event = one("SELECT payload FROM outbox WHERE event_key LIKE 'aktivasi:%'")
        path = json.loads(event["payload"])["link"].replace("http://localhost", "")
    assert c.get(path).status_code == 200
    with app.app_context():
        assert one("SELECT active FROM users WHERE username=?", (number,))["active"] == 0
    assert post(c, path).status_code == 302
    assert post(c, path).status_code == 400
    assert post(c, "/login", {"username": number, "password": PASSWORD}).status_code == 302


def test_reset_expiry_single_use_and_session_revocation(app):
    with app.app_context():
        g.user = one("SELECT * FROM users WHERE username='bendahara'")
        with transaction():
            pid, _, _ = paid_participant(account=True)
        number = participant(pid)["number"]
    c = app.test_client()
    login_as(app, c, number)
    assert post(c, "/lupa-password", {"number": number, "email": DATA["email"]}).status_code == 302
    with app.app_context():
        path = json.loads(
            one("SELECT payload FROM outbox WHERE event_key LIKE 'reset:%'")["payload"]
        )["link"].replace("http://localhost", "")
    assert post(c, path, {"password": PASSWORD + "x", "confirm": PASSWORD + "x"}).status_code == 302
    assert c.get("/dashboard").status_code == 302
    assert post(c, path, {"password": PASSWORD, "confirm": PASSWORD}).status_code == 400
    assert post(c, "/lupa-password", {"number": number, "email": DATA["email"]}).status_code == 302
    with app.app_context():
        event = one(
            "SELECT payload FROM outbox WHERE event_key LIKE 'reset:%' ORDER BY created_at DESC LIMIT 1"
        )
        path = json.loads(event["payload"])["link"].replace("http://localhost", "")
        execute("UPDATE account_tokens SET expires_at='2000-01-01' WHERE kind='reset'")
    assert c.get(path).status_code == 400


def test_isolation_and_roles(app):
    with app.app_context():
        g.user = one("SELECT * FROM users WHERE username='bendahara'")
        with transaction():
            p1, _, _ = paid_participant(account=True)
            p2, _, _ = paid_participant(account=True)
        number = participant(p1)["number"]
        doc = one("SELECT id FROM documents WHERE participant_id=?", (p2,))["id"]
    c = app.test_client()
    login_as(app, c, number)
    assert c.get(f"/peserta/{p2}").status_code == 403
    assert c.get(f"/dokumen/{doc}").status_code == 403
    assert c.get("/laporan/pendaftaran.xlsx").status_code == 403
    assert c.get("/pengaturan").status_code == 403
    login_as(app, c, "admin")
    assert post(c, "/keuangan", {"action": "approve", "payment_id": 1}).status_code == 403
    assert post(c, f"/peserta/{p1}/draft", {"result": "Lulus"}).status_code == 403
    login_as(app, c, "bendahara")
    assert c.get(f"/peserta/{p1}").status_code == 403
    assert c.get("/laporan/pendaftaran.xlsx").status_code == 403
    login_as(app, c, "berkas")
    assert c.get("/laporan/pembayaran.xlsx").status_code == 403
    assert c.get("/keuangan").status_code == 403
    login_as(app, c, "rangkap")
    assert c.get("/keuangan").status_code == 200
    assert post(c, f"/peserta/{p1}/draft", {"result": "Lulus"}).status_code == 302


def test_bio_lock_and_draft_hidden_and_scan_no_attendance(app):
    with app.app_context():
        g.user = one("SELECT * FROM users WHERE username='rangkap'")
        with transaction():
            pid, _, _ = paid_participant(account=True)
            save_bio(pid, BIO)
            open_schedule(wednesday())
            sid = one("SELECT id FROM schedules")["id"]
            set_schedule(pid, sid)
            execute("UPDATE participants SET draft_result='Tidak lulus' WHERE id=?", (pid,))
        number = participant(pid)["number"]
    c = app.test_client()
    login_as(app, c, number)
    html = c.get(f"/peserta/{pid}").get_data(as_text=True)
    assert "Menunggu hasil" in html and "Tidak lulus" not in html
    assert post(c, f"/peserta/{pid}/card").status_code == 302
    assert post(c, f"/peserta/{pid}/bio", BIO).status_code == 400
    with app.app_context():
        token = one("SELECT token FROM documents WHERE kind='kartu'")["token"]
    assert c.get("/absensi/" + token).status_code == 403
    login_as(app, c, "berkas")
    assert c.get("/absensi/" + token).status_code == 302
    with app.app_context():
        assert participant(pid)["attendance"] == "Belum dicatat"
    assert post(c, f"/peserta/{pid}/attendance", {"attendance": "Hadir"}).status_code == 400
    assert (
        post(c, f"/peserta/{pid}/attendance", {"attendance": "Hadir", "ack": "ya"}).status_code
        == 302
    )


def test_schedule_weekday_close_and_cancel(app):
    with app.app_context():
        g.user = one("SELECT * FROM users WHERE username='rangkap'")
        wrong = date.fromisoformat(wednesday()) + timedelta(days=1)
        with pytest.raises(RuleError):
            open_schedule(wrong.isoformat())
        with transaction():
            pid, _, _ = paid_participant()
            save_bio(pid, BIO)
            open_schedule(wednesday())
            sid = one("SELECT id FROM schedules")["id"]
            set_schedule(pid, sid)
            open_schedule((date.fromisoformat(wednesday()) + timedelta(days=7)).isoformat())
    c = app.test_client()
    login_as(app, c, "berkas")
    assert post(c, "/jadwal", {"action": "close", "schedule_id": sid}).status_code == 302
    with app.app_context():
        assert participant(pid)["schedule_id"] == sid
        g.user = one("SELECT * FROM users WHERE username='rangkap'")
        p2, _, _ = paid_participant()
        save_bio(p2, BIO)
        with pytest.raises(RuleError):
            set_schedule(p2, sid)
    assert (
        post(
            c,
            "/jadwal",
            {
                "action": "cancel",
                "schedule_id": sid,
                "replacement": sid + 1,
                "reason": "Perawatan lokasi",
                "confirm": "ya",
            },
        ).status_code
        == 302
    )
    with app.app_context():
        assert participant(pid)["schedule_id"] == sid + 1


def test_result_correction_revokes_letter_and_preserves_money(ctx):
    with transaction():
        pid, aid, _ = paid_participant()
        passed(pid)
        doc = one("SELECT * FROM documents WHERE kind='kelulusan'")
        pay = create_payment(aid, "daftar_ulang", "tunai", 500000, secrets.token_hex(20))
        approve_payment(pay)
        publish_result(pid, "Tidak lulus", "Koreksi keputusan", True)
    assert one("SELECT valid FROM documents WHERE id=?", (doc["id"],))["valid"] == 0
    assert participant(pid)["financial_review"] == 1
    assert balance(pid)["paid"] == 500000
    with pytest.raises(RuleError):
        create_payment(aid, "daftar_ulang", "tunai", 500000, secrets.token_hex(20))


@pytest.mark.parametrize("level", ["MI", "MTS", "MA"])
def test_required_docs_including_photo_and_diploma(ctx, level):
    with transaction():
        pid, _, _ = paid_participant(level)
        passed(pid)
        accepted_files(pid, level)
    assert documents_complete(pid)
    assert ("skl" in required_docs(level)) == (level != "MI")
    assert "foto" in latest_uploads(pid)
    assert ("ijazah" in latest_uploads(pid)) == (level != "MI")


def test_upload_lock_and_finance_cannot_read_identity(app):
    with app.app_context():
        g.user = one("SELECT * FROM users WHERE username='rangkap'")
        with transaction():
            pid, _, _ = paid_participant(account=True)
            passed(pid)
            accepted_files(pid)
        number = participant(pid)["number"]
        uid = latest_uploads(pid)["akta"]["id"]
    c = app.test_client()
    login_as(app, c, number)
    result = post(
        c, f"/peserta/{pid}/upload", {"category": "akta", "file": (io.BytesIO(PDF), "akta.pdf")}
    )
    assert result.status_code == 400
    login_as(app, c, "bendahara")
    assert c.get(f"/berkas/{uid}").status_code == 403


def test_installment_pending_rejection_and_max_two(ctx):
    with transaction():
        pid, aid, _ = paid_participant()
        passed(pid)
        with pytest.raises(RuleError):
            create_payment(aid, "daftar_ulang", "tunai", 499999, secrets.token_hex(20))
        uid = execute(
            "INSERT INTO uploads(application_id,category,filename,storage_name,mime,size,created_at) VALUES(?,'bukti','a.pdf',?,'application/pdf',1,?)",
            (aid, secrets.token_hex(20), now()),
        ).lastrowid
        pay = create_payment(aid, "daftar_ulang", "transfer", 600000, secrets.token_hex(20), uid)
        assert balance(pid)["paid"] == 0
        reject_payment(pay, "Bukti tidak sesuai")
        assert balance(pid)["count"] == 0
        pay = create_payment(aid, "daftar_ulang", "tunai", 600000, "test-key")
        approve_payment(pay)
        approve_payment(pay)
        assert create_payment(aid, "daftar_ulang", "tunai", 600000, "test-key") == pay
        with pytest.raises(RuleError):
            create_payment(aid, "daftar_ulang", "tunai", 300000, secrets.token_hex(20))
        p2 = create_payment(aid, "daftar_ulang", "tunai", 400000, secrets.token_hex(20))
        approve_payment(p2)
        with pytest.raises(RuleError):
            create_payment(aid, "daftar_ulang", "tunai", 1, secrets.token_hex(20))
    assert balance(pid)["paid"] == 1000000 and balance(pid)["count"] == 2


def test_completion_correction_reissues_and_revokes(ctx):
    with transaction():
        pid, aid, _ = paid_participant()
        passed(pid)
        accepted_files(pid)
        pay = create_payment(aid, "daftar_ulang", "tunai", 1000000, secrets.token_hex(20))
        approve_payment(pay)
        assert participant(pid)["completed"]
        old = one("SELECT * FROM documents WHERE kind='daftar_ulang'")
        correct_payment(pay, 900000, "Salah catat nominal")
        assert not participant(pid)["completed"]
        assert not one("SELECT valid FROM documents WHERE id=?", (old["id"],))["valid"]
        correct_payment(pay, 1000000, "Selisih diterima, rekonsiliasi oleh Bendahara")
    assert participant(pid)["completed"]
    assert one("SELECT COUNT(*) AS n FROM documents WHERE kind='daftar_ulang'")["n"] == 2
    assert one("SELECT COUNT(*) AS n FROM audit WHERE action='Pembayaran dikoreksi'")["n"] == 2


def test_unset_fee_not_zero_and_fee_snapshot(ctx):
    with transaction():
        pid, _, _ = paid_participant()
        execute("UPDATE participants SET draft_result='Lulus' WHERE id=?", (pid,))
        publish_result(pid, "Lulus")
        assert balance(pid)["remaining"] is None
        assert not participant(pid)["completed"]
        execute(
            "INSERT INTO fee_versions(level,components,total,created_at) VALUES(?,?,?,?)",
            ("MI", "[]", 1000000, now()),
        )
        assert invoice(pid)["total"] == 1000000
        execute(
            "INSERT INTO fee_versions(level,components,total,created_at) VALUES(?,?,?,?)",
            ("MI", "[]", 2000000, now()),
        )
        assert invoice(pid)["total"] == 1000000


def test_reminder_deferred_pending_and_dedup(ctx):
    with transaction():
        pid, aid, _ = paid_participant()
        passed(pid)
        uid = execute(
            "INSERT INTO uploads(application_id,category,filename,storage_name,mime,size,created_at) VALUES(?,'bukti','a.pdf',?,'application/pdf',1,?)",
            (aid, secrets.token_hex(20), now()),
        ).lastrowid
        pay = create_payment(aid, "daftar_ulang", "transfer", 500000, secrets.token_hex(20), uid)
    queue_reminders(date(2027, 9, 23))
    queue_reminders(date(2027, 9, 23))
    events = all_rows("SELECT * FROM outbox WHERE event_key LIKE 'payment-reminder:%'")
    assert len(events) == 2
    process_outbox(ctx)
    assert all(
        e["status"] == "menunggu"
        for e in all_rows("SELECT * FROM outbox WHERE event_key LIKE 'payment-reminder:%'")
    )
    with transaction():
        reject_payment(pay, "Uji")
        execute(
            "UPDATE outbox SET next_attempt_at=? WHERE event_key LIKE 'payment-reminder:%'",
            (now(),),
        )
    process_outbox(ctx)
    assert all(
        e["status"] == "simulasi"
        for e in all_rows("SELECT * FROM outbox WHERE event_key LIKE 'payment-reminder:%'")
    )


def test_callback_auth_and_duplicate(app):
    with app.app_context():
        g.user = one("SELECT * FROM users WHERE username='bendahara'")
        with transaction():
            paid_participant()
        e = one("SELECT * FROM outbox")
        execute("UPDATE outbox SET status='diproses' WHERE id=?", (e["id"],))
    c = app.test_client()
    data = {
        "event_id": e["id"],
        "attempt": 0,
        "status": "berhasil",
        "delivery_id": "provider-example",
    }
    assert c.post("/integrasi/callback", json=data).status_code == 401
    headers = {"Authorization": "Bearer test-integration-only"}
    assert c.post("/integrasi/callback", json=data, headers=headers).status_code == 200
    assert c.post("/integrasi/callback", json=data, headers=headers).json["duplicate"]
    assert not c.post("/integrasi/event/" + e["id"], headers=headers).json["send"]


def test_public_verification_minimal_and_pdf_word_xlsx(app):
    with app.app_context():
        g.user = one("SELECT * FROM users WHERE username='rangkap'")
        with transaction():
            pid, _, _ = paid_participant(account=True)
            passed(pid)
        doc = one("SELECT * FROM documents WHERE kind='kelulusan'")
    c = app.test_client()
    response = c.get("/verifikasi/" + doc["token"])
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert DATA["email"] not in html and DATA["birth_date"] not in html and "snapshot" not in html
    login_as(app, c, "admin")
    pdf = c.get("/dokumen/" + str(doc["id"]))
    assert pdf.status_code == 200 and pdf.data.startswith(b"%PDF")
    word = c.get("/dokumen/" + str(doc["id"]) + "?format=docx")
    assert word.status_code == 200 and word.data.startswith(b"PK")
    excel = c.get("/laporan/pendaftaran.xlsx")
    assert excel.status_code == 200 and excel.data.startswith(b"PK")
    assert c.get("/laporan/pembayaran.xlsx").status_code == 200


def test_all_main_pages_and_csrf(app):
    c = app.test_client()
    for url in (
        "/",
        "/login",
        "/daftar-akun",
        "/pendaftaran-online",
        "/lupa-password",
        "/kirim-aktivasi",
        "/health",
    ):
        assert c.get(url).status_code == 200, url
    assert c.post("/login", data={"username": "admin", "password": PASSWORD}).status_code == 400
    login_as(app, c, "rangkap")
    for url in (
        "/dashboard",
        "/peserta",
        "/jadwal",
        "/keuangan",
        "/laporan",
        "/pengaturan",
        "/aktivitas",
        "/akun",
    ):
        assert c.get(url).status_code == 200, url


def test_file_content_size_and_ktp_replacement(app):
    with app.app_context():
        g.user = one("SELECT * FROM users WHERE username='rangkap'")
        with transaction():
            pid, _, _ = paid_participant(account=True)
            passed(pid)
        number = participant(pid)["number"]
    c = app.test_client()
    login_as(app, c, number)
    assert (
        post(
            c,
            f"/peserta/{pid}/upload",
            {"category": "akta", "file": (io.BytesIO(b"<script>bad</script>"), "a.pdf")},
        ).status_code
        == 400
    )
    assert (
        post(
            c,
            f"/peserta/{pid}/upload",
            {"category": "ktp_ayah", "replacement": "wali", "file": (io.BytesIO(PDF), "a.pdf")},
        ).status_code
        == 302
    )
    assert (
        post(
            c,
            f"/peserta/{pid}/upload",
            {
                "category": "ktp_ayah",
                "replacement": "wali",
                "reason": "Ayah tidak tersedia",
                "file": (io.BytesIO(PDF), "a.pdf"),
            },
        ).status_code
        == 302
    )
    html=c.get(f"/peserta/{pid}/menu/berkas").get_data(as_text=True)
    assert 'Alasan penggantian / penggunaan KTP wali' not in html
    assert 'Alasan penggantian oleh petugas' not in html
    with app.app_context():
        u = latest_uploads(pid)["ktp_ayah"]
        assert u["replaces"] == "KTP wali"
        assert "ktp_ibu" not in latest_uploads(pid)


def test_original_tracking_link_survives_rejection(ctx):
    with transaction():
        aid, token = new_application(DATA, "online")
        uid = execute(
            "INSERT INTO uploads(application_id,category,filename,storage_name,mime,size,created_at) VALUES(?,'bukti','a.pdf',?,'application/pdf',1,?)",
            (aid, secrets.token_hex(20), now()),
        ).lastrowid
        pay = create_payment(aid, "pendaftaran", "transfer", 200000, "proof-key", uid)
        reject_payment(pay, "Nominal tidak cocok")
    assert one("SELECT tracking_hash FROM applications WHERE id=?", (aid,))[
        "tracking_hash"
    ] == digest(token)
