import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import abort, current_app, g, request, session, redirect, url_for
from .db import one, execute, now, transaction
from .domain import digest, require


def has_role(*roles):
    return bool(getattr(g, "user", None)) and bool(set(g.user["roles"].split(",")) & set(roles))


def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not g.user:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapped


def roles_required(*roles):
    def decorate(fn):
        @wraps(fn)
        @login_required
        def wrapped(*args, **kwargs):
            if not has_role(*roles):
                abort(403)
            return fn(*args, **kwargs)

        return wrapped

    return decorate


def check_participant(pid, financial=False):
    if not g.user:
        abort(401)
    if g.user["participant_id"] == pid:
        return
    if has_role("admin", "bendahara" if financial else "pemberkasan"):
        return
    abort(403)


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def rate_limit(bucket, limit=8, seconds=900):
    key = digest(bucket + ":" + (request.remote_addr or "local"))
    with transaction():
        row = one("SELECT * FROM rate_limits WHERE key=?", (key,))
        if not row or row["reset_at"] < now():
            expiry = (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()
            execute("INSERT OR REPLACE INTO rate_limits VALUES(?,1,?)", (key, expiry))
            return
        require(row["count"] < limit, "Terlalu banyak permintaan. Coba lagi setelah 15 menit.")
        execute("UPDATE rate_limits SET count=count+1 WHERE key=?", (key,))


def create_session(user):
    token = secrets.token_urlsafe(32)
    expiry = (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat()
    execute("INSERT INTO sessions VALUES(?,?,?)", (digest(token), user["id"], expiry))
    session.clear()
    session["sid"] = token
    session["csrf"] = secrets.token_urlsafe(32)


def install_security(app):
    @app.before_request
    def load_user():
        g.user = None
        if session.get("sid"):
            g.user = one(
                "SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>? AND u.active=1",
                (digest(session["sid"]), now()),
            )
        if request.method == "POST" and not request.path.startswith("/integrasi/"):
            token = request.form.get("csrf", "") or request.headers.get("X-CSRF-Token", "")
            if not session.get("csrf") or not secrets.compare_digest(token, session["csrf"]):
                abort(
                    400,
                    description="Sesi formulir kedaluwarsa. Muat ulang halaman dan coba kembali.",
                )

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
        response.headers["Cache-Control"] = "no-store"
        if current_app.config["SESSION_COOKIE_SECURE"]:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
