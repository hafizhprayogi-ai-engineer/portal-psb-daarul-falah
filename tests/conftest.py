import secrets
import os
from urllib.parse import urlsplit, urlunsplit
import pytest
from flask import g
from werkzeug.security import generate_password_hash
from psb.app import create_app
from psb.db import execute, one, transaction


@pytest.fixture
def mysql_database():
    url = os.getenv("PSB_TEST_MYSQL_URL", "")
    if not url:
        yield ""
        return
    import pymysql
    from psb.mysql import connection_options

    options = connection_options(url)
    if not options["database"].startswith("psb_test_"):
        raise RuntimeError("PSB_TEST_MYSQL_URL harus memakai nama database psb_test_*.")
    options.pop("database")
    connection = pymysql.connect(**options)
    name = "psb_test_" + secrets.token_hex(10)
    connection.cursor().execute(
        f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin"
    )
    parsed = urlsplit(url)
    try:
        yield urlunsplit(parsed._replace(path="/" + name))
    finally:
        connection.cursor().execute(f"DROP DATABASE `{name}`")
        connection.close()


PASSWORD = "Uji-lokal-saja-2027!"


@pytest.fixture
def app(tmp_path, mysql_database):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": secrets.token_hex(32),
            "DATA_DIR": str(tmp_path),
            "DATABASE": str(tmp_path / "test.sqlite3"),
            "DATABASE_URL": mysql_database,
            "UPLOAD_DIR": str(tmp_path / "private"),
            "BASE_URL": "http://localhost",
            "NOTIFICATION_MODE": "simulation",
            "INTEGRATION_TOKEN": "test-integration-only",
        }
    )
    with app.app_context():
        with transaction():
            for username, roles in [
                ("admin", "admin"),
                ("bendahara", "bendahara"),
                ("berkas", "pemberkasan"),
                ("rangkap", "admin,pemberkasan,bendahara"),
            ]:
                execute(
                    "INSERT INTO users(username,password_hash,roles,active) VALUES(?,?,?,1)",
                    (username, generate_password_hash(PASSWORD), roles),
                )
            for k, v in {
                "open_date": "2020-01-01",
                "close_date": "2099-12-31",
                "bank": "BANK UJI",
                "bank_number": "000000",
                "bank_owner": "DATA FIKTIF",
            }.items():
                execute("INSERT INTO settings VALUES(?,?)", (k, v))
    return app


@pytest.fixture
def ctx(app):
    with app.app_context():
        g.user = one("SELECT * FROM users WHERE username='rangkap'")
        yield app


def login_as(app, client, username):
    from psb.security import create_session

    with app.test_request_context():
        user = one("SELECT * FROM users WHERE username=?", (username,))
        with transaction():
            create_session(user)
        from flask import session

        sid = session["sid"]
    with client.session_transaction() as sess:
        sess["sid"] = sid
        sess["csrf"] = "csrf-test"


def post(client, url, data=None):
    with client.session_transaction() as sess:
        sess["csrf"] = "csrf-test"
    return client.post(url, data={"csrf": "csrf-test", **(data or {})})
