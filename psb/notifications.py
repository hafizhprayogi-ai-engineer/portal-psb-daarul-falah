import json
import secrets
import smtplib
import socket
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr
from flask import abort, request
from .db import all_rows, one, execute, transaction, now, audit
from .domain import participant, balance, notify, today, tanggal, service_hours, rupiah


def smtp_ready(app):
    """Periksa konfigurasi tanpa membuka koneksi atau menampilkan rahasia."""
    required = ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM")
    missing = [key for key in required if not app.config.get(key)]
    if missing:
        raise ValueError("Konfigurasi SMTP belum lengkap: " + ", ".join(missing) + ".")
    _, address = parseaddr(app.config["SMTP_FROM"])
    if not address or "@" not in address:
        raise ValueError("SMTP_FROM harus berupa alamat email pengirim yang valid.")
    if not (1 <= int(app.config["SMTP_PORT"]) <= 65535):
        raise ValueError("SMTP_PORT tidak valid.")


def smtp_connection(app):
    smtp_ready(app)
    connection = smtplib.SMTP(
        app.config["SMTP_HOST"], int(app.config["SMTP_PORT"]), timeout=20
    )
    connection.ehlo()
    if app.config["SMTP_STARTTLS"]:
        connection.starttls()
        connection.ehlo()
    connection.login(app.config["SMTP_USERNAME"], app.config["SMTP_PASSWORD"])
    return connection


def send_email(app, event):
    """Kirim satu event email dan kembalikan Message-ID yang diterima penyedia SMTP."""
    recipient = event["destination"].strip()
    if not recipient or "@" not in parseaddr(recipient)[1]:
        raise ValueError("Alamat email tujuan tidak valid.")
    message = EmailMessage()
    message["Subject"] = "Portal Penerimaan Santri Baru — Daarul Falah 2 Maliku"
    message["From"] = formataddr(("Portal PSB Daarul Falah 2 Maliku", app.config["SMTP_FROM"]))
    message["To"] = recipient
    message["Message-ID"] = make_msgid(idstring=event["id"], domain=socket.getfqdn())
    message.set_content(event["message"])
    with smtp_connection(app) as connection:
        refused = connection.send_message(message)
    if refused:
        raise ValueError("Server SMTP menolak alamat tujuan.")
    return message["Message-ID"]


def eligible(event):
    payload = json.loads(event["payload"])
    if payload.get("reminder") == "payment":
        p = participant(event["participant_id"])
        b = balance(p["id"])
        return (
            p["published_result"] == "Lulus"
            and b["remaining"] is not None
            and b["remaining"] > 0
            and not one(
                "SELECT id FROM payments WHERE participant_id=? AND kind='daftar_ulang' AND status='Menunggu verifikasi'",
                (p["id"],),
            )
        )
    if payload.get("reminder") == "test":
        p = participant(event["participant_id"])
        s = one("SELECT * FROM schedules WHERE id=?", (p["schedule_id"],))
        return s and s["date"] == payload["date"] and s["status"] != "Dibatalkan"
    return True


def queue_reminders(on=None):
    on = on or today()
    tomorrow = (on + timedelta(days=1)).isoformat()
    from flask import current_app

    with transaction():
        for p in all_rows(
            "SELECT p.*,s.date,a.id AS aid FROM participants p JOIN schedules s ON s.id=p.schedule_id JOIN applications a ON a.id=p.application_id WHERE s.date=? AND s.status<>'Dibatalkan'",
            (tomorrow,),
        ):
            notify(
                p["aid"],
                f'test-reminder:{p["id"]}:{tomorrow}',
                f"Pengingat tes besok, {tanggal(tomorrow)}, {service_hours(tomorrow)}, di Pondok Pesantren Daarul Falah 2 Maliku. Kartu: {current_app.config['BASE_URL']}/peserta/{p['id']}/menu/jadwal",
                payload={"reminder": "test", "date": tomorrow},
            )
        if on.isoformat() in ("2027-09-23", "2027-09-29"):
            for p in all_rows("SELECT * FROM participants WHERE published_result='Lulus'"):
                b = balance(p["id"])
                if b["remaining"] is None or b["remaining"] == 0:
                    continue
                notify(
                    p["application_id"],
                    f'payment-reminder:{p["id"]}:{on.isoformat()}',
                    f"Pengingat pelunasan: sisa {rupiah(b['remaining'])}. Tenggat 30 September 2027. Periksa rincian tagihan di akun.",
                    payload={"reminder": "payment", "date": on.isoformat()},
                )


