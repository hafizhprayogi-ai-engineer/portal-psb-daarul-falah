# Berkas santri pada Google Drive privat

File utama tetap di penyimpanan privat aplikasi dan hanya diunduh melalui pemeriksaan akun/peran di server. Google Drive menjadi salinan privat terpisah per santri. Database menyimpan ID folder/file dan checksum pada drive_objects. Ini bukan tautan publik untuk menggantikan pemeriksaan akses portal.

## Aktivasi oleh operator

Gunakan proyek Google Cloud yang sama dengan OAuth Desktop Sheets. Aktifkan **Google Drive API** melalui APIs & Services → Library. Pada Google Auth Platform → Data Access, tambahkan scope `https://www.googleapis.com/auth/drive.file` bila belum tercantum, lalu simpan. Akun Google yang dipakai harus menjadi Test user bila aplikasi masih Testing.

Client yang sudah disimpan di instance/google-oauth-client.json dapat dipakai. Tidak perlu service-account key atau JSON client baru. Login Drive memakai token terpisah `instance/google-drive-token.json`; token Sheets tetap dipertahankan. Permission drive.file membatasi aplikasi pada file yang dibuat/dibuka untuk aplikasi, bukan seluruh isi Drive.

Dari terminal baru pada folder proyek, jalankan:

```powershell
.venv\Scripts\python.exe scripts\google_drive.py login
```

Jika login Google sudah menyimpan token tetapi penyiapan folder belum selesai, lanjutkan tanpa persetujuan ulang menggunakan `.venv\Scripts\python.exe scripts\google_drive.py setup`. Jangan memakai ulang URL callback 127.0.0.1 dari tab lama; alamat tersebut hanya aktif selama proses login berlangsung. Batas menunggu login saat ini 10 menit.

Pilih akun Google panitia yang akan memiliki folder, periksa izin, dan setujui jika sesuai. Sesudah akses terverifikasi, perintah membuat folder privat tahun/jenjang/santri, mencetak link folder induk yang benar-benar dikembalikan Google, dan mengisi GOOGLE_DRIVE_ENABLED=true di .env. Putaran worker Sheets berikutnya menyalin file, biasanya sekitar 60 detik. Tidak perlu menghentikan worker Sheets untuk login Drive karena token/lock dipisahkan.

Susunan yang dibuat aplikasi:

```text
Berkas PSB 2027-2028/
  MI/MI-01 - Nama santri/
  MTS/MTS-01 - Nama santri/
  MA/MA-01 - Nama santri/
```

Nomor/ID peserta menjadi identitas folder; mengganti file tidak membuat folder peserta baru. Nama folder saat pertama dibuat memakai nama saat itu. Versi unggahan diberi nama kategori dan ID versi, misalnya akta - versi-42.pdf. Folder/file baru tidak diberi permission publik atau seluruh domain oleh aplikasi. Folder yang terdeteksi publik/domain, pindah lokasi atau dibuang ke sampah menghentikan penyalinan sampai operator memperbaikinya. Operator dapat membagikan folder induk secara Restricted hanya kepada email panitia tertentu; jangan memakai Anyone with the link.

Untuk memeriksa jumlah versi tersalin:

```powershell
.venv\Scripts\python.exe scripts\google_drive.py status
```

Perintah sync tersedia untuk sekali jalan, tetapi dapat berbenturan dengan worker yang sedang memegang lock:

```powershell
.venv\Scripts\python.exe scripts\google_drive.py sync
```

## Perilaku unggahan dan keamanan

- Wali tetap mengunggah PDF/JPG/PNG maksimal 5 MB pada menu Berkas setelah Lulus. Validasi dan akses unduhan portal tidak berubah.
- Hanya kategori berkas daftar ulang yang disalin: formulir, akta, KK, KTP ayah/ibu, SKL dan ijazah. Bukti transaksi tidak ikut disalin.
- Setiap versi pada tabel uploads dipertahankan, termasuk berkas lama yang diganti/perlu diperbaiki. Tidak ada penghapusan file lokal, file Drive atau riwayat.
- ID Drive dicadangkan dalam transaksi sebelum API create. Jika upload diterima tetapi respons timeout, percobaan berikutnya memakai ID yang sama, membaca ulang metadata dan memeriksa checksum/ukuran.
- Source SHA-256 disimpan. MD5 dan ukuran dari Drive dibandingkan dengan file sumber sebelum status ready. MD5 dipakai sebagai verifikasi transfer, bukan autentikasi/kerahasiaan.
- Gangguan koneksi tidak membatalkan penyimpanan wali; salinan yang belum selesai dicoba lagi oleh worker. Jika sebuah file/folder tidak valid, putaran Drive berhenti dan dicoba kembali setelah perbaikan; Sheets tetap berjalan.
- ID/token, nama file fisik dan kunci tidak ditampilkan kepada wali. Status salinan ditampilkan pada berkas. Tautan folder Drive hanya muncul bagi Admin/Pemberkasan; izin Google tetap membatasi siapa yang dapat membukanya.
- Aktivasi tidak memindahkan kepemilikan Google atau memberikan akses otomatis kepada seluruh akun petugas. Gunakan akun Drive yang tepat saat login. Pergantian pemilik Drive memerlukan perencanaan migrasi folder, bukan sekadar mengganti token.

Folder/file Drive tidak boleh dipindah/dihapus manual saat penyalinan aktif. Status ready menunjukkan transfer pernah diverifikasi; aplikasi tidak dapat mencegah pemilik mengubah izin secara manual di kemudian hari. Kuota Drive harus dipantau; cadangan ini memakai kapasitas akun pemilik. Laptop tetap perlu menyala untuk menerima unggahan dan menjalankan worker sampai aplikasi dipindahkan ke server.

GOOGLE_DRIVE_ENABLED=false menghentikan penyalinan Drive pada putaran berikutnya tanpa menghapus file atau mengubah sinkronisasi Sheets. `drive_objects` disertakan dalam backup database; file lokal dan OAuth berada di instance privat. Snapshot pra-migrasi skema telah dibuat sebelum aktivasi kode. Drive belum diuji dengan berkas nyata sampai operator memberi izin OAuth Drive; pengujian otomatis memakai API tiruan dan file fiktif.

Referensi: [scope Drive per file](https://developers.google.com/workspace/drive/api/guides/api-specific-auth) dan [unggah dengan ID yang sudah dibuat](https://developers.google.com/workspace/drive/api/guides/manage-uploads).
