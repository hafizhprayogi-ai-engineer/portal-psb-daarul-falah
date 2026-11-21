import hashlib
import json
import re
import secrets
import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo
from flask import current_app, g
from .db import one, all_rows, execute, now, audit, settings
from .biodata import BIO_GROUPS, BIO_FIELDS, PARENT_NOTES, bio_values, bio_errors, bio_group_status

LEVELS = ("MI", "MTS", "MA")
DOC_LABELS = {
    "foto": "Pasfoto / foto profil",
    "formulir": "Formulir bertanda tangan",
    "akta": "Akta kelahiran",
    "kk": "Kartu keluarga",
    "ktp_ayah": "KTP ayah",
    "ktp_ibu": "KTP ibu",
    "skl": "SKL",
    "ijazah": "Ijazah",
}


class RuleError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise RuleError(message)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def today():
    return datetime.now(ZoneInfo("Asia/Jakarta")).date()


def rupiah(value):
    return "Rp" + f"{int(value):,}".replace(",", ".")


def tanggal(value):
    if not value:
        return "Belum ditentukan"
    months = [
        "Januari",
        "Februari",
        "Maret",
        "April",
        "Mei",
        "Juni",
        "Juli",
        "Agustus",
        "September",
        "Oktober",
        "November",
        "Desember",
    ]
    text = str(value)
    if len(text) > 10:
        timestamp = datetime.fromisoformat(text)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=ZoneInfo("UTC"))
        d = timestamp.astimezone(ZoneInfo("Asia/Jakarta")).date()
    else:
        d = date.fromisoformat(text)
    return f"{d.day} {months[d.month-1]} {d.year}"


def waktu(value):
    if not value:
        return "Belum tersedia"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    dt = dt.astimezone(ZoneInfo("Asia/Jakarta"))
    return tanggal(dt.date().isoformat()) + " " + dt.strftime("%H.%M") + " WIB"


def service_hours(value):
    return "08.30–16.30 WIB" if date.fromisoformat(value).weekday() == 2 else "09.30–16.00 WIB"


def participant(pid):
    p = one(
        "SELECT p.*, a.name,a.level,a.birth_place,a.birth_date,a.phone,a.email,a.channel,a.created_at,a.year_id,a.status AS application_status FROM participants p JOIN applications a ON a.id=p.application_id WHERE p.id=?",
        (pid,),
    )
    require(p, "Peserta tidak ditemukan.")
    result = dict(p)
    stored = json.loads(result["bio"])
    if not result["locked_at"] and stored.get("schema_version") != 2:
        result["bio_complete"] = 0
    return result


def notify(app_id, key, message, channels=("whatsapp", "email"), payload=None):
    a = one("SELECT * FROM applications WHERE id=?", (app_id,))
    p = one("SELECT * FROM participants WHERE application_id=?", (app_id,))
    prefix = f"{a['name']} ({p['number'] if p else 'nomor belum diterbitkan; ' + a['reference']}): "
    for channel in channels:
        execute(
            "INSERT OR IGNORE INTO outbox(id,event_key,participant_id,application_id,channel,destination,message,payload,next_attempt_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                str(uuid.uuid4()),
                key,
                p["id"] if p else None,
                app_id,
                channel,
                a["phone"] if channel == "whatsapp" else a["email"],
                prefix + message,
                json.dumps(payload or {}, ensure_ascii=False),
                now(),
                now(),
            ),
        )


def initial_data(data):
    fields = ("level", "name", "birth_place", "birth_date", "phone", "email")
    result = {k: str(data.get(k, "")).strip() for k in fields}
    require(all(result.values()), "Lengkapi seluruh data awal peserta.")
    require(result["level"] in LEVELS, "Jenjang tidak valid.")
    require(
        len(result["name"]) <= 160 and len(result["birth_place"]) <= 160,
        "Nama/tempat lahir terlalu panjang.",
    )
    try:
        born = date.fromisoformat(result["birth_date"])
        require(date(1980, 1, 1) < born <= today(), "Tanggal lahir tidak valid.")
    except ValueError:
        raise RuleError("Tanggal lahir tidak valid.")
    result["email"] = result["email"].lower()
    require(
        re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", result["email"]) and len(result["email"]) <= 254,
        "Alamat email tidak valid.",
    )
    phone = re.sub(r"[\s+()-]", "", result["phone"])
    if phone.startswith("0"):
        phone = "62" + phone[1:]
    require(re.fullmatch(r"[0-9]{9,15}", phone), "Nomor WhatsApp harus berupa 9–15 digit.")
    result["phone"] = phone
    return result


def new_application(data, channel):
    d = initial_data(data)
    cfg = settings()
    if channel == "online":
        require(
            cfg.get("open_date") and cfg.get("close_date"),
            "Periode pendaftaran belum ditentukan. Hubungi panitia.",
        )
        require(
            cfg["open_date"] <= today().isoformat() <= cfg["close_date"],
            "Pendaftaran online sedang ditutup.",
        )
    token = secrets.token_urlsafe(32)
    app_id = execute(
        "INSERT INTO applications(reference,tracking_hash,level,name,birth_place,birth_date,phone,email,channel,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            "REF-" + secrets.token_hex(6).upper(),
            digest(token),
            *[d[k] for k in ("level", "name", "birth_place", "birth_date", "phone", "email")],
            channel,
            now(),
        ),
    ).lastrowid
    link = current_app.config["BASE_URL"] + "/pantau/" + token
    notify(
        app_id,
        f"application:{app_id}",
        f"Pengajuan tersimpan. Pantau dan unggah bukti melalui {link}",
        payload={"link": link},
    )
    audit("application", app_id, "Pengajuan dibuat", new={"channel": channel})
    return app_id, token


def invoice(pid):
    existing = one("SELECT * FROM invoices WHERE participant_id=?", (pid,))
    if existing:
        return existing
    p = participant(pid)
    if p["published_result"] != "Lulus":
        return None
    fee = one(
        "SELECT * FROM fee_versions WHERE level=? AND year_id=? ORDER BY id DESC LIMIT 1",
        (p["level"], p["year_id"]),
    )
    if fee:
        execute(
            "INSERT INTO invoices(participant_id,fee_version_id,components,total,created_at) VALUES(?,?,?,?,?)",
            (pid, fee["id"], fee["components"], fee["total"], now()),
        )
    return one("SELECT * FROM invoices WHERE participant_id=?", (pid,))


def invoice_revision_token(inv):
    revision = one("SELECT MAX(id) AS n FROM audit WHERE entity='invoice' AND entity_id=? AND action='Tagihan direvisi'", (inv["id"],))["n"]
    return digest(json.dumps([inv["id"], inv["components"], inv["total"], revision], ensure_ascii=False))


def revise_invoice(pid, components, reason, expected):
    inv = one("SELECT * FROM invoices WHERE participant_id=?", (pid,))
    require(inv is not None, "Tagihan peserta belum diterbitkan.")
    require(expected == invoice_revision_token(inv), "Tagihan sudah berubah. Muat ulang halaman sebelum merevisi.")
    require(3 <= len(reason.strip()) <= 500, "Isi alasan revisi (3-500 karakter).")
    require(components and len(components) <= 100, "Isi 1 sampai 100 komponen tagihan.")
    for item in components:
        require(isinstance(item.get("name"), str) and 0 < len(item["name"].strip()) <= 150
                and type(item.get("amount")) is int and 0 < item["amount"] < 1000000000,
                "Nama atau nominal tagihan tidak valid.")
    total = sum(item["amount"] for item in components)
    bal = balance(pid)
    require(not one("SELECT id FROM payments WHERE participant_id=? AND kind='daftar_ulang' AND status='Menunggu verifikasi'", (pid,)),
            "Selesaikan verifikasi transfer terlebih dahulu sebelum merevisi tagihan.")
    require(total >= bal["paid"], "Total revisi tidak boleh lebih kecil dari pembayaran yang sudah disahkan.")
    require(bal["count"] < 2 or total == bal["paid"], "Sudah dua pembayaran sah. Revisi harus tetap lunas; hubungi Bendahara untuk koreksi transaksi.")
    encoded = json.dumps(components, ensure_ascii=False)
    require(encoded != inv["components"] or total != inv["total"], "Rincian tagihan belum berubah.")
    was_complete = bool(participant(pid)["completed"])
    execute("UPDATE invoices SET components=?,total=? WHERE id=?", (encoded, total, inv["id"]))
    audit("invoice", inv["id"], "Tagihan direvisi", old=dict(inv),
          new={"components": components, "total": total}, reason=reason.strip())
    sync_completion(pid)
    if was_complete and participant(pid)["completed"]:
        invalidate(pid, ["daftar_ulang"])
        issue_document(pid, "daftar_ulang")


