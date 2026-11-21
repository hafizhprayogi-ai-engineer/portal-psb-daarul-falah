import hashlib
import io

import pytest
from werkzeug.datastructures import FileStorage

from psb.db import transaction, all_rows, one
from psb.files import save_upload
from psb.drive_sync import sync_uploads, DriveError, private_metadata
from test_system import paid_participant, PDF


def test_drive_login_uses_separate_token_and_narrow_scope(monkeypatch, tmp_path):
    from psb import drive_sync

    captured = {}

    def credentials(data, **kwargs):
        captured.update(kwargs)
        return "test-only"

    monkeypatch.setattr(drive_sync, "credentials_for", credentials)
    assert drive_sync.drive_credentials(tmp_path, login=True) == "test-only"
    assert captured["token_filename"] == "google-drive-token.json"
    assert captured["scopes"] == ["https://www.googleapis.com/auth/drive.file"]


def test_setup_resumes_saved_login_and_checks_valid_about_fields(ctx, monkeypatch, tmp_path):
    from scripts import google_drive
    from dotenv import dotenv_values

    pid, aid = participant_example()
    calls = []

    class Client(FakeDrive):
        def request(self, method, suffix, **kwargs):
            assert suffix == "about" and kwargs["params"]["fields"] == "user(permissionId)"
            calls.append("about")
            return {"user": {"permissionId": "test-only"}}

        def close(self):
            pass

    client = Client()
    monkeypatch.setattr(google_drive, "ROOT", tmp_path)
    monkeypatch.setattr(google_drive, "create_app", lambda: ctx)

    def credentials(data, login=False):
        assert not login
        return "saved-test-only"

    monkeypatch.setattr(google_drive, "drive_credentials", credentials)
    monkeypatch.setattr(google_drive, "DriveClient", lambda credentials: client)
    monkeypatch.setattr("sys.argv", ["google_drive.py", "setup"])
    google_drive.main()
    assert calls == ["about"] and len(client.objects) == 3
    assert dotenv_values(tmp_path / ".env")["GOOGLE_DRIVE_ENABLED"] == "true"


def test_drive_folder_link_visible_only_to_staff(ctx):
    from conftest import login_as
    from test_system import passed

    pid, aid = participant_example()
    with transaction():
        passed(pid)
    upload_example(pid, aid)
    sync_uploads(FakeDrive())
    client = ctx.test_client()
    login_as(ctx, client, "MI-01")
    response = client.get(f"/peserta/{pid}/menu/berkas")
    assert response.status_code == 200
    assert b"Buka folder Drive privat santri" not in response.data
    assert (
        b"Tersalin &amp; terverifikasi" in response.data
        or b"Tersalin & terverifikasi" in response.data
    )
    login_as(ctx, client, "berkas")
    response = client.get(f"/peserta/{pid}/menu/berkas")
    assert response.status_code == 200 and b"Buka folder Drive privat santri" in response.data


class FakeDrive:
    def __init__(self):
        self.objects = {}
        self.next_id = 0
        self.created = []
        self.fail_after_file = False

    def generate_id(self):
        self.next_id += 1
        return "fake_drive_" + str(self.next_id)

    def metadata(self, file_id):
        return self.objects.get(file_id)

    def create(self, file_id, name, parent=None, content=None, mime=None):
        assert file_id not in self.objects
        result = dict(
            id=file_id,
            name=name,
            trashed=False,
            parents=[parent] if parent else [],
            permissions=[{"type": "user", "role": "owner"}],
            webViewLink="https://drive.google.com/file/d/" + file_id,
            mimeType=mime if content is not None else "application/vnd.google-apps.folder",
        )
        if content is not None:
            result.update(
                size=str(len(content)),
                md5Checksum=hashlib.md5(content, usedforsecurity=False).hexdigest(),
            )
        self.objects[file_id] = result
        self.created.append(file_id)
        if content is not None and self.fail_after_file:
            self.fail_after_file = False
            raise DriveError("Timeout setelah upload diterima.")
        return {"id": file_id}


def upload_example(pid, aid, category="akta"):
    with transaction():
        return save_upload(
            FileStorage(stream=io.BytesIO(PDF), filename="contoh.pdf"), aid, pid, category
        )


def participant_example():
    with transaction():
        pid, aid, _ = paid_participant(account=True)
    return pid, aid


