"""Menu dan progres antarmuka berdasarkan izin dan status peserta."""

from flask import g, request
from .security import has_role
from .biodata import BIO_GROUPS

PARTICIPANT_MENUS = (
    ("biodata", "Biodata", "👤", "Identitas santri dan orang tua"),
    ("jadwal", "Tes & kartu", "🗓️", "Tanggal tes, formulir, dan kartu peserta"),
    ("hasil", "Hasil seleksi", "📋", "Pengumuman dan tindak lanjut seleksi"),
    ("berkas", "Berkas", "📁", "Unggah dan periksa dokumen daftar ulang"),
    ("pembayaran", "Pembayaran", "💳", "Tagihan, pembayaran, dan riwayat"),
    ("dokumen", "Dokumen", "📄", "Unduh surat dan bukti resmi"),
    ("notifikasi", "Pemberitahuan", "🔔", "Informasi terbaru untuk peserta"),
    ("bantuan", "Bantuan", "💬", "Panduan dan kontak panitia"),
)
SECTION_TITLES = {key: label for key, label, _, _ in PARTICIPANT_MENUS}
SECTION_TITLES["absensi"] = "Absensi tes"
SECTION_TITLES["progres"] = "Progres penerimaan"


def participant_menus(pid):
    return [
        dict(
            key=key,
            label=label,
            icon=icon,
            description=description,
            url=f"/peserta/{pid}/menu/{key}",
        )
        for key, label, icon, description in PARTICIPANT_MENUS
    ]


def staff_menus():
    items = []

    def add(key, label, icon, url, description):
        items.append(dict(key=key, label=label, icon=icon, url=url, description=description))

    if has_role("pemberkasan", "admin"):
        add("peserta", "Data santri", "👥", "/peserta", "Cari peserta dan buka layanan per peserta")
        add(
            "biodata",
            "Biodata santri",
            "👤",
            "/layanan/biodata",
            "Buka identitas dan data keluarga peserta",
        )
        add(
            "berkas",
            "Verifikasi berkas",
            "📁",
            "/layanan/berkas",
            "Pemeriksaan dokumen daftar ulang",
        )
        add(
            "hasil",
            "Hasil seleksi",
            "📋",
            "/layanan/hasil",
            "Tinjau dan umumkan hasil sesuai peran",
        )
        add(
            "dokumen",
            "Dokumen peserta",
            "📄",
            "/layanan/dokumen",
            "Surat dan dokumen milik peserta",
        )
        add("jadwal", "Jadwal tes", "🗓️", "/jadwal", "Tanggal dan pelaksanaan tes")
    if has_role("pemberkasan"):
        add("absensi", "Absensi QR", "📷", "/pemindai", "Pindai kartu dan konfirmasi kehadiran")
    if has_role("bendahara", "admin"):
        add("keuangan", "Keuangan", "💳", "/keuangan", "Pantau transaksi dan bukti pembayaran")
    if has_role("bendahara"):
        add(
            "awal",
            "Pendaftaran tunai",
            "🧾",
            "/keuangan/pendaftaran",
            "Catat peserta dan pembayaran awal",
        )
        add(
            "transfer",
            "Verifikasi transfer",
            "✅",
            "/keuangan/verifikasi",
            "Periksa bukti pembayaran masuk",
        )
        add(
            "ulang",
            "Tunai daftar ulang",
            "💵",
            "/keuangan/daftar-ulang",
            "Catat penerimaan daftar ulang",
        )
    if has_role("pemberkasan", "bendahara", "admin"):
        add("laporan", "Laporan", "📊", "/laporan", "Unduh laporan sesuai kewenangan")
    if has_role("admin"):
        add("petugas", "Akun petugas", "👤", "/pengaturan/petugas", "Kelola petugas dan peran")
        add(
            "biaya",
            "Biaya & tagihan",
            "🧮",
            "/pengaturan/biaya",
            "Tetapkan rincian biaya per jenjang",
        )
        add("pengaturan", "Pengaturan", "⚙️", "/pengaturan", "Periode, rekening, dan template")
        add("aktivitas", "Riwayat aktivitas", "🕘", "/aktivitas", "Audit dan antrean pemberitahuan")
    add(
        "pekerjaan",
        "Perlu ditindaklanjuti",
        "🔔",
        "/pekerjaan",
        "Lihat pekerjaan yang menunggu petugas",
    )
    add("bantuan", "Bantuan", "💬", "/bantuan", "Panduan menggunakan portal")
    return items


def portal_context():
    user = getattr(g, "user", None)
    if not user:
        return {}
    owner = user["participant_id"]
    items = participant_menus(owner) if owner else staff_menus()
    pid = owner or (request.view_args or {}).get("pid")
    for item in items:
        if item["key"] == "biodata":
            item["url"] = f"/peserta/{pid}/menu/biodata" if pid else "/layanan/biodata"
            item["children"] = [
                dict(label=group["label"], url=item["url"] + "/" + key)
                for key, group in BIO_GROUPS.items()
            ]
    return {
        "app_shell": request.endpoint
        not in (
            "home",
            "login",
            "register",
            "recovery",
            "consume_token",
            "online",
            "tracking",
            "verify",
            "tracking_receipt",
        ),
        "app_menus": items,
        "app_alert_url": f"/peserta/{owner}/menu/notifikasi" if owner else "/pekerjaan",
        "app_role": (
            "Wali / peserta"
            if owner
            else "Ketua PSB"
            if all(has_role(role) for role in ("admin", "bendahara", "pemberkasan"))
            else " · ".join(
                label
                for role, label in [
                    ("admin", "Admin Utama"),
                    ("pemberkasan", "Pemberkasan"),
                    ("bendahara", "Bendahara"),
                ]
                if has_role(role)
            )
        ),
    }


def admission_progress(p, documents_ready, payment_balance=None):
    if payment_balance is None:
        from .domain import balance
        payment_balance = balance(p["id"])
    payment_complete = payment_balance["invoice"] is not None and payment_balance["remaining"] == 0
    passed = p["published_result"] == "Lulus"
    steps = [
        dict(label="Pembayaran awal", done=True, section="pembayaran"),
        dict(label="Biodata lengkap", done=bool(p["bio_complete"]), section="biodata"),
        dict(
            label="Tes & kartu peserta",
            done=bool(p["schedule_id"] and p["locked_at"]),
            section="jadwal",
        ),
        dict(label="Lulus seleksi", done=passed, section="hasil"),
        dict(label="Berkas diterima", done=bool(passed and documents_ready), section="berkas"),
        dict(label="Pembayaran daftar ulang lunas", done=payment_complete, section="pembayaran"),
    ]
    count = sum(step["done"] for step in steps)
    next_section = next((step["section"] for step in steps if not step["done"]), "dokumen")
    if p["published_result"] == "Tidak lulus":
        next_section = "hasil"
    elif passed and documents_ready and not p["completed"]:
        next_section = "pembayaran"
    return dict(
        steps=steps,
        count=count,
        total=6,
        percent=round(count / 6 * 100),
        next_section=next_section,
        next_url=f'/peserta/{p["id"]}/menu/{next_section}',
    )