def balance(pid):
    inv = one("SELECT * FROM invoices WHERE participant_id=?", (pid,))
    paid = one(
        "SELECT COALESCE(SUM(amount),0) AS total, COUNT(*) AS count FROM payments WHERE participant_id=? AND kind='daftar_ulang' AND status='Disahkan'",
        (pid,),
    )
    return {
        "invoice": inv,
        "paid": paid["total"],
        "count": paid["count"],
        "remaining": max(0, inv["total"] - paid["total"]) if inv else None,
    }


def required_docs(level):
    return ["foto", "formulir", "akta", "kk", "ktp_ayah", "ktp_ibu"] + (
        [] if level == "MI" else ["skl", "ijazah"]
    )


def latest_uploads(pid):
    return {
        r["category"]: r
        for r in all_rows(
            "SELECT * FROM uploads WHERE id IN (SELECT MAX(id) FROM uploads WHERE participant_id=? AND category<>'bukti' GROUP BY category)",
            (pid,),
        )
    }


def documents_complete(pid):
    p = participant(pid)
    uploaded = latest_uploads(pid)
    accepted = {k for k, v in uploaded.items() if v["status"] == "Diterima"}
    base = set(required_docs("MI"))
    return base.issubset(accepted) and (p["level"] == "MI" or "ijazah" in accepted)


def cash_receiver(payment_id):
    entry = one("SELECT new_value FROM audit WHERE entity='payment' AND entity_id=? AND action='Penerima tunai dicatat' ORDER BY id DESC LIMIT 1", (payment_id,))
    return json.loads(entry["new_value"])["receiver_name"] if entry else ""


def issue_document(pid, kind, payment_id=None):
    p = participant(pid)
    previous = one(
        "SELECT COALESCE(MAX(version),0) AS version FROM documents WHERE participant_id=? AND kind=?",
        (pid, kind),
    )["version"]
    schedule = (
        one("SELECT * FROM schedules WHERE id=?", (p["schedule_id"],)) if p["schedule_id"] else None
    )
    bal = balance(pid)
    cfg = settings()
    snapshot = {
        k: p[k]
        for k in ("number", "name", "level", "birth_place", "birth_date", "bio", "published_result")
    }
    snapshot.update(
        {
            "schedule": dict(schedule) if schedule else None,
            "year": "2027/2028",
            "invoice": dict(bal["invoice"]) if bal["invoice"] else None,
            "paid": bal["paid"],
            "remaining": bal["remaining"],
            "template": cfg.get("letter_body" if kind == "kelulusan" else "form_body", ""),
            "letterhead": cfg.get("letterhead", ""),
            "signer": cfg.get("signer", ""),
            "letter_number": cfg.get("letter_number", ""),
            "draft": cfg.get("template_official") != "ya",
        }
    )
    if payment_id:
        snapshot["payment"] = dict(one("SELECT * FROM payments WHERE id=?", (payment_id,)))
        snapshot["payment"]["receiver_name"] = cash_receiver(payment_id)
    doc_id = execute(
        "INSERT INTO documents(participant_id,kind,version,token,snapshot,payment_id,created_at) VALUES(?,?,?,?,?,?,?)",
        (
            pid,
            kind,
            previous + 1,
            secrets.token_urlsafe(32),
            json.dumps(snapshot, ensure_ascii=False),
            payment_id,
            now(),
        ),
    ).lastrowid
    audit("document", doc_id, "Dokumen diterbitkan", new={"kind": kind, "version": previous + 1})
    return doc_id


