"""Salinan Drive privat. ID dicadangkan di DB sebelum API create agar retry idempoten."""

import hashlib
import json
from pathlib import Path

from flask import current_app
from .db import one, all_rows, execute, transaction, now
from .domain import DOC_LABELS
from .sheets_sync import credentials_for

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class DriveError(RuntimeError):
    pass


def drive_credentials(data_dir, login=False):
    return credentials_for(
        data_dir, login=login, scopes=DRIVE_SCOPES, token_filename="google-drive-token.json"
    )


def private_metadata(metadata, parent=None):
    if metadata.get("trashed"):
        raise DriveError(
            "Folder/file Drive berada di sampah. Pulihkan; salinan lama tidak akan diganti diam-diam."
        )
    if any(p.get("type") in ("anyone", "domain") for p in metadata.get("permissions", [])):
        raise DriveError(
            "Folder/file Drive dibagikan publik atau ke seluruh domain. Batasi akses dahulu."
        )
    if not metadata.get("permissions"):
        raise DriveError("Izin file Drive tidak dapat diverifikasi.")
    if parent and parent not in metadata.get("parents", []):
        raise DriveError(
            "Folder/file Drive dipindahkan dari lokasi yang dicatat. Periksa sebelum melanjutkan."
        )
    return metadata


class DriveClient:
    def __init__(self, credentials):
        from google.auth.transport.requests import AuthorizedSession

        self.session = AuthorizedSession(credentials)

    def request(self, method, suffix, upload=False, allow_missing=False, **kwargs):
        base = (
            "https://www.googleapis.com/upload/drive/v3/"
            if upload
            else "https://www.googleapis.com/drive/v3/"
        )
        response = self.session.request(method, base + suffix, timeout=60, **kwargs)
        if response.status_code == 404 and allow_missing:
            return None
        if not response.ok:
            raise DriveError(
                f"Drive belum berhasil (HTTP {response.status_code}). Periksa izin, Drive API, kuota dan internet."
            )
        return response.json()

    def generate_id(self):
        return self.request(
            "GET", "files/generateIds", params={"count": 1, "space": "drive", "type": "files"}
        )["ids"][0]

    def metadata(self, file_id):
        return self.request(
            "GET",
            "files/" + file_id,
            allow_missing=True,
            params={
                "fields": "id,name,mimeType,trashed,parents,permissions(type,role),md5Checksum,size,webViewLink,appProperties"
            },
        )

    def create(self, file_id, name, parent=None, content=None, mime=None):
        metadata = {"id": file_id, "name": name}
        if parent:
            metadata["parents"] = [parent]
        if content is None:
            metadata["mimeType"] = "application/vnd.google-apps.folder"
            return self.request("POST", "files", json=metadata, params={"fields": "id"})
        import secrets

        boundary = "psb_" + secrets.token_hex(16)
        body = (
            f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
            + json.dumps(metadata).encode()
            + f"\r\n--{boundary}\r\nContent-Type: {mime}\r\n\r\n".encode()
            + content
            + f"\r\n--{boundary}--\r\n".encode()
        )
        return self.request(
            "POST",
            "files",
            upload=True,
            params={"uploadType": "multipart", "fields": "id"},
            headers={"Content-Type": f"multipart/related; boundary={boundary}"},
            data=body,
        )

    def close(self):
        self.session.close()


def reserve(client, key, parent=None, pid=None, upload_id=None, checksum=None):
    existing = one("SELECT * FROM drive_objects WHERE item_key=?", (key,))
    if existing:
        if checksum and existing["checksum"] != checksum:
            raise DriveError(
                "File privat sumber berubah setelah versi dicatat. Buat unggahan versi baru."
            )
        return dict(existing)
    generated = client.generate_id()
    with transaction():
        existing = one("SELECT * FROM drive_objects WHERE item_key=?", (key,))
        if not existing:
            execute(
                "INSERT INTO drive_objects(item_key,drive_id,parent_id,participant_id,upload_id,checksum,updated_at) VALUES(?,?,?,?,?,?,?)",
                (key, generated, parent, pid, upload_id, checksum, now()),
            )
        return dict(one("SELECT * FROM drive_objects WHERE item_key=?", (key,)))


