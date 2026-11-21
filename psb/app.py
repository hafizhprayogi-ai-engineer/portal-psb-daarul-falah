import io
import json
import os
import secrets
import sqlite3
from pymysql import IntegrityError as MySQLIntegrityError
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from functools import wraps
from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from .db import initialize, get_db, one, all_rows, execute, transaction, now, settings, audit
from .domain import (
    RuleError,
    require,
    digest,
    LEVELS,
    DOC_LABELS,
    participant,
    initial_data,
    new_application,
    create_payment,
    cash_receiver,
    approve_payment,
    reject_payment,
    correct_payment,
    save_bio,
    open_schedule,
    set_schedule,
    publish_result,
    invoice,
    balance,
    revise_invoice,
    invoice_revision_token,
    latest_uploads,
    required_docs,
    documents_complete,
    sync_completion,
    issue_document,
    invalidate,
    notify,
    today,
    rupiah,
    tanggal,
    waktu,
    service_hours,
)
from .security import (
    install_security,
    has_role,
    login_required,
    roles_required,
    check_participant,
    csrf_token,
    rate_limit,
    create_session,
)
from .files import save_upload, render_document
from .network import resolve_base_url
from .interface import portal_context, participant_menus, SECTION_TITLES, admission_progress
from .biodata import (
    BIO_GROUPS,
    BIO_FIELDS,
    EDUCATION_OPTIONS,
    bio_values,
    bio_group_status,
    required_fields,
)


