# Hak akses

Izin diperiksa pada server di setiap endpoint. Akun dengan beberapa peran memperoleh gabungan izin eksplisit. Admin Utama yang memerlukan kewenangan transaksi harus diberi peran Bendahara atau Pemberkasan.

| Tindakan | Wali | Pemberkasan | Bendahara | Admin Utama |
| --- | --- | --- | --- | --- |
| Melihat biodata | Peserta sendiri | Ya | Identitas minimum di transaksi | Ya |
| Mengubah biodata | Sebelum terkunci | Dengan alasan dan riwayat | Tidak | Memerlukan peran Pemberkasan |
| Mengunggah identitas | Peserta sendiri setelah Lulus | Penggantian dengan alasan | Tidak | Memerlukan peran Pemberkasan |
| Mengunduh identitas | Peserta sendiri | Ya | Tidak | Ya |
| Menerima/perbaikan berkas | Tidak | Ya | Tidak | Memerlukan peran Pemberkasan |
| Memilih tanggal pertama | Peserta sendiri | Melalui pemindahan dengan alasan | Tidak | Memerlukan peran Pemberkasan |
| Mengelola tanggal/absensi | Tidak | Ya | Tidak | Pengawasan |
| Draf/publikasi/koreksi hasil | Tidak | Ya | Tidak | Memerlukan peran Pemberkasan |
| Mengunggah transfer | Peserta sendiri atau token pengajuan | Tidak | Tidak | Tidak |
| Mengesahkan/menolak/koreksi pembayaran | Tidak | Tidak | Ya | Memerlukan peran Bendahara |
| Mengunduh kuitansi | Peserta sendiri | Memerlukan peran Bendahara | Ya | Ya |
| Mengunduh surat Word | Tidak | Ya | Tidak | Ya |
| Mengunduh formulir kosong untuk layanan langsung | Tidak | Ya | Ya | Ya |
| Melihat riwayat berkas/biodata/jadwal | Tidak | Ya | Tidak | Ya |
| Ekspor pendaftaran | Tidak | Ya | Tidak | Ya |
| Ekspor pembayaran | Tidak | Tidak | Ya | Ya |
| Mengatur akun/peran/tagihan/template | Tidak | Tidak | Tidak | Ya |
| Mengawasi audit/notifikasi | Tidak | Tidak | Tidak | Ya |

Pengajuan online menggunakan token acak 256 bit sebelum akun tersedia. Token akses dan token akun disimpan sebagai hash. Token dokumen publik hanya mengizinkan verifikasi nama, nomor, jenjang, jenis dokumen, dan keabsahan. QR kartu memerlukan sesi Pemberkasan dan hanya membuka halaman peserta.

Sesi berlaku delapan jam. Perubahan kata sandi dan peran mengakhiri sesi lama. Perubahan peran dibatasi agar Admin Utama aktif terakhir tetap tersedia. Hash kata sandi memakai scrypt dari Werkzeug. Login, pendaftaran akun, aktivasi ulang, dan reset dibatasi per alamat IP.

Unggahan berukuran maksimal 5 MB berupa PDF/JPEG/PNG. Tipe berkas diperiksa dari konten. Gambar ditulis ulang untuk membuang metadata. Penyimpanan berada di luar static/, dan unduhan dikirim sebagai attachment setelah pemeriksaan izin.

Akun yang memiliki ketiga peran Admin, Bendahara dan Pemberkasan ditampilkan sebagai **Ketua PSB**. Ini nama tampilan gabungan izin yang sudah ada, bukan pemberian otomatis izin transaksi kepada Admin saja.
