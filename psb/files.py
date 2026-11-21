import io
import json
import secrets
from pathlib import Path
from xml.sax.saxutils import escape
import qrcode
from PIL import Image as PILImage, ImageOps
from flask import current_app, g
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from docx import Document
from .db import execute, now
from .domain import require, rupiah, tanggal, service_hours
from .biodata import BIO_GROUPS, BIO_FIELDS


def save_upload(file, app_id=None, pid=None, category="bukti", replaces=None, reason=""):
    require(file and file.filename, "Pilih berkas untuk diunggah.")
    data = file.read(5 * 1024 * 1024 + 1)
    require(0 < len(data) <= 5 * 1024 * 1024, "Ukuran berkas maksimal 5 MB.")
    ext = Path(file.filename).suffix.lower()
    if ext == ".pdf":
        require(
            data.startswith(b"%PDF-") and b"%%EOF" in data[-2048:],
            "Isi berkas bukan PDF yang valid.",
        )
        mime = "application/pdf"
    else:
        require(ext in (".jpg", ".jpeg", ".png"), "Gunakan PDF, JPG, atau PNG.")
        try:
            img = PILImage.open(io.BytesIO(data))
            require(
                img.format in ("JPEG", "PNG") and img.width * img.height <= 25000000,
                "Gambar terlalu besar atau tidak valid.",
            )
            img.verify()
            # Tulis ulang gambar untuk membuang metadata dan isi tambahan.
            img = ImageOps.exif_transpose(PILImage.open(io.BytesIO(data))).convert("RGB")
            clean = io.BytesIO()
            img.save(clean, format="JPEG", quality=90)
            data = clean.getvalue()
            ext = ".jpg"
            mime = "image/jpeg"
        except (OSError, ValueError, PILImage.DecompressionBombError):
            require(False, "Gambar tidak dapat dibaca.")
    require(len(data) <= 5 * 1024 * 1024, "Ukuran gambar setelah diproses melebihi 5 MB. Gunakan foto lebih kecil.")
    name = secrets.token_hex(24) + ext
    path = Path(current_app.config["UPLOAD_DIR"]) / name
    path.write_bytes(data)
    if hasattr(g, "pending_uploads"):
        g.pending_uploads.append(name)
    return execute(
        "INSERT INTO uploads(application_id,participant_id,category,filename,storage_name,mime,size,replaces,reason,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            app_id,
            pid,
            category,
            Path(file.filename).name[:160],
            name,
            mime,
            len(data),
            replaces,
            reason,
            now(),
        ),
    ).lastrowid


def document_lines(doc):
    s = json.loads(doc["snapshot"])
    titles = {
        "kartu": "KARTU PESERTA TES",
        "formulir": "FORMULIR PENDAFTARAN",
        "kelulusan": "SURAT KELULUSAN",
        "kuitansi": "BUKTI PEMBAYARAN",
        "daftar_ulang": "BUKTI DAFTAR ULANG",
    }
    lines = [
        ("Tahun ajaran", s["year"]),
        ("Nama peserta", s["name"]),
        ("Nomor pendaftaran", s["number"]),
        ("Jenjang", s["level"]),
        ("Identitas dokumen", f"DF2-{doc['id']:06d} / versi {doc['version']}"),
        ("Tanggal terbit", tanggal(doc["created_at"])),
    ]
    if not doc["id"]:
        lines = [line for line in lines if line[0] not in ("Identitas dokumen", "Tanggal terbit")]
    if doc["kind"] == "kartu":
        sched = s["schedule"]
        lines += [
            ("Tanggal tes", tanggal(sched["date"])),
            ("Jam pelayanan", service_hours(sched["date"])),
            ("Lokasi", "Pondok Pesantren Daarul Falah 2 Maliku"),
            (
                "Jenis tes",
                (
                    "Membaca; Menulis"
                    if s["level"] == "MI"
                    else "Membaca Al-Qur’an; Tes tertulis; Wawancara"
                ),
            ),
            (
                "Petunjuk",
                "Bawa kartu ini. Datang kapan saja dalam jam pelayanan pada tanggal terpilih.",
            ),
        ]
    elif doc["kind"] == "formulir":
        bio = json.loads(s["bio"])
        lines += [("Tempat, tanggal lahir", s["birth_place"] + ", " + tanggal(s["birth_date"]))]
        labels = {
            "gender": "Jenis kelamin",
            "address": "Alamat",
            "school": "Asal sekolah",
            "father": "Data ayah",
            "mother": "Data ibu",
            "guardian": "Data wali",
            "phone": "WhatsApp orang tua",
        }
        if bio.get("schema_version") == 2:
            for group in BIO_GROUPS.values():
                lines.append((group["label"], ""))
                for key in group["fields"]:
                    if key not in ("number", "name", "birth_place", "birth_date"):
                        lines.append((BIO_FIELDS[key][0], bio.get(key) or "Belum diisi"))
            for parent, label in [("father", "ayah"), ("mother", "ibu")]:
                if bio.get(parent + "_note"):
                    lines.append(("Keterangan data " + label, bio[parent + "_note"]))
        else:
            lines += [
                (labels[k], v or "Belum pernah sekolah") for k, v in bio.items() if k in labels
            ]
        lines += [
            (
                "Pernyataan",
                s["template"]
                or "Saya menyatakan data di atas benar. Formulir ini harus ditandatangani wali.",
            ),
            ("Tanda tangan wali", "_________________________"),
        ]
    elif doc["kind"] == "kelulusan":
        lines += [
            ("Keputusan", "Lulus"),
            (
                "Isi surat",
                s["template"]
                or "Peserta dinyatakan lulus seleksi. Lengkapi pemberkasan dan pembayaran daftar ulang melalui portal.",
            ),
            (
                "Nomor surat",
                s["letter_number"]
                .replace("{nomor}", s["number"])
                .replace("{versi}", str(doc["version"]))
                or "Belum ditentukan",
            ),
            ("Penandatangan", s["signer"] or "Belum tersedia"),
        ]
    elif doc["kind"] == "kuitansi":
        pay = s["payment"]
        initial = pay["kind"] == "pendaftaran"
        lines += [
            ("Jenis pembayaran", "Pendaftaran" if initial else "Daftar ulang"),
            ("Metode", pay["method"].title()),
            ("Tanggal transaksi", tanggal(pay["confirmed_at"] or pay["created_at"])),
            ("Nominal transaksi", rupiah(pay["amount"])),
        ]
        if pay.get("receiver_name"):
            lines.append(("Diterima oleh", pay["receiver_name"]))
        if initial:
            lines += [
                ("Rincian", "Pendaftaran: Rp200.000"),
                ("Total pembayaran sah", "Rp200.000"),
                ("Sisa tagihan", "Rp0"),
                ("Status", "Lunas"),
            ]
        else:
            lines += [
                (c["name"], rupiah(c["amount"])) for c in json.loads(s["invoice"]["components"])
            ]
            lines += [
                ("Total tagihan", rupiah(s["invoice"]["total"])),
                ("Total pembayaran sah", rupiah(s["paid"])),
                ("Sisa tagihan", rupiah(s["remaining"])),
                ("Status", "Lunas" if s["remaining"] == 0 else "Belum lunas"),
            ]
    else:
        lines += [
            ("Status", "Daftar ulang selesai"),
            (
                "Keterangan",
                "Persyaratan berkas diterima dan pembayaran lunas. Keabsahan terkini tersedia melalui QR.",
            ),
        ]
    return s, titles[doc["kind"]], lines


