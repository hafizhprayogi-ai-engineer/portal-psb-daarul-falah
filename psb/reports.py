import io
import json
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from .db import all_rows, one
from .domain import balance, documents_complete, waktu


def build_report(kind, filters):
    wb = Workbook()
    ws = wb.active
    ws.title = "Pendaftaran" if kind == "pendaftaran" else "Pembayaran"
    level = filters.get("level", "")
    start = filters.get("start", "")
    end = filters.get("end", "")
    status = filters.get("status", "")
    year = filters.get("year", "2027/2028")
    if kind == "pendaftaran":
        ws.append(
            [
                "Nomor pendaftaran",
                "Nama",
                "Jenjang",
                "Jenis kelamin",
                "Kanal",
                "Tanggal daftar",
                "Status akun",
                "Pembayaran awal",
                "Jadwal",
                "Kehadiran",
                "Hasil publikasi",
                "Status berkas",
                "Daftar ulang",
            ]
        )
        rows = all_rows(
            "SELECT p.*,a.reference,a.name,a.level,a.channel,a.created_at,a.status AS payment_status,s.date,u.active FROM applications a LEFT JOIN participants p ON a.id=p.application_id JOIN years y ON y.id=a.year_id LEFT JOIN schedules s ON s.id=p.schedule_id LEFT JOIN users u ON u.participant_id=p.id WHERE (?='' OR a.level=?) AND (?='' OR date(a.created_at,'+7 hours')>=?) AND (?='' OR date(a.created_at,'+7 hours')<=?) AND y.name=? AND (?='' OR p.published_result=?) ORDER BY a.id",
            (level, level, start, start, end, end, year, status, status),
        )
        for r in rows:
            ws.append(
                [
                    r["number"] or r["reference"],
                    r["name"],
                    r["level"],
                    json.loads(r["bio"] or "{}").get("gender", ""),
                    r["channel"],
                    waktu(r["created_at"]),
                    (
                        "Belum dibuat"
                        if r["active"] is None
                        else ("Aktif" if r["active"] else "Menunggu aktivasi")
                    ),
                    r["payment_status"],
                    r["date"],
                    r["attendance"] or "Belum dicatat",
                    r["published_result"] or "Menunggu hasil",
                    "Lengkap" if r["id"] and documents_complete(r["id"]) else "Belum lengkap",
                    "Selesai" if r["completed"] else "Belum selesai",
                ]
            )
    else:
        ws.append(
            [
                "Nomor / referensi",
                "Nama",
                "Jenjang",
                "Jenis tagihan",
                "Rincian tagihan",
                "Total tagihan",
                "Nominal transaksi",
                "Metode",
                "Tanggal",
                "Status verifikasi",
                "Petugas",
                "Total pembayaran sah",
                "Sisa tagihan",
                "Status lunas",
            ]
        )
        rows = all_rows(
            "SELECT t.*,a.name,a.level,a.reference,p.number,u.username FROM payments t JOIN applications a ON a.id=t.application_id JOIN years y ON y.id=a.year_id LEFT JOIN participants p ON p.id=t.participant_id LEFT JOIN users u ON u.id=t.confirmed_by WHERE (?='' OR a.level=?) AND (?='' OR date(t.created_at,'+7 hours')>=?) AND (?='' OR date(t.created_at,'+7 hours')<=?) AND (?='' OR t.status=?) AND y.name=? ORDER BY t.id",
            (level, level, start, start, end, end, status, status, year),
        )
        for r in rows:
            if r["kind"] == "pendaftaran":
                paid = one(
                    "SELECT COALESCE(SUM(amount),0) AS n FROM payments WHERE application_id=? AND kind='pendaftaran' AND status='Disahkan'",
                    (r["application_id"],),
                )["n"]
                total = 200000
                remaining = total - paid
                components = "Pendaftaran: 200000"
            else:
                b = balance(r["participant_id"])
                paid = b["paid"]
                remaining = b["remaining"]
                total = b["invoice"]["total"]
                components = "; ".join(
                    f"{x['name']}: {x['amount']}" for x in json.loads(b["invoice"]["components"])
                )
            ws.append(
                [
                    r["number"] or r["reference"],
                    r["name"],
                    r["level"],
                    "Pendaftaran" if r["kind"] == "pendaftaran" else "Daftar ulang",
                    components,
                    total,
                    r["amount"],
                    r["method"],
                    waktu(r["created_at"]),
                    r["status"],
                    r["username"],
                    paid,
                    remaining,
                    "Lunas" if remaining == 0 else "Belum lunas",
                ]
            )
    for row in ws:
        for cell in row:
            # Teks dari pengguna tidak pernah menjadi formula Excel.
            if isinstance(cell.value, str):
                cell.data_type = "s"
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="145C46")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = min(
            45, max(18, max(len(str(c.value or "")) for c in col[:100]) + 2)
        )
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return out
