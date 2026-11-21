Bertindaklah sebagai pengembang full stack untuk membangun Sistem Penerimaan Santri Baru Pondok Pesantren Daarul Falah 2 Maliku.

Bangun aplikasi yang benar-benar berfungsi, memiliki database, backend, antarmuka responsif, hak akses, penyimpanan dokumen, dan integrasi otomatisasi n8n.

Gunakan bahasa Indonesia pada seluruh antarmuka.

==================================================
1. CARA KERJA DAN HASIL YANG DIHARAPKAN
==================================================

Periksa terlebih dahulu folder proyek dan alat pengembangan yang tersedia.

Jika sudah ada aplikasi, pelajari dan lanjutkan struktur yang relevan. Jika folder kosong, pilih satu susunan teknologi yang konsisten untuk aplikasi full stack ini. Jelaskan pilihan secara singkat, kemudian implementasikan.

Kerjakan bertahap sampai aplikasi dapat dijalankan dan diuji:
1. Dokumentasi kebutuhan dan fondasi.
2. Database, autentikasi, dan hak akses.
3. Pendaftaran dan pembayaran awal.
4. Biodata, jadwal, kartu, dan absensi tes.
5. Seleksi dan surat kelulusan.
6. Pemberkasan dan pembayaran daftar ulang.
7. Dokumen, QR, laporan, dan pengaturan.
8. Integrasi n8n, notifikasi, pengujian, dan panduan deployment.

Jangan berhenti hanya pada rencana atau tampilan.
Setiap tombol utama harus memiliki fungsi yang sesuai.
Bedakan integrasi simulasi dan integrasi aktif secara jelas.

Buat dan perbarui:
- docs/kebutuhan-sistem.md
- docs/tahapan-pengerjaan.md
- docs/hak-akses.md
- docs/integrasi-n8n.md
- AGENTS.md
- README.md
- .env.example

Simpan progres agar pekerjaan dapat dilanjutkan lintas sesi.

Gunakan data fiktif untuk pengembangan.
Jangan memasukkan password, token, atau data pribadi nyata ke repositori.

Jika ada detail kecil yang belum ditentukan, gunakan pilihan implementasi yang wajar dan dokumentasikan. Jangan mengubah ketentuan bisnis eksplisit berikut.

==================================================
2. IDENTITAS SISTEM
==================================================

Nama lembaga:
Pondok Pesantren Daarul Falah 2 Maliku.

Nama aplikasi:
Portal Penerimaan Santri Baru.

Tahun ajaran:
2027/2028.

Jenjang:
- MI
- MTs
- MA

Melayani putra dan putri dalam satu sistem, dengan pilihan jenis kelamin pada biodata.

Biaya pendaftaran:
Rp200.000 untuk semua jenjang dan metode pendaftaran.

Lokasi tes:
Pondok Pesantren Daarul Falah 2 Maliku.

Pas foto tidak diperlukan.

Semua jadwal operasional menggunakan WIB / Asia/Jakarta.
Gunakan format tanggal Indonesia dan mata uang Rupiah.

Tanggal pembukaan dan penutupan pendaftaran belum ditentukan.

==================================================
3. KONSEP AKUN PESERTA
==================================================

Satu akun digunakan untuk satu peserta.
Username adalah nomor pendaftaran.

Format nomor:
- MI-01, MI-02, MI-03, dan seterusnya.
- MTS-01, MTS-02, MTS-03, dan seterusnya.
- MA-01, MA-02, MA-03, dan seterusnya.

Angka dapat bertambah melewati dua digit tanpa terpotong.

Urutan nomor terpisah per jenjang.
Pendaftaran online dan langsung memakai urutan yang sama dalam jenjangnya.
Nomor harus unik dan aman terhadap proses persetujuan bersamaan.

Nomor baru diterbitkan setelah:
- Bendahara mencatat dan mengonfirmasi pembayaran tunai, atau
- Bendahara menyetujui pembayaran transfer.

Satu nomor pendaftaran hanya bisa digunakan membuat satu akun peserta.

Satu email orang tua boleh digunakan untuk beberapa akun anak.
Satu nomor WhatsApp orang tua juga boleh digunakan untuk beberapa akun anak.

Jangan menjadikan email atau nomor WhatsApp sebagai identitas unik akun peserta.

Setiap anak tetap memiliki:
- Nomor pendaftaran.
- Kata sandi.
- Biodata.
- Tagihan.
- Dokumen.
- Jadwal dan hasil seleksi masing-masing.

Setiap pesan menyebut nama dan nomor pendaftaran peserta.

==================================================
4. HALAMAN PUBLIK DAN AUTENTIKASI
==================================================

Halaman sebelum login menyediakan:
- Login.
- Daftar Akun.
- Pendaftaran Online.
- Lupa Password.
- Aktivasi akun melalui email.
- Pemantauan pengajuan melalui link khusus.
- Informasi alur, biaya, persyaratan, dan jam tes.
- Bantuan jika kontak panitia sudah diatur.

