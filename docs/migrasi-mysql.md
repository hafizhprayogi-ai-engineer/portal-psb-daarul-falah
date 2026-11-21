# Migrasi SQLite ke MySQL dan phpMyAdmin

Aplikasi mendukung MySQL 8.0.16+ atau MariaDB 10.6+ dengan InnoDB dan utf8mb4. SQLite tetap digunakan jika DATABASE_URL kosong. Migrasi tidak memerlukan perubahan Python menjadi PHP. phpMyAdmin mengelola MySQL; instalasi dan URL phpMyAdmin mengikuti perangkat pengguna.

## Cara menjalankan

Pastikan MySQL aktif dan ketahui akun administrator database. Password dimasukkan langsung pada terminal, tidak dikirim di chat atau ditulis dalam perintah. Hentikan worker notifikasi selama migrasi.

Dari PowerShell pada direktori proyek:

```powershell
Set-Location 'D:\CODING\pendaftaran 2027-2028'
.venv\Scripts\python.exe -m pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File .\scripts\pindah-mysql.ps1
```

Skrip PowerShell membaca PORT dari .env (default 5000), memeriksa identitas server PSB, menghentikan server/induk dan worker proyek yang terdeteksi, serta menunggu proses keluar dan port bebas sebelum migrasi. Server dijalankan kembali setelah percobaan migrasi. Jika pemeriksaan identitas gagal, hentikan server PSB secara manual. Mode `-CheckOnly` memeriksa penghentian dan pengaktifan ulang tanpa migrasi. Untuk menjalankan Python langsung, hentikan server dan worker, jalankan `.venv\Scripts\python.exe scripts\migrate_mysql.py`, lalu mulai ulang aplikasi.

Isi pertanyaan terminal: host (default 127.0.0.1), port (3306), nama database baru (psb_daarulfalah), username administrator (root), dan password MySQL (tidak ditampilkan). Skrip khusus MySQL pada komputer yang sama; koneksi jarak jauh memerlukan pengaturan TLS tersendiri.

Skrip menolak database tujuan yang sudah berisi tabel. Sumber SQLite dikunci untuk penulisan, lalu API backup SQLite membuat snapshot. File privat dan konfigurasi lama juga dicadangkan di `instance/backups/sebelum-mysql-<waktu>/`. Semua ID, hash password, sesi/token, nomor urut, biodata, nominal integer, riwayat pembayaran, dokumen, audit dan outbox dipindahkan serta dibandingkan nilainya satu per satu. File privat tetap pada folder semula dan mempunyai cadangan terpisah. SQLite sumber tidak dihapus atau diubah oleh penyalinan.

Skrip membuat akun aplikasi khusus dengan password acak dan izin hanya pada database tujuan. Password administrator tidak disimpan. DATABASE_URL di `.env` lokal baru diisi setelah semua data cocok. `.env`, cadangan dan `instance/` tidak boleh dibagikan atau dimasukkan repository. Jika migrasi gagal, konfigurasi lama tetap berlaku; database/pengguna dari percobaan gagal tidak otomatis dihapus. Jika pembuatan skema terputus, gunakan nama database kosong baru.

## Melihat data

Login phpMyAdmin dengan akun MySQL yang memiliki akses. Pilih `psb_daarulfalah` atau nama database yang dimasukkan, lalu tabel dan **Browse/Jelajahi**. Identitas awal berada pada `applications`, nomor/biodata JSON pada `participants`, pembayaran pada `payments`, dan riwayat pada `audit`. Contoh SQL hanya-baca:

```sql
SELECT p.number AS nomor_pendaftaran, a.name AS nama,
       JSON_UNQUOTE(JSON_EXTRACT(p.bio, '$.nisn')) AS nisn,
       JSON_UNQUOTE(JSON_EXTRACT(p.bio, '$.father_name')) AS nama_ayah,
       JSON_UNQUOTE(JSON_EXTRACT(p.bio, '$.mother_name')) AS nama_ibu,
       p.bio_complete AS biodata_lengkap
FROM participants p
JOIN applications a ON a.id=p.application_id
ORDER BY p.id DESC;
```

Perubahan bisnis tetap melalui aplikasi agar validasi, izin dan audit berjalan.

## Transaksi, cadangan dan kembali ke SQLite

SQLite tetap memakai BEGIN IMMEDIATE. MySQL memakai InnoDB READ COMMITTED dan kunci baris `psb_write_lock ... FOR UPDATE` sebelum setiap mutasi, mempertahankan semantik satu penulis. Dua indeks unik bersyarat pembayaran digantikan generated columns dengan UNIQUE; foreign key, rupiah integer dan transaksi outbox tetap dipertahankan. Kunci ini mengutamakan konsistensi pada beban aplikasi sekarang; optimasi penulisan paralel memerlukan pengujian tersendiri.

`manage.py backup` menghasilkan `psb.sql` dan file privat pada backend MySQL. Impor SQL ke database kosong melalui phpMyAdmin, pulihkan file privat, lalu atur DATABASE_URL ke database pemulihan. Jangan mengimpor ke database operasional yang berisi tabel.

Untuk kembali segera setelah migrasi, hentikan server/worker, kosongkan DATABASE_URL pada `.env`, lalu mulai ulang. SQLite lama tidak memuat perubahan yang terjadi setelah MySQL mulai dipakai; setelah ada transaksi baru, pemulihan harus disertai rekonsiliasi.

## Pengujian

SQLite: `.venv\Scripts\python.exe -m pytest -q`.

MySQL: set PSB_TEST_MYSQL_URL ke akun pengujian yang boleh membuat/menghapus database, dengan nama awal psb_test_. Fixture membuat database acak per pengujian dan hanya menghapus database miliknya. Jangan gunakan database operasional.

```powershell
$env:PSB_TEST_MYSQL_URL='mysql://AKUN_UJI:PASSWORD_URL_ENCODED@127.0.0.1:3307/psb_test_suite'
.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:PSB_TEST_MYSQL_URL
```

Referensi: [penguncian InnoDB](https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html) dan [generated columns MariaDB](https://mariadb.com/docs/server/reference/sql-statements/data-definition/create/generated-columns).
