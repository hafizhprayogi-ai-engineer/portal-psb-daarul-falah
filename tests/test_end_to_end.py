import io
import json
import secrets
from pathlib import Path
from flask import g
from openpyxl import load_workbook
from psb.db import one, execute, transaction, all_rows, now
from psb.domain import participant, balance, latest_uploads, required_docs
from conftest import login_as, post, PASSWORD
from test_system import DATA, BIO, PDF, wednesday, paid_participant, passed


def test_online_to_completed_through_http(app):
    guardian = app.test_client()
    result = post(guardian, "/pendaftaran-online", DATA)
    assert result.status_code == 302
    tracking = result.location
    assert guardian.get(tracking).status_code == 200
    assert (
        post(
            guardian, tracking, {"key": "online-proof", "file": (io.BytesIO(PDF), "bukti.pdf")}
        ).status_code
        == 302
    )

    treasurer = app.test_client()
    login_as(app, treasurer, "bendahara")
    with app.app_context():
        pay = one("SELECT id FROM payments")["id"]
    assert post(treasurer, "/keuangan", {"action": "approve", "payment_id": pay}).status_code == 302
    with app.app_context():
        p = one("SELECT * FROM participants")
        pid = p["id"]
        number = p["number"]
        receipt = one("SELECT id FROM documents WHERE kind='kuitansi'")["id"]
    assert guardian.get(f"{tracking}/bukti/{receipt}").data.startswith(b"%PDF")

    assert (
        post(
            guardian,
            "/daftar-akun",
            {**DATA, "number": number, "password": PASSWORD, "confirm": PASSWORD},
        ).status_code
        == 302
    )
    with app.app_context():
        link = json.loads(
            one("SELECT payload FROM outbox WHERE event_key LIKE 'aktivasi:%'")["payload"]
        )["link"].replace("http://localhost", "")
    assert post(guardian, link).status_code == 302
    assert post(guardian, "/login", {"username": number, "password": PASSWORD}).status_code == 302
    assert post(guardian, f"/peserta/{pid}/bio", BIO).status_code == 302

    files = app.test_client()
    login_as(app, files, "berkas")
    assert post(files, "/jadwal", {"action": "open", "date": wednesday()}).status_code == 302
    with app.app_context():
        sid = one("SELECT id FROM schedules")["id"]
    assert post(guardian, f"/peserta/{pid}/schedule", {"schedule_id": sid}).status_code == 302
    card = post(guardian, f"/peserta/{pid}/card")
    assert card.status_code == 302 and guardian.get(card.location).data.startswith(b"%PDF")
    form = post(guardian, f"/peserta/{pid}/form")
    assert guardian.get(form.location).data.startswith(b"%PDF")
    assert (
        post(files, f"/peserta/{pid}/attendance", {"attendance": "Hadir", "ack": "ya"}).status_code
        == 302
    )
    assert post(files, f"/peserta/{pid}/draft", {"result": "Lulus"}).status_code == 302
    assert (
        post(files, f"/peserta/{pid}/publish", {"confirm": "ya", "key": "publish-e2e"}).status_code
        == 302
    )
    assert (
        post(files, f"/peserta/{pid}/publish", {"confirm": "ya", "key": "publish-e2e"}).status_code
        == 302
    )

    admin = app.test_client()
    login_as(app, admin, "admin")
    assert (
        post(
            admin,
            "/pengaturan",
            {
                "action": "fee",
                "level": "MI",
                "components": "Pendidikan contoh | 600000\nPerlengkapan contoh | 400000",
            },
        ).status_code
        == 302
    )
    assert guardian.get(f"/peserta/{pid}").status_code == 200
    for category in required_docs("MI"):
        from test_profile_photo import image
        is_photo = category == "foto"
        assert post(guardian, f"/peserta/{pid}/{'photo' if is_photo else 'upload'}", {
            "category": category,
            "file": (image(), "foto.png") if is_photo else (io.BytesIO(PDF), category + ".pdf")
        }).status_code == 302
        with app.app_context():
            uid = latest_uploads(pid)[category]["id"]
        assert files.get(f"/berkas/{uid}").status_code == 200
        if not is_photo:
            assert files.get(f"/berkas/{uid}").data == PDF
        assert (
            post(
                files, f"/peserta/{pid}/review", {"upload_id": uid, "status": "Diterima"}
            ).status_code
            == 302
        )
    assert (
        post(
            guardian,
            f"/peserta/{pid}/payment",
            {"key": "e2e-pay", "amount": "1000000", "file": (io.BytesIO(PDF), "daftar-ulang.pdf")},
        ).status_code
        == 302
    )
    with app.app_context():
        pay = one("SELECT id FROM payments WHERE kind='daftar_ulang'")["id"]
        assert not participant(pid)["completed"]
    assert post(treasurer, "/keuangan", {"action": "approve", "payment_id": pay}).status_code == 302
    with app.app_context():
        assert participant(pid)["completed"]
        doc = one("SELECT * FROM documents WHERE kind='daftar_ulang'")
    assert guardian.get("/dokumen/" + str(doc["id"])).data.startswith(b"%PDF")
    assert b"Dokumen berlaku" in guardian.get("/verifikasi/" + doc["token"]).data
    assert guardian.get(f"/peserta/{pid}").status_code == 200