LOGIN:
Nomor pendaftaran dan kata sandi.

DAFTAR AKUN:
Hanya dapat dilakukan dengan nomor pendaftaran sah yang belum digunakan.

Data:
- Nomor pendaftaran.
- Nama lengkap peserta.
- Tempat lahir.
- Tanggal lahir.
- Nomor WhatsApp orang tua.
- Email.
- Kata sandi.
- Konfirmasi kata sandi.

Cocokkan data dengan pendaftaran yang sudah dicatat.
Nomor pendaftaran saja tidak boleh cukup untuk mengambil alih akun peserta lain.

Setelah daftar akun:
- Kirim link aktivasi email.
- Akun dapat digunakan setelah aktivasi.
- Sediakan pengiriman ulang aktivasi dengan pembatasan permintaan.

LUPA PASSWORD:
- Meminta nomor pendaftaran dan email terdaftar.
- Mengirim link reset ke email terkait.
- Token terbatas waktu dan sekali pakai.
- Respons tidak membocorkan keberadaan akun secara berlebihan.

Kata sandi disimpan dengan hashing yang aman.
Seluruh sesi dan akses diperiksa di server.

==================================================
5. PENDAFTARAN LANGSUNG
==================================================

Alur:
1. Wali datang ke pondok.
2. Bendahara mencatat data awal peserta.
3. Bendahara menerima dan mengonfirmasi pembayaran Rp200.000.
4. Sistem menerbitkan nomor pendaftaran otomatis.
5. Wali menerima nomor dan formulir fisik.
6. Wali membuat akun melalui Daftar Akun.
7. Wali membuat kata sandinya sendiri dan mengaktifkan akun melalui email.
8. Wali melengkapi biodata.
9. Wali memilih tanggal tes.
10. Wali mengunduh atau mencetak kartu.

Data awal harus cukup untuk mencocokkan pembuatan akun, termasuk jenjang, nama, tempat/tanggal lahir, nomor WhatsApp orang tua, dan email.

Sediakan bukti pembayaran PDF setelah transaksi disahkan.

==================================================
6. PENDAFTARAN ONLINE
==================================================

Alur:
1. Wali mengisi data awal tanpa harus memiliki akun.
2. Website menampilkan biaya Rp200.000 dan rekening tujuan.
3. Wali mengunggah bukti transfer.
4. Sistem memberikan nomor referensi pengajuan dan link khusus.
5. Link pemantauan dikirim melalui WhatsApp dan email.
6. Bendahara memeriksa bukti transfer.
7. Jika disetujui, sistem menerbitkan nomor pendaftaran.
8. Nomor dan petunjuk pembuatan akun dikirim melalui WhatsApp dan email.
9. Wali membuat akun dan aktivasi.
10. Setelah login, wali melengkapi biodata, mengunduh formulir, memilih tanggal tes, dan mencetak kartu.

Data awal:
- Jenjang.
- Nama peserta.
- Tempat dan tanggal lahir.
- Nomor WhatsApp orang tua.
- Email.

Status pengajuan:
- Menunggu pembayaran.
- Menunggu verifikasi.
- Perlu perbaikan bukti pembayaran.
- Pembayaran disetujui / nomor diterbitkan.

Bendahara wajib memberikan alasan jika menolak bukti.

Saat penolakan:
- Simpan data awal.
- Kirim alasan serta link unggah ulang melalui WhatsApp dan email.
- Wali tidak perlu mengisi data dari awal.
- Simpan riwayat pengajuan bukti.

Link khusus memakai token acak yang tidak mudah ditebak.
Pengajuan dapat dipantau sebelum akun peserta tersedia.

Tombol unduh formulir, pemilihan tanggal tes, dan penerbitan kartu hanya aktif setelah pembayaran disahkan dan prasyarat biodata dipenuhi.

==================================================
7. BIODATA DAN FORMULIR
==================================================

Biodata mencakup:
- Identitas santri.
- Jenis kelamin.
- Tempat dan tanggal lahir.
- Alamat.
- Asal sekolah.
- Data ayah.
- Data ibu.
- Data wali.
- Nomor WhatsApp orang tua.

Asal sekolah boleh kosong untuk MI yang belum pernah sekolah.

Biodata harus lengkap sebelum pemilihan tanggal tes.

Biodata dikunci setelah kartu pertama kali diterbitkan untuk diunduh/dicetak.
Gunakan kejadian penerbitan kartu sebagai pemicu karena aplikasi tidak dapat memastikan kertas benar-benar dicetak.

Wali tetap dapat mengunduh ulang kartu.
Perubahan biodata terkunci dilakukan melalui bagian Pemberkasan dan dicatat dalam riwayat.

Formulir:
- Satu template untuk MI, MTs, dan MA.
- Dibedakan melalui pilihan jenjang.
- Pendaftar langsung menerima formulir fisik.
- Pendaftar online dapat mengunduh setelah pembayaran disetujui.
- Formulir diisi dan ditandatangani wali.
- Formulir bertanda tangan diunggah setelah lulus.