def process_outbox(app, limit=50):
    sent = 0
    # Jangan mengirim ulang status diproses tanpa keputusan petugas: timeout callback
    # dapat berarti pesan sudah terkirim. Retry memakai event ID yang sama.
    for _ in range(limit):
        with transaction():
            rows = all_rows(
                "SELECT * FROM outbox WHERE status IN ('menunggu','gagal') AND attempts<5 AND next_attempt_at<=? ORDER BY created_at LIMIT 100",
                (now(),),
            )
            event = None
            for row in rows:
                if not eligible(row):
                    payload = json.loads(row["payload"])
                    if payload.get("reminder") == "payment":
                        p = participant(row["participant_id"])
                        if p["published_result"] == "Lulus" and balance(p["id"])["remaining"]:
                            later = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
                            execute(
                                "UPDATE outbox SET next_attempt_at=? WHERE id=?", (later, row["id"])
                            )
                            continue
                    execute("UPDATE outbox SET status='dibatalkan' WHERE id=?", (row["id"],))
                    continue
                event = row
                execute(
                    "UPDATE outbox SET status='diproses',attempts=attempts+1,claimed_at=? WHERE id=?",
                    (now(), event["id"]),
                )
                break
        if event is None:
            break
        if event["channel"] == "email" and app.config["EMAIL_DELIVERY_MODE"] == "smtp":
            try:
                delivery_id = send_email(app, event)
                with transaction():
                    execute(
                        "UPDATE outbox SET status='berhasil',delivery_id=?,last_error=NULL WHERE id=?",
                        (delivery_id[:200], event["id"]),
                    )
                    execute(
                        "INSERT INTO delivery_attempts(event_id,status,detail,created_at) VALUES(?,?,?,?)",
                        (event["id"], "berhasil", "Diterima server SMTP Gmail.", now()),
                    )
            except (smtplib.SMTPAuthenticationError, smtplib.SMTPConnectError, ConnectionRefusedError, ValueError) as exc:
                # Kredensial/koneksi diketahui gagal sebelum pesan diterima; aman dicoba ulang
                # setelah operator memperbaiki konfigurasi.
                with transaction():
                    execute("UPDATE outbox SET status='gagal',last_error=? WHERE id=?", (str(exc)[:500], event["id"]))
                    execute(
                        "INSERT INTO delivery_attempts(event_id,status,detail,created_at) VALUES(?,?,?,?)",
                        (event["id"], "gagal", "SMTP belum menerima pesan.", now()),
                    )
            except (smtplib.SMTPException, OSError) as exc:
                # Selain penolakan autentikasi/koneksi, kegagalan SMTP dapat terjadi sesudah
                # server menerima isi pesan. Jangan kirim ulang otomatis agar wali tidak
                # menerima email ganda; Admin memutuskan lewat halaman Aktivitas.
                with transaction():
                    execute("UPDATE outbox SET last_error=? WHERE id=?", (str(exc)[:500], event["id"]))
                    execute(
                        "INSERT INTO delivery_attempts(event_id,status,detail,created_at) VALUES(?,?,?,?)",
                        (event["id"], "diproses", "Perlu pemeriksaan SMTP sebelum dikirim ulang.", now()),
                    )
            sent += 1
            continue
        if app.config["NOTIFICATION_MODE"] == "simulation":
            with transaction():
                execute("UPDATE outbox SET status='simulasi' WHERE id=?", (event["id"],))
                execute(
                    "INSERT INTO delivery_attempts(event_id,status,detail,created_at) VALUES(?,?,?,?)",
                    (event["id"], "simulasi", "Tidak dikirim ke penyedia.", now()),
                )
            sent += 1
            continue
        try:
            url = app.config["N8N_WEBHOOK_URL"]
            if (
                not url.startswith("https://")
                or not app.config["N8N_WEBHOOK_TOKEN"]
                or not app.config["INTEGRATION_TOKEN"]
            ):
                raise ValueError("Konfigurasi webhook HTTPS dan token belum lengkap.")
            data = json.dumps(
                {"event_id": event["id"], "base_url": app.config["BASE_URL"]}
            ).encode()
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + app.config["N8N_WEBHOOK_TOKEN"],
                    "Idempotency-Key": event["id"],
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as response:
                if not 200 <= response.status < 300:
                    raise ValueError("Webhook tidak menerima kejadian.")
            with transaction():
                execute(
                    "INSERT INTO delivery_attempts(event_id,status,detail,created_at) VALUES(?,?,?,?)",
                    (
                        event["id"],
                        "diproses",
                        "Diterima webhook; menunggu callback penyedia.",
                        now(),
                    ),
                )
        except (urllib.error.URLError, ValueError, TimeoutError) as exc:
            # Timeout ambigu tidak di-retry otomatis: mencegah kirim ganda.
            with transaction():
                execute("UPDATE outbox SET last_error=? WHERE id=?", (str(exc)[:500], event["id"]))
                execute(
                    "INSERT INTO delivery_attempts(event_id,status,detail,created_at) VALUES(?,?,?,?)",
                    (event["id"], "diproses", "Perlu rekonsiliasi: " + str(exc)[:500], now()),
                )
        sent += 1
    return sent