def create_app(test_config=None):
    load_dotenv()
    root = Path(__file__).parent.parent
    app = Flask(
        __name__, template_folder=str(root / "templates"), static_folder=str(root / "static")
    )
    data = Path(os.getenv("DATA_DIR", str(root / "instance"))).resolve()
    app.config.update(
        DATA_DIR=str(data),
        DATABASE=str(data / "psb.sqlite3"),
        DATABASE_URL=os.getenv("DATABASE_URL", ""),
        UPLOAD_DIR=str(data / "private"),
        SECRET_KEY=os.getenv("SECRET_KEY"),
        BASE_URL=resolve_base_url(
            os.getenv("BASE_URL", "http://127.0.0.1:5000"), os.getenv("PORT", "5000")
        ),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false") == "true",
        MAX_CONTENT_LENGTH=6 * 1024 * 1024,
        MAX_FORM_PARTS=60,
        NOTIFICATION_MODE=os.getenv("NOTIFICATION_MODE", "simulation"),
        EMAIL_DELIVERY_MODE=os.getenv("EMAIL_DELIVERY_MODE", "simulation").strip().lower(),
        SMTP_HOST=os.getenv("SMTP_HOST", "").strip(),
        SMTP_PORT=int(os.getenv("SMTP_PORT", "587")),
        SMTP_USERNAME=os.getenv("SMTP_USERNAME", "").strip(),
        SMTP_PASSWORD=os.getenv("SMTP_PASSWORD", ""),
        SMTP_FROM=os.getenv("SMTP_FROM", "").strip(),
        SMTP_STARTTLS=os.getenv("SMTP_STARTTLS", "true").strip().lower() == "true",
        N8N_WEBHOOK_URL=os.getenv("N8N_WEBHOOK_URL", ""),
        N8N_WEBHOOK_TOKEN=os.getenv("N8N_WEBHOOK_TOKEN", ""),
        INTEGRATION_TOKEN=os.getenv("INTEGRATION_TOKEN", ""),
    )
    if test_config:
        app.config.update(test_config)
        if "DATABASE" in test_config and "DATABASE_URL" not in test_config:
            app.config["DATABASE_URL"] = ""
    if not app.config["SECRET_KEY"]:
        if os.getenv("APP_ENV") == "production":
            raise RuntimeError("SECRET_KEY wajib diisi pada produksi.")
        Path(app.config["DATA_DIR"]).mkdir(parents=True, exist_ok=True)
        keyfile = Path(app.config["DATA_DIR"]) / "session.key"
        if not keyfile.exists():
            keyfile.write_text(secrets.token_hex(32))
        app.config["SECRET_KEY"] = keyfile.read_text().strip()
    initialize(app)
    if os.getenv("TRUST_PROXY", "false") == "true":
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    install_security(app)
    app.context_processor(portal_context)
    app.jinja_env.filters.update(rupiah=rupiah, tanggal=tanggal, waktu=waktu, fromjson=json.loads)
    app.jinja_env.globals.update(
        has_role=has_role,
        csrf_token=csrf_token,
        nonce=lambda: secrets.token_urlsafe(24),
        service_hours=service_hours,
        DOC_LABELS=DOC_LABELS,
    )

    @app.context_processor
    def context():
        return {
            "profile_photo": one("SELECT id FROM uploads WHERE participant_id=? AND category='foto' ORDER BY id DESC LIMIT 1", (g.user["participant_id"],)) if getattr(g, "user", None) and g.user["participant_id"] else None,
            "cfg": settings(),
            "current_user": getattr(g, "user", None),
            "simulation": app.config["NOTIFICATION_MODE"] == "simulation",
            "email_simulation": app.config["EMAIL_DELIVERY_MODE"] != "smtp",
        }

    @app.teardown_appcontext
    def close(error):
        db = g.pop("db", None)
        if db:
            db.close()

    @app.errorhandler(RuleError)
    def business_error(error):
        if (
            request.endpoint == "participant_action"
            and request.method == "POST"
            and (request.view_args or {}).get("action") in ("bio", "staff-bio")
        ):
            group = request.form.get("bio_group")
            pid = request.view_args["pid"]
            if group in BIO_GROUPS and one("SELECT id FROM participants WHERE id=?", (pid,)):
                from .biodata import PARENT_NOTES

                draft = {
                    key: request.form[key]
                    for key in (*BIO_FIELDS, *PARENT_NOTES)
                    if key != "number" and key in request.form
                }
                if group == "orang-tua":
                    for parent in ("father", "mother"):
                        draft[parent + "_unavailable"] = request.form.get(
                            parent + "_unavailable", ""
                        )
                draft["edit_reason"] = request.form.get("reason", "")
                flash(str(error), "error")
                return render_participant(pid, "biodata", group, draft), 400
        return render_template("error.html", title="Periksa kembali", message=str(error)), 400

    @app.errorhandler(MySQLIntegrityError)
    @app.errorhandler(sqlite3.IntegrityError)
    def conflict(error):
        app.logger.warning("Konflik integritas database: %s", error)
        return (
            render_template(
                "error.html",
                title="Data sudah berubah",
                message="Permintaan bertabrakan dengan data yang sudah tersimpan. Muat ulang dan periksa status sebelum mencoba lagi.",
            ),
            409,
        )

    @app.errorhandler(ValueError)
    def invalid_value(error):
        return (
            render_template(
                "error.html",
                title="Nilai belum sesuai",
                message="Periksa format tanggal dan nominal. Gunakan angka rupiah tanpa titik atau koma.",
            ),
            400,
        )

    for code, title, message in [
        (400, "Permintaan tidak valid", "Muat ulang halaman sebelum mengirim formulir."),
        (401, "Silakan login", "Masuk terlebih dahulu untuk melanjutkan."),
        (403, "Akses dibatasi", "Akun Anda tidak memiliki izin untuk tindakan ini."),
        (404, "Tidak ditemukan", "Halaman atau dokumen tidak ditemukan."),
        (413, "Berkas terlalu besar", "Gunakan berkas maksimal 5 MB."),
    ]:
        app.register_error_handler(
            code,
            lambda err, c=code, t=title, m=message: (
                render_template("error.html", title=t, message=m),
                c,
            ),
        )

    @app.get("/")
    def home():
        return render_template("home.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            rate_limit("login", 20)
            user = one(
                "SELECT * FROM users WHERE username=?", (request.form.get("username", "").strip(),)
            )
            valid = (
                check_password_hash(user["password_hash"], request.form.get("password", ""))
                if user
                else check_password_hash(
                    app.config.setdefault(
                        "DUMMY_HASH", generate_password_hash(secrets.token_urlsafe(20))
                    ),
                    request.form.get("password", ""),
                )
            )
            require(
                user and valid and user["active"],
                "Nomor/username, kata sandi, atau aktivasi akun belum sesuai.",
            )
            with transaction():
                create_session(user)
            return redirect("/dashboard")
        return render_template("login.html", title="Selamat datang kembali")

    @app.post("/logout")
    def logout():
        execute("DELETE FROM sessions WHERE token_hash=?", (digest(session.get("sid", "")),))
        session.clear()
        return redirect("/")

    def account_token(user, kind):
        token = secrets.token_urlsafe(32)
        expiry = (
            datetime.now(timezone.utc) + timedelta(hours=24 if kind == "aktivasi" else 1)
        ).isoformat()
        execute(
            "UPDATE account_tokens SET used_at=? WHERE user_id=? AND kind=? AND used_at IS NULL",
            (now(), user["id"], kind),
        )
        execute(
            "INSERT INTO account_tokens(token_hash,user_id,kind,expires_at) VALUES(?,?,?,?)",
            (digest(token), user["id"], kind, expiry),
        )
        p = participant(user["participant_id"])
        link = app.config["BASE_URL"] + f"/{kind}/{token}"
        notify(
            p["application_id"],
            f"{kind}:{digest(token)}",
            f'{"Aktifkan akun" if kind=="aktivasi" else "Atur ulang kata sandi"}: {link}. Tautan sekali pakai dan terbatas waktu.',
            channels=("email",),
            payload={"link": link},
        )

    @app.route("/daftar-akun", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            rate_limit("register")
            d = initial_data(request.form)
            with transaction():
                p = one(
                    "SELECT a.* FROM participants p JOIN applications a ON a.id=p.application_id WHERE p.number=?",
                    (request.form.get("number", "").strip().upper(),),
                )
                require(
                    p and all(str(p[k]).casefold() == d[k].casefold() for k in d),
                    "Nomor atau data pencocokan belum sesuai dengan pendaftaran.",
                )
                pid = one(
                    "SELECT id FROM participants WHERE number=?",
                    (request.form["number"].strip().upper(),),
                )["id"]
                require(
                    not one("SELECT id FROM users WHERE participant_id=?", (pid,)),
                    "Nomor ini sudah memiliki akun. Gunakan Login atau Lupa Password.",
                )
                password = request.form.get("password", "")
                require(
                    len(password) >= 8 and password == request.form.get("confirm"),
                    "Kata sandi minimal 8 karakter dan konfirmasi harus sama.",
                )
                uid = execute(
                    "INSERT INTO users(username,password_hash,participant_id) VALUES(?,?,?)",
                    (request.form["number"].strip().upper(), generate_password_hash(password), pid),
                ).lastrowid
                account_token(one("SELECT * FROM users WHERE id=?", (uid,)), "aktivasi")
                audit("user", uid, "Akun wali dibuat")
            flash(
                "Akun dibuat. Periksa email untuk aktivasi. Dalam mode simulasi, panitia dapat memeriksa antrean lokal.",
                "success",
            )
            return redirect("/login")
        return render_template("auth.html", mode="register", title="Buat akun peserta")

    @app.route("/lupa-password", methods=["GET", "POST"])
    @app.route("/kirim-aktivasi", methods=["GET", "POST"])
    def recovery():
        kind = "aktivasi" if request.path == "/kirim-aktivasi" else "reset"
        if request.method == "POST":
            rate_limit("recovery", 5)
            with transaction():
                user = one(
                    "SELECT u.* FROM users u JOIN participants p ON p.id=u.participant_id JOIN applications a ON a.id=p.application_id WHERE u.username=? AND a.email=?",
                    (
                        request.form.get("number", "").strip(),
                        request.form.get("email", "").strip().lower(),
                    ),
                )
                if user and (kind == "reset" or not user["active"]):
                    account_token(user, kind)
            flash("Jika data sesuai, tautan akan dikirim ke email terdaftar.", "success")
            return redirect("/login")
        return render_template(
            "auth.html",
            mode="recovery",
            title="Kirim ulang aktivasi" if kind == "aktivasi" else "Lupa kata sandi",
        )

    @app.route("/aktivasi/<token>", methods=["GET", "POST"])
    @app.route("/reset/<token>", methods=["GET", "POST"])
    def consume_token(token):
        kind = "aktivasi" if request.path.startswith("/aktivasi/") else "reset"
        row = one(
            "SELECT * FROM account_tokens WHERE token_hash=? AND kind=? AND used_at IS NULL AND expires_at>?",
            (digest(token), kind, now()),
        )
        require(row, "Tautan tidak berlaku atau kedaluwarsa. Minta tautan baru.")
        if request.method == "POST":
            with transaction():
                row = one(
                    "SELECT * FROM account_tokens WHERE token_hash=? AND used_at IS NULL AND expires_at>?",
                    (digest(token), now()),
                )
                require(row, "Tautan sudah digunakan.")
                if kind == "aktivasi":
                    execute("UPDATE users SET active=1 WHERE id=?", (row["user_id"],))
                else:
                    pwd = request.form.get("password", "")
                    require(
                        len(pwd) >= 8 and pwd == request.form.get("confirm"),
                        "Kata sandi minimal 8 karakter dan konfirmasi harus sama.",
                    )
                    execute(
                        "UPDATE users SET password_hash=? WHERE id=?",
                        (generate_password_hash(pwd), row["user_id"]),
                    )
                    execute("DELETE FROM sessions WHERE user_id=?", (row["user_id"],))
                execute(
                    "UPDATE account_tokens SET used_at=? WHERE token_hash=?", (now(), digest(token))
                )
            flash(
                (
                    "Aktivasi berhasil. Silakan login."
                    if kind == "aktivasi"
                    else "Kata sandi diperbarui. Silakan login."
                ),
                "success",
            )
            return redirect("/login")
        return render_template(
            "auth.html",
            mode=kind,
            title="Aktivasi akun" if kind == "aktivasi" else "Atur kata sandi baru",
        )

    @app.route("/pendaftaran-online", methods=["GET", "POST"])
    def online():
        if request.method == "POST":
            rate_limit("application", 10)
            with transaction():
                _, token = new_application(request.form, "online")
            return redirect("/pantau/" + token)
        return render_template("apply.html")

    @app.route("/pantau/<token>", methods=["GET", "POST"])
    def tracking(token):
        a = one("SELECT * FROM applications WHERE tracking_hash=?", (digest(token),))
        if not a:
            abort(404)
        if request.method == "POST":
            rate_limit("proof", 20)
            with transaction():
                existing = one(
                    "SELECT id FROM payments WHERE idempotency_key=?", (request.form.get("key"),)
                )
                if not existing:
                    upload = save_upload(request.files.get("file"), app_id=a["id"])
                    create_payment(
                        a["id"], "pendaftaran", "transfer", 200000, request.form["key"], upload
                    )
            flash("Bukti tersimpan dan menunggu pemeriksaan Bendahara.", "success")
            return redirect(request.path)
        p = one("SELECT * FROM participants WHERE application_id=?", (a["id"],))
        payments = all_rows(
            "SELECT * FROM payments WHERE application_id=? ORDER BY id DESC", (a["id"],)
        )
        receipt = (
            one(
                "SELECT * FROM documents WHERE participant_id=? AND kind='kuitansi' AND valid=1 ORDER BY id DESC LIMIT 1",
                (p["id"],),
            )
            if p
            else None
        )
        return render_template(
            "tracking.html", a=a, p=p, payments=payments, token=token, receipt=receipt
        )

    @app.get("/pantau/<token>/bukti/<int:did>")
    def tracking_receipt(token, did):
        doc = one(
            "SELECT d.* FROM documents d JOIN participants p ON p.id=d.participant_id JOIN applications a ON a.id=p.application_id JOIN payments t ON t.id=d.payment_id WHERE d.id=? AND a.tracking_hash=? AND t.kind='pendaftaran' AND d.valid=1",
            (did, digest(token)),
        )
        if not doc:
            abort(404)
        return send_file(
            render_document(doc),
            mimetype="application/pdf",
            as_attachment=True,
            download_name="bukti-pendaftaran.pdf",
        )

    @app.get("/dashboard")
    @login_required
    def dashboard():
        if g.user["participant_id"]:
            return redirect("/peserta/" + str(g.user["participant_id"]))
        return render_template(
            "dashboard.html",
            stats={
                "applications": one("SELECT COUNT(*) AS n FROM applications")["n"],
                "participants": one("SELECT COUNT(*) AS n FROM participants")["n"],
                "pending": one(
                    "SELECT COUNT(*) AS n FROM payments WHERE status='Menunggu verifikasi'"
                )["n"],
                "pending_files": one(
                    "SELECT COUNT(DISTINCT participant_id) AS n FROM uploads WHERE participant_id IS NOT NULL AND category<>'bukti' AND status='Menunggu pemeriksaan' AND id IN (SELECT MAX(id) FROM uploads WHERE participant_id IS NOT NULL AND category<>'bukti' GROUP BY participant_id,category)"
                )["n"],
                "complete": one("SELECT COUNT(*) AS n FROM participants WHERE completed=1")["n"],
            },
        )

    @app.get("/peserta")
    @app.get("/layanan/<workflow>")
    @app.get("/layanan/biodata/<bio_group>", defaults={"workflow": "biodata"})
    @roles_required("pemberkasan", "admin")
    def participants(workflow=None, bio_group=None):
        if bio_group and bio_group not in BIO_GROUPS:
            abort(404)
        if workflow and workflow not in ("biodata", "hasil", "berkas", "dokumen"):
            abort(404)
        q = request.args.get("q", "").strip()
        level = request.args.get("level", "")
        rows = all_rows(
            "SELECT p.*,a.name,a.level,a.channel FROM participants p JOIN applications a ON a.id=p.application_id WHERE (a.name LIKE ? OR p.number LIKE ?) AND (?='' OR a.level=?) ORDER BY p.id DESC",
            ("%" + q + "%", "%" + q + "%", level, level),
        )
        review = request.args.get("review", "all")
        if review not in ("all", "pending"):
            review = "all"
        show_file_review = workflow in (None, "berkas")
        pending_summary = {
            row["participant_id"]: dict(row) for row in all_rows(
                "SELECT u.participant_id, SUM(CASE WHEN u.status='Menunggu pemeriksaan' THEN 1 ELSE 0 END) AS pending_count, SUM(CASE WHEN u.status='Perlu diperbaiki' THEN 1 ELSE 0 END) AS repair_count FROM uploads u WHERE u.participant_id IS NOT NULL AND u.category<>'bukti' AND NOT EXISTS (SELECT 1 FROM uploads newer WHERE newer.participant_id=u.participant_id AND newer.category=u.category AND newer.id>u.id) GROUP BY u.participant_id"
            )
        } if show_file_review else {}
        rows = [dict(row) for row in rows]
        for row in rows:
            counts = pending_summary.get(row["id"], {})
            row["pending_files"] = int(counts.get("pending_count", 0))
            row["repair_files"] = int(counts.get("repair_count", 0))
        if show_file_review:
            rows.sort(key=lambda row: bool(row["pending_files"]), reverse=True)
            if review == "pending":
                rows = [row for row in rows if row["pending_files"]]
        return render_template(
            "participants.html",
            rows=rows,
            review=review,
            show_file_review=show_file_review,
            q=q,
            level=level,
            workflow=workflow,
            workflow_title=(
                BIO_GROUPS[bio_group]["label"] if bio_group else SECTION_TITLES.get(workflow)
            ),
            bio_group=bio_group,
        )

    @app.get("/peserta/<int:pid>")
    @login_required
    def detail(pid):
        return render_participant(pid)

    @app.post("/peserta/<int:pid>/revisi-tagihan")
    @roles_required("admin")
    def revise_participant_invoice(pid):
        check_participant(pid)
        names = request.form.getlist("component_name")
        amounts = request.form.getlist("component_amount")
        require(len(names) == len(amounts) and 0 < len(names) <= 100, "Rincian tagihan tidak valid.")
        components = []
        for name, amount in zip(names, amounts):
            require(amount.isascii() and amount.isdigit() and len(amount) <= 9,
                    "Nominal harus angka bulat rupiah tanpa Rp, titik atau koma.")
            components.append({"name": name.strip(), "amount": int(amount)})
        require(request.form.get("confirm") == "ya", "Konfirmasikan revisi tagihan.")
        with transaction():
            revise_invoice(pid, components, request.form.get("reason", ""), request.form.get("revision_token", ""))
        flash("Revisi tagihan disimpan. Pembayaran sah tetap diperhitungkan.", "success")
        return redirect(f"/peserta/{pid}/menu/pembayaran")

    @app.get("/peserta/<int:pid>/menu/<section>")
    @login_required
    def participant_menu(pid, section):
        if section not in SECTION_TITLES:
            abort(404)
        if section == "absensi" and not has_role("pemberkasan"):
            abort(403)
        return render_participant(pid, section)

    @app.get("/peserta/<int:pid>/menu/biodata/<bio_group>")
    @login_required
    def participant_biodata(pid, bio_group):
        if bio_group not in BIO_GROUPS:
            abort(404)
        return render_participant(pid, "biodata", bio_group)

    def render_participant(pid, section=None, bio_group=None, bio_draft=None):
        check_participant(pid)
        p = participant(pid)
        with transaction():
            invoice(pid)
        schedule = (
            one("SELECT * FROM schedules WHERE id=?", (p["schedule_id"],))
            if p["schedule_id"]
            else None
        )
        notifications = all_rows(
            "SELECT event_key,message,MAX(created_at) AS created_at FROM outbox WHERE application_id=? GROUP BY event_key ORDER BY created_at DESC LIMIT 20",
            (p["application_id"],),
        )
        bal = balance(pid)
        complete = documents_complete(pid)
        values = bio_values(p, json.loads(p["bio"]))
        if bio_draft:
            values.update(bio_draft)
        return render_template(
            "participant.html" if section else "participant_dashboard.html",
            section=section,
            section_title=(
                BIO_GROUPS[bio_group]["label"]
                if bio_group
                else SECTION_TITLES.get(section, "Ringkasan peserta")
            ),
            participant_menu_items=participant_menus(pid),
            flow=admission_progress(p, complete, bal),
            revision_token=invoice_revision_token(bal["invoice"]) if bal["invoice"] else "",
            invoice_history=all_rows("SELECT reason,created_at,old_value,new_value FROM audit WHERE entity='invoice' AND entity_id=? AND action='Tagihan direvisi' ORDER BY id DESC", (bal["invoice"]["id"],)) if bal["invoice"] else [],
            p=p,
            bio=values,
            bio_group=bio_group,
            bio_groups=BIO_GROUPS,
            bio_fields=BIO_FIELDS,
            bio_status=bio_group_status(values, p["level"]),
            bio_required=required_fields(values, p["level"], bio_group) if bio_group else set(),
            education_options=EDUCATION_OPTIONS,
            bal=bal,
            schedule=schedule,
            schedules=all_rows(
                "SELECT * FROM schedules WHERE status='Terbuka' AND date>=? ORDER BY date",
                (today().isoformat(),),
            ),
            uploads=latest_uploads(pid),
            drive_status={
                r["upload_id"]: r["state"]
                for r in all_rows(
                    "SELECT upload_id,state FROM drive_objects WHERE participant_id=? AND upload_id IS NOT NULL",
                    (pid,),
                )
            },
            drive_folder=(
                one(
                    "SELECT web_url FROM drive_objects WHERE item_key=? AND state='ready'",
                    (f"participant:{pid}",),
                )
                if has_role("admin", "pemberkasan")
                else None
            ),
            required=required_docs(p["level"]),
            docs_complete=complete,
            docs=all_rows(
                "SELECT * FROM documents WHERE participant_id=? ORDER BY id DESC", (pid,)
            ),
            payments=all_rows(
                "SELECT * FROM payments WHERE application_id=? ORDER BY id DESC",
                (p["application_id"],),
            ),
            notifications=notifications,
        )

    @app.post("/peserta/<int:pid>/<action>")
    @login_required
    def participant_action(pid, action):
        check_participant(pid)
        owner = g.user["participant_id"] == pid
        staff_actions = {
            "attendance",
            "draft",
            "publish",
            "correct-result",
            "review",
            "replace",
            "move",
            "staff-bio",
            "remind-files",
        }
        if action in staff_actions and not has_role("pemberkasan"):
            abort(403)
        if action not in staff_actions and not owner and not has_role("pemberkasan"):
            abort(403)
        with transaction():
            p = participant(pid)
            if action in ("bio", "staff-bio"):
                require(
                    owner if action == "bio" else True, "Gunakan perbaikan biodata oleh petugas."
                )
                save_bio(
                    pid,
                    request.form,
                    staff=action == "staff-bio",
                    reason=request.form.get("reason", ""),
                )
            elif action in ("schedule", "move"):
                set_schedule(
                    pid,
                    int(request.form["schedule_id"]),
                    staff=action == "move",
                    reason=request.form.get("reason", ""),
                )
            elif action in ("card", "form"):
                require(p["bio_complete"], "Lengkapi biodata terlebih dahulu.")
                kind = "kartu" if action == "card" else "formulir"
                if action == "card":
                    require(p["schedule_id"], "Pilih tanggal tes terlebih dahulu.")
                    execute(
                        "UPDATE participants SET locked_at=COALESCE(locked_at,?) WHERE id=?",
                        (now(), pid),
                    )
                doc = one(
                    "SELECT id FROM documents WHERE participant_id=? AND kind=? AND valid=1 ORDER BY id DESC LIMIT 1",
                    (pid, kind),
                )
                did = doc["id"] if doc else issue_document(pid, kind)
                return redirect("/dokumen/" + str(did))
            elif action == "photo":
                file = request.files.get("file")
                require(file and Path(file.filename or "").suffix.lower() in (".jpg", ".jpeg", ".png"),
                        "Foto harus berupa JPG atau PNG, maksimal 5 MB.")
                old = latest_uploads(pid).get("foto")
                uid = save_upload(file, p["application_id"], pid, "foto")
                audit("upload", uid, "Foto profil diperbarui", old={"upload_id": old["id"]} if old else None,
                      new={"participant_id": pid, "upload_id": uid})
                sync_completion(pid)
            elif action in ("upload", "replace"):
                require(
                    p["published_result"] == "Lulus",
                    "Unggah berkas hanya setelah hasil Lulus diumumkan.",
                )
                cat = request.form.get("category")
                require(cat != "foto", "Gunakan menu Pasfoto untuk mengunggah JPG atau PNG.")
                require(cat in required_docs(p["level"]), "Jenis berkas tidak sesuai jenjang.")
                old = latest_uploads(pid).get(cat)
                require(
                    not old or old["status"] != "Diterima" or action == "replace",
                    "Berkas diterima sudah dikunci. Hubungi Pemberkasan.",
                )
                reason = request.form.get("reason", "").strip()
                if action == "replace":
                    require(reason, "Alasan penggantian wajib diisi.")
                replacement = request.form.get("replacement") == "wali"
                require(
                    not replacement or cat in ("ktp_ayah", "ktp_ibu"),
                    "KTP wali hanya dapat menggantikan KTP ayah atau KTP ibu.",
                )
                uid = save_upload(
                    request.files.get("file"),
                    p["application_id"],
                    pid,
                    cat,
                    "KTP wali" if replacement else None,
                    reason,
                )
                audit(
                    "upload",
                    uid,
                    "Penggantian berkas" if old else "Unggah berkas",
                    old=dict(old) if old else None,
                    reason=reason,
                )
                sync_completion(pid)
            elif action == "review":
                u = one(
                    "SELECT * FROM uploads WHERE id=? AND participant_id=?",
                    (request.form["upload_id"], pid),
                )
                require(u and u["category"] != "bukti", "Berkas tidak ditemukan.")
                require(
                    latest_uploads(pid).get(u["category"])["id"] == u["id"],
                    "Periksa versi terbaru.",
                )
                status = request.form.get("status")
                reason = request.form.get("reason", "").strip()
                require(
                    status in ("Diterima", "Perlu diperbaiki"), "Status pemeriksaan tidak valid."
                )
                require(status == "Diterima" or reason, "Catatan perbaikan wajib diisi.")
                require(
                    u["status"] != "Diterima" or reason,
                    "Alasan mengubah berkas diterima wajib diisi.",
                )
                execute(
                    "UPDATE uploads SET status=?,review_note=?,reviewed_by=? WHERE id=?",
                    (status, reason, g.user["id"], u["id"]),
                )
                audit(
                    "upload",
                    u["id"],
                    "Berkas diperiksa",
                    old=u["status"],
                    new=status,
                    reason=reason,
                )
                if status == "Perlu diperbaiki":
                    notify(
                        p["application_id"],
                        f'file:{u["id"]}:{secrets.token_hex(6)}',
                        f'Perbaiki {DOC_LABELS[u["category"]]}: {reason}',
                        channels=("whatsapp",),
                    )
                sync_completion(pid)
            elif action == "remind-files":
                require(
                    p["published_result"] == "Lulus", "Pengingat berkas hanya untuk peserta Lulus."
                )
                accepted = {
                    category
                    for category, upload in latest_uploads(pid).items()
                    if upload["status"] == "Diterima"
                }
                missing = [
                    category for category in required_docs(p["level"]) if category not in accepted
                ]
                if "ijazah" in accepted:
                    missing = [category for category in missing if category != "skl"]
                require(missing, "Seluruh dokumen wajib sudah diterima.")
                key = request.form["key"]
                if not one("SELECT key FROM operations WHERE key=?", (key,)):
                    summary = ", ".join(DOC_LABELS[category] for category in missing)
                    note = request.form.get("reason", "").strip()
                    notify(
                        p["application_id"],
                        f"missing-files:{pid}:{key}",
                        f"Berkas yang perlu dilengkapi atau diperiksa: {summary}. {note}",
                        channels=("whatsapp",),
                    )
                    audit(
                        "participant", pid, "Pengingat kekurangan berkas", new=missing, reason=note
                    )
                    execute("INSERT INTO operations VALUES(?,?,?)", (key, g.user["id"], now()))
            elif action == "payment":
                require(owner, "Unggah pembayaran melalui akun peserta.")
                key = request.form["key"]
                if not one("SELECT id FROM payments WHERE idempotency_key=?", (key,)):
                    uid = save_upload(request.files.get("file"), p["application_id"], pid)
                    create_payment(
                        p["application_id"],
                        "daftar_ulang",
                        "transfer",
                        int(request.form["amount"]),
                        key,
                        uid,
                    )
            elif action == "attendance":
                require(p["schedule_id"], "Peserta belum memilih jadwal.")
                s = one("SELECT * FROM schedules WHERE id=?", (p["schedule_id"],))
                status = request.form.get("attendance")
                require(status in ("Hadir", "Tidak hadir"), "Pilih status kehadiran.")
                require(
                    s["date"] == today().isoformat() or request.form.get("ack") == "ya",
                    "Tanggal kedatangan berbeda. Konfirmasikan peringatan; jadwal tidak berubah.",
                )
                execute("UPDATE participants SET attendance=? WHERE id=?", (status, pid))
                audit(
                    "participant",
                    pid,
                    "Absensi dicatat",
                    old=p["attendance"],
                    new=status,
                    reason="Di luar tanggal terpilih" if s["date"] != today().isoformat() else None,
                )
            elif action == "draft":
                require(request.form.get("result") in ("Lulus", "Tidak lulus"), "Pilih hasil.")
                require(not p["published_result"], "Hasil sudah diumumkan. Gunakan koreksi.")
                execute(
                    "UPDATE participants SET draft_result=? WHERE id=?",
                    (request.form["result"], pid),
                )
                audit("participant", pid, "Draf hasil disimpan", new=request.form["result"])
            elif action in ("publish", "correct-result"):
                require(
                    request.form.get("confirm") == "ya", "Konfirmasikan tindakan publikasi/koreksi."
                )
                key = request.form["key"]
                if not one("SELECT key FROM operations WHERE key=?", (key,)):
                    publish_result(
                        pid,
                        p["draft_result"] if action == "publish" else request.form.get("result"),
                        request.form.get("reason", ""),
                        action == "correct-result",
                    )
                    execute("INSERT INTO operations VALUES(?,?,?)", (key, g.user["id"], now()))
            else:
                abort(404)
        flash("Perubahan berhasil disimpan.", "success")
        if action in ("bio", "staff-bio") and request.form.get("bio_group") in BIO_GROUPS:
            return redirect(
                url_for("participant_biodata", pid=pid, bio_group=request.form["bio_group"])
            )
        destination = {
            "bio": "biodata",
            "staff-bio": "biodata",
            "schedule": "jadwal",
            "move": "jadwal",
            "draft": "hasil",
            "publish": "hasil",
            "correct-result": "hasil",
            "attendance": "absensi",
            "upload": "berkas",
            "photo": "berkas",
            "replace": "berkas",
            "review": "berkas",
            "remind-files": "berkas",
            "payment": "pembayaran",
        }.get(action, "dokumen")
        return redirect(url_for("participant_menu", pid=pid, section=destination))

    @app.get("/dokumen/<int:did>")
    @login_required
    def download_document(did):
        doc = one("SELECT * FROM documents WHERE id=?", (did,))
        if not doc:
            abort(404)
        check_participant(doc["participant_id"], financial=doc["kind"] == "kuitansi")
        p = participant(doc["participant_id"])
        if g.user["participant_id"] and (
            not doc["valid"]
            or (doc["kind"] in ("kelulusan", "daftar_ulang") and p["published_result"] != "Lulus")
        ):
            abort(403)
        word = request.args.get("format") == "docx"
        if word and (doc["kind"] != "kelulusan" or not has_role("pemberkasan", "admin")):
            abort(403)
        return send_file(
            render_document(doc, word),
            mimetype=(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                if word
                else "application/pdf"
            ),
            as_attachment=True,
            download_name=f"{doc['kind']}-{p['number']}-v{doc['version']}.{'docx' if word else 'pdf'}",
        )

    @app.get("/formulir-kosong")
    @roles_required("bendahara", "pemberkasan", "admin")
    def blank_form():
        cfg = settings()
        snapshot = {
            "year": "2027/2028",
            "name": "________________________________",
            "number": "________________________________",
            "level": "MI / MTs / MA (pilih satu)",
            "birth_place": "________________________________",
            "birth_date": None,
            "bio": json.dumps(
                {
                    "schema_version": 2,
                    **{key: "________________________________" for key in BIO_FIELDS},
                }
            ),
            "template": cfg.get("form_body", ""),
            "draft": cfg.get("template_official") != "ya",
            "letterhead": cfg.get("letterhead", ""),
        }
        doc = {
            "id": 0,
            "kind": "formulir",
            "version": 1,
            "valid": 1,
            "token": "",
            "created_at": now(),
            "snapshot": json.dumps(snapshot),
        }
        return send_file(
            render_document(doc),
            mimetype="application/pdf",
            as_attachment=True,
            download_name="formulir-kosong-2027-2028.pdf",
        )

    @app.get("/peserta/<int:pid>/riwayat")
    @roles_required("pemberkasan", "admin")
    def participant_history(pid):
        p = participant(pid)
        rows = all_rows(
            "SELECT a.*,u.username FROM audit a LEFT JOIN users u ON u.id=a.actor_id WHERE (a.entity='participant' AND a.entity_id=?) OR (a.entity='upload' AND a.entity_id IN (SELECT id FROM uploads WHERE participant_id=? AND category<>'bukti')) OR (a.entity='document' AND a.entity_id IN (SELECT id FROM documents WHERE participant_id=? AND kind<>'kuitansi')) ORDER BY a.id DESC",
            (pid, pid, pid),
        )
        uploads = all_rows(
            "SELECT * FROM uploads WHERE participant_id=? AND category<>'bukti' ORDER BY id DESC",
            (pid,),
        )
        return render_template("history.html", p=p, rows=rows, uploads=uploads)

    @app.get("/foto/<int:uid>")
    @login_required
    def participant_photo(uid):
        photo = one("SELECT * FROM uploads WHERE id=? AND category='foto'", (uid,))
        if not photo:
            abort(404)
        check_participant(photo["participant_id"])
        require(photo["mime"] in ("image/jpeg", "image/png"), "Berkas bukan foto.")
        return send_file(Path(app.config["UPLOAD_DIR"]) / photo["storage_name"], mimetype=photo["mime"], as_attachment=False)

    @app.get("/berkas/<int:uid>")
    @app.get("/berkas/<int:uid>/lihat")
    @login_required
    def download_upload(uid):
        u = one("SELECT * FROM uploads WHERE id=?", (uid,))
        if not u:
            abort(404)
        if u["participant_id"]:
            check_participant(u["participant_id"], financial=u["category"] == "bukti")
        elif not has_role("bendahara", "admin"):
            abort(403)
        return send_file(
            Path(app.config["UPLOAD_DIR"]) / u["storage_name"],
            mimetype=u["mime"],
            as_attachment=not request.path.endswith("/lihat"),
            download_name=u["filename"],
        )

    @app.get("/verifikasi/<token>")
    def verify(token):
        doc = one(
            "SELECT d.*,p.number,a.name,a.level FROM documents d JOIN participants p ON p.id=d.participant_id JOIN applications a ON a.id=p.application_id WHERE d.token=? AND d.kind IN ('kelulusan','daftar_ulang','kuitansi','formulir')",
            (token,),
        )
        # Hanya lima atribut publik diteruskan ke template; tidak ada snapshot keuangan/biodata.
        public = {k: doc[k] for k in ("name", "number", "level", "kind", "valid")} if doc else None
        return render_template("verify.html", doc=public), 200 if doc else 404

    @app.get("/absensi/<token>")
    @roles_required("pemberkasan")
    def scan(token):
        doc = one("SELECT * FROM documents WHERE token=? AND kind='kartu'", (token,))
        if not doc:
            abort(404)
        if not doc["valid"]:
            flash(
                "Kartu lama sudah tidak berlaku. Periksa jadwal terbaru sebelum mencatat kehadiran.",
                "warning",
            )
        return redirect(url_for("participant_menu", pid=doc["participant_id"], section="absensi"))

    @app.get("/pemindai")
    @roles_required("pemberkasan")
    def scanner():
        return render_template("scanner.html")

    @app.route("/jadwal", methods=["GET", "POST"])
    @roles_required("pemberkasan", "admin")
    def schedules():
        if request.method == "POST":
            if not has_role("pemberkasan"):
                abort(403)
            with transaction():
                action = request.form.get("action")
                if action == "open":
                    open_schedule(request.form["date"])
                else:
                    sid = int(request.form["schedule_id"])
                    s = one("SELECT * FROM schedules WHERE id=?", (sid,))
                    require(s, "Jadwal tidak ditemukan.")
                    if action == "cancel":
                        reason = request.form.get("reason", "").strip()
                        require(
                            reason and request.form.get("confirm") == "ya",
                            "Alasan dan konfirmasi pembatalan wajib diisi.",
                        )
                        replacement = int(request.form["replacement"])
                        require(replacement != sid, "Pilih tanggal pengganti yang berbeda.")
                        target = one(
                            "SELECT * FROM schedules WHERE id=? AND status='Terbuka' AND date>=?",
                            (replacement, today().isoformat()),
                        )
                        require(target, "Tanggal pengganti harus terbuka dan belum berlalu.")
                        for p in all_rows(
                            "SELECT id FROM participants WHERE schedule_id=?", (sid,)
                        ):
                            set_schedule(p["id"], replacement, True, "Pembatalan tes: " + reason)
                        execute(
                            "UPDATE schedules SET status='Dibatalkan',reason=? WHERE id=?",
                            (reason, sid),
                        )
                    else:
                        require(
                            action in ("close", "reopen") and s["status"] != "Dibatalkan",
                            "Tindakan jadwal tidak valid.",
                        )
                        execute(
                            "UPDATE schedules SET status=? WHERE id=?",
                            ("Ditutup" if action == "close" else "Terbuka", sid),
                        )
                    audit(
                        "schedule",
                        sid,
                        "Pengaturan jadwal",
                        old=dict(s),
                        new=action,
                        reason=request.form.get("reason"),
                    )
            flash(
                "Jadwal diperbarui. Penutupan tanggal tidak membatalkan peserta yang sudah terjadwal.",
                "success",
            )
            return redirect("/jadwal")
        return render_template(
            "schedules.html",
            rows=all_rows(
                "SELECT s.*, (SELECT COUNT(*) FROM participants p WHERE p.schedule_id=s.id) AS count FROM schedules s ORDER BY date"
            ),
        )

    @app.get("/jadwal/<int:sid>")
    @roles_required("pemberkasan", "admin")
    def schedule_participants(sid):
        schedule = one("SELECT * FROM schedules WHERE id=?", (sid,))
        if not schedule:
            abort(404)
        level = request.args.get("level", "")
        if level not in ("", "MI", "MTS", "MA"):
            abort(400)
        rows = all_rows(
            "SELECT p.id,p.number,p.attendance,a.name,a.level FROM participants p "
            "JOIN applications a ON a.id=p.application_id WHERE p.schedule_id=? "
            "AND (?='' OR a.level=?) ORDER BY a.level,p.number",
            (sid, level, level),
        )
        return render_template(
            "schedule_participants.html", schedule=schedule, rows=rows, level=level
        )

    @app.route("/keuangan", methods=["GET", "POST"])
    @app.route("/keuangan/<view>", methods=["GET", "POST"])
    @roles_required("bendahara", "admin")
    def finance(view=None):
        if view not in (None, "pendaftaran", "daftar-ulang", "verifikasi", "riwayat"):
            abort(404)
        if view in ("pendaftaran", "daftar-ulang") and not has_role("bendahara"):
            abort(403)
        if request.method == "POST":
            if not has_role("bendahara"):
                abort(403)
            with transaction():
                action = request.form.get("action")
                if action == "cash-initial":
                    key = request.form["key"]
                    old = one("SELECT id FROM payments WHERE idempotency_key=?", (key,))
                    if not old:
                        aid, _ = new_application(request.form, "langsung")
                        pay_id = create_payment(aid, "pendaftaran", "tunai", 200000, key)
                        approve_payment(pay_id)
                elif action == "cash":
                    p = one(
                        "SELECT * FROM participants WHERE number=?",
                        (request.form.get("number", "").strip().upper(),),
                    )
                    require(p, "Nomor peserta tidak ditemukan.")
                    receiver = request.form.get("receiver_name", "").strip()
                    require(2 <= len(receiver) <= 150, "Isi nama penerima uang tunai (2-150 karakter).")
                    pay_id = create_payment(
                        p["application_id"],
                        "daftar_ulang",
                        "tunai",
                        int(request.form["amount"]),
                        request.form["key"],
                    )
                    pay = one("SELECT * FROM payments WHERE id=?", (pay_id,))
                    require(pay["kind"] == "daftar_ulang" and pay["method"] == "tunai", "Identitas transaksi tunai tidak sesuai.")
                    recorded_receiver = cash_receiver(pay_id)
                    require(not recorded_receiver or recorded_receiver == receiver, "Transaksi sudah dicatat dengan penerima berbeda. Jangan kirim ulang dengan nama lain.")
                    if not recorded_receiver:
                        require(pay["status"] != "Disahkan", "Transaksi lama sudah disahkan; nama penerima tidak dapat ditambahkan dengan mengirim ulang pembayaran.")
                        audit("payment", pay_id, "Penerima tunai dicatat", new={"receiver_name": receiver})
                    approve_payment(pay_id)
                elif action == "approve":
                    approve_payment(int(request.form["payment_id"]))
                elif action == "reject":
                    reject_payment(int(request.form["payment_id"]), request.form.get("reason", ""))
                elif action == "correct":
                    require(
                        request.form.get("confirm") == "ya", "Konfirmasi koreksi terlebih dahulu."
                    )
                    key = request.form["key"]
                    if not one("SELECT key FROM operations WHERE key=?", (key,)):
                        correct_payment(
                            int(request.form["payment_id"]),
                            int(request.form["amount"]),
                            request.form.get("reason", ""),
                        )
                        execute("INSERT INTO operations VALUES(?,?,?)", (key, g.user["id"], now()))
                elif action == "registration-note":
                    require(
                        request.form.get("confirm") == "ya", "Konfirmasi koreksi terlebih dahulu."
                    )
                    key = request.form["key"]
                    if one("SELECT key FROM operations WHERE key=?", (key,)):
                        return redirect("/keuangan")
                    reason = request.form.get("reason", "").strip()
                    pay = one(
                        "SELECT * FROM payments WHERE id=? AND kind='pendaftaran' AND status='Disahkan'",
                        (request.form["payment_id"],),
                    )
                    require(pay and reason, "Pilih pembayaran sah dan isi alasan.")
                    method = request.form.get("method")
                    require(method in ("tunai", "transfer"), "Metode tidak valid.")
                    execute(
                        "UPDATE payments SET method=?,reason=? WHERE id=?",
                        (method, reason, pay["id"]),
                    )
                    invalidate(pay["participant_id"], ["kuitansi"], pay["id"])
                    did = issue_document(pay["participant_id"], "kuitansi", pay["id"])
                    audit(
                        "payment",
                        pay["id"],
                        "Koreksi keterangan pendaftaran",
                        old=dict(pay),
                        new={"method": method},
                        reason=reason,
                    )
                    notify(
                        pay["application_id"],
                        f"reg-correction:{did}",
                        f"Keterangan pembayaran dikoreksi: {reason}. Bukti terbaru: "
                        + app.config["BASE_URL"]
                        + f"/dokumen/{did}",
                    )
                    execute("INSERT INTO operations VALUES(?,?,?)", (key, g.user["id"], now()))
                else:
                    abort(404)
            flash("Transaksi berhasil diproses.", "success")
            return redirect(request.path)
        q = request.args.get("q", "")
        rows = all_rows(
            "SELECT t.*,a.name,a.level,a.reference,p.number,p.financial_review,(SELECT id FROM documents d WHERE d.payment_id=t.id AND d.valid=1 ORDER BY d.id DESC LIMIT 1) AS receipt_id FROM payments t JOIN applications a ON a.id=t.application_id LEFT JOIN participants p ON p.id=t.participant_id WHERE a.name LIKE ? OR p.number LIKE ? ORDER BY t.id DESC",
            ("%" + q + "%", "%" + q + "%"),
        )
        receivers = {row["entity_id"]: json.loads(row["new_value"])["receiver_name"] for row in all_rows("SELECT entity_id,new_value FROM audit WHERE entity='payment' AND action='Penerima tunai dicatat' ORDER BY id")}
        rows = [dict(row, receiver_name=receivers.get(row["id"], "")) for row in rows]
        return render_template(
            "finance.html",
            view=view,
            rows=(
                [row for row in rows if row["status"] == "Menunggu verifikasi"]
                if view == "verifikasi"
                else rows
            ),
            q=q,
            total=one("SELECT COALESCE(SUM(amount),0) AS n FROM payments WHERE status='Disahkan'")[
                "n"
            ],
        )

    @app.route("/pengaturan", methods=["GET", "POST"])
    @app.route("/pengaturan/<view>", methods=["GET", "POST"])
    @roles_required("admin")
    def configuration(view=None):
        if view not in (None, "lembaga", "biaya", "petugas"):
            abort(404)
        if request.method == "POST":
            with transaction():
                action = request.form.get("action")
                if action == "settings":
                    fields = (
                        "open_date",
                        "close_date",
                        "contact",
                        "bank",
                        "bank_number",
                        "bank_owner",
                        "first_deadline",
                        "form_body",
                        "letter_body",
                        "letterhead",
                        "signer",
                        "letter_number",
                        "template_official",
                    )
                    old = settings()
                    new = {k: request.form.get(k, "").strip() for k in fields}
                    for k in ("open_date", "close_date", "first_deadline"):
                        if new[k]:
                            try:
                                date.fromisoformat(new[k])
                            except ValueError:
                                raise RuleError("Format tanggal tidak valid.")
                    require(
                        not new["open_date"]
                        or not new["close_date"]
                        or new["open_date"] <= new["close_date"],
                        "Tanggal tutup harus setelah tanggal buka.",
                    )
                    if new["template_official"] == "ya":
                        require(
                            all(
                                new[k]
                                for k in (
                                    "form_body",
                                    "letter_body",
                                    "letterhead",
                                    "signer",
                                    "letter_number",
                                )
                            ),
                            "Lengkapi seluruh template dan identitas resmi sebelum mengaktifkannya.",
                        )
                    for k, v in new.items():
                        execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (k, v))
                    audit("settings", None, "Pengaturan diperbarui", old=old, new=new)
                elif action == "fee":
                    level = request.form.get("level")
                    require(level in LEVELS, "Jenjang tidak valid.")
                    components = []
                    if "component_name" in request.form:
                        names = request.form.getlist("component_name")
                        amounts = request.form.getlist("component_amount")
                        require(len(names) == len(amounts) and len(names) <= 100,
                                "Rincian tagihan tidak valid. Maksimal 100 komponen.")
                        rows = zip(names, amounts)
                    else:
                        # Kompatibilitas dengan formulir lama.
                        rows = []
                        for line in request.form.get("components", "").splitlines():
                            if not line.strip():
                                continue
                            require("|" in line, "Format rincian: Nama komponen | nominal rupiah.")
                            rows.append(line.rsplit("|", 1))
                    for name, amount in rows:
                        require(amount.strip().isascii() and amount.strip().isdigit(),
                                "Nominal komponen harus angka bulat rupiah tanpa Rp, titik, atau koma.")
                        require(len(amount.strip()) <= 9, "Nominal komponen terlalu besar.")
                        amount = int(amount.strip())
                        require(
                            name.strip() and len(name.strip()) <= 150 and 0 < amount < 1000000000,
                            "Isi nama tagihan dan nominal antara 1 sampai 999999999 rupiah.",
                        )
                        components.append({"name": name.strip(), "amount": amount})
                    require(components, "Isi setidaknya satu komponen tagihan.")
                    fid = execute(
                        "INSERT INTO fee_versions(level,components,total,created_at,created_by) VALUES(?,?,?,?,?)",
                        (
                            level,
                            json.dumps(components, ensure_ascii=False),
                            sum(c["amount"] for c in components),
                            now(),
                            g.user["id"],
                        ),
                    ).lastrowid
                    audit("fee", fid, "Versi tagihan ditetapkan", new=components)
                elif action == "staff":
                    roles = request.form.getlist("roles")
                    require(
                        roles and set(roles) <= {"admin", "bendahara", "pemberkasan"},
                        "Pilih peran petugas.",
                    )
                    username = request.form.get("username", "").strip()
                    require(
                        username
                        and len(username) <= 80
                        and not any(username.upper().startswith(k + "-") for k in LEVELS),
                        "Gunakan username petugas yang berbeda dari pola nomor peserta.",
                    )
                    pwd = request.form.get("password", "")
                    require(len(pwd) >= 8, "Kata sandi minimal 8 karakter.")
                    uid = execute(
                        "INSERT INTO users(username,password_hash,roles,active) VALUES(?,?,?,1)",
                        (username, generate_password_hash(pwd), ",".join(sorted(set(roles)))),
                    ).lastrowid
                    audit("user", uid, "Akun petugas dibuat", new=roles)
                elif action == "roles":
                    uid = int(request.form["user_id"])
                    user = one("SELECT * FROM users WHERE id=? AND participant_id IS NULL", (uid,))
                    require(user, "Akun petugas tidak ditemukan.")
                    roles = request.form.getlist("roles")
                    require(
                        roles and set(roles) <= {"admin", "bendahara", "pemberkasan"},
                        "Pilih peran petugas.",
                    )
                    active = int(request.form.get("active") == "ya")
                    if "admin" in user["roles"] and ("admin" not in roles or not active):
                        require(
                            one(
                                "SELECT COUNT(*) AS n FROM users WHERE active=1 AND (roles='admin' OR roles LIKE 'admin,%' OR roles LIKE '%,admin,%' OR roles LIKE '%,admin')"
                            )["n"]
                            > 1,
                            "Tidak boleh menonaktifkan Admin Utama terakhir.",
                        )
                    execute(
                        "UPDATE users SET roles=?,active=? WHERE id=?",
                        (",".join(sorted(set(roles))), active, uid),
                    )
                    execute("DELETE FROM sessions WHERE user_id=?", (uid,))
                    audit("user", uid, "Peran diubah", old=user["roles"], new=roles)
                else:
                    abort(404)
            flash(
                "Pengaturan disimpan. Tagihan yang sudah diterbitkan tetap memakai versi sebelumnya.",
                "success",
            )
            return redirect("/pengaturan")
        return render_template(
            "settings.html",
            view=view,
            fees=all_rows("SELECT * FROM fee_versions ORDER BY id DESC"),
            staff=all_rows(
                "SELECT id,username,roles,active FROM users WHERE participant_id IS NULL"
            ),
        )

    @app.route("/akun", methods=["GET", "POST"])
    @login_required
    def account():
        if request.method == "POST":
            rate_limit("change-password")
            require(
                check_password_hash(g.user["password_hash"], request.form.get("old_password", "")),
                "Kata sandi lama tidak sesuai.",
            )
            pwd = request.form.get("password", "")
            require(
                len(pwd) >= 8 and pwd == request.form.get("confirm"),
                "Kata sandi minimal 8 karakter dan konfirmasi harus sama.",
            )
            with transaction():
                execute(
                    "UPDATE users SET password_hash=? WHERE id=?",
                    (generate_password_hash(pwd), g.user["id"]),
                )
                execute("DELETE FROM sessions WHERE user_id=?", (g.user["id"],))
            session.clear()
            flash("Kata sandi diperbarui. Silakan login kembali.", "success")
            return redirect("/login")
        return render_template("auth.html", mode="password", title="Pengaturan kata sandi")

    @app.route("/aktivitas", methods=["GET", "POST"])
    @roles_required("admin")
    def activity():
        if request.method == "POST":
            with transaction():
                require(
                    request.form.get("confirm") == "ya", "Konfirmasikan hasil pemeriksaan penyedia."
                )
                reason = request.form.get("reason", "").strip()
                require(reason, "Catatan rekonsiliasi wajib diisi.")
                event = one("SELECT * FROM outbox WHERE id=?", (request.form.get("event_id"),))
                require(
                    event and event["status"] in ("diproses", "gagal"),
                    "Hanya kejadian bermasalah yang dapat direkonsiliasi.",
                )
                action = request.form.get("action")
                require(action in ("retry", "delivered"), "Tindakan tidak valid.")
                if action == "retry":
                    require(
                        event["attempts"] < 5,
                        "Batas lima percobaan tercapai. Periksa layanan dan tangani pesan secara operasional.",
                    )
                    execute(
                        "UPDATE outbox SET status='gagal',last_error=?,next_attempt_at=? WHERE id=?",
                        (reason, now(), event["id"]),
                    )
                else:
                    delivery_id = request.form.get("delivery_id", "").strip()
                    require(delivery_id, "Identitas pengiriman dari penyedia wajib diisi.")
                    execute(
                        "UPDATE outbox SET status='berhasil',delivery_id=?,last_error=NULL WHERE id=?",
                        (delivery_id, event["id"]),
                    )
                execute(
                    "INSERT INTO delivery_attempts(event_id,status,detail,created_at) VALUES(?,?,?,?)",
                    (event["id"], "rekonsiliasi", reason, now()),
                )
                audit(
                    "outbox",
                    None,
                    "Rekonsiliasi notifikasi",
                    old={"id": event["id"], "status": event["status"]},
                    new=action,
                    reason=reason,
                )
            flash("Hasil rekonsiliasi disimpan.", "success")
            return redirect("/aktivitas")
        events = [dict(row) for row in all_rows("SELECT * FROM outbox ORDER BY created_at DESC LIMIT 200")]
        from urllib.parse import urlsplit
        for event in events:
            event["account_link"] = None
            kind, _, token_hash = event["event_key"].partition(":")
            if kind not in ("aktivasi", "reset"):
                continue
            token_row = one("SELECT t.*,u.username FROM account_tokens t JOIN users u ON u.id=t.user_id WHERE t.token_hash=? AND t.kind=?", (token_hash, kind))
            if not token_row:
                continue
            event["account_number"] = token_row["username"]
            event["account_status"] = "Sudah dipakai / diganti tautan baru" if token_row["used_at"] else ("Kedaluwarsa" if token_row["expires_at"] <= now() else "Masih berlaku")
            if not token_row["used_at"] and token_row["expires_at"] > now():
                path = urlsplit(json.loads(event["payload"]).get("link", "")).path
                raw_token = path.rsplit("/", 1)[-1]
                if path == f"/{kind}/{raw_token}" and digest(raw_token) == token_hash:
                    event["account_link"] = path
                    event["account_label"] = "Buka aktivasi akun" if kind == "aktivasi" else "Buka pengaturan kata sandi"
        return render_template(
            "activity.html",
            rows=all_rows(
                "SELECT a.*,u.username FROM audit a LEFT JOIN users u ON u.id=a.actor_id ORDER BY a.id DESC LIMIT 300"
            ),
            outbox=events,
        )

    @app.get("/laporan")
    @roles_required("admin", "pemberkasan", "bendahara")
    def reports():
        return render_template("reports.html")

    @app.get("/laporan/<kind>.xlsx")
    @login_required
    def export(kind):
        from .reports import build_report

        if kind not in ("pendaftaran", "pembayaran") or not has_role(
            "admin", "pemberkasan" if kind == "pendaftaran" else "bendahara"
        ):
            abort(403)
        return send_file(
            build_report(kind, request.args),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"laporan-{kind}-2027-2028.xlsx",
        )

    @app.get("/health")
    def health():
        one("SELECT 1")
        return {"status": "ok"}

    @app.get("/bantuan")
    @login_required
    def help_page():
        return render_template("help.html")

    @app.get("/pekerjaan")
    @roles_required("admin", "bendahara", "pemberkasan")
    def work_queue():
        work = []
        if has_role("admin", "bendahara"):
            work.append(
                dict(
                    label="Pembayaran menunggu verifikasi",
                    icon="💳",
                    url="/keuangan/verifikasi",
                    count=one(
                        "SELECT COUNT(*) AS n FROM payments WHERE status='Menunggu verifikasi'"
                    )["n"],
                    description="Periksa bukti sesuai kewenangan Bendahara.",
                )
            )
        if has_role("admin", "pemberkasan"):
            work.append(
                dict(
                    label="Berkas menunggu pemeriksaan",
                    icon="📁",
                    url="/layanan/berkas",
                    count=one(
                        "SELECT COUNT(*) AS n FROM uploads WHERE category<>'bukti' AND status='Menunggu pemeriksaan' AND id IN (SELECT MAX(id) FROM uploads WHERE category<>'bukti' GROUP BY participant_id,category)"
                    )["n"],
                    description="Pilih peserta untuk memeriksa dokumen terbaru.",
                )
            )
            work.append(
                dict(
                    label="Draf hasil siap ditinjau",
                    icon="📋",
                    url="/layanan/hasil",
                    count=one(
                        "SELECT COUNT(*) AS n FROM participants WHERE draft_result IS NOT NULL AND published_result IS NULL"
                    )["n"],
                    description="Publikasi hasil dilakukan per peserta oleh Pemberkasan.",
                )
            )
        return render_template("work.html", work=work)

    from .notifications import register_integration

    register_integration(app)
    return app