Template formulir belum tersedia.
Sediakan pengelolaan template oleh Admin Utama.
Contoh pengembangan harus diberi tanda DRAF.

==================================================
8. JADWAL DAN TES
==================================================

Jenis tes:
MI:
- Membaca.
- Menulis.

MTs dan MA:
- Membaca Al-Qur'an.
- Tes tertulis.
- Wawancara.

Jam pelayanan:
- Rabu: 08.30–16.30 WIB.
- Minggu: 09.30–16.00 WIB.

Peserta memilih tanggal spesifik, bukan hanya nama hari.
Hanya tanggal Rabu/Minggu yang dibuka Pemberkasan yang dapat dipilih.
Tidak ada kuota peserta per tanggal.

Peserta boleh datang kapan saja dalam jam pelayanan.
Tidak ada pembagian jam kedatangan per peserta.

Setelah dipilih:
- Tanggal tidak dapat diubah sendiri oleh wali.
- Perubahan melalui Pemberkasan setelah wali menghubungi panitia.

Pemberkasan berwenang:
- Membuka tanggal.
- Menutup tanggal untuk pendaftar baru.
- Memindahkan jadwal peserta.
- Membatalkan pelaksanaan tes.
- Mencatat alasan pembatalan.

Menutup tanggal tidak membatalkan jadwal peserta yang sudah terdaftar.

Pembatalan tes:
- Alasan wajib dicatat.
- Pemberkasan memindahkan peserta ke tanggal pengganti yang valid.
- Kartu diperbarui.
- WhatsApp dan email dikirim berisi alasan, jadwal baru, dan link kartu terbaru.

Perubahan jadwal lain juga memperbarui kartu dan pemberitahuan.
Peserta tidak hadir dapat dijadwalkan ulang melalui Pemberkasan.

==================================================
9. KARTU PESERTA DAN ABSENSI
==================================================

Kartu PDF berisi:
- Nama lembaga.
- Tahun ajaran.
- Nama peserta.
- Nomor pendaftaran.
- Jenjang.
- Tanggal tes.
- Jam pelayanan.
- Lokasi.
- Jenis tes.
- QR.
- Instruksi membawa kartu.

Tidak memerlukan foto.

QR membuka halaman petugas untuk peserta terkait.
Akses pencatatan absensi harus mensyaratkan login dan peran Pemberkasan.

Alur:
Pindai QR → tampil identitas dan jadwal → tekan Konfirmasi Hadir.

Pemindaian tidak otomatis mengubah status.

Status:
- Belum dicatat.
- Hadir.
- Tidak hadir.

Sediakan pencarian manual bila kamera tidak tersedia.

Kedatangan di luar tanggal terpilih belum memiliki keputusan bisnis.
Tampilkan peringatan dan jangan otomatis mengubah jadwal.
Dokumentasikan sebagai aturan operasional yang masih perlu ditetapkan.

==================================================
10. SELEKSI
==================================================

Tidak perlu menyimpan nilai per jenis tes.
Keputusan hanya:
- Lulus.
- Tidak lulus.

Pisahkan hasil draf dari hasil yang dipublikasikan.

Alur:
1. Pemberkasan menyimpan hasil draf.
2. Peserta masih melihat Menunggu hasil.
3. Pemberkasan menekan Umumkan Hasil.
4. Hasil ditampilkan pada akun.
5. Pemberitahuan WhatsApp dikirim.

Pengumuman dilakukan per peserta ketika keputusan siap.

Hanya bagian Pemberkasan berwenang:
- Menetapkan hasil.
- Mengumumkan hasil.
- Mengoreksi hasil yang telah diumumkan.

Admin Utama tidak otomatis memperoleh kewenangan tersebut kecuali juga diberi peran Pemberkasan.

Peserta Lulus:
- Dapat mengunduh surat kelulusan.
- Dapat mengunggah berkas.
- Dapat memulai daftar ulang.

Peserta Tidak lulus:
- Melihat hasil.
- Menerima WhatsApp.
- Tidak mendapat surat hasil seleksi.

Koreksi hasil:
- Wajib alasan.
- Simpan hasil lama, baru, petugas, dan waktu.
- Kirim WhatsApp dan email berisi hasil terbaru serta alasan.
- Jika menjadi Tidak lulus, surat kelulusan lama tidak berlaku.
- Akses proses lanjutan harus mengikuti hasil terbaru.
- Jangan menghapus riwayat berkas atau pembayaran yang sudah ada.
- Jika sudah ada pembayaran, tandai untuk penanganan petugas;
  jangan mengasumsikan kebijakan pengembalian dana.

==================================================
11. SURAT KELULUSAN
==================================================

- Dibuat setelah hasil Lulus dipublikasikan.
- PDF diunduh wali.
- Word tersedia bagi petugas berwenang pada bagian data.
- Memiliki QR verifikasi.
- Memiliki versi/identitas dokumen.
- Dokumen lama ditandai tidak berlaku ketika dibatalkan.
- Jangan menimpa dokumen lama tanpa riwayat.

