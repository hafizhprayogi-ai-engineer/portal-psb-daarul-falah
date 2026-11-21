# Deployment dan pemeliharaan

## Bentuk deployment

Gunakan satu server dengan disk lokal persisten untuk SQLite dan unggahan. Jalankan Waitress di belakang reverse proxy HTTPS. Semua proses aplikasi pada server menggunakan database yang sama. SQLite WAL mengizinkan pembaca bersamaan dan menserialkan penulis. Uji beban dengan jumlah petugas/pendaftar yang diharapkan sebelum peluncuran.

Jika dibutuhkan beberapa server aplikasi yang menulis bersamaan, migrasikan database ke PostgreSQL serta unggahan ke penyimpanan objek privat. SQLite WAL memerlukan disk lokal yang mendukung penguncian file dengan benar.

## Instalasi produksi

1. Salin kode aplikasi tanpa `.env`, `.venv`, `instance`, `backups`, dan data demo.
2. Buat virtual environment dan pasang `requirements.lock.txt` untuk versi yang diuji.
3. Buat direktori data privat yang dapat ditulis oleh akun layanan.
4. Isi variabel lingkungan di bawah.
5. Jalankan `python manage.py init` dan `python manage.py admin`.
6. Jalankan `python run.py` sebagai layanan dengan restart otomatis.
7. Pasang reverse proxy pada port 443 menuju 127.0.0.1:5000.
8. Atur data lembaga melalui akun Admin Utama.
9. Jalankan uji penerimaan menggunakan akun dan transaksi fiktif pada lingkungan staging.

```dotenv
APP_ENV=production
SECRET_KEY=<rahasia acak setidaknya 32 byte>
BASE_URL=https://alamat-portal-lembaga
DATA_DIR=/srv/psb-data
COOKIE_SECURE=true
NOTIFICATION_MODE=simulation
PORT=5000
```

Aktifkan notifikasi setelah konfigurasi dan uji penyedia selesai. Ikuti integrasi-n8n.md untuk variabel tambahan. Gunakan rahasia yang berbeda bagi cookie, webhook masuk n8n, dan endpoint integrasi aplikasi.

## Reverse proxy

Berikut contoh bagian lokasi Nginx. Konfigurasi sertifikat dan nama server mengikuti domain yang digunakan lembaga.

```nginx
location / {
    proxy_pass http://127.0.0.1:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header X-Forwarded-For $remote_addr;
    client_max_body_size 6m;
    proxy_read_timeout 60s;
}
```

Aplikasi menggunakan `BASE_URL` untuk tautan resmi dan QR. Tanpa konfigurasi proxy tepercaya, pembatasan IP melihat alamat reverse proxy. Atur `TRUST_PROXY=true` hanya ketika aplikasi sepenuhnya berada di belakang satu proxy tepercaya yang menimpa header forwarded dan port aplikasi hanya dapat dijangkau proxy tersebut. Pada lingkungan lokal, biarkan false.

Batasi izin baca/tulis direktori data pada akun layanan dan administrator pencadangan. Jangan petakan `instance/private` sebagai direktori web publik. Endpoint `/health` dapat digunakan untuk pemeriksaan layanan.

## Penjadwal

Jalankan `manage.py worker` setiap menit dan `manage.py reminders` setiap jam. Pengingat memakai tanggal Asia/Jakarta dan tetap idempoten jika perintah dijalankan lebih dari sekali. Windows Task Scheduler dapat menggunakan executable `.venv\Scripts\python.exe`, argumen `manage.py worker` atau `manage.py reminders`, serta Start in pada direktori proyek. Akun penjadwal harus memiliki akses ke variabel lingkungan dan direktori data yang sama.

Pada Linux, contoh cron berikut mengasumsikan proyek di `/srv/psb` dan timezone cron Asia/Jakarta.

```cron
CRON_TZ=Asia/Jakarta
* * * * * cd /srv/psb && .venv/bin/python manage.py worker
5 * * * * cd /srv/psb && .venv/bin/python manage.py reminders
```

Perintah worker sekali jalan. Pengambilan kejadian dilindungi transaksi sehingga dua worker tidak mengambil baris yang sama. Pantau status gagal, diproses terlalu lama, dan jumlah percobaan pada halaman Aktivitas.

## Pencadangan

```powershell
.\.venv\Scripts\python.exe manage.py backup --output backups
```

Perintah membuat subdirektori bertanggal berisi `psb.sqlite3` menggunakan SQLite backup API serta salinan `private/`. Penulis database ditahan selama snapshot dibuat agar metadata dan berkas konsisten. Salin cadangan ke penyimpanan terenkripsi terpisah dan tetapkan retensi menurut kebijakan lembaga.

Simpan rahasia aplikasi dan konfigurasi penyedia melalui pengelola rahasia terpisah. Berkas backup aplikasi tidak memuat `.env`. Data cadangan mengandung identitas peserta dan tautan akun, sehingga akses mengikuti kewenangan administrator.

## Pemulihan tanpa menimpa data aktif

1. Hentikan aplikasi dan worker atau gunakan lingkungan pemulihan terisolasi.
2. Buat direktori data baru, misalnya `instance-restored`.
3. Salin database cadangan ke `instance-restored/psb.sqlite3` dan folder `private` ke dalam direktori yang sama.
4. Ubah `DATA_DIR` ke direktori hasil pemulihan dan gunakan `NOTIFICATION_MODE=simulation` selama pemeriksaan.
5. Jalankan `manage.py init` agar migrasi yang diperlukan diterapkan.
6. Periksa `PRAGMA integrity_check`, login, unduhan privat, total pembayaran, dan verifikasi QR.
7. Periksa status outbox terhadap log penyedia sebelum mengaktifkan worker nyata. Cadangan lama dapat memuat kejadian yang sudah dikirim sesudah waktu snapshot.
8. Alihkan layanan setelah pemeriksaan pemulihan selesai.

## Dokumen dan koreksi

Versi dokumen menyimpan snapshot saat diterbitkan. Koreksi menonaktifkan versi terkait dan menerbitkan versi baru. PDF yang sudah dimiliki wali tetap dapat dibaca, sedangkan QR menunjukkan keabsahan terkini.

Untuk kekurangan setelah dua transaksi daftar ulang, Bendahara membuka transaksi terdahulu dan mencatat koreksi nominal dengan alasan yang memuat dasar pemeriksaan serta penerimaan selisih jika ada. Audit menyimpan nominal sebelumnya, nominal terbaru, petugas, dan waktu. Ini merupakan alur rekonsiliasi khusus setelah koreksi. Ketentuan dua pembayaran umum tetap diperiksa pada pengajuan baru.

Koreksi hasil menjadi Tidak lulus menandai peserta yang sudah membayar untuk penanganan petugas. Keputusan pengembalian dana mengikuti kebijakan lembaga yang belum ditentukan.

## Verifikasi sebelum dipakai lembaga

Pengujian otomatis tersedia untuk aturan bisnis dan alur HTTP. Pemeriksaan visual desktop/ponsel, pencetakan dokumen, izin kamera pada perangkat petugas, impor workflow n8n, dan pengiriman nyata masih harus diuji pada lingkungan staging yang menyediakan layanan tersebut.

Dasar pengamanan aplikasi mengikuti pemeriksaan CSRF, escaping template, batas unggahan, cookie sesi, serta header respons yang dijelaskan dokumentasi Flask. [Security Considerations Flask](https://flask.palletsprojects.com/en/stable/web-security/)
