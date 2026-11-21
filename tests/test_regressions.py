import io
import json
import secrets
import shutil
import sqlite3
import pytest
from datetime import date
from pathlib import Path
from flask import g
from psb.app import create_app
from psb.db import one, execute, transaction, all_rows, now
from psb.domain import save_bio, issue_document, participant, notify
from psb.notifications import queue_reminders
from conftest import login_as, post
from test_system import paid_participant, passed, BIO, PDF


def test_operational_date_uses_jakarta():
    from psb.domain import tanggal, waktu

    assert tanggal("2026-11-11T18:30:00+00:00") == "12 November 2026"
    assert waktu("2026-11-11T18:30:00+00:00") == "12 November 2026 01.30 WIB"


def test_form_regenerates_after_edit_before_card(app):
    with app.app_context():
        g.user = one("SELECT * FROM users WHERE username='rangkap'")
        with transaction():
            pid, _, _ = paid_participant(account=True)
            save_bio(pid, BIO)
            did = issue_document(pid, "formulir")
            save_bio(pid, {**BIO, "address": "Alamat Fiktif Diperbarui"})
        assert not one("SELECT valid FROM documents WHERE id=?", (did,))["valid"]
        number = participant(pid)["number"]
    client = app.test_client()
    login_as(app, client, number)
    result = post(client, f"/peserta/{pid}/form")
    assert result.status_code == 302
    assert result.location != f"/dokumen/{did}"
    assert client.get(result.location).data.startswith(b"%PDF")


def test_blank_form_and_history_follow_roles(app):
    with app.app_context():
        g.user = one("SELECT * FROM users WHERE username='rangkap'")
        with transaction():
            pid, _, _ = paid_participant(account=True)
        number = participant(pid)["number"]
    client = app.test_client()
    login_as(app, client, "bendahara")
    assert client.get("/formulir-kosong").data.startswith(b"%PDF")
    assert client.get(f"/peserta/{pid}/riwayat").status_code == 403
    login_as(app, client, "berkas")
    assert client.get(f"/peserta/{pid}/riwayat").status_code == 200
    login_as(app, client, number)
    assert client.get("/formulir-kosong").status_code == 403
    assert client.get(f"/peserta/{pid}/riwayat").status_code == 403


def test_payment_correction_http_is_idempotent(app):
    from psb.domain import create_payment, approve_payment

    with app.app_context():
        g.user = one("SELECT * FROM users WHERE username='bendahara'")
        with transaction():
            pid, aid, _ = paid_participant()
            passed(pid)
            pay = create_payment(aid, "daftar_ulang", "tunai", 1000000, secrets.token_hex(20))
            approve_payment(pay)
    client = app.test_client()
    login_as(app, client, "bendahara")
    data = {
        "action": "correct",
        "payment_id": pay,
        "amount": 900000,
        "reason": "Koreksi jumlah yang tercatat",
        "confirm": "ya",
        "key": "same-correction",
    }
    assert post(client, "/keuangan", data).status_code == 302
    assert post(client, "/keuangan", data).status_code == 302
    with app.app_context():
        assert one("SELECT COUNT(*) AS n FROM audit WHERE action='Pembayaran dikoreksi'")["n"] == 1


def test_reminder_status_changes_after_worker_claim(app):
    from psb.domain import create_payment

    with app.app_context():
        g.user = one("SELECT * FROM users WHERE username='rangkap'")
        with transaction():
            pid, aid, _ = paid_participant()
            passed(pid)
        queue_reminders(date(2027, 9, 23))
        event = one("SELECT * FROM outbox WHERE event_key LIKE 'payment-reminder:%'")
        execute("UPDATE outbox SET status='diproses',attempts=1 WHERE id=?", (event["id"],))
        with transaction():
            # Penerimaan tunai belum disahkan untuk mensimulasikan status menunggu.
            create_payment(aid, "daftar_ulang", "tunai", 500000, "pending-at-preflight")
    client = app.test_client()
    response = client.post(
        "/integrasi/event/" + event["id"], headers={"Authorization": "Bearer test-integration-only"}
    )
    assert response.status_code == 200 and response.json["send"] is False
    with app.app_context():
        assert one("SELECT status FROM outbox WHERE id=?", (event["id"],))["status"] == "menunggu"


def test_old_callback_does_not_mutate_new_attempt(app):
    with app.app_context():
        g.user = one("SELECT * FROM users WHERE username='rangkap'")
        with transaction():
            paid_participant()
        event = one("SELECT id FROM outbox")
        execute("UPDATE outbox SET status='diproses',attempts=2 WHERE id=?", (event["id"],))
    response = app.test_client().post(
        "/integrasi/callback",
        headers={"Authorization": "Bearer test-integration-only"},
        json={"event_id": event["id"], "attempt": 1, "status": "gagal", "safe_to_retry": True},
    )
    assert response.status_code == 409
    with app.app_context():
        assert one("SELECT status FROM outbox WHERE id=?", (event["id"],))["status"] == "diproses"


def test_missing_files_notification_is_idempotent(app):
    with app.app_context():
        g.user = one("SELECT * FROM users WHERE username='rangkap'")
        with transaction():
            pid, _, _ = paid_participant()
            passed(pid)
    client = app.test_client()
    login_as(app, client, "berkas")
    data = {"key": "missing-files-test", "reason": "Mohon dilengkapi sebelum pelunasan."}
    assert post(client, f"/peserta/{pid}/remind-files", data).status_code == 302
    assert post(client, f"/peserta/{pid}/remind-files", data).status_code == 302
    with app.app_context():
        events = all_rows("SELECT * FROM outbox WHERE event_key LIKE 'missing-files:%'")
        assert len(events) == 1 and events[0]["channel"] == "whatsapp"


def test_database_restore_keeps_document_validity(app, tmp_path):
    if app.config.get("DATABASE_URL"):
        pytest.skip("Pemulihan SQLite diperiksa pada backend SQLite; MySQL mempunyai uji dump/restore sendiri.")
    with app.app_context():
        g.user = one("SELECT * FROM users WHERE username='rangkap'")
        with transaction():
            paid_participant()
        token = one("SELECT token FROM documents")["token"]
    restored = tmp_path / "restored"
    restored.mkdir()
    with (
        sqlite3.connect(app.config["DATABASE"]) as source,
        sqlite3.connect(restored / "psb.sqlite3") as destination,
    ):
        source.backup(destination)
        assert destination.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    shutil.copytree(app.config["UPLOAD_DIR"], restored / "private")
    recovered = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": secrets.token_hex(32),
            "DATA_DIR": str(restored),
            "DATABASE": str(restored / "psb.sqlite3"),
            "UPLOAD_DIR": str(restored / "private"),
            "NOTIFICATION_MODE": "simulation",
        }
    )
    response = recovered.test_client().get("/verifikasi/" + token)
    assert response.status_code == 200 and b"Dokumen berlaku" in response.data