Belum tersedia:
- Template resmi.
- Kop.
- Nama penandatangan.
- Format nomor surat.

Sediakan pengaturan oleh Admin Utama.
Gunakan template DRAF untuk pengujian.
Jangan mengarang nama pejabat atau tanda tangan resmi.

==================================================
12. PEMBERKASAN
==================================================

Menu unggah hanya terbuka setelah Lulus dipublikasikan.

MI:
- Formulir yang ditandatangani wali.
- Akta kelahiran.
- KK.
- KTP ayah.
- KTP ibu.
- Tidak memerlukan SKL dan ijazah.

MTs dan MA:
- Formulir yang ditandatangani wali.
- Akta kelahiran.
- KK.
- KTP ayah.
- KTP ibu.
- SKL.
- Ijazah.

SKL dapat digunakan terlebih dahulu.
Ijazah boleh menyusul.
Daftar ulang tetap bisa selesai jika SKL diterima, dokumen lain lengkap, dan pembayaran lunas.

Jika KTP ayah/ibu tidak tersedia:
- Boleh diganti KTP wali.
- Wajib keterangan alasan.
- Diperiksa Pemberkasan.
- Catat dokumen mana yang digantikan agar pengganti tidak dihitung keliru.

Berkas boleh diunggah bertahap.
Pemberkasan boleh memeriksa tiap dokumen segera setelah masuk.

Status per dokumen:
- Belum diunggah.
- Menunggu pemeriksaan.
- Diterima.
- Perlu diperbaiki.
- Menyusul untuk ijazah bila relevan.

Penolakan/perbaikan wajib alasan.
Kirim WhatsApp berisi kekurangan atau perbaikan.
Tampilkan catatan di akun.

Dokumen diterima dikunci.
Penggantian melalui Pemberkasan dan simpan riwayat.

Gunakan penyimpanan privat.
Validasi ukuran, jenis file, dan akses unduhan di server.
Jangan membuat berkas identitas dapat diakses publik melalui URL permanen.

==================================================
13. TAGIHAN DAFTAR ULANG
==================================================

Biaya berbeda antara MI, MTs, MA.
Dalam jenjang yang sama, putra dan putri memiliki biaya sama.

Tagihan menampilkan:
- Rincian komponen.
- Nominal tiap komponen.
- Total.

Contoh kategori dapat berupa seragam, perlengkapan, dan pendidikan,
tetapi rincian serta nominal resmi belum ditentukan.

Admin Utama mengatur dan menetapkan tagihan.

Sebelum ditetapkan:
- Tampilkan Menunggu penetapan tagihan.
- Pembayaran daftar ulang belum dibuka.
- Peserta tetap boleh melengkapi berkas.

Jangan menganggap nominal belum ditentukan sebagai nol rupiah atau lunas.

Tagihan yang sudah digunakan transaksi harus memiliki riwayat.
Perubahan pengaturan biaya tidak boleh diam-diam mengubah transaksi atau kuitansi lama.

==================================================
14. PEMBAYARAN DAFTAR ULANG
==================================================

Metode:
- Tunai di pondok.
- Transfer dan unggah bukti.

Rekening sama dengan pembayaran pendaftaran.

Pilihan:
- Langsung lunas.
- Dicicil maksimal dua kali pembayaran yang sah.

Cicilan pertama:
- Minimal 50% dari total.
- Boleh lebih dari 50%.
- Tenggat belum ditentukan.

Pembayaran kedua melunasi seluruh sisa.
Batas pelunasan: 30 September 2027.

Pembayaran boleh dilakukan sambil melengkapi berkas.

Hanya Bendahara:
- Mencatat dan mengonfirmasi tunai.
- Menyetujui transfer.
- Menolak transfer beserta alasan.
- Mengoreksi pembayaran.

Transfer menunggu verifikasi belum dihitung sebagai dana masuk.
Bukti yang ditolak boleh diunggah ulang.
Penolakan dikirim melalui WhatsApp dan email.

Percobaan transfer ditolak tidak dihitung sebagai cicilan sah.
Koreksi pencatatan tidak boleh merusak riwayat.
Jika koreksi membuat kekurangan setelah dua transaksi,
sediakan alur penanganan koreksi Bendahara yang terdokumentasi
tanpa diam-diam menganggap cicilan umum ketiga diperbolehkan.

Bukti pembayaran PDF:
- Identitas lembaga dan peserta.
- Nomor bukti dan tanggal.
- Jenis pembayaran.
- Metode.
- Rincian tagihan.
- Nominal transaksi.
- Total pembayaran sah.
- Sisa tagihan.
- Status lunas/belum lunas.

Koreksi pembayaran:
- Hanya Bendahara.
- Wajib alasan.
- Simpan nilai lama, nilai baru, waktu, dan petugas.
- Perbarui total serta sisa tagihan.
- Kirim WhatsApp dan email dengan alasan serta link bukti terbaru.

