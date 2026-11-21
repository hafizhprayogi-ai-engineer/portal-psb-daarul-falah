# Dashboard dan halaman layanan

Pembaruan 14 November 2026 mengikuti pola antarmuka pada referensi `Ui mobile design (1).jfif`. Palet hijau digunakan pada kartu progres, ikon menu, tombol, dan navigasi. Ikon memakai glyph/emoji sistem agar menu dapat dirender tanpa unduhan pustaka ikon.

## Susunan setelah login

Dashboard wali berisi sambutan, kartu progres, tombol untuk melanjutkan tahap berikutnya, serta delapan menu layanan. Biodata, jadwal/kartu, seleksi, berkas, pembayaran, dokumen, pemberitahuan, dan bantuan membuka halaman khusus. Rincian enam tahap juga mempunyai halaman sendiri.

Dashboard petugas menampilkan jumlah peserta yang menyelesaikan daftar ulang, menu sesuai peran, statistik penerimaan, dan akses akun. Menu petugas mengikuti izin gabungan yang diberikan pada akun.

Pada HP dan tablet, navigasi bawah menyediakan Beranda, Menu, pusat dashboard, Info/Tugas, serta Akun. Tombol Menu membuka dialog berisi menu yang diizinkan. Pada desktop, navigasi tampil sebagai sidebar. Formulir, laporan, audit, jadwal, dan halaman lainnya memakai kerangka aplikasi yang sama.

## Rute peserta

| Halaman | Rute |
| --- | --- |
| Dashboard peserta | /peserta/&lt;id&gt; |
| Biodata | /peserta/&lt;id&gt;/menu/biodata |
| Tes, formulir, dan kartu | /peserta/&lt;id&gt;/menu/jadwal |
| Hasil seleksi | /peserta/&lt;id&gt;/menu/hasil |
| Berkas daftar ulang | /peserta/&lt;id&gt;/menu/berkas |
| Tagihan dan pembayaran | /peserta/&lt;id&gt;/menu/pembayaran |
| Dokumen dan bukti | /peserta/&lt;id&gt;/menu/dokumen |
| Pemberitahuan | /peserta/&lt;id&gt;/menu/notifikasi |
| Bantuan wali | /peserta/&lt;id&gt;/menu/bantuan |
| Rincian progres | /peserta/&lt;id&gt;/menu/progres |
| Absensi petugas | /peserta/&lt;id&gt;/menu/absensi |

Setelah menyimpan formulir, pengguna kembali ke halaman layanan yang sesuai. QR absensi membuka halaman absensi khusus yang tetap mensyaratkan peran Pemberkasan. Tautan pemberitahuan baru memakai rute menu khusus. Tautan lama pada halaman peserta yang memakai fragment seperti `#jadwal` diteruskan oleh JavaScript ke halaman menu tersebut.

## Enam tahap progres

| Tahap | Syarat dihitung selesai |
| --- | --- |
| 1. Pembayaran awal | Nomor peserta sudah diterbitkan setelah pembayaran sah |
| 2. Biodata | Biodata dinyatakan lengkap oleh validasi server |
| 3. Tes dan kartu | Tanggal sudah dipilih dan kartu pertama sudah diterbitkan |
| 4. Kelulusan | Hasil terbaru yang dipublikasikan adalah Lulus |
| 5. Pemberkasan | Hasil masih Lulus dan seluruh persyaratan dokumen terpenuhi |
| 6. Daftar ulang selesai | Status selesai hasil perhitungan persyaratan dan pembayaran di server |

Tampilan menunjukkan jumlah tahap yang terpenuhi, seperti 1/6 atau 3/6, dan persentasenya. Koreksi hasil atau pembayaran dapat mengurangi progres sesuai kondisi terbaru. Untuk petugas, ringkasan progres menunjukkan jumlah peserta selesai terhadap total peserta.

## Rute petugas

- `/layanan/biodata`, `/layanan/hasil`, `/layanan/berkas`, dan `/layanan/dokumen` membuka pemilihan peserta untuk layanan terkait.
- `/keuangan` membuka menu keuangan.
- `/keuangan/pendaftaran` dan `/keuangan/daftar-ulang` membuka formulir tunai khusus Bendahara.
- `/keuangan/verifikasi` membuka pembayaran menunggu verifikasi, dan `/keuangan/riwayat` membuka riwayat serta koreksi.
- `/pengaturan` membuka menu pengaturan.
- `/pengaturan/lembaga`, `/pengaturan/biaya`, serta `/pengaturan/petugas` membuka bagian pengaturan masing-masing.
- `/pekerjaan` menampilkan jumlah pekerjaan yang perlu ditindaklanjuti sesuai peran.
- `/bantuan` menyediakan panduan petugas.

Admin Utama dapat mengawasi data dan keuangan. Transaksi pembayaran tetap mensyaratkan peran Bendahara, dan tindakan seleksi/pemberkasan tetap mensyaratkan peran Pemberkasan. Setiap rute peserta memeriksa pemilik atau peran pada server.

## Berkas implementasi

`psb/interface.py` memetakan menu per peran dan menghitung tampilan progres. `templates/app_navigation.html`, `static/app-shell.css`, dan `static/app-shell.js` menyediakan kerangka aplikasi. Bagian layanan peserta dipisahkan pada `templates/participant_sections/`, sedangkan formulir petugas berada pada `templates/staff_sections/`.

## Verifikasi

Pengujian otomatis mencakup halaman khusus, dashboard tanpa formulir biodata, perpindahan setelah simpan, isolasi akun, pembatasan peran, serta penurunan progres setelah koreksi hasil. Pengujian bisnis dari alur sebelumnya tetap dijalankan.

`scripts/preview_dashboard.py` memeriksa seluruh tujuan menu lima akun demo menggunakan Chrome terisolasi. Skrip menyimpan tangkapan layar desktop/HP serta memeriksa lebar halaman, dialog menu, dan pemisahan isi layanan. Hasil tersedia lokal pada `test-results/dashboard-preview/`. Pemeriksaan animasi menyesuaikan formulir petugas yang kini berada di halaman khusus.
