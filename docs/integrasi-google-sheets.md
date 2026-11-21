# Salinan biodata ke Google Sheets

## Rekap Jadwal Tes

Tab **Jadwal Tes** menyalin nomor pendaftaran, nama, jenjang, tanggal dan jam tes WIB, status pemilihan/status tanggal serta kehadiran. Tab berada pada spreadsheet yang sama dengan MI/MTS/MA. Setiap peserta bernomor mempunyai satu baris, termasuk yang belum memilih. Saat petugas memindahkan jadwal, tanggal pada baris yang sama diperbarui dan absensi kembali mengikuti sumber. Riwayat perpindahan tetap terdapat pada audit aplikasi.

Tab disiapkan satu kali menggunakan `scripts/google_sheets.py setup-tests` saat worker berhenti. Perintah ini tidak menimpa tab bernama sama dengan kolom berbeda. Sesudah tab ada, `sync` dan `sync --watch` otomatis menyertakannya. Jangan mengubah urutan/judul delapan kolom rekap atau memasukkan tanggal secara manual di Sheets; pilih/pindahkan tanggal melalui portal.

Panitia dapat membuka **Jadwal tes → Lihat peserta** pada portal untuk melihat peserta per tanggal dan memfilter jenjang. Admin hanya melihat rekap; perubahan jadwal/absensi tetap membutuhkan Pemberkasan.

Integrasi ini memakai OAuth Desktop melalui login browser lokal. Tidak memerlukan service-account key. Client OAuth diunduh sekali saat pembuatan dan disimpan sebagai `instance/google-oauth-client.json`. Aktifkan Google Sheets API; bila audience External masih Testing, tambahkan akun pemilik/editor spreadsheet ke Test users. Aplikasi OAuth ini digunakan oleh operator lokal, bukan login wali.

Isi `GOOGLE_SHEETS_ID` dalam .env lokal dengan bagian URL spreadsheet di antara `/d/` dan `/edit`. Jangan menulis Client ID, secret, refresh token atau biodata dalam repository. Token login disimpan privat sebagai `instance/google-sheets-token.json`. File lock mencegah dua proses sinkronisasi proyek berjalan bersamaan.

## Langkah operator

Jalankan dari PowerShell proyek:

```powershell
.venv\Scripts\python.exe scripts\google_sheets.py login
```

Browser membuka persetujuan Google. Gunakan akun yang dapat mengedit spreadsheet, lalu berikan izin jika setuju. Callback hanya pada loopback lokal dengan port acak dan PKCE. Setelah berhasil, CLI membaca metadata tab, tanpa menulis biodata. Selanjutnya:

```powershell
.venv\Scripts\python.exe scripts\google_sheets.py preview
```

Periksa rencana: tab MI, MTS, MA harus ada persis, baris 1 berisi NO PENDAFTARAN dan NAMA SISWA/NAMA LENGKAP, serta kolom lainnya sesuai template. Preview hanya membaca. Kolom yang tidak dikenali tercantum di `kolom_dibiarkan`. Judul kolom ambigu/ganda atau nomor ganda menghentikan sinkronisasi sebelum penulisan.

Jika rencana sesuai, jalankan satu kali:

```powershell
.venv\Scripts\python.exe scripts\google_sheets.py sync
```

Untuk terus menyalin perubahan tiap 60 detik:

```powershell
.venv\Scripts\python.exe scripts\google_sheets.py sync --watch
```

Biarkan terminal, komputer, database dan internet aktif. Ctrl+C menghentikan sinkronisasi. Belum ada tugas Windows otomatis saat startup. Kegagalan internet/API tidak membatalkan penyimpanan wali; putaran berikutnya membaca ulang data sumber dan nomor di spreadsheet. OAuth External Testing dapat memerlukan login ulang karena refresh token akses Sheets pada mode pengujian umumnya berakhir setelah tujuh hari. Jika Google menolak aplikasi karena belum terverifikasi, periksa konfigurasi proyek/akun dan izin organisasi sebelum melanjutkan.

## Aturan data

MySQL/SQLite tetap sumber utama. Hanya peserta yang sudah memiliki nomor disalin ke tab jenjang yang sesuai. Nomor pendaftaran adalah kunci baris: baris yang sudah ada diperbarui, baris baru ditambahkan. Tidak ada penghapusan riwayat atau penyalinan balik dari Sheets. Data yang berubah di kolom yang dikelola aplikasi akan ditimpa pada putaran berikutnya; kolom manual seperti NIS LOKAL dibiarkan. Jangan mengurutkan/mengedit kolom kunci saat worker sedang menulis.

Nama, NISN, jenis kelamin, TTL, NIK/KK, data ayah/ibu, alamat/kontak dan sekolah dipetakan jika header yang sesuai tersedia. NIK, pendidikan dan pekerjaan yang berulang ditentukan berdasarkan urutan NAMA AYAH/NAMA IBU sebelumnya. Sebaiknya gunakan judul lengkap NIK AYAH, NIK IBU, PENDIDIKAN AYAH/IBU dan PEKERJAAN AYAH/IBU. TTL menggabungkan tempat dan tanggal lahir. NIS lokal tidak ditebak. Nol di depan dipertahankan dengan penulisan RAW sebagai string; teks yang dimulai '=' tidak menjadi formula.

Penulisan hanya melalui Values API: header, format dan kolom manual tidak dihapus. Batas pemeriksaan saat ini 64 kolom/20.000 baris per tab. Tab MI/MTS/MA divalidasi semuanya sebelum penulisan pertama. Setiap pembaruan sel dan penambahan baris terpisah; kegagalan jaringan bisa menghasilkan sebagian baris sudah tersalin. Ulangi sinkronisasi setelah koneksi pulih: nomor dibaca kembali untuk menghindari duplikasi. Spreadsheet ini memuat data anak, sehingga akses perlu dibatasi pada petugas terkait. Password, sesi/token akun portal, token verifikasi dan file privat tidak diekspor.

Ini proses salinan berkala, terpisah dari transactional outbox notifikasi yang tetap berlaku untuk pesan email/WA. Tidak ada layanan Google yang dipanggil pada request wali. Perubahan biodata di antara putaran akan tersalin pada putaran berikutnya selama worker aktif.

Referensi: [OAuth Desktop dan PKCE](https://developers.google.com/identity/protocols/oauth2/native-app), [penulisan batch Values API](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/batchUpdate), serta [masa berlaku refresh token pengujian](https://developers.google.com/identity/protocols/oauth2#expiration).