def invalidate(pid, kinds, payment_id=None):
    for kind in kinds:
        sql = "SELECT id FROM documents WHERE participant_id=? AND kind=? AND valid=1"
        args = [pid, kind]
        if payment_id:
            sql += " AND payment_id=?"
            args.append(payment_id)
        for doc in all_rows(sql, args):
            execute("UPDATE documents SET valid=0 WHERE id=?", (doc["id"],))
            audit("document", doc["id"], "Dokumen tidak berlaku")


def sync_completion(pid):
    p = participant(pid)
    bal = balance(pid)
    complete = (
        p["published_result"] == "Lulus"
        and documents_complete(pid)
        and bal["invoice"] is not None
        and bal["remaining"] == 0
    )
    if bool(p["completed"]) == bool(complete):
        return
    execute("UPDATE participants SET completed=? WHERE id=?", (int(complete), pid))
    invalidate(pid, ["daftar_ulang"])
    if complete:
        doc_id = issue_document(pid, "daftar_ulang")
        link = current_app.config["BASE_URL"] + f"/dokumen/{doc_id}"
        notify(
            p["application_id"],
            f"complete:{doc_id}",
            f"Daftar ulang selesai. Unduh bukti: {link}",
            payload={"link": link},
        )
    audit(
        "participant",
        pid,
        "Status daftar ulang dihitung",
        old=bool(p["completed"]),
        new=bool(complete),
    )


def validate_installment(pid, amount, exclude=None):
    p = participant(pid)
    require(
        p["published_result"] == "Lulus",
        "Pembayaran daftar ulang hanya untuk peserta yang dinyatakan Lulus.",
    )
    inv = invoice(pid)
    require(inv is not None, "Menunggu penetapan tagihan.")
    sums = one(
        "SELECT COUNT(*) AS count, COALESCE(SUM(amount),0) AS paid FROM payments WHERE participant_id=? AND kind='daftar_ulang' AND status='Disahkan' AND id<>?",
        (pid, exclude or -1),
    )
    remaining = inv["total"] - sums["paid"]
    require(
        sums["count"] < 2,
        "Sudah dua pembayaran sah. Gunakan penanganan koreksi Bendahara pada transaksi terdahulu.",
    )
    require(
        amount > 0 and amount <= remaining, "Nominal harus positif dan tidak melebihi sisa tagihan."
    )
    if sums["count"] == 0:
        require(amount * 2 >= inv["total"], "Pembayaran pertama minimal 50% dari total tagihan.")
    else:
        require(amount == remaining, "Pembayaran kedua harus melunasi seluruh sisa tagihan.")


def create_payment(app_id, kind, method, amount, key, upload_id=None):
    existing = one("SELECT * FROM payments WHERE idempotency_key=?", (key,))
    if existing:
        require(existing["application_id"] == app_id, "Identitas transaksi tidak sesuai.")
        return existing["id"]
    require(
        method in ("tunai", "transfer") and kind in ("pendaftaran", "daftar_ulang"),
        "Jenis pembayaran tidak valid.",
    )
    p = one("SELECT * FROM participants WHERE application_id=?", (app_id,))
    require(
        not one(
            "SELECT id FROM payments WHERE application_id=? AND kind=? AND status='Menunggu verifikasi'",
            (app_id, kind),
        ),
        "Masih ada bukti menunggu verifikasi.",
    )
    if kind == "pendaftaran":
        require(
            not p and amount == 200000, "Pembayaran pendaftaran harus Rp200.000 dan belum disahkan."
        )
    else:
        require(p is not None, "Peserta belum terdaftar.")
        validate_installment(p["id"], amount)
    if method == "transfer":
        cfg = settings()
        require(
            all(cfg.get(k) for k in ("bank", "bank_number", "bank_owner")),
            "Rekening tujuan belum tersedia.",
        )
        require(upload_id is not None, "Unggah bukti transfer terlebih dahulu.")
    pay_id = execute(
        "INSERT INTO payments(application_id,participant_id,kind,method,amount,status,upload_id,idempotency_key,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (
            app_id,
            p["id"] if p else None,
            kind,
            method,
            amount,
            "Menunggu verifikasi",
            upload_id,
            key,
            now(),
        ),
    ).lastrowid
    if kind == "pendaftaran":
        execute("UPDATE applications SET status='Menunggu verifikasi' WHERE id=?", (app_id,))
    audit("payment", pay_id, "Pembayaran diajukan", new={"amount": amount, "method": method})
    return pay_id