Gunakan transaksi database dan perhitungan uang yang tepat.
Cegah penghitungan ganda akibat klik atau webhook berulang.

==================================================
15. PENYELESAIAN DAFTAR ULANG
==================================================

Selesai jika:
1. Hasil terbaru Lulus.
2. Dokumen wajib diterima.
3. Untuk MTs/MA, SKL diterima dapat memenuhi syarat sementara ijazah menyusul.
4. Pembayaran daftar ulang lunas.

Setelah selesai:
- Tampilkan status Daftar ulang selesai.
- Terbitkan bukti PDF ber-QR.
- Kirim WhatsApp dan email berisi link unduh.

Jika koreksi pembayaran menyebabkan belum lunas:
- Pembayaran menjadi Belum lunas.
- Daftar ulang menjadi Belum selesai.
- Bukti lama tidak berlaku.
- Setelah kekurangan dilunasi dan persyaratan terpenuhi,
  terbitkan bukti baru.

Status akhir dihitung dari prasyarat, bukan sekadar tombol manual tanpa pemeriksaan.

==================================================
16. VERIFIKASI DOKUMEN PUBLIK
==================================================

QR surat kelulusan dan bukti daftar ulang mengarah ke halaman verifikasi.

Hanya tampilkan:
- Nama peserta.
- Nomor pendaftaran.
- Jenjang.
- Jenis dokumen.
- Status keabsahan.

Jangan tampilkan:
- Tanggal lahir.
- Alamat.
- Nomor HP.
- Email.
- Dokumen identitas.
- Informasi keuangan.

Status minimal:
- Berlaku.
- Tidak berlaku.
- Dokumen tidak ditemukan.

Gunakan token dokumen yang tidak mudah ditebak.
PDF yang sudah diunduh tidak dapat diubah dari jarak jauh;
halaman verifikasi menjadi sumber status keabsahan terbaru.

==================================================
17. PERAN DAN HAK AKSES
==================================================

PERAN:
- Wali/peserta.
- Pemberkasan.
- Bendahara.
- Admin Utama.

Satu petugas dapat memiliki beberapa peran.

WALI:
- Hanya mengakses akun peserta terkait.
- Mengisi biodata sebelum dikunci.
- Mengunggah bukti pembayaran.
- Memilih jadwal sesuai ketentuan.
- Mengunduh dokumen miliknya.
- Mengunggah dan memperbaiki berkas yang belum dikunci.
- Melihat status, catatan, hasil, dan notifikasi.

PEMBERKASAN:
- Mengakses data santri.
- Memeriksa berkas.
- Memperbaiki biodata melalui prosedur petugas.
- Membuka/menutup tanggal tes.
- Mengubah jadwal.
- Mencatat kehadiran.
- Menetapkan, mengumumkan, dan mengoreksi hasil.
- Mengakses dokumen peserta sesuai tugas.
- Mengekspor laporan pendaftaran.
- Tidak mengesahkan atau mengoreksi pembayaran.

BENDAHARA:
- Mengakses menu keuangan.
- Melihat identitas minimum peserta untuk transaksi.
- Mencatat pembayaran tunai.
- Memverifikasi transfer.
- Mengoreksi pembayaran.
- Menerbitkan/mengunduh bukti pembayaran.
- Mengekspor laporan pembayaran.
- Tidak mengakses berkas pribadi yang tidak diperlukan.
- Tidak menetapkan hasil seleksi.

ADMIN UTAMA:
- Dapat mengakses bagian data santri dan keuangan untuk pengawasan.
- Mengunduh kedua jenis laporan.
- Membuat akun petugas.
- Mengatur peran, termasuk peran rangkap.
- Mengatur biaya, rincian tagihan, rekening, periode, dan template.
- Mengatur konfigurasi sistem.

Kewenangan transaksi khusus tetap berlaku:
- Hanya peran Bendahara dapat mengonfirmasi dan mengoreksi pembayaran.
- Hanya peran Pemberkasan dapat memutuskan dan mengoreksi hasil.
- Admin Utama tidak otomatis mendapat kedua kewenangan tersebut.
- Jika petugas memiliki peran rangkap, gunakan gabungan izin eksplisit.

Periksa izin di server pada setiap endpoint dan unduhan.
Jangan hanya menyembunyikan menu.

==================================================
18. MENU
==================================================

PUBLIK:
- Informasi PSB.
- Login.
- Daftar Akun.
- Pendaftaran Online.
- Lupa Password.
- Aktivasi.
- Status pengajuan melalui link khusus.

WALI:
- Dashboard dan progres.
- Biodata.
- Pembayaran pendaftaran.
- Unduh formulir.
- Jadwal tes.
- Kartu peserta.
- Hasil seleksi.
- Surat kelulusan.
- Berkas daftar ulang.
- Rincian tagihan.
- Pembayaran dan unggah bukti.
- Riwayat/bukti pembayaran.
- Bukti daftar ulang.
- Notifikasi.
- Bantuan.
- Pengaturan akun.