def complete(item, metadata):
    url = metadata.get("webViewLink", "")
    if url and not url.startswith("https://drive.google.com/"):
        raise DriveError("Alamat Drive tidak sesuai.")
    with transaction():
        execute(
            "UPDATE drive_objects SET state='ready',web_url=?,updated_at=? WHERE item_key=?",
            (url, now(), item["item_key"]),
        )


def ensure_folder(client, key, name, parent=None, pid=None):
    item = reserve(client, key, parent=parent, pid=pid)
    metadata = client.metadata(item["drive_id"])
    if metadata is None:
        if item["state"] in ("ready", "trashed"):
            raise DriveError(
                "Folder Drive tidak ditemukan. Pulihkan folder lama sebelum sinkronisasi."
            )
        client.create(item["drive_id"], name, parent=parent)
        metadata = client.metadata(item["drive_id"])
    private_metadata(metadata, parent=parent)
    if metadata["mimeType"] != "application/vnd.google-apps.folder":
        raise DriveError("Lokasi Drive bukan folder.")
    complete(item, metadata)
    return item["drive_id"]


def participant_folder(client, p):
    year = ensure_folder(
        client, f"year:{p['year_id']}", f"Berkas PSB {p['year_name'].replace('/','-')}"
    )
    level = ensure_folder(client, f"level:{p['year_id']}:{p['level']}", p["level"], parent=year)
    return ensure_folder(
        client, f"participant:{p['id']}", f"{p['number']} - {p['name']}", parent=level, pid=p["id"]
    )


def sync_uploads(client):
    participants = all_rows(
        "SELECT p.id,p.number,a.name,a.level,a.year_id,y.name AS year_name FROM participants p "
        "JOIN applications a ON a.id=p.application_id JOIN years y ON y.id=a.year_id ORDER BY p.id"
    )
    count = 0
    trashed = 0
    root_path = Path(current_app.config["UPLOAD_DIR"]).resolve()
    for p in participants:
        folder = participant_folder(client, p)
        uploads = all_rows("SELECT * FROM uploads WHERE participant_id=? ORDER BY id", (p["id"],))
        for upload in uploads:
            if upload["category"] not in DOC_LABELS:
                continue
            path = (root_path / upload["storage_name"]).resolve()
            if not path.is_relative_to(root_path) or not path.is_file():
                raise DriveError("File privat sumber tidak ditemukan atau lokasi tidak sesuai.")
            content = path.read_bytes()
            if len(content) != upload["size"] or len(content) > 5 * 1024 * 1024:
                raise DriveError("Ukuran salinan sumber tidak sesuai metadata unggahan.")
            sha = hashlib.sha256(content).hexdigest()
            item = reserve(
                client,
                f"upload:{upload['id']}",
                parent=folder,
                pid=p["id"],
                upload_id=upload["id"],
                checksum=sha,
            )
            metadata = client.metadata(item["drive_id"])
            if metadata is None:
                if item["state"] == "ready":
                    raise DriveError(
                        "Versi berkas Drive tidak ditemukan. Pulihkan dari sampah; versi tidak dihapus otomatis."
                    )
                filename = f"{upload['category']} - versi-{upload['id']}{path.suffix.lower()}"
                client.create(
                    item["drive_id"], filename, parent=folder, content=content, mime=upload["mime"]
                )
                metadata = client.metadata(item["drive_id"])
            if metadata and metadata.get("trashed"):
                # Jangan pulihkan file yang mungkin sengaja dibuang operator.
                # Folder dan pemeriksaan izin tetap wajib; hanya versi ini ditunda.
                with transaction():
                    execute("UPDATE drive_objects SET state='trashed',updated_at=? WHERE item_key=?", (now(), item["item_key"]))
                trashed += 1
                continue
            private_metadata(metadata, parent=folder)
            md5 = hashlib.md5(content, usedforsecurity=False).hexdigest()
            if metadata.get("md5Checksum") != md5 or int(metadata.get("size", -1)) != len(content):
                raise DriveError(
                    "Verifikasi isi/ukuran file Drive belum cocok. Salinan tidak ditandai selesai."
                )
            complete(item, metadata)
            count += 1
    return {"folder_santri": len(participants), "versi_berkas_terverifikasi": count, "versi_di_sampah": trashed}