def approve_payment(pay_id):
    pay = one("SELECT * FROM payments WHERE id=?", (pay_id,))
    require(pay is not None, "Transaksi tidak ditemukan.")
    if pay["status"] == "Disahkan":
        return pay["participant_id"]
    require(
        pay["status"] == "Menunggu verifikasi",
        "Transaksi ini sudah ditolak. Gunakan pengajuan baru.",
    )
    pid = pay["participant_id"]
    if pay["kind"] == "pendaftaran":
        a = one("SELECT * FROM applications WHERE id=?", (pay["application_id"],))
        execute("UPDATE sequences SET value=value+1 WHERE level=?", (a["level"],))
        seq = one("SELECT value FROM sequences WHERE level=?", (a["level"],))["value"]
        number = f"{a['level']}-{seq:02d}"
        pid = execute(
            "INSERT INTO participants(application_id,number) VALUES(?,?)", (a["id"], number)
        ).lastrowid
        execute(
            "UPDATE applications SET status='Pembayaran disetujui / nomor diterbitkan' WHERE id=?",
            (a["id"],),
        )
        link = current_app.config["BASE_URL"] + "/daftar-akun"
        notify(
            a["id"],
            f"number:{pid}",
            f"Pembayaran Rp200.000 disahkan. Nomor pendaftaran {number}. Buat akun dan cocokkan data melalui {link}",
            payload={"link": link},
        )
    else:
        validate_installment(pid, pay["amount"])
    execute(
        "UPDATE payments SET status='Disahkan',participant_id=?,confirmed_by=?,confirmed_at=? WHERE id=?",
        (pid, g.user["id"], now(), pay_id),
    )
    if pay["upload_id"]:
        execute("UPDATE uploads SET participant_id=? WHERE id=?", (pid, pay["upload_id"]))
    issue_document(pid, "kuitansi", pay_id)
    audit("payment", pay_id, "Pembayaran disahkan", new={"amount": pay["amount"]})
    sync_completion(pid)
    return pid


def reject_payment(pay_id, reason):
    require(reason.strip(), "Alasan penolakan wajib diisi.")
    pay = one("SELECT * FROM payments WHERE id=?", (pay_id,))
    require(
        pay and pay["status"] == "Menunggu verifikasi",
        "Transaksi tidak sedang menunggu verifikasi.",
    )
    execute(
        "UPDATE payments SET status='Ditolak',reason=?,confirmed_by=?,confirmed_at=? WHERE id=?",
        (reason, g.user["id"], now(), pay_id),
    )
    if pay["kind"] == "pendaftaran":
        execute(
            "UPDATE applications SET status='Perlu perbaikan bukti pembayaran' WHERE id=?",
            (pay["application_id"],),
        )
        original = one(
            "SELECT payload FROM outbox WHERE event_key=? LIMIT 1",
            (f'application:{pay["application_id"]}',),
        )
        link = json.loads(original["payload"])["link"]
    else:
        link = (
            current_app.config["BASE_URL"]
            + "/peserta/"
            + str(pay["participant_id"])
            + "/menu/pembayaran"
        )
    notify(
        pay["application_id"],
        f"payment-rejected:{pay_id}",
        f"Bukti pembayaran perlu diperbaiki: {reason}. Unggah ulang: {link}",
        payload={"link": link},
    )
    audit("payment", pay_id, "Pembayaran ditolak", reason=reason)