PEMBERKASAN:
- Dashboard.
- Data santri.
- Verifikasi berkas.
- Jadwal tes.
- Perubahan/pembatalan jadwal.
- Absensi dan pemindai QR.
- Hasil seleksi.
- Dokumen.
- Laporan pendaftaran.

BENDAHARA:
- Dashboard keuangan.
- Pembayaran pendaftaran.
- Verifikasi transfer.
- Pencatatan tunai.
- Pembayaran daftar ulang.
- Riwayat dan koreksi.
- Bukti pembayaran.
- Laporan pembayaran.

ADMIN UTAMA:
- Ringkasan sistem.
- Pemantauan data santri.
- Pemantauan keuangan.
- Akun petugas dan peran.
- Tahun ajaran dan periode.
- Biaya dan rincian tagihan.
- Rekening.
- Template formulir/surat.
- Pengaturan notifikasi.
- Riwayat aktivitas.

==================================================
19. NOTIFIKASI DAN N8N
==================================================

Gunakan database aplikasi sebagai sumber kebenaran.
n8n mengatur proses otomatis berdasarkan kejadian aplikasi.

Kejadian:
1. Pengajuan online masuk:
   WhatsApp dan email berisi link pemantauan.

2. Transfer pendaftaran ditolak:
   WhatsApp dan email berisi alasan dan link unggah ulang.

3. Pembayaran pendaftaran disetujui:
   WhatsApp dan email berisi nomor pendaftaran serta petunjuk akun.

4. Aktivasi dan reset:
   Email.

5. Jadwal ditetapkan:
   WhatsApp berisi jadwal dan link kartu bila sudah tersedia.

6. Jadwal diubah/dibatalkan:
   WhatsApp dan email berisi jadwal terbaru, alasan yang relevan,
   dan link kartu terbaru.

7. H-1 tes:
   WhatsApp dan email berisi tanggal, jam, lokasi, dan link kartu.

8. Hasil dipublikasikan:
   WhatsApp, serta hasil tersedia di akun.

9. Hasil dikoreksi:
   WhatsApp dan email berisi hasil baru serta alasan.

10. Berkas kurang/perlu perbaikan:
    WhatsApp berisi daftar dokumen dan catatan.

11. Transfer daftar ulang ditolak:
    WhatsApp dan email berisi alasan dan link perbaikan.

12. Pembayaran dikoreksi:
    WhatsApp dan email berisi alasan serta bukti terbaru.

13. H-7 dan H-1 pelunasan:
    WhatsApp dan email untuk yang belum lunas.
    Cantumkan nama, nomor pendaftaran, sisa tagihan, tenggat.
    Tunda selama bukti pembayaran menunggu verifikasi.
    Periksa status terbaru sebelum pengiriman.
    Jangan kirim pengingat untuk peserta yang tidak lagi memenuhi
    syarat menjalani daftar ulang.

14. Daftar ulang selesai:
    WhatsApp dan email berisi link bukti PDF.

Untuk batas 30 September 2027:
- H-7: 23 September 2027.
- H-1: 29 September 2027.

Persiapkan:
- Pencatatan kejadian/antrean notifikasi.
- Identitas kejadian unik.
- Status menunggu, diproses, berhasil, gagal.
- Percobaan ulang dengan pembatasan.
- Pencegahan pesan ganda.
- Pencatatan status pengiriman.
- Autentikasi webhook.
- Penanganan callback.
- Mode simulasi saat kredensial belum tersedia.

Buat workflow n8n yang dapat diimpor jika memungkinkan,
serta dokumentasi pemetaan kredensial dan endpoint.
Jangan menyertakan kredensial nyata dalam workflow.

Gunakan WhatsApp Business API melalui konfigurasi penyedia.
Jangan membuat klaim pesan sudah terkirim ketika hanya simulasi.
Email dan WhatsApp merupakan pengiriman terpisah:
kegagalan salah satu tidak boleh membatalkan pencatatan pembayaran.

Aplikasi PSB tidak memerlukan AI untuk keputusan kelulusan
atau verifikasi pembayaran. Keputusan dilakukan petugas.

==================================================
20. LAPORAN EXCEL
==================================================

Laporan pendaftaran:
- Nomor pendaftaran.
- Nama.
- Jenjang.
- Jenis kelamin.
- Kanal pendaftaran.
- Tanggal daftar.
- Status akun.
- Status pembayaran awal.
- Jadwal dan kehadiran.
- Hasil yang dipublikasikan.
- Status berkas.
- Status daftar ulang.

Laporan pembayaran:
- Identitas peserta.
- Jenis tagihan.
- Rincian/total tagihan.
- Nominal transaksi.
- Metode.
- Tanggal.
- Status verifikasi.
- Petugas.
- Total pembayaran sah.
- Sisa tagihan.
- Status lunas.

Filter:
- Jenjang.
- Rentang tanggal.
- Status yang relevan.
- Tahun ajaran.

Hak ekspor:
- Pemberkasan: pendaftaran.
- Bendahara: pembayaran.
- Admin Utama: keduanya.

