from types import SimpleNamespace

import pytest

from scripts import startup_portal as startup
from scripts import google_sheets


def prepare(monkeypatch):
    monkeypatch.setattr(startup, "wait_for", lambda check, **kwargs: check())
    monkeypatch.setattr(startup, "database_ready", lambda *args: True)
    monkeypatch.setattr(startup, "health_ready", lambda *args: True)
    monkeypatch.setattr(startup.time, "sleep", lambda seconds: None)


def test_startup_keeps_existing_server_and_worker(monkeypatch, tmp_path):
    prepare(monkeypatch)
    monkeypatch.setattr(
        startup, "project_processes", lambda: {"server": [11, 12], "sheets": [13, 14], "notifications": [15, 16]}
    )
    monkeypatch.setattr(
        startup, "launch", lambda *args: pytest.fail("Tidak boleh membuat proses ganda")
    )
    assert startup.start_services({}, tmp_path) == 0


def test_database_unavailable_does_not_start_anything(monkeypatch, tmp_path):
    prepare(monkeypatch)
    monkeypatch.setattr(startup, "database_ready", lambda *args: False)
    monkeypatch.setattr(startup, "launch", lambda *args: pytest.fail("Database belum siap"))
    assert startup.start_services({}, tmp_path) == 1


def test_restart_stops_only_detected_project_processes(monkeypatch):
    stopped = []

    class Process:
        def __init__(self, pid):
            self.pid = pid

        def terminate(self):
            stopped.append(("terminate", self.pid))

        def wait(self, timeout):
            stopped.append(("wait", self.pid, timeout))

    monkeypatch.setattr(
        startup,
        "project_processes",
        lambda: {"server": [11], "sheets": [12], "notifications": [13]},
    )
    monkeypatch.setattr(startup.psutil, "Process", Process)
    startup.stop_project_services()
    assert [item[1] for item in stopped if item[0] == "terminate"] == [11, 12, 13]


def test_foreign_port_is_not_killed_or_reused(monkeypatch, tmp_path):
    prepare(monkeypatch)
    monkeypatch.setattr(startup, "project_processes", lambda: {"server": [], "sheets": [], "notifications": []})
    monkeypatch.setattr(startup, "port_busy", lambda port: True)
    monkeypatch.setattr(startup, "launch", lambda *args: pytest.fail("Port milik proses lain"))
    assert startup.start_services({}, tmp_path) == 1


def test_fresh_start_orders_server_before_sheets(monkeypatch, tmp_path):
    prepare(monkeypatch)
    monkeypatch.setattr(startup, "project_processes", lambda: {"server": [], "sheets": [], "notifications": []})
    monkeypatch.setattr(startup, "port_busy", lambda port: False)
    (tmp_path / "google-sheets-token.json").write_text("test-only")
    calls = []
    monkeypatch.setattr(
        startup,
        "launch",
        lambda kind, *args: calls.append(kind) or SimpleNamespace(poll=lambda: None),
    )
    assert startup.start_services({"GOOGLE_SHEETS_ID": "test-only"}, tmp_path) == 0
    assert calls == ["server", "notifications", "sheets"]


def test_missing_google_token_starts_only_portal(monkeypatch, tmp_path):
    prepare(monkeypatch)
    monkeypatch.setattr(startup, "project_processes", lambda: {"server": [], "sheets": [], "notifications": []})
    monkeypatch.setattr(startup, "port_busy", lambda port: False)
    calls = []
    monkeypatch.setattr(startup, "launch", lambda kind, *args: calls.append(kind))
    assert startup.start_services({"GOOGLE_SHEETS_ID": "test-only"}, tmp_path) == 0
    assert calls == ["server", "notifications"]


def test_watch_retries_offline_credentials_without_new_login(monkeypatch, tmp_path):
    from google.auth.exceptions import TransportError

    attempts = []

    def credentials(*args, **kwargs):
        attempts.append(kwargs)
        if len(attempts) < 3:
            raise TransportError("offline test")
        return "ready"

    monkeypatch.setattr(google_sheets, "credentials_for", credentials)
    monkeypatch.setattr(google_sheets.time, "sleep", lambda seconds: None)
    assert google_sheets.load_credentials(tmp_path, watch=True) == "ready"
    assert len(attempts) == 3 and not any(call["login"] for call in attempts)


def test_preview_does_not_loop_on_network_failure(monkeypatch, tmp_path):
    from google.auth.exceptions import TransportError

    def offline(*args, **kwargs):
        raise TransportError("offline test")

    monkeypatch.setattr(google_sheets, "credentials_for", offline)
    with pytest.raises(TransportError):
        google_sheets.load_credentials(tmp_path)