def register_integration(app):
    def authenticate():
        token = app.config["INTEGRATION_TOKEN"]
        if not token or not secrets.compare_digest(
            request.headers.get("Authorization", ""), "Bearer " + token
        ):
            abort(401)

    @app.post("/integrasi/event/<event_id>")
    def integration_event(event_id):
        authenticate()
        with transaction():
            e = one("SELECT * FROM outbox WHERE id=?", (event_id,))
            if not e:
                abort(404)
            if e["status"] != "diproses":
                return {"send": False, "event_id": event_id}
            if not eligible(e):
                payload = json.loads(e["payload"])
                defer = False
                if payload.get("reminder") == "payment":
                    p = participant(e["participant_id"])
                    defer = p["published_result"] == "Lulus" and bool(balance(p["id"])["remaining"])
                if defer:
                    later = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
                    execute(
                        "UPDATE outbox SET status='menunggu',next_attempt_at=? WHERE id=?",
                        (later, event_id),
                    )
                else:
                    execute("UPDATE outbox SET status='dibatalkan' WHERE id=?", (event_id,))
                return {"send": False, "event_id": event_id}
            claimed = execute(
                "INSERT OR IGNORE INTO delivery_claims(event_id,attempt,claimed_at) VALUES(?,?,?)",
                (e["id"], e["attempts"], now()),
            )
            if not claimed.rowcount:
                return {"send": False, "event_id": event_id}
            message = e["message"]
            if json.loads(e["payload"]).get("reminder") == "payment":
                p = participant(e["participant_id"])
                b = balance(p["id"])
                message = f"{p['name']} ({p['number']}): Sisa tagihan {rupiah(b['remaining'])}. Pelunasan paling lambat 30 September 2027."
            return {
                "send": True,
                "event_id": e["id"],
                "attempt": e["attempts"],
                "channel": e["channel"],
                "destination": e["destination"],
                "message": message,
                "idempotency_key": e["id"],
            }

    @app.post("/integrasi/callback")
    def integration_callback():
        authenticate()
        data = request.get_json(silent=True) or {}
        if data.get("status") not in ("berhasil", "gagal") or not data.get("event_id"):
            abort(400)
        with transaction():
            e = one("SELECT * FROM outbox WHERE id=?", (data["event_id"],))
            if not e:
                abort(404)
            if e["status"] == "berhasil":
                return {"ok": True, "duplicate": True}
            if data.get("attempt") != e["attempts"]:
                abort(409)
            if e["status"] != "diproses":
                abort(409)
            if data["status"] == "berhasil" and not data.get("delivery_id"):
                abort(400)
            if data["status"] == "gagal" and data.get("safe_to_retry") is not True:
                execute(
                    "UPDATE outbox SET last_error=? WHERE id=?",
                    ("Kegagalan ambigu; rekonsiliasi penyedia diperlukan.", e["id"]),
                )
                return {"ok": True, "reconciliation": True}
            later = (datetime.now(timezone.utc) + timedelta(minutes=2 ** e["attempts"])).isoformat()
            execute(
                "UPDATE outbox SET status=?,delivery_id=?,last_error=?,next_attempt_at=? WHERE id=?",
                (
                    data["status"],
                    str(data.get("delivery_id", ""))[:200],
                    str(data.get("error", ""))[:500],
                    later,
                    e["id"],
                ),
            )
            execute(
                "INSERT INTO delivery_attempts(event_id,status,detail,created_at) VALUES(?,?,?,?)",
                (
                    e["id"],
                    data["status"],
                    str(data.get("delivery_id") or data.get("error", ""))[:500],
                    now(),
                ),
            )
        return {"ok": True}