Ekspor harus mengikuti izin pengguna dan tidak memasukkan data
sensitif tambahan yang tidak diperlukan.

==================================================
21. PENGATURAN YANG BELUM TERSEDIA
==================================================

Tandai sebagai Belum ditentukan / Belum tersedia:
- Tanggal buka dan tutup pendaftaran.
- Nomor WhatsApp panitia.
- Nama bank.
- Nomor rekening.
- Nama pemilik rekening.
- Rincian dan nominal daftar ulang per jenjang.
- Tenggat cicilan pertama.
- Template formulir.
- Kop surat.
- Contoh surat kelulusan.
- Nama penandatangan.
- Format nomor surat.

Jangan mengarang data resmi.
Jika pengaturan wajib belum ada, tampilkan pesan yang jelas
dan blokir hanya proses yang memerlukannya.

Sediakan data contoh terpisah untuk demonstrasi.

==================================================
22. DATA DAN RIWAYAT
==================================================

Rancang database dengan pemisahan yang jelas untuk:
- Tahun ajaran dan jenjang.
- Pengajuan sebelum akun.
- Peserta dan nomor pendaftaran.
- Akun, aktivasi, reset, sesi.
- Petugas, peran, izin.
- Biodata.
- Jadwal dan riwayat perubahan.
- Absensi.
- Hasil draf dan publikasi.
- Dokumen serta versi.
- Unggahan dan pemeriksaan berkas.
- Tagihan dan rincian.
- Pembayaran, bukti, verifikasi, koreksi.
- Penyelesaian daftar ulang.
- Antrean notifikasi dan percobaan pengiriman.
- Pengaturan.
- Audit aktivitas.

Gunakan status terpisah untuk pembayaran, seleksi, berkas,
dan daftar ulang. Jangan menyatukannya dalam satu kolom status.

Simpan riwayat untuk:
- Perubahan biodata terkunci.
- Perubahan jadwal.
- Pembatalan tes.
- Koreksi hasil.
- Pemeriksaan dan penggantian dokumen.
- Konfirmasi/koreksi pembayaran.
- Penerbitan/pembatalan dokumen.
- Perubahan pengaturan dan peran.

==================================================
23. TAMPILAN
==================================================

Buat antarmuka yang:
- Nyaman di HP dan komputer.
- Memakai bahasa sederhana untuk wali.
- Menampilkan progres dan tindakan berikutnya.
- Memiliki pesan kesalahan yang membantu.
- Menampilkan status dengan teks, bukan warna saja.
- Memiliki konfirmasi untuk publikasi hasil, koreksi,
  dan pembatalan yang berpengaruh pada peserta.
- Memiliki keadaan kosong, memuat, berhasil, dan gagal.
- Tidak menampilkan istilah teknis n8n/API kepada wali.
- Tidak memiliki tombol utama yang sekadar dekorasi.

Gunakan identitas visual yang rapi dan konsisten.
Logo belum tersedia; gunakan teks nama pondok sementara.

==================================================
24. PENGUJIAN DAN PENYELESAIAN
==================================================

Buat dan jalankan pengujian yang bermakna untuk:
- Isolasi akun peserta.
- Email/WA yang sama untuk beberapa anak.
- Nomor pendaftaran unik saat proses bersamaan.
- Nomor tidak diterbitkan sebelum pembayaran sah.
- Aktivasi dan reset token.
- Hak akses semua peran, termasuk akun rangkap.
- Penguncian biodata.
- Validasi Rabu/Minggu dan tanggal yang dibuka.
- Penutupan tanggal tidak membatalkan peserta lama.
- Pemindaian QR tidak langsung mencatat kehadiran.
- Draf hasil tidak terlihat peserta.
- Koreksi hasil membatalkan surat yang relevan.
- Persyaratan MI berbeda dari MTs/MA.
- SKL diterima dengan ijazah menyusul.
- Dokumen diterima tidak dapat diganti wali.
- Cicilan pertama minimal 50%.
- Pembayaran menunggu verifikasi belum dihitung.
- Pembayaran/koreksi tidak dihitung ganda.
- Koreksi pembayaran mengubah status daftar ulang.
- Dokumen lama tidak berlaku pada verifikasi QR.
- Penundaan pengingat saat menunggu verifikasi.
- Pencegahan notifikasi ganda.
- Unduhan dan ekspor sesuai hak akses.

Sediakan:
- Migrasi database.
- Data contoh dan akun uji lokal.
- Petunjuk instalasi dan menjalankan.
- Konfigurasi layanan nyata.
- Petunjuk pencadangan dan pemulihan.
- Panduan deployment.
- Daftar fitur selesai, simulasi, dan kebutuhan konfigurasi.

Mulai kerjakan proyek sekarang secara bertahap.
Pada setiap tahap, jelaskan singkat apa yang selesai,
hasil pengujian, dan pekerjaan berikutnya.
Jika sesi berakhir, simpan progres dalam dokumentasi agar
bisa dilanjutkan tanpa mengulang pekerjaan.
<!-- Tambahan permintaan pengguna 16 November 2026 -->