def correct_payment(pay_id, amount, reason):
    require(reason.strip(), "Alasan koreksi wajib diisi.")
    pay = one("SELECT * FROM payments WHERE id=?", (pay_id,))
    require(pay and pay["status"] == "Disahkan", "Hanya pembayaran sah yang dapat dikoreksi.")
    require(
        pay["kind"] == "daftar_ulang",
        "Nominal pendaftaran tetap Rp200.000. Koreksi keterangan memakai catatan audit, bukan mengubah tarif.",
    )
    bal = balance(pay["participant_id"])
    require(
        0 <= amount <= bal["invoice"]["total"] - bal["paid"] + pay["amount"],
        "Nominal koreksi di luar total tagihan.",
    )
    execute("UPDATE payments SET amount=?,reason=? WHERE id=?", (amount, reason, pay_id))
    invalidate(pay["participant_id"], ["kuitansi"], pay_id)
    doc_id = issue_document(pay["participant_id"], "kuitansi", pay_id)
    audit(
        "payment",
        pay_id,
        "Pembayaran dikoreksi",
        old=dict(pay),
        new={"amount": amount},
        reason=reason,
    )
    sync_completion(pay["participant_id"])
    link = current_app.config["BASE_URL"] + f"/dokumen/{doc_id}"
    notify(
        pay["application_id"],
        f"correction:{doc_id}",
        f"Pembayaran dikoreksi menjadi {rupiah(amount)}. Alasan: {reason}. Bukti terbaru: {link}",
        payload={"link": link},
    )


def save_bio(pid, data, staff=False, reason=""):
    p = participant(pid)
    require(not p["locked_at"] or staff, "Biodata sudah dikunci. Hubungi bagian Pemberkasan.")
    if staff:
        require(reason.strip(), "Alasan perubahan biodata oleh petugas wajib diisi.")
    group = data.get("bio_group")
    require(group is None or group in BIO_GROUPS, "Bagian biodata tidak valid.")
    groups = (group,) if group else tuple(BIO_GROUPS)
    bio = bio_values(p, json.loads(p["bio"]))
    require(
        "number" not in data or data["number"] == p["number"],
        "Nomor pendaftaran tidak dapat diubah.",
    )
    for selected in groups:
        for key in BIO_GROUPS[selected]["fields"]:
            if key != "number" and key in data:
                bio[key] = str(data[key]).strip()
    if "orang-tua" in groups:
        for key in PARENT_NOTES:
            bio[key] = str(data.get(key, "")).strip()
        for old_key, new_key in [("father", "father_name"), ("mother", "mother_name")]:
            if old_key in data and new_key not in data:
                bio[new_key] = str(data[old_key]).strip()
    require(
        all(len(str(bio.get(key, ""))) <= 2000 for key in (*BIO_FIELDS, *PARENT_NOTES)),
        "Isi biodata terlalu panjang.",
    )
    errors = [error for selected in groups for error in bio_errors(bio, p["level"], selected)]
    require(not errors, " ".join(errors))
    identity = initial_data(
        {**p, **{key: bio[key] for key in ("name", "birth_place", "birth_date", "phone")}}
    )
    execute(
        "UPDATE applications SET name=?,birth_place=?,birth_date=?,phone=? WHERE id=?",
        (
            identity["name"],
            identity["birth_place"],
            identity["birth_date"],
            identity["phone"],
            p["application_id"],
        ),
    )
    bio["phone"] = identity["phone"]
    bio["email"] = bio.get("email", "").lower()
    bio["father"] = bio.get("father_name", "")
    bio["mother"] = bio.get("mother_name", "")
    bio["guardian"] = bio.get("guardian") or bio["father"] or bio["mother"]
    bio["schema_version"] = 2
    complete = all(bio_group_status(bio, p["level"]).values()) or bool(
        p["locked_at"] and p["bio_complete"]
    )
    execute(
        "UPDATE participants SET bio=?,bio_complete=? WHERE id=?",
        (json.dumps(bio, ensure_ascii=False), int(complete), pid),
    )
    audit(
        "participant",
        pid,
        "Biodata diperbarui",
        old={
            "bio": p["bio"],
            "name": p["name"],
            "birth_place": p["birth_place"],
            "birth_date": p["birth_date"],
            "phone": p["phone"],
        },
        new={**bio, "name": identity["name"], "saved_group": group or "semua"},
        reason=reason,
    )
    invalidate(pid, ["formulir"])
    if p["locked_at"]:
        invalidate(pid, ["kartu", "kelulusan", "daftar_ulang"])
        issue_document(pid, "kartu")
        if p["published_result"] == "Lulus":
            issue_document(pid, "kelulusan")
        if p["completed"]:
            issue_document(pid, "daftar_ulang")


