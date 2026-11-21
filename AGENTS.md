# Portal PSB Daarul Falah 2 Maliku

Bahasa antarmuka dan dokumentasi: Indonesia. Baca docs/kebutuhan-sistem.md dan docs/tahapan-pengerjaan.md sebelum melanjutkan.

Stack: Python 3.12+, Flask, SQLite WAL atau MySQL 8.0.16+/MariaDB 10.6+ InnoDB melalui DATABASE_URL, Jinja, CSS, penyimpanan privat di instance/.
Jalankan pengujian dengan `.venv\Scripts\python.exe -m pytest -q`.

Ketentuan tetap: pembayaran pendaftaran Rp200.000; nomor hanya setelah persetujuan Bendahara; email/WA tidak unik; Admin tidak mewarisi izin transaksi; semua waktu operasional Asia/Jakarta; uang berupa integer rupiah; transaksi BEGIN IMMEDIATE pada SQLite atau transaksi InnoDB dengan psb_write_lock FOR UPDATE pada MySQL untuk mutasi; jangan hapus riwayat. PDF resmi belum tersedia: template default harus bertanda DRAF.

Jangan commit instance/, .env, kredensial atau data pribadi. Seluruh unduhan privat harus memeriksa peran/pemilik di server. Token publik acak; verifikasi publik hanya lima identitas yang disetujui. Notifikasi menggunakan transactional outbox, mode simulasi bukan pengiriman nyata.

Perbarui progres dan batasan terverifikasi di docs/tahapan-pengerjaan.md setelah pekerjaan. Jangan mengklaim integrasi eksternal telah diuji bila belum ada kredensial.

Catatan=============
Selain biaya daftar ulang dan jadwal tes, siapkan ini sebelum membuka pendaftaran asli:
1. Rekening pembayaran — nama bank, nomor rekening, dan nama pemilik. Untuk tunai, tentukan petugas penerima.
2. Akun petugas — pastikan Admin, Bendahara, Pemberkasan, dan Ketua PSB bisa login. Ganti kata sandi percobaan sebelum digunakan resmi.
3. Informasi pendaftaran — tanggal buka/tutup, jenjang yang dibuka, kuota, serta kontak WhatsApp panitia.
4. Persyaratan berkas — tetapkan berkas wajib dan ketentuan ijazah menyusul agar informasi kepada wali konsisten.
5. Ketentuan pembayaran — batas pelunasan dan aturan cicilan yang akan diumumkan kepada wali.
6. Dokumen resmi — template formulir, kartu tes, kuitansi, dan bukti daftar ulang. Template bawaan masih bertanda DRAF.
7. Penyimpanan dan cadangan — pastikan akun Google, Sheets, dan Drive tetap dapat diakses panitia serta tersedia ruang penyimpanan.
8. Akses website — jika akan dibuka untuk masyarakat, siapkan domain dan server yang menyala terus. Saat ini akses masih bergantung pada laptop.
9. Pemberitahuan — pengiriman WhatsApp/email masih mode simulasi, sehingga belum otomatis terkirim sungguhan.
Terakhir, lakukan satu pengujian lengkap: pendaftaran → verifikasi Rp200.000 → aktivasi akun → biodata → tes → hasil seleksi → berkas → pembayaran → bukti daftar ulang. Gunakan lingkungan pengujian terpisah agar database yang sudah dikosongkan tetap siap untuk data asli.