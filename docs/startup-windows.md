# Portal dan Sheets otomatis saat login Windows

Tugas Windows **PSB Daarul Falah - Portal dan Sheets** menjalankan peluncur `scripts/startup_portal.py` sekitar 20 detik setelah pengguna Windows masuk. Tugas berjalan pada sesi pengguna dengan izin biasa, tanpa menyimpan password Windows. Ini pemicu login, bukan layanan sebelum layar login.

Database operasional saat pemeriksaan memakai layanan Windows **MySQL80**, yang sudah berstatus Automatic. Peluncur menunggu koneksi database siap maksimal 10 menit. Tidak ada perubahan konfigurasi Laragon atau layanan database lain. Jika kelak DATABASE_URL dipindahkan ke MySQL Laragon yang berbeda, pastikan layanan tujuan tersebut juga menyala ketika Windows masuk.

Peluncur membaca .env terbaru, menjalankan server, worker Sheets, dan worker notifikasi dengan jendela tersembunyi, serta membiarkan proses proyek yang sudah berjalan. Proses Python launcher/anak Windows dapat terlihat sebagai dua PID untuk satu layanan; itu bukan dua server/worker. File lock peluncur dan worker mencegah peluncuran ganda. Port yang dipakai proses lain tidak direbut atau dimatikan.

Worker Sheets berjalan tiap 60 detik dan worker notifikasi tiap 30 detik. Gangguan internet saat memakai token tersimpan dicoba kembali; token dicabut/kedaluwarsa dapat memerlukan login manual. Tidak ada browser login yang dibuka otomatis saat Windows masuk. Task memiliki tiga percobaan ulang saat peluncur gagal, jeda dua menit, tidak dibatasi tiga hari, dan tetap diizinkan saat laptop memakai baterai. Ini peluncuran saat login, bukan watchdog yang langsung menyalakan server setiap kali operator sengaja menghentikannya.

## Pemakaian harian

Setelah masuk Windows, tunggu sekitar 20-60 detik, lalu buka `http://127.0.0.1:5000/login` (atau port .env). Alamat HP terdeteksi saat server dimulai dan dicatat di `instance/server.stdout.log`; HP harus berada pada jaringan yang sama. Komputer harus tetap menyala, terhubung internet untuk Sheets, dan tidak tidur agar portal bisa diakses dari HP. Tidak perlu membuka terminal run.py atau worker lagi.

Periksa kondisi tanpa menampilkan rahasia:

```powershell
.venv\Scripts\python.exe scripts\startup_portal.py --status
```

Log peluncur: `instance/startup-portal.log`. Log server: `instance/server.stdout.log` dan `instance/server.stderr.log`. Log Sheets: `instance/sheets-sync.stdout.log` dan `instance/sheets-sync.stderr.log`. Log notifikasi: `instance/notifications.stdout.log` dan `instance/notifications.stderr.log`. PID proses yang dibuat peluncur tersimpan pada `instance/server.pid`, `instance/sheets-sync.pid`, dan `instance/notifications.pid`. Seluruhnya lokal dan tidak masuk repository.

Untuk menjalankan peluncur lagi secara manual:

```powershell
.venv\Scripts\python.exe scripts\startup_portal.py
```

Setelah mengubah `.env` (misalnya konfigurasi Gmail), muat ulang server dan seluruh worker proyek dengan aman:

```powershell
.venv\Scripts\python.exe scripts\startup_portal.py --restart
```

Perintah ini hanya menghentikan proses portal, Sheets, dan notifikasi dari folder proyek ini; layanan MySQL tidak dihentikan.

## Mengubah pengaturan startup

Pasang ulang setelah lokasi folder proyek berubah:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\atur-startup.ps1
```

Nonaktifkan otomatis tanpa menghentikan layanan yang sedang dipakai:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\atur-startup.ps1 -Disable
```

Task dapat dilihat pada **Task Scheduler → Task Scheduler Library**. Jangan menghapus file .env, token OAuth atau .venv. Penggantian akun Google tetap dilakukan lewat perintah login setelah menghentikan worker Sheets.

Pemeriksaan langsung menggunakan pemicu manual Task Scheduler; reboot/logoff fisik tidak dilakukan selama pengujian.