def test_separate_folders_and_preserve_all_file_versions(ctx):
    pid, aid = participant_example()
    first = upload_example(pid, aid)
    client = FakeDrive()
    result = sync_uploads(client)
    assert result["versi_berkas_terverifikasi"] == 1
    count = len(client.created)
    sync_uploads(client)
    assert len(client.created) == count
    old = one("SELECT * FROM drive_objects WHERE upload_id=?", (first,))
    second = upload_example(pid, aid)
    sync_uploads(client)
    new = one("SELECT * FROM drive_objects WHERE upload_id=?", (second,))
    assert new["parent_id"] == old["parent_id"] and new["drive_id"] != old["drive_id"]
    assert old["drive_id"] in client.objects
    assert one("SELECT COUNT(*) AS n FROM uploads")["n"] == 2
    with transaction():
        other, _, _ = paid_participant(level="MA")
    sync_uploads(client)
    folders = all_rows(
        "SELECT participant_id,drive_id FROM drive_objects WHERE item_key LIKE 'participant:%'"
    )
    assert len(folders) == 2 and len({r["drive_id"] for r in folders}) == 2


def test_retry_after_ambiguous_timeout_uses_reserved_id(ctx):
    pid, aid = participant_example()
    uid = upload_example(pid, aid)
    client = FakeDrive()
    client.fail_after_file = True
    with pytest.raises(DriveError, match="Timeout"):
        sync_uploads(client)
    pending = one("SELECT * FROM drive_objects WHERE upload_id=?", (uid,))
    assert pending["state"] == "pending" and pending["drive_id"] in client.objects
    created = len(client.created)
    sync_uploads(client)
    assert len(client.created) == created
    assert one("SELECT state FROM drive_objects WHERE upload_id=?", (uid,))["state"] == "ready"


@pytest.mark.parametrize("audience", ["anyone", "domain"])
def test_public_or_domain_folder_rejected(ctx, audience):
    pid, aid = participant_example()
    client = FakeDrive()
    sync_uploads(client)
    root = one("SELECT drive_id FROM drive_objects WHERE item_key LIKE 'year:%'")
    client.objects[root["drive_id"]]["permissions"].append({"type": audience, "role": "reader"})
    upload_example(pid, aid)
    created = len(client.created)
    with pytest.raises(DriveError, match="publik"):
        sync_uploads(client)
    assert len(client.created) == created


def test_payment_proof_is_not_copied(ctx):
    pid, aid = participant_example()
    upload_example(pid, aid, "bukti")
    result = sync_uploads(FakeDrive())
    assert result["versi_berkas_terverifikasi"] == 0
    assert not all_rows("SELECT * FROM drive_objects WHERE upload_id IS NOT NULL")


def test_rollback_upload_never_enters_drive_copy(ctx):
    pid, aid = participant_example()
    with pytest.raises(ValueError):
        with transaction():
            save_upload(FileStorage(stream=io.BytesIO(PDF), filename="contoh.pdf"), aid, pid, "kk")
            raise ValueError("rollback contoh")
    result = sync_uploads(FakeDrive())
    assert result["versi_berkas_terverifikasi"] == 0


def test_deleted_remote_version_not_recreated_silently(ctx):
    pid, aid = participant_example()
    uid = upload_example(pid, aid)
    client = FakeDrive()
    sync_uploads(client)
    file_id = one("SELECT drive_id FROM drive_objects WHERE upload_id=?", (uid,))["drive_id"]
    del client.objects[file_id]
    with pytest.raises(DriveError, match="tidak ditemukan"):
        sync_uploads(client)
    assert file_id not in client.objects


def test_tampered_local_file_fails_checksum(ctx):
    pid, aid = participant_example()
    uid = upload_example(pid, aid)
    client = FakeDrive()
    sync_uploads(client)
    from pathlib import Path

    row = one("SELECT storage_name FROM uploads WHERE id=?", (uid,))
    path = Path(ctx.config["UPLOAD_DIR"]) / row["storage_name"]
    original = path.read_bytes()
    path.write_bytes(b"X" + original[1:])
    with pytest.raises(DriveError, match="berubah"):
        sync_uploads(client)


def test_missing_permissions_and_moved_file_rejected():
    with pytest.raises(DriveError):
        private_metadata({"trashed": False})
    with pytest.raises(DriveError):
        private_metadata(
            {"permissions": [{"type": "user", "role": "owner"}], "parents": ["other"]},
            parent="expected",
        )
    with pytest.raises(DriveError):
        private_metadata({"permissions": []})

def test_trashed_old_file_does_not_block_new_versions(ctx):
    pid,aid=participant_example()
    first=upload_example(pid,aid)
    client=FakeDrive();sync_uploads(client)
    old=one('SELECT * FROM drive_objects WHERE upload_id=?',(first,))
    client.objects[old['drive_id']]['trashed']=True
    second=upload_example(pid,aid,'foto')
    result=sync_uploads(client)
    assert result['versi_di_sampah']==1
    assert one('SELECT state FROM drive_objects WHERE upload_id=?',(first,))['state']=='trashed'
    assert one('SELECT state FROM drive_objects WHERE upload_id=?',(second,))['state']=='ready'
    assert client.objects[old['drive_id']]['trashed'] is True
    client.objects[old['drive_id']]['trashed']=False
    sync_uploads(client)
    assert one('SELECT state FROM drive_objects WHERE upload_id=?',(first,))['state']=='ready'