def render_document(doc, word=False):
    s, title, lines = document_lines(doc)
    qr_url = current_app.config["BASE_URL"] + (
        "/absensi/" + doc["token"] if doc["kind"] == "kartu" else "/verifikasi/" + doc["token"]
    )
    qr = io.BytesIO()
    qrcode.make(qr_url).save(qr, format="PNG")
    qr.seek(0)
    out = io.BytesIO()
    draft = s["draft"] and doc["kind"] in ("formulir", "kelulusan")
    if word:
        d = Document()
        d.add_heading("Pondok Pesantren Daarul Falah 2 Maliku", 0)
        d.add_heading(("DRAF — " if draft else "") + title, 1)
        if not doc["valid"]:
            d.add_paragraph("TIDAK BERLAKU")
        for label, value in lines:
            d.add_paragraph(f"{label}: {value}")
        d.add_picture(qr, width=__import__("docx").shared.Inches(1.3))
        d.add_paragraph(qr_url)
        d.save(out)
    else:
        styles = getSampleStyleSheet()
        styles["Normal"].fontSize = 10
        styles["Normal"].leading = 15
        content = [
            Paragraph("PONDOK PESANTREN", styles["Heading2"]),
            Paragraph("Daarul Falah 2 Maliku", styles["Title"]),
        ]
        if s.get("letterhead"):
            content.append(Paragraph(escape(s["letterhead"]), styles["Normal"]))
        content += [
            Spacer(1, 0.5 * cm),
            Paragraph(("DRAF — " if draft else "") + title, styles["Heading1"]),
        ]
        if not doc["valid"]:
            content.append(Paragraph("TIDAK BERLAKU", styles["Heading1"]))
        rows = [
            [
                Paragraph(escape(str(k)), styles["Normal"]),
                Paragraph(escape(str(v)).replace("\n", "<br/>"), styles["Normal"]),
            ]
            for k, v in lines
        ]
        table = Table(rows, colWidths=[5 * cm, 11 * cm], hAlign="LEFT", splitInRow=1)
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#d8e5df")),
                ]
            )
        )
        content += [table, Spacer(1, 0.5 * cm)]
        if doc["id"]:
            content += [
                Image(qr, 3.4 * cm, 3.4 * cm),
                Paragraph(
                    (
                        "Pindai QR untuk halaman petugas."
                        if doc["kind"] == "kartu"
                        else "Pindai QR untuk memeriksa status keabsahan terbaru."
                    ),
                    styles["Normal"],
                ),
            ]
        SimpleDocTemplate(
            out,
            title=title,
            author="Portal PSB Daarul Falah 2 Maliku",
            rightMargin=2 * cm,
            leftMargin=2 * cm,
        ).build(content)
    out.seek(0)
    return out