def open_schedule(value):
    try:
        d = date.fromisoformat(value)
    except ValueError:
        raise RuleError("Tanggal tes tidak valid.")
    require(d.weekday() in (2, 6), "Tanggal tes hanya Rabu atau Minggu.")
    require(d >= today(), "Tanggal tes tidak boleh di masa lalu.")
    require(
        not one("SELECT id FROM schedules WHERE date=?", (value,)),
        "Tanggal ini sudah tersedia. Gunakan pengaturan buka/tutup.",
    )
    sid = execute("INSERT INTO schedules(date) VALUES(?)", (value,)).lastrowid
    audit("schedule", sid, "Tanggal tes dibuka", new=value)


def set_schedule(pid, sid, staff=False, reason=""):
    p = participant(pid)
    require(p["bio_complete"], "Lengkapi biodata sebelum memilih tanggal tes.")
    require(staff or not p["schedule_id"], "Tanggal sudah dipilih. Perubahan melalui Pemberkasan.")
    if staff:
        require(reason.strip(), "Alasan perubahan jadwal wajib diisi.")
    s = one("SELECT * FROM schedules WHERE id=? AND status='Terbuka'", (sid,))
    require(s and s["date"] >= today().isoformat(), "Tanggal tidak terbuka atau sudah berlalu.")
    execute(
        "UPDATE participants SET schedule_id=?,attendance='Belum dicatat' WHERE id=?", (sid, pid)
    )
    invalidate(pid, ["kartu"])
    if p["locked_at"]:
        issue_document(pid, "kartu")
    audit(
        "participant",
        pid,
        "Jadwal dipindahkan" if p["schedule_id"] else "Jadwal dipilih",
        old=p["schedule_id"],
        new=sid,
        reason=reason,
    )
    link = current_app.config["BASE_URL"] + f"/peserta/{pid}/menu/jadwal"
    notify(
        p["application_id"],
        f"schedule:{pid}:{uuid.uuid4()}",
        f"Tes {tanggal(s['date'])}, {service_hours(s['date'])}, di Pondok Pesantren Daarul Falah 2 Maliku. {reason} Kartu terbaru: {link}",
        channels=("whatsapp", "email") if staff else ("whatsapp",),
        payload={"link": link},
    )


def publish_result(pid, result, reason="", correction=False):
    p = participant(pid)
    require(result in ("Lulus", "Tidak lulus"), "Pilih hasil seleksi.")
    require(
        correction == bool(p["published_result"]),
        "Gunakan tindakan koreksi untuk hasil yang sudah diumumkan.",
    )
    if correction:
        require(reason.strip(), "Alasan koreksi hasil wajib diisi.")
    else:
        require(p["draft_result"] == result, "Simpan hasil draf terlebih dahulu.")
    execute(
        "UPDATE participants SET published_result=?,draft_result=?,result_version=result_version+1 WHERE id=?",
        (result, result, pid),
    )
    invalidate(pid, ["kelulusan"])
    if result == "Lulus":
        issue_document(pid, "kelulusan")
        invoice(pid)
    else:
        paid = balance(pid)["paid"]
        if paid:
            execute("UPDATE participants SET financial_review=1 WHERE id=?", (pid,))
    sync_completion(pid)
    audit(
        "participant",
        pid,
        "Hasil dikoreksi" if correction else "Hasil dipublikasikan",
        old=p["published_result"],
        new=result,
        reason=reason,
    )
    notify(
        p["application_id"],
        f'result:{pid}:{p["result_version"]+1}',
        f"Hasil seleksi: {result}. "
        + (f"Alasan koreksi: {reason}. " if correction else "")
        + "Lihat akun untuk tindak lanjut.",
        channels=("whatsapp", "email") if correction else ("whatsapp",),
    )
