from flask import g

from psb.db import all_rows, one, transaction
from psb.domain import new_application, notify
from psb.notifications import process_outbox


DATA = {
    "level": "MI",
    "name": "Santri Uji Email",
    "birth_place": "Maliku",
    "birth_date": "2017-01-01",
    "phone": "6281111111111",
    "email": "wali@example.test",
}


class FakeSMTP:
    sent = []

    def __init__(self, host, port, timeout):
        self.host, self.port, self.timeout = host, port, timeout

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def ehlo(self):
        pass

    def starttls(self):
        pass

    def login(self, username, password):
        self.login_values = (username, password)

    def send_message(self, message):
        self.sent.append(message)
        return {}


def email_event():
    aid, _ = new_application(DATA, "online")
    notify(
        aid,
        "uji-smtp",
        "Aktifkan akun melalui tautan ini.",
        channels=("email",),
        payload={"link": "http://localhost/aktivasi/uji"},
    )
    return one("SELECT * FROM outbox WHERE application_id=? AND event_key='uji-smtp' AND channel='email'", (aid,))


def test_smtp_email_sent_and_marked_success(app, monkeypatch):
    FakeSMTP.sent = []
    monkeypatch.setattr("psb.notifications.smtplib.SMTP", FakeSMTP)
    app.config.update(
        EMAIL_DELIVERY_MODE="smtp",
        SMTP_HOST="smtp.example.test",
        SMTP_PORT=587,
        SMTP_USERNAME="pengirim@example.test",
        SMTP_PASSWORD="rahasia-lokal",
        SMTP_FROM="pengirim@example.test",
        SMTP_STARTTLS=True,
    )
    with app.app_context(), transaction():
        event = email_event()
    with app.app_context():
        assert process_outbox(app) >= 1
        stored = one("SELECT * FROM outbox WHERE id=?", (event["id"],))
        assert stored["status"] == "berhasil"
        assert stored["delivery_id"]
    sent = [message for message in FakeSMTP.sent if "Aktifkan akun" in message.get_content()]
    assert len(sent) == 1
    assert sent[0]["To"] == DATA["email"]


def test_smtp_without_credentials_does_not_send(app):
    app.config.update(EMAIL_DELIVERY_MODE="smtp")
    with app.app_context(), transaction():
        event = email_event()
    with app.app_context():
        process_outbox(app)
        stored = one("SELECT * FROM outbox WHERE id=?", (event["id"],))
        assert stored["status"] == "gagal"
        assert "SMTP" in stored["last_error"]
