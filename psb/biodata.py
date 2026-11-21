"""Definisi kolom, pembagian halaman, dan pemeriksaan biodata santri."""

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

EDUCATION_OPTIONS = (
    "Tidak sekolah",
    "SD / MI",
    "SMP / MTs",
    "SMA / MA / SMK",
    "Diploma",
    "S1",
    "S2",
    "S3",
    "Lainnya",
)
BIO_GROUPS = {
    "santri": {
        "label": "Data Santri",
        "icon": "👤",
        "fields": (
            "number",
            "name",
            "nisn",
            "gender",
            "birth_place",
            "birth_date",
            "nik",
            "kk_number",
            "illness_history",
        ),
    },
    "orang-tua": {
        "label": "Data Orang Tua",
        "icon": "👪",
        "fields": (
            "father_name",
            "father_nik",
            "father_education",
            "father_job",
            "mother_name",
            "mother_nik",
            "mother_education",
            "mother_job",
        ),
    },
    "alamat-kontak": {
        "label": "Alamat & Kontak",
        "icon": "🏠",
        "fields": ("address", "postal_code", "phone", "email", "guardian"),
    },
    "sekolah": {
        "label": "Sekolah Asal",
        "icon": "🏫",
        "fields": ("school", "school_address", "school_npsn"),
    },
}
BIO_FIELDS = {
    "number": ("Nomor pendaftaran", "readonly", None),
    "name": ("Nama lengkap pendaftar", "text", None),
    "nisn": ("NISN", "digits", 10),
    "gender": ("Jenis kelamin", "gender", None),
    "birth_place": ("Tempat lahir", "text", None),
    "birth_date": ("Tanggal lahir", "date", None),
    "nik": ("NIK santri", "digits", 16),
    "kk_number": ("Nomor KK", "digits", 16),
    "illness_history": ("Riwayat penyakit anak", "textarea", None),
    "father_name": ("Nama ayah", "text", None),
    "father_nik": ("NIK ayah", "digits", 16),
    "father_education": ("Pendidikan terakhir ayah", "education", None),
    "father_job": ("Pekerjaan ayah", "text", None),
    "mother_name": ("Nama ibu", "text", None),
    "mother_nik": ("NIK ibu", "digits", 16),
    "mother_education": ("Pendidikan terakhir ibu", "education", None),
    "mother_job": ("Pekerjaan ibu", "text", None),
    "address": ("Alamat rumah", "textarea", None),
    "postal_code": ("Kode pos", "digits", 5),
    "phone": ("Nomor telepon / WhatsApp", "tel", None),
    "email": ("Email kontak (opsional)", "email", None),
    "guardian": ("Nama wali (jika berbeda dari orang tua)", "text", None),
    "school": ("Sekolah asal", "text", None),
    "school_address": ("Alamat sekolah asal", "textarea", None),
    "school_npsn": ("NPSN sekolah asal", "digits", 8),
}
PARENT_NOTES = ("father_unavailable", "father_note", "mother_unavailable", "mother_note")


def bio_values(p, stored):
    values = dict(stored)
    for key in ("number", "name", "birth_place", "birth_date"):
        values[key] = p[key]
    values.setdefault("phone", p["phone"])
    values.setdefault("email", p["email"])
    values.setdefault("father_name", stored.get("father", ""))
    values.setdefault("mother_name", stored.get("mother", ""))
    return values


def required_fields(values, level, group):
    required = set(BIO_GROUPS[group]["fields"]) - {"number", "email", "guardian"}
    if group == "santri" and level == "MI":
        required.discard("nisn")
    if (
        group == "sekolah"
        and level == "MI"
        and not any(str(values.get(key, "")).strip() for key in BIO_GROUPS[group]["fields"])
    ):
        required.clear()
    if group == "orang-tua":
        for parent in ("father", "mother"):
            if values.get(parent + "_unavailable") == "ya":
                required.difference_update(
                    key for key in BIO_GROUPS[group]["fields"] if key.startswith(parent + "_")
                )
                required.add(parent + "_note")
    if group == "alamat-kontak" and all(
        values.get(parent + "_unavailable") == "ya" for parent in ("father", "mother")
    ):
        required.add("guardian")
    return required


def bio_errors(values, level, group):
    errors = []
    for key in sorted(required_fields(values, level, group)):
        if not str(values.get(key, "")).strip():
            label = (
                BIO_FIELDS[key][0]
                if key in BIO_FIELDS
                else ("Keterangan data ayah" if key == "father_note" else "Keterangan data ibu")
            )
            errors.append(label + " perlu diisi.")
    for key in BIO_GROUPS[group]["fields"]:
        value = str(values.get(key, "")).strip()
        label, kind, length = BIO_FIELDS[key]
        if len(value) > 2000:
            errors.append(label + " terlalu panjang.")
        if value and kind == "digits" and not re.fullmatch(r"[0-9]{" + str(length) + "}", value):
            errors.append(f"{label} harus berisi {length} digit angka.")
        if value and kind == "education" and value not in EDUCATION_OPTIONS:
            errors.append(label + " tidak valid.")
    if group == "santri":
        if values.get("gender") not in ("Putra", "Putri"):
            errors.append("Pilih jenis kelamin.")
        try:
            born = date.fromisoformat(values.get("birth_date", ""))
            if not date(1980, 1, 1) < born <= datetime.now(ZoneInfo("Asia/Jakarta")).date():
                errors.append("Tanggal lahir tidak valid.")
        except ValueError:
            errors.append("Tanggal lahir tidak valid.")
    if group == "alamat-kontak":
        phone = re.sub(r"[\s+()-]", "", values.get("phone", ""))
        if not re.fullmatch(r"[0-9]{9,15}", phone):
            errors.append("Nomor telepon / WhatsApp harus berisi 9–15 digit.")
        email = values.get("email", "")
        if email and (len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)):
            errors.append("Alamat email kontak tidak valid.")
    return list(dict.fromkeys(errors))


def bio_group_status(values, level):
    return {key: not bio_errors(values, level, key) for key in BIO_GROUPS}