## Tambahan: pembagian biodata santri

Biodata dibuka melalui submenu khusus: Data Santri, Data Orang Tua, Alamat & Kontak, dan Sekolah Asal. Sidebar menyediakan kategori layanan serta submenu Biodata yang dapat dibuka/ditutup. Setiap bagian memiliki halaman dan tombol simpan sendiri; tampilan HP menyediakan tab bagian.

Data Santri memuat nomor pendaftaran otomatis (tidak dapat diubah), nama lengkap, NISN, jenis kelamin, tempat/tanggal lahir, NIK, nomor KK, dan riwayat penyakit anak. Data Orang Tua memuat nama, NIK, pendidikan terakhir, serta pekerjaan masing-masing ayah dan ibu. Alamat & Kontak memuat alamat rumah, kode pos, telepon/WA, email kontak opsional, dan nama wali bila diperlukan. Sekolah Asal memuat nama sekolah, alamat sekolah, dan NPSN. Data orang tua yang tidak tersedia diberi keterangan. Ketentuan jenjang MI yang belum memiliki NISN atau belum bersekolah tetap didukung.

## Tambahan permintaan: backend MySQL/MariaDB (16 November 2026)

Pengguna memilih migrasi dari SQLite agar database dapat dikelola melalui phpMyAdmin. Flask dan seluruh aturan bisnis tetap digunakan. Backend ditentukan oleh DATABASE_URL, dengan SQLite sebagai fallback ketika kosong. Pemindahan wajib mencadangkan sumber dan file privat, mempertahankan ID/nomor/hash password/dokumen/riwayat, memeriksa seluruh nilai, dan menolak penimpaan database tujuan berisi data. Penguncian satu penulis BEGIN IMMEDIATE diterjemahkan menjadi transaksi InnoDB dengan kunci baris FOR UPDATE; indeks unik dan foreign key tetap aktif. Kredensial MySQL dimasukkan secara lokal, bukan dalam repository atau chat. Panduan ada di `docs/migrasi-mysql.md`.

## Tambahan permintaan: startup Windows otomatis (17 November 2026)

Portal dan worker sinkronisasi Sheets dijalankan otomatis setelah pengguna masuk Windows, dengan jeda singkat dan menunggu database siap. Proses berjalan tersembunyi dengan izin pengguna biasa, tanpa password Windows tersimpan, tanpa membuka login Google otomatis, dan tidak menggandakan proses yang sudah aktif. Database Windows MySQL80 yang digunakan sudah Automatic. Pengguna dapat menonaktifkan tugas startup melalui skrip yang didokumentasikan. Pemicu ini setelah login Windows; akses sebelum login dan pemulihan otomatis dari mode tidur belum menjadi layanan tersendiri.

## Tambahan permintaan: rekap pemilihan tes (17 November 2026)

Sediakan daftar peserta per tanggal tes untuk Admin/Pemberkasan serta tab Jadwal Tes pada spreadsheet yang sudah terhubung, dengan nomor, nama, jenjang, tanggal/jam WIB, status pemilihan/tanggal dan kehadiran. Pemilihan serta perpindahan memperbarui baris berdasarkan nomor; peserta yang belum memilih tetap terlihat. Data dan audit aplikasi adalah sumber utama. Sinkronisasi berkala berjalan terpisah dari request wali. Tidak memberikan izin transaksi atau absensi baru pada Admin/Bendahara.

## Tambahan permintaan: Google Drive privat untuk berkas (18 November 2026)

Sediakan salinan berkas daftar ulang pada Drive privat dalam folder terpisah per peserta, dikelompokkan menurut tahun dan jenjang. Simpan setiap versi tanpa menghapus file lama. Database mencatat identitas file/folder, kepemilikan peserta, checksum dan hasil verifikasi. Drive membutuhkan OAuth tersendiri; tidak memakai tautan publik atau mengganti pemeriksaan unduhan server. Penyalinan asinkron tidak boleh membatalkan unggahan wali saat internet gagal. Penyimpanan privat aplikasi tetap sumber file utama sampai ada keputusan migrasi penyimpanan tersendiri.


## Perubahan syarat berkas (19 November 2026)

Pasfoto JPG/PNG menjadi berkas wajib untuk semua jenjang dan harus diterima Pemberkasan. Foto baru tetap menjadi foto profil, tetapi penggantian foto mengembalikan status pemeriksaannya ke menunggu. Untuk MTs/MA, ijazah wajib diterima agar berkas lengkap; SKL tidak lagi menggantikan ijazah untuk status lengkap. Ijazah boleh menyusul tanpa menghalangi pembayaran. Pembayaran lunas dengan ijazah/pasfoto belum diterima tetap berstatus berkas belum lengkap dan belum selesai daftar ulang. Ketentuan ini menggantikan aturan SKL sementara dan pasfoto opsional sebelumnya.