def test_delivery_preflight_claimed_once_and_retry(app):
    with app.app_context():
        g.user = one("SELECT * FROM users WHERE username='bendahara'")
        with transaction():
            paid_participant()
        e = one("SELECT * FROM outbox")
        execute("UPDATE outbox SET status='diproses',attempts=1 WHERE id=?", (e["id"],))
    client = app.test_client()
    headers = {"Authorization": "Bearer test-integration-only"}
    assert client.post("/integrasi/event/" + e["id"], headers=headers).json["send"]
    assert not client.post("/integrasi/event/" + e["id"], headers=headers).json["send"]
    assert (
        client.post(
            "/integrasi/callback",
            headers=headers,
            json={
                "event_id": e["id"],
                "attempt": 1,
                "status": "gagal",
                "safe_to_retry": True,
                "error": "Ditolak sebelum diterima",
            },
        ).status_code
        == 200
    )
    with app.app_context():
        execute("UPDATE outbox SET status='diproses',attempts=2 WHERE id=?", (e["id"],))
    assert client.post("/integrasi/event/" + e["id"], headers=headers).json["send"]


def test_failed_upload_rolls_back_private_file(app):
    with app.app_context():
        g.user = one("SELECT * FROM users WHERE username='bendahara'")
        with transaction():
            pid, _, _ = paid_participant(account=True)
        number = participant(pid)["number"]
    client = app.test_client()
    login_as(app, client, number)
    result = post(
        client,
        f"/peserta/{pid}/payment",
        {"amount": 1000000, "key": "invalid-fee", "file": (io.BytesIO(PDF), "a.pdf")},
    )
    assert result.status_code == 400
    assert list(Path(app.config["UPLOAD_DIR"]).iterdir()) == []


def test_export_includes_pending_and_escapes_formulas(app):
    client = app.test_client()
    assert post(client, "/pendaftaran-online", {**DATA, "name": "=1+1"}).status_code == 302
    login_as(app, client, "berkas")
    response = client.get("/laporan/pendaftaran.xlsx")
    workbook = load_workbook(io.BytesIO(response.data))
    assert workbook.active["B2"].value == "=1+1"
    assert workbook.active["B2"].data_type == "s"


def test_scanner_and_reconciliation_permissions(app):
    client = app.test_client()
    login_as(app, client, "admin")
    assert client.get("/pemindai").status_code == 403
    assert client.get("/aktivitas").status_code == 200
    login_as(app, client, "berkas")
    assert client.get("/pemindai").status_code == 200
    assert client.get("/aktivitas").status_code == 403


def test_workflow_structure():
    path = Path(__file__).resolve().parents[1] / "n8n" / "psb-notifikasi.json"
    workflow = json.loads(path.read_text(encoding="utf-8"))
    assert workflow["active"] is False
    names = {node["name"] for node in workflow["nodes"]}
    for source, outputs in workflow["connections"].items():
        assert source in names
        for branch in outputs["main"]:
            for target in branch:
                assert target["node"] in names
    assert all("credentials" not in node for node in workflow["nodes"])
