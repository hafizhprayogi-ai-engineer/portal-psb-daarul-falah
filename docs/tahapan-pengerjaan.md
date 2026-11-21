# Progres implementasi

## Pengiriman email Gmail langsung pada 21 November 2026

Portal kini mendukung pengiriman email langsung melalui SMTP Gmail untuk setiap event outbox berkanal email, termasuk tautan aktivasi dan reset kata sandi. Konfigurasi dipisahkan dari `NOTIFICATION_MODE`: `EMAIL_DELIVERY_MODE=smtp` hanya aktif jika host, port, alamat pengirim, username, dan App Password tersedia pada `.env` lokal. Kata sandi Gmail biasa tidak digunakan atau disimpan di kode/repository. Bila konfigurasi belum lengkap, email tetap tersimpan sebagai simulasi/antrean dan tidak dikirim.

Peluncur Windows menjalankan worker notifikasi tersembunyi setiap 30 detik bersamaan dengan portal dan worker Sheets. SMTP yang menerima pesan ditandai `berhasil` bersama Message-ID. Kegagalan autentikasi/koneksi diberi status gagal. Kegagalan ambigu ditahan sebagai `diproses` untuk rekonsiliasi Admin agar email tidak terkirim ganda. Panduan operator tersedia di `docs/integrasi-email-gmail.md`.

Pengujian terarah SMTP dan startup: 11 passed setelah konfigurasi akhir. Pengujian memakai SMTP tiruan dan database sementara; pengiriman ke Gmail nyata belum dilakukan karena App Password lembaga belum dimasukkan.

## Reset data percobaan untuk pendaftaran asli pada 20 November 2026

Pengguna meminta semua data kembali nol dan secara eksplisit menyetujui reset aplikasi, Google Sheets dan Google Drive dengan arsip terlebih dahulu. Portal/worker dihentikan sebelum pencadangan. Cadangan penuh SQL MySQL, seluruh file privat dan manifest disimpan di instance/backups/reset-data-asli-20261120-173851/. Direktori privat asli juga dipindahkan ke private-original di cadangan; lokasi aktif dibuat kosong. Arsip menyimpan seluruh data/histori lama, termasuk 5 pengajuan/peserta, 9 transaksi, 26 unggahan, 20 dokumen, 1 versi biaya, 3 tagihan, 2 jadwal, 155 audit dan 36 notifikasi sebelum reset.

Data aktif pengajuan, peserta, akun wali, transaksi, unggahan, dokumen, tagihan/versi biaya, jadwal, notifikasi/antrean pengiriman dan pemetaan Drive dikosongkan dalam transaksi berurutan sesuai foreign key. Semua sesi/token lama serta pembatas percobaan dibersihkan. Sequence nomor MI/MTS/MA diatur nol sehingga pendaftar baru mendapat nomor 01 setelah pengesahan Bendahara. ID internal tidak dipaksa ulang agar identitas arsip tidak rancu. Empat akun petugas, hash password, peran, status akun dan konfigurasi lembaga/rekening/template/OAuth tetap. Satu audit baru mencatat reset; riwayat lama tetap dapat dipulihkan dari arsip penuh. Jadwal dan nominal daftar ulang perlu ditetapkan kembali sebelum operasional.

Sheets: MI/MTS/MA/Jadwal Tes diduplikasi ke empat tab Arsip Uji 20261120 (tersembunyi), lalu hanya nilai baris 2 dan seterusnya pada empat tab aktif dibersihkan; header/format tetap. Snapshot metadata/cells sebelum tindakan disimpan di cadangan privat. Drive: folder tahun lama diganti nama Arsip Uji 20261120 - Berkas PSB 2027-2028, tanpa menghapus file atau memulihkan file yang sebelumnya dibuang. Folder aktif Berkas PSB 2027-2028 baru disiapkan dengan MI/MTS/MA kosong. Manifest mencatat ID/URL arsip dan folder baru. Database lama pada SQLite fallback tidak dipakai dan tidak diubah.

Verifikasi operasional: seluruh tabel pendaftaran/transaksi/berkas/tagihan/jadwal/outbox bernilai nol, akun wali nol, sequence nol. Sinkronisasi satu putaran nyata menghasilkan 0 peserta di seluruh tab dan 0 versi berkas Drive. Login empat akun petugas melalui browser berhasil, semua angka dashboard nol; portal/database/worker kembali aktif. Header Sheets dan tab arsip diperiksa ulang, folder Drive jenjang aktif kosong. Tidak membuat pendaftar atau pembayaran uji baru setelah reset. Tidak menjalankan suite backend karena tidak ada perubahan kode.

## Nama peran Ketua PSB pada 20 November 2026

Akun dengan tiga peran eksplisit admin,bendahara,pemberkasan kini ditampilkan sebagai Ketua PSB pada header/sidebar/dashboard, pengaturan dan daftar akun petugas. Penamaan berlaku berdasarkan kombinasi peran, bukan hanya username demo. Username login rangkap.demo, password, sesi, database dan pemeriksaan izin tidak diubah. Akun Admin saja tetap tidak memiliki hak transaksi. README dan dokumentasi hak akses diperbarui.

Tes navigasi/peran 10 passed, termasuk label Ketua PSB, akses gabungan tiga layanan, serta penolakan transaksi untuk Admin saja. Server diperbarui, tidak memerlukan migrasi atau perubahan data operasional.

## Nama penerima pembayaran daftar ulang tunai pada 20 November 2026

Formulir Keuangan -> Tunai daftar ulang menambahkan nama penerima uang wajib 2-150 karakter. Identitas penerima dicatat permanen pada audit transaksi pembayaran (aksi Penerima tunai dicatat) dalam transaksi yang sama, lalu dimasukkan ke snapshot kuitansi saat pengesahan. Riwayat transaksi menampilkan Diterima oleh; kuitansi PDF/DOCX menggunakan data snapshot ini. Koreksi nominal menerbitkan kuitansi baru dengan nama penerima tetap dari audit. Tidak menambah skema dan tidak mengisi nama perkiraan pada transaksi lama. Pengesahan tetap hanya Bendahara; Admin tidak mewarisi izin.

Kiriman ulang dengan kunci sama tidak menggandakan transaksi/audit; nama berbeda ditolak. Transaksi lama yang sudah disahkan tanpa nama tidak dapat diberi nama dengan mengirim ulang pembayaran. Pengujian kas/ujung-ke-ujung: 7 passed, mencakup kolom wajib, penyimpanan, kuitansi, pengulangan, koreksi nominal dan penolakan Admin. Tes awal sempat memakai indeks judul alih-alih daftar baris pada document_lines; assertion diperbaiki dan seluruh tes terkait lulus. Tidak membuat pembayaran operasional. Server diperbarui; worker tidak diubah.

## Formulir unggah wali tanpa alasan penggantian pada 20 November 2026

Kolom Alasan penggantian / penggunaan KTP wali dihapus dari formulir unggah milik wali sesuai permintaan. Pemilihan KTP wali tetap menyebut kategori KTP ayah/ibu yang digantikan melalui kartu unggahan; alasan tidak lagi diwajibkan untuk unggahan wali. Kategori selain KTP ayah/ibu tetap menolak pilihan KTP wali. Penggantian oleh petugas tetap memerlukan alasan untuk jejak koreksi, dengan label terpisah Alasan penggantian oleh petugas. Catatan pemeriksaan dan riwayat lama tidak diubah.

Tes unggah konten/pengganti KTP dan penguncian/izin berkas: 2 passed. Mencakup KTP wali tanpa alasan berhasil, kolom tidak muncul pada halaman wali, serta berkas diterima tetap terkunci. Server diperbarui, tidak mengubah data operasional atau Drive.

## Progres pembayaran terpisah dari kelengkapan berkas pada 20 November 2026

Pengguna mengoreksi progres MA-02 yang sudah membayar lunas tetapi masih 4/6 karena tahap terakhir sebelumnya memakai completed (status akhir yang juga mensyaratkan berkas). Tahap keenam sekarang Pembayaran daftar ulang lunas, dihitung dari invoice tersedia dan saldo nol. Tahap kelima tetap Berkas diterima. Maka pembayaran lunas dengan ijazah menyusul menjadi 5/6, bukan 4/6. Status akhir completed dan penerbitan bukti selesai tetap mensyaratkan seluruh berkas wajib diterima dan pembayaran lunas; tidak diubah atau dipaksakan selesai.

Pengujian navigasi/progres 9 passed, mencakup lunas/ijazah menyusul 5/6, cicilan dan tagihan belum ditetapkan tetap 4/6, serta lengkap+lunas 6/6. Pembacaan MySQL operasional mengonfirmasi MA-02 5/6 dan completed tetap false. Tidak ada perubahan transaksi atau status berkas. Server dimulai ulang; worker tidak diubah.

## Pratinjau bukti transfer pada 20 November 2026

Tautan Lihat bukti transfer pada Verifikasi transfer/Riwayat transaksi kini membuka endpoint privat inline /berkas/<id>/lihat di tab baru. Unduh tetap tersedia terpisah. Menggunakan pemeriksaan keuangan yang sama: pemilik/Admin/Bendahara dapat melihat, Pemberkasan tanpa peran keuangan ditolak. Tidak mengubah isi bukti atau status pembayaran. Pratinjau PDF tetap mengikuti dukungan browser.

Pengujian preview 3 passed, termasuk tautan keuangan, disposition inline, otorisasi bukti transfer dan regresi gambar/PDF berkas identitas. Server diperbarui untuk memuat template. Tidak melakukan transaksi pada database operasional.

## Pratinjau berkas privat pada 20 November 2026

Tombol Lihat berkas sebelumnya memakai endpoint unduhan dengan Content-Disposition attachment sehingga pengguna harus menyimpan file. Ditambahkan GET /berkas/<uid>/lihat dengan disposition inline dan tautan tab baru dari menu Berkas. Tautan Unduh tetap disediakan. Kedua rute berbagi pemeriksaan login/peran/pemilik yang sama dan header no-store; tidak membuka akses publik atau mengubah file. Gambar dapat ditampilkan langsung, sedangkan pratinjau PDF mengikuti dukungan/pengaturan viewer browser.

Tes PDF dan gambar: 2 passed, memeriksa disposition inline vs attachment, byte yang sama, header privat, akses pemilik/Admin/Pemberkasan dan penolakan wali lain/Bendahara/anonim. Server dimulai ulang; tidak mengubah status pemeriksaan atau integrasi Drive.

## Penanda santri menunggu pemeriksaan pada 20 November 2026

Tabel Data santri/Berkas menampilkan badge Perlu diperiksa, latar baris berbeda, jumlah berkas terbaru menunggu dan tautan Periksa berkas. Peserta berantrean ditampilkan lebih dahulu. Filter Semua santri/Menunggu pemeriksaan dapat dikombinasikan dengan pencarian nama/nomor dan jenjang. Tombol statistik dashboard langsung menuju filter pending. Status tanpa antrean tidak disebut lengkap agar tidak menyesatkan saat ada dokumen belum diunggah; berkas Perlu diperbaiki ditampilkan tersendiri.

Perhitungan hanya memakai versi terbaru per peserta/kategori dan tidak memasukkan bukti pembayaran. Tes terarah 1 passed mencakup hitungan peserta, duplikasi kategori, filter, prioritas, pencarian serta visibilitas peran. Sempat ditemukan sqlite3.Row tidak menyediakan get pada agregat, diperbaiki menjadi dict sebelum tes lulus. Browser MySQL mengonfirmasi filter menampilkan MA-02 saja dengan 7 berkas menunggu dan label/tombol yang sesuai. Pada HP 390px setelah animasi selesai lebar halaman 390px; tabel bergulir horizontal di dalam panel. Server diperbarui, tidak ada data/status berkas yang diubah.

## Angka pemeriksaan berkas dashboard pada 20 November 2026

Laporan berkas.demo menampilkan Menunggu verifikasi 0 ditelusuri: statistik lama menghitung payments, sementara MA-02 memiliki 7 unggahan terbaru berstatus Menunggu pemeriksaan. Dashboard kini membedakan Santri menunggu pemeriksaan berkas (Pemberkasan/Admin) dan Pembayaran menunggu verifikasi (Bendahara/Admin), masing-masing dengan tautan layanan. Statistik berkas menghitung peserta unik dengan minimal satu versi terbaru berkas non-bukti yang menunggu pemeriksaan, termasuk pasfoto. Versi lama dan bukti pembayaran tidak dihitung. Satu santri dengan tujuh berkas tetap dihitung satu.

Tes regresi terarah 1 passed: beberapa berkas satu peserta, versi lama menunggu tetapi versi baru diterima, bukti pembayaran dikecualikan dan visibilitas sesuai peran. Browser operasional MySQL berkas.demo pada 390px menunjukkan angka 1, tautan layanan benar serta tanpa overflow. Tidak mengubah status berkas atau transaksi. Server dimulai ulang; worker tidak diubah.

## Kata sandi minimal 8 karakter pada 19 November 2026

Sesuai permintaan pengguna, minimal kata sandi diturunkan menjadi 8 karakter pada pembuatan akun wali, akun petugas, ganti kata sandi dan reset. Validasi server, label formulir dan minlength input disamakan. Hash, konfirmasi, verifikasi kata sandi lama, aktivasi, token sekali pakai dan pencabutan sesi tetap berlaku. Tidak mengganti kata sandi akun yang sudah ada.

Tes batas 7 ditolak dan 8 diterima pada keempat alur: 8 passed. Pengujian menggunakan database terisolasi dan memeriksa hash tersimpan. Server dimulai ulang; worker tidak diubah.

## Penyelarasan ukuran banner dashboard pada 19 November 2026

Menindaklanjuti screenshot pengguna, banner hijau dibuat lebih ringkas dengan padding vertikal lebih kecil. Margin samping kartu progres/ringkasan dihilangkan sehingga sisi kiri/kanan banner dan kartu sejajar persis, tidak tampak hijau lebih panjang dari kartu putih. Tetap memakai lengkung dan aksen hijau serta menu yang sama. Perubahan berlaku pada dashboard wali dan petugas. Cache CSS diperbarui dan server dimulai ulang.

Browser Admin dan wali pada lebar 390, 1100 dan 1366px mengonfirmasi lebar banner/kartu sama (356/800/1046px), sisi sejajar dan tanpa overflow. Pemeriksaan dilakukan setelah animasi masuk selesai; screenshot wali 1100px diperiksa visual. Tidak mengubah data atau menjalankan ulang tes backend untuk penyesuaian CSS ini.

## Bentuk banner dashboard mengikuti referensi pada 19 November 2026

Dashboard wali dan seluruh peran petugas menggunakan satu bidang sapaan hijau dengan sudut bawah lebih melengkung dan lapisan lengkung halus. Kartu progres/ringkasan yang sebelumnya hijau menjadi kartu putih membulat di depan bagian bawah banner, mengikuti komposisi referensi portal mobile. Aksen hijau, data progres, tombol dan fungsi tetap. Perubahan CSS dibatasi pembungkus dashboard-hero agar ringkasan keuangan di halaman lain tidak ikut berubah. Semua markup, ikon, ukuran dan susunan menu utama dipertahankan. Avatar bawaan topbar diubah dari emoji menjadi siluet CSS dengan kepala lingkaran, tanpa topi; foto unggahan tetap tampil sebagaimana sebelumnya.

Verifikasi browser operasional pada lebar 390px dan 1366px untuk admin.demo, bendahara.demo, berkas.demo, rangkap.demo serta wali MA-01 berhasil: banner/kartu tampil, latar ringkasan putih dan tidak ada overflow horizontal. Screenshot wali HP dan Admin desktop diperiksa visual. Tidak ada mutasi data atau integrasi eksternal. Tidak menjalankan ulang suite backend karena perubahan hanya template/CSS; server dimulai ulang agar template baru dimuat. Versi cache CSS diperbarui.

## Perbaikan antrean Drive terhambat file di Sampah pada 19 November 2026

Laporan foto belum tersalin ditelusuri ke log worker: Drive terhenti pada salinan formulir upload:1 yang berada di Sampah. Foto unggahan #10 masih lokal dan belum memiliki pemetaan Drive. Tidak ada masalah pada validitas foto atau worker Sheets.

Sinkronisasi kini menandai hanya versi file yang dibuang sebagai state trashed, tidak memulihkannya otomatis, tidak membuat pengganti dan melanjutkan versi lain. Semua folder tetap harus lolos pemeriksaan parent/izin/trashed; file yang disalin tetap diperiksa ukuran/checksum dan privat. Versi yang pulih secara manual akan diverifikasi ulang dan kembali ready pada ID yang sama. File state trashed yang hilang tidak boleh dibuat ulang otomatis. UI berkas menampilkan status Sampah Drive secara jelas. Perubahan ini menggantikan perilaku lama yang menghentikan seluruh batch bila salah satu versi file berada di Sampah.

Tes terarah Drive/profil: 15 passed (termasuk file lama trashed tidak menghambat versi baru dan pulih pada ID lama). Worker dihentikan sementara, CLI sync operasional berhasil: 4 folder santri, 8 versi terverifikasi, 1 versi di Sampah. Foto #10 kini ready dengan nama foto - versi-10.jpg. Metadata Google dibaca ulang, parent sesuai dan izin privat terverifikasi. Ini verifikasi foto nyata pertama setelah penambahan kategori foto; file lama yang dibuang tidak dipulihkan. Portal/worker dimulai ulang untuk memuat perbaikan.

## Pasfoto wajib dan ijazah menyusul pada 19 November 2026

Permintaan pengguna mengubah aturan sebelumnya: pasfoto wajib semua jenjang dan perlu diterima Pemberkasan; foto pengganti mengembalikan status ke menunggu pemeriksaan dan memicu perhitungan status selesai ulang. Menu pasfoto menampilkan status/catatan serta formulir pemeriksaan petugas. Unggah foto tetap melalui rute khusus JPG/PNG; rute berkas umum menolak kategori foto agar PDF tidak lolos sebagai pasfoto. Riwayat dan penyalinan versi Drive tetap berlaku.

Untuk MTs/MA, ijazah harus diterima agar berkas lengkap. SKL tetap tersedia untuk unggahan sementara tetapi tidak menggantikan ijazah pada status kelengkapan. Jika ijazah sudah diterima, SKL tidak menjadi penghalang. MI tidak membutuhkan keduanya. Pembayaran tetap diizinkan setelah Lulus dan tagihan tersedia, tanpa mensyaratkan berkas lengkap; halaman pembayaran menjelaskan bahwa lunas belum berarti selesai daftar ulang bila ada kekurangan berkas. Pengingat kekurangan kini tetap mencantumkan ijazah walaupun SKL sudah diterima.

Data operasional dicadangkan privat di instance/backups/syarat-pasfoto-ijazah-20261119-170537/database.sql. Status seluruh peserta dihitung ulang dengan audit; satu status selesai berubah mengikuti syarat baru dan dokumen selesai lama dinonaktifkan oleh alur yang sudah ada. Tidak mengubah pembayaran atau menghapus dokumen/unggahan. Tidak ada foto lama berstatus Tersimpan yang perlu diubah ke menunggu pemeriksaan. Server operasional dan worker aktif.

Pengujian suite lengkap: 111 passed, 5 skipped dalam 211.62 detik. Pengujian terarah: 11 passed, termasuk pembayaran tunai sah MTs/MA tanpa ijazah, kelengkapan menunggu lalu selesai setelah ijazah diterima, pasfoto wajib diterima, unggah/profil/izin dan alur HTTP lengkap. Data pengujian menggunakan SQLite terisolasi dan FakeDrive; tidak melakukan upload nyata Drive baru pada perubahan aturan ini.

## Pasfoto dan foto profil santri pada 19 November 2026

Menu Berkas kini memiliki unggahan JPG/PNG maksimal 5 MB yang tersedia sebelum maupun sesudah seleksi. Pemilik atau Pemberkasan dapat mengunggah foto baru. Foto terbaru otomatis menjadi avatar akun wali; Akun saya menyediakan tautan untuk menggantinya melalui Berkas. Foto bersifat opsional dan tidak menjadi syarat berkas lengkap. Seluruh versi tetap di uploads dan riwayat audit. Endpoint inline /foto/<id> memeriksa login serta pemilik/Admin/Pemberkasan; Bendahara dan wali lain ditolak. Unduhan lama tetap memakai pemeriksaan privat.

Foto ditulis ulang ke JPEG tanpa metadata, orientasi EXIF diperbaiki, serta ukuran hasil pemrosesan dibatasi 5 MB. Category foto ditambahkan ke daftar kategori yang disalin oleh worker Drive yang sudah ada: folder privat tahun/jenjang/santri yang sama dan file versi terpisah; tidak ada izin publik atau perubahan skema. Status penyalinan tampil pada kartu foto. Server dan worker telah dimulai ulang agar memuat kategori baru.

Verifikasi: suite awal 107 passed, 5 skipped dan satu kegagalan fixture baru karena berkas dummy accepted_files hanya membuat metadata. Fixture diperbaiki dengan file dummy yang sesuai, lalu 2 tes foto lulus ulang. Mencakup unggah/ganti, avatar terbaru, file lama tetap, foto tidak memengaruhi kelengkapan, PDF/gambar palsu ditolak, izin akses, dua versi di folder Drive sama dengan FakeDrive. Chrome headless pada lebar HP 390px membuktikan gambar/avatar dimuat, tautan Akun saya tersedia dan tidak ada overflow horizontal. Pengujian mutasi memakai SQLite terisolasi. Upload foto nyata ke Google Drive dan mutasi MySQL untuk kategori foto belum diuji; tidak mengunggah gambar pengujian ke database operasional. Pemeriksaan status operasional menunjukkan portal, database dan worker aktif.

## Tautan aktivasi langsung pada 19 November 2026

Laporan aktivasi selalu kedaluwarsa diperiksa: token terbaru akun percobaan belum digunakan dan belum melewati batas waktu. GET tautan persis menghasilkan HTTP 200, sedangkan jika titik penutup kalimat ikut tersalin menghasilkan HTTP 400 dengan pesan token tidak berlaku. Salah salin ini terbukti dapat mereproduksi gejala, tetapi URL yang sebelumnya dibuka pengguna tidak direkam sehingga tidak dipastikan sebagai satu-satunya penyebab.

Riwayat aktivitas Admin kini menampilkan nomor akun, waktu, status valid/dipakai/diganti/kedaluwarsa dan tombol langsung untuk aktivasi/reset yang masih berlaku. Path lokal diambil dari payload terstruktur dan hash token dicocokkan, sehingga tidak perlu menyalin alamat dari kalimat pesan. Token bekas tidak diberi tombol. Tidak mengubah masa berlaku, aturan sekali pakai atau aktivasi eksplisit melalui POST, dan tidak mengirim email nyata.

Tes terarah 1 passed: tautan terbaru, token diganti, titik salah salin, konsumsi token dan hilangnya tombol setelah aktivasi. Browser operasional MySQL membuktikan satu tombol aktif MA-02 dan formulir Aktifkan akun saya berhasil dibuka. Tidak menekan konfirmasi aktivasi akun operasional. Server dimulai ulang; worker tetap berjalan.

## Revisi tagihan peserta pada 19 November 2026

Admin kini dapat membuka Pembayaran peserta -> Ubah rincian tagihan, mengubah pasangan nama/nominal, mengisi alasan wajib 3-500 karakter dan konfirmasi. Revisi hanya mengubah snapshot invoice peserta, bukan versi biaya umum atau invoice peserta lain. Riwayat audit menyimpan aktor, waktu, alasan, snapshot sebelum dan rincian sesudah; Admin serta wali pemilik dapat melihat rincian perubahan pada halaman pembayaran. Tidak ada fitur pembatalan versi yang diaktifkan kembali, tidak ada tagihan operasional yang ditetapkan atau direvisi selama implementasi ini.

Mutasi tetap menggunakan transaksi dan kunci penulis backend. Token revisi berdasarkan snapshot invoice dan ID audit terakhir mencegah penimpaan halaman lama serta submit berulang. Pembayaran sah tidak diubah. Total di bawah pembayaran sah ditolak (refund belum tersedia), revisi saat transfer menunggu verifikasi ditolak, dan setelah dua pembayaran sah revisi harus tetap lunas. Status selesai dihitung ulang. Bila tagihan bertambah setelah lunas, bukti daftar ulang lama dinonaktifkan; bila rincian berubah tetapi masih selesai, bukti baru diterbitkan dan versi lama tetap di riwayat. Kuitansi pembayaran tetap berlaku.

Verifikasi suite: 104 passed, 5 skipped. Pengujian tambahan regenerasi bukti/status selesai kemudian ditambahkan; seluruh 3 tes revisi lulus dalam eksekusi terarah. Mencakup penyimpanan HTTP, riwayat, token kedaluwarsa, izin Admin (Bendahara/Pemberkasan ditolak), total di bawah pembayaran, transfer pending, dua pembayaran, saldo serta dokumen. Pengujian mutasi memakai SQLite terisolasi; revisi MySQL dan integrasi eksternal belum diuji ulang. Tidak ada migrasi skema. Server operasional sudah dimulai ulang dan pemeriksaan status database/portal serta worker aktif berhasil.

## Pengembalian fitur dan reset tagihan pada 18 November 2026

Atas permintaan pengguna, fitur pembatalan versi tagihan dihapus kembali dari endpoint, pemilihan versi dan antarmuka. Formulir per baris nama/nominal, tambah/hapus sebelum submit dan total otomatis tetap tersedia. Catatan pembatalan di bawah merupakan keadaan historis yang sudah digantikan oleh perubahan ini.

Data operasional diperiksa: 3 versi biaya, 1 invoice, 0 transaksi daftar ulang dan 0 peserta completed. Portal dan worker dihentikan sementara. Cadangan penuh MySQL disimpan secara privat di instance/backups/reset-tagihan-20261118-235121/database.sql. Snapshot lengkap ketiga versi dan invoice disimpan dalam audit aksi Arsip sebelum reset tagihan beserta alasan permintaan pengguna; hanya data tagihan aktif dikosongkan. Tidak ada pembayaran, biodata, berkas, identitas atau audit lama yang dihapus. Pemeriksaan ulang menghasilkan 0 versi biaya dan 0 invoice. Penetapan biaya berikutnya akan menerbitkan tagihan baru sesuai alur biasa.

Verifikasi 7 tes terarah lulus (formulir biaya dan aturan tagihan belum ditetapkan/snapshot). Browser operasional MySQL mengonfirmasi biaya belum ditentukan, tombol pembatalan tidak tersedia, serta halaman pembayaran peserta menunggu penetapan tagihan. Portal, database dan worker sudah berjalan kembali. Tidak melakukan sinkronisasi eksternal baru secara manual untuk reset ini.

## Pembatalan versi tagihan pada 18 November 2026

Admin dapat membuka Batalkan versi tagihan pada tabel Biaya & tagihan, mengisi alasan 3-500 karakter dan mencentang konfirmasi. Pembatalan disimpan sebagai kejadian audit fee_cancelled (aktor, waktu, alasan dan snapshot versi) dalam transaksi dengan kunci penulis yang sudah tersedia; kiriman berulang tidak menggandakan pembatalan. Tidak ada versi, tagihan peserta, pembayaran atau riwayat yang dihapus. Penerbitan baru melewati versi batal dan memakai versi terbaru yang masih tersedia pada tahun/jenjang peserta; bila semuanya batal, tagihan baru menunggu penetapan biaya. Tagihan peserta yang sudah terbit tetap berlaku, termasuk yang belum dibayar. Halaman menampilkan status, alasan, waktu dan jumlah tagihan yang sudah memakai versi tersebut. Koreksi nominal tagihan peserta lama belum tersedia melalui fitur ini.

Verifikasi: suite awal 103 passed, 5 skipped dengan satu kegagalan fixture tes baru karena aktor transaksi belum disiapkan. Fixture diperbaiki dan seluruh 8 tes formulir/pembatalan lulus ulang, termasuk fallback versi, semua versi batal, snapshot lama tetap, pengulangan, alasan/konfirmasi wajib dan larangan Bendahara. Pemeriksaan baca halaman pada MySQL operasional HTTP 200 dan lebar HP 390px sesuai; tidak membatalkan versi nyata. Mutasi pembatalan diuji pada SQLite terisolasi, belum pada MySQL. Tidak ada perubahan skema database. Server operasional telah dimulai ulang; worker sinkronisasi tetap berjalan.

## Formulir biaya per baris pada 18 November 2026

Kotak teks berformat Nama | nominal diganti pasangan input nama tagihan dan nominal rupiah. Admin dapat menambah/menghapus baris (maksimal 100), melihat total otomatis, dan mengisi melalui susunan satu kolom di HP. Server tetap memvalidasi nama, pasangan baris serta integer positif di bawah satu miliar per komponen; versi biaya dan tagihan lama tetap dipertahankan. Format POST lama tetap didukung. Cache aset diperbarui dan server operasional dimulai ulang tanpa mengubah nominal tagihan pengguna.

Verifikasi: pengujian baru 6 passed, mencakup penyimpanan beberapa komponen/total serta penolakan Rp, pemisah, pecahan, negatif, nol dan batas nominal. Pada eksekusi suite awal 101 pengujian lain lolos dan 5 dilewati; satu kegagalan berasal dari helper pengujian baru yang menghilangkan nama field berulang, telah diperbaiki memakai MultiDict langsung dan keenam tes terkait lulus ulang. Pemeriksaan Chrome headless pada lebar 390px dan 1366px membuktikan tambah/hapus, total otomatis dan tidak ada overflow horizontal. Tidak menyimpan tagihan pada database operasional selama pemeriksaan browser. Pengujian perubahan ini memakai SQLite terisolasi; MySQL tidak diuji ulang untuk perubahan formulir ini.

## Perbaikan aktivasi Drive pada 18 November 2026

Pengguna melaporkan halaman callback OAuth lokal ERR_CONNECTION_REFUSED. Pemeriksaan menemukan proses login sudah berakhir dan token Drive dengan scope drive.file sudah tersimpan, tetapi aktivasi belum berlangsung. Pemeriksaan about.get pada skrip memakai selector `user.permissionId`, yang ditolak Google dengan HTTP 400. Selector diperbaiki menjadi `user(permissionId)` dan dibuktikan HTTP 200 menggunakan token tersimpan. CLI setup ditambahkan untuk melanjutkan aktivasi tanpa membuka login ulang. Batas menunggu callback login juga diperpanjang dari 180 menjadi 600 detik.

Aktivasi dengan token yang telah disetujui pengguna berhasil: tujuh folder privat (satu tahun, tiga jenjang, tiga santri) dibuat dan metadata/perizinan seluruhnya dibaca ulang. GOOGLE_DRIVE_ENABLED kini true. Sinkronisasi berjalan dengan tiga folder santri dan nol versi berkas karena belum ada unggahan kategori berkas daftar ulang pada sumber. Upload file nyata ke Drive belum diverifikasi; operator perlu mengunggah satu berkas melalui akun wali yang sudah Lulus. Tidak ada izin publik/domain yang ditambahkan, tidak ada file sumber/riwayat yang dihapus. Status nonaktif pada catatan sebelumnya merupakan kondisi sebelum perbaikan ini.

Pengujian terarah setelah perbaikan: **20 passed in 12.32s**, termasuk regresi selector about.get, setup memakai token tersimpan tanpa login baru, dan batas tunggu callback 600 detik. Sinkronisasi operasional Sheets dan Drive tetap berjalan setelah aktivasi.

## Salinan berkas Google Drive privat pada 18 November 2026

Pengguna memilih Google Drive privat. Dukungan disiapkan untuk folder tahun ajaran → jenjang → nomor/nama santri, dengan salinan setiap versi berkas daftar ulang. Penyimpanan utama privat dan unduhan dengan pemeriksaan peran/pemilik tetap berlaku. Drive tidak menjadi URL publik atau menghapus file utama. Bukti pembayaran dikecualikan dari penyalinan. Token OAuth Drive terpisah dari Sheets dan hanya meminta drive.file, memakai client Desktop yang sudah ada.

Migrasi skema 3 menambahkan drive_objects dengan relasi unggahan/peserta, ID Drive unik, parent ID, checksum SHA-256, status serta link hasil metadata Google. ID dicadangkan sebelum API create agar timeout ambigu dapat diulang tanpa menggandakan folder/file. Ukuran dan MD5 transfer dibandingkan sebelum ready; folder/file publik/domain, tidak dapat diverifikasi izinnya, dipindah, hilang atau di sampah ditolak. Semua versi unggahan tetap disimpan. Tidak ada endpoint unduhan publik baru; tautan folder di website hanya untuk Admin/Pemberkasan. Wali melihat status salinan pada menu Berkas.

Backup database SQL, file privat dan konfigurasi dibuat sebelum migrasi. Skema operasional MySQL berhasil diperbarui tanpa mengubah data santri/pembayaran. Kompatibilitas migrasi dari SQLite skema 2 dan upgrade MySQL 2→3 diuji. Sinkronisasi Sheets tetap berjalan, dan worker diperbarui untuk memproses Drive pada tiap putaran jika GOOGLE_DRIVE_ENABLED=true. Kegagalan Drive tidak membatalkan unggahan wali atau hasil sinkronisasi Sheets. Login Drive menyediakan folder privat, baru mengaktifkan penyalinan setelah akses terverifikasi.

Pengujian: suite SQLite sebelum dua uji tambahan **93 passed, 5 skipped in 91.52s**; sebelas uji Drive terarah lulus. Suite MySQL 8.0.46 terisolasi **99 passed, 1 skipped in 249.93s**. Meliputi pemisahan folder, preservasi versi, idempotensi setelah timeout, blokir publik/domain, perlindungan file berubah/hilang, pengecualian bukti transaksi, rollback unggahan, scope/token terpisah dan tautan folder khusus petugas. Login/health/halaman utama/laporan melalui server aktual lulus HTTP 200; menu berkas HP diperiksa tanpa mengubah data sumber. Pemeriksaan dependensi lulus. Layanan MySQL pengujian terisolasi dihentikan setelah pemeriksaan.

**Status aktivasi:** Drive tetap nonaktif, belum ada google-drive-token.json dan belum ada objek/file yang dikirim ke Drive asli. Operator perlu mengaktifkan Google Drive API, menambahkan scope drive.file pada Data Access bila diperlukan, lalu menjalankan scripts/google_drive.py login dan memberi persetujuan akun Google. Pengujian Drive memakai API tiruan dan file fiktif; upload berkas nyata belum diverifikasi. Panduan: docs/integrasi-google-drive.md. Batasan: kuota Drive, perubahan izin manual pemilik dan kegagalan satu file/folder dapat menghentikan putaran Drive sampai diperbaiki; source lokal dan Sheets tetap tersedia.

## Rekap pemilihan tanggal tes pada 17 November 2026

Menu Jadwal tes petugas kini mempunyai tombol Lihat peserta untuk setiap tanggal. Halaman `/jadwal/<id>` menampilkan nomor pendaftaran, nama, jenjang, kehadiran dan tautan Tes & kartu/Absensi, dengan filter jenjang. Hanya Admin dan Pemberkasan dapat melihat rekap; kewenangan mutasi tetap Pemberkasan. Wali serta Bendahara tanpa peran tambahan ditolak. Menu Tes & kartu pada detail peserta petugas juga menyediakan tautan daftar tanggal terkait.

Tab baru **Jadwal Tes** dibuat pada spreadsheet yang sudah terhubung. Delapan kolom: NO PENDAFTARAN, NAMA SISWA, JENJANG, TANGGAL TES, JAM TES (WIB), STATUS PEMILIHAN, STATUS TANGGAL, KEHADIRAN. Tab memuat seluruh peserta bernomor; yang belum memilih ditandai Belum memilih dengan tanggal/jam kosong. Nomor menjadi kunci sehingga pemilihan, pemindahan, pembatalan yang memindahkan peserta dan absensi memperbarui baris yang sama. Riwayat sumber/audit tetap disimpan; ini rekap keadaan terkini. Header dibekukan, dapat difilter, dan diberi warna hijau serta lebar kolom/wrapping sesuai isi. Tab biodata MI/MTS/MA dipertahankan.

CLI `setup-tests` menyiapkan tab baru secara atomik dan menolak penimpaan tab bernama sama dengan header berbeda. Worker lama dimulai ulang, lalu sinkronisasi berjalan otomatis setiap 60 detik termasuk tab rekap baru. Header rekap yang berubah menghentikan validasi sebelum menulis. Pengujian seluruh aplikasi menghasilkan **84 passed, 3 skipped in 68.34s**; pengujian terarah setelah pemeriksaan akhir **13 passed in 2.59s**. Termasuk isolasi tanggal/peran, filter jenjang, snapshot sebelum dan setelah pemindahan, peserta belum memilih, setup tanpa penimpaan serta pembaruan tanpa baris ganda.

Integrasi nyata diuji dengan akun OAuth yang sudah diotorisasi: tiga peserta tersalin, kemudian pembacaan ulang seluruh delapan kolom cocok dengan MySQL. Putaran worker berikutnya melaporkan nol baris baru pada semua tab. Format header, frozen row dan filter diverifikasi melalui Google Sheets API. Halaman daftar peserta diuji melalui Chrome terisolasi pada desktop 1440px dan HP 390px; screenshot lokal di test-results/peserta-jadwal-*.png. Tidak ada jadwal/biodata sumber yang diubah untuk pengujian operasional. Masa pengujian tidak mencakup kamera fisik atau perubahan jadwal operasional melalui wali nyata.

## Startup Windows otomatis pada 17 November 2026

Atas persetujuan pengguna, tugas Windows `PSB Daarul Falah - Portal dan Sheets` dipasang dengan trigger login pengguna, jeda 20 detik, principal Interactive/Limited, tanpa password Windows tersimpan. Action menggunakan pythonw dari virtual environment dan `scripts/startup_portal.py`. Task tidak dibatasi waktu eksekusi, tetap diizinkan pada baterai dan memakai IgnoreNew. Installer/penonaktifan tersedia melalui `scripts/atur-startup.ps1`; panduan di `docs/startup-windows.md`.

Peluncur menunggu database, memeriksa proses proyek untuk menghindari duplikasi, menolak port yang dipakai aplikasi lain, lalu menjalankan server dan worker Sheets tersembunyi. Worker watch mencoba ulang koneksi token tersimpan bila internet belum siap, tanpa browser login otomatis. File lock dan log privat dipertahankan. Layanan database operasional teridentifikasi sebagai Windows MySQL80, sudah Automatic; konfigurasi Laragon/database tidak diubah.

Pengujian Task Scheduler pertama selesai dengan LastTaskResult 0 dan melewati server/worker yang sudah aktif tanpa duplikasi. Uji kedua menghentikan hanya kedua proses proyek kemudian memulai task: server baru aktif, health berhasil, dan worker baru menyelesaikan sinkronisasi MI/MTS/MA. Pengujian login Waitress, peserta, keuangan, pengaturan, aktivitas dan laporan XLSX menghasilkan HTTP 200. Lima belas pengujian khusus startup/Sheets lulus (**15 passed in 1.36s**); dependency check lulus. Pengujian restart Windows atau login ulang secara fisik belum dilakukan; tidak ada reboot otomatis.

Pengujian seluruh aplikasi setelah perubahan: **79 passed, 3 skipped in 52.58s**. Tiga pengujian khusus MySQL dilewati karena tidak menjalankan instance pengujian MySQL terisolasi pada sesi ini; pembacaan MySQL operasional dan health tetap diverifikasi tanpa perubahan data sumber. Hasil lokal disimpan di test-results/startup-pytest.log.

Log peluncur berada di instance/startup-portal.log. PID/log server dan Sheets memakai lokasi yang didokumentasikan. IP Wi-Fi terdeteksi pada peluncuran baru sebagai 192.168.1.36; akses dari perangkat HP fisik belum diverifikasi. Komputer masih harus menyala, tidak tidur, dan mempunyai koneksi internet untuk sinkronisasi. Catatan sebelumnya bahwa startup belum tersedia merupakan kondisi sebelum pembaruan ini.

## Pemeriksaan perubahan MA pada Google Sheets, 17 November 2026

Pengguna melaporkan perubahan MA belum terlihat. Pemeriksaan langsung menemukan worker `sync --watch` aktif dan semua kolom MA yang telah dipetakan cocok dengan database MySQL saat dibaca. Header live `NPSN SEKOLAH` ternyata belum dikenali, sehingga alias tersebut ditambahkan ke school_npsn. NIS LOKAL tetap kolom manual. Delapan pengujian khusus Sheets lulus (**8 passed in 1.23s**), termasuk regresi alias NPSN dan nol di depan.

Sinkronisasi langsung ke spreadsheet yang sudah diotorisasi berhasil untuk MI/MTS/MA tanpa menambah baris ganda. Worker lama dimulai ulang untuk memuat pemetaan baru, kemudian diteruskan di latar belakang setiap 60 detik. PID lokal disimpan di instance/sheets-sync.pid; stdout/stderr di instance/sheets-sync.stdout.log dan instance/sheets-sync.stderr.log. Worker ini tidak otomatis hidup setelah komputer dimulai ulang. Verifikasi pembacaan ulang sel dilakukan tanpa mencetak biodata atau token. Tidak ada perubahan data sumber atau format/header spreadsheet.

## Penyiapan Google Sheets pada 17 November 2026

Pengguna sudah menyiapkan OAuth Desktop lokal dan spreadsheet dengan tab MI, MTS, MA. Service-account key sebelumnya diblokir kebijakan Google Cloud, sehingga koneksi menggunakan OAuth browser loopback dan PKCE. `scripts/google_sheets.py` menyediakan login, preview hanya-baca, sinkronisasi sekali dan `sync --watch` tiap 60 detik. Target spreadsheet berada di .env lokal, kredensial/token hanya pada instance yang diabaikan repository. Dependency OAuth, requests dan filelock sudah dipasang.

Salinan memakai nomor pendaftaran untuk memperbarui baris yang sama dan menambahkan baris baru menurut jenjang. Header dibaca langsung saat dijalankan; kolom NIK/pendidikan/pekerjaan ayah dan ibu dipetakan berdasarkan label lengkap atau urutan kelompok. TTL digabung. Kolom manual seperti NIS LOKAL dibiarkan; header/format tidak dihapus. Nomor ganda atau header ambigu menggagalkan validasi sebelum penulisan. RAW string mempertahankan nol di depan dan mencegah input dianggap formula. Kegagalan append yang ambigu ditangani dengan membaca ulang nomor pada percobaan berikutnya. File lock mencegah dua worker proyek bersamaan.

Ini salinan berkala terpisah dari request wali dan outbox notifikasi. Database tetap sumber utama; Sheets tidak mengubah data aplikasi. Riwayat dan file privat tidak dihapus. Belum ada tugas Windows otomatis saat startup. Batas saat ini 64 kolom/20.000 baris per tab, dan perubahan kolom kunci/pengurutan saat penulisan harus dihindari. Petugas perlu membatasi akses spreadsheet karena bisa memuat biodata anak sesuai header yang dipilih.

Pengujian lokal: **71 passed, 3 skipped in 49.50s**; pengujian khusus MySQL dilewati karena tidak menggunakan instance pengujian MySQL. Tujuh pengujian sinkronisasi lulus untuk pemetaan tiga NIK, kolom manual, pemisahan jenjang, preview tanpa tulis, validasi semua tab sebelum penulisan, retry append tanpa duplikasi, pembatasan data akun/token dan konfigurasi OAuth PKCE. Dependency check lulus. Panduan operator tersedia di `docs/integrasi-google-sheets.md`.

**Batasan terverifikasi:** belum ada persetujuan OAuth operator/token Sheets, sehingga metadata/header live serta penulisan ke spreadsheet asli belum diuji. Tidak ada biodata yang dikirim selama penyiapan. Proses koneksi/sinkronisasi belum dijalankan di latar belakang; langkah berikutnya operator menjalankan `scripts/google_sheets.py login`, menyetujui akses Google, kemudian preview sebelum sync.

Pembacaan langsung sumber operasional pada 17 November 2026 berhasil melalui MySQL/MariaDB: masing-masing satu peserta MI, MTS dan MA terbaca tanpa mencetak identitas/kredensial. Ini mengonfirmasi aplikasi sudah memakai backend MySQL setelah migrasi yang dijalankan pengguna; status aktivasi pada catatan 16 November di bawah merupakan kondisi sebelum migrasi tersebut.

## Perbaikan penghentian server sebelum migrasi

Pada 16 November 2026, pengguna melaporkan skrip migrasi masih mendeteksi server aktif. Skrip PowerShell diperbaiki agar membaca PORT dari .env, memeriksa listener di seluruh alamat, memvalidasi identitas proses, menghentikan proses Python server/induk yang cocok dan worker proyek yang terdeteksi, lalu memakai Wait-Process serta menunggu port bebas sebelum memanggil migrasi. Kegagalan penghentian tidak lagi disembunyikan. Jika port masih terpakai, migrasi dibatalkan tanpa membuat server tambahan.

Mode `-CheckOnly` memeriksa siklus berhenti/port bebas/mulai ulang tanpa migrasi atau perubahan database. Pemeriksaan langsung pada server lokal berhasil. Aktivasi MySQL utama tetap memerlukan isian kredensial lokal; data operasional belum dimigrasikan oleh pemeriksaan ini.

## Persiapan migrasi MySQL pada 16 November 2026

Atas pilihan pengguna, aplikasi mendukung DATABASE_URL untuk MySQL/MariaDB. SQLite tetap tersedia dengan BEGIN IMMEDIATE; MySQL memakai transaksi InnoDB READ COMMITTED dan kunci baris tunggal FOR UPDATE untuk mempertahankan serialisasi mutasi, penerbitan nomor, transaksi uang, serta klaim outbox. Foreign key dan indeks unik bersyarat pembayaran dipertahankan dengan generated columns. Nominal tetap integer; SUM MySQL dikonversi dari Decimal integral tanpa float. Filter tanggal laporan tetap mengikuti WIB. SQL tetap memakai parameter.

Skema ada di `migrations/mysql/001_schema.sql`. `scripts/migrate_mysql.py` meminta kredensial administrator secara lokal, membuat akun aplikasi khusus, mencadangkan database SQLite/file privat/.env, memindahkan data tanpa menghapus sumber, membandingkan seluruh nilai setiap tabel dan baru mengubah DATABASE_URL setelah cocok. Database tujuan berisi tabel ditolak. `scripts/pindah-mysql.ps1` menghentikan server PSB yang identitasnya sesuai dan memulainya kembali. Panduan operasional, pemulihan dan cara melihat biodata melalui phpMyAdmin tersedia di `docs/migrasi-mysql.md`. Perintah backup mendukung snapshot SQL MySQL beserta file privat.

MySQL 8.0.46 tersedia pada komputer. Pengujian memakai instance baru pada loopback port 3307, dengan direktori data terpisah `instance/mysql-test-server/`; layanan MySQL utama pada port 3306 tidak diubah. Uji migrasi membandingkan setiap nilai sumber/tujuan, mempertahankan hash password dan dokumen, menolak pengulangan ke tujuan berisi data, memulihkan dump SQL yang memuat Unicode/tanda kutip/titik koma, dan menjalankan skrip interaktif dengan akun aplikasi khusus. MariaDB, phpMyAdmin, serta migrasi data operasional belum diverifikasi langsung.

SQLite: **64 passed, 3 skipped in 80.76s** (pengujian khusus MySQL dilewati). Pemeriksaan dependensi dan kompilasi lulus. Setelah restart, login Waitress, health, peserta, keuangan, pengaturan, aktivitas dan laporan XLSX menghasilkan HTTP 200.

MySQL **8.0.46** terisolasi pada loopback port 3307: **66 passed, 1 skipped in 185.39s**. Pengujian pemulihan khusus SQLite dilewati pada MySQL dan diganti uji dump/restore MySQL. Empat pengujian khusus adaptor, migrasi/verifikasi/pemulihan, batasan unik pembayaran, serta skrip interaktif dengan akun aplikasi khusus juga lulus (**4 passed in 10.66s**). Database pengujian memakai nama acak dan data fiktif, tidak memakai layanan MySQL utama port 3306. Layanan pengujian dihentikan setelah pemeriksaan.

**Status aktivasi:** aplikasi operasional masih menggunakan SQLite. Akun root MySQL utama membutuhkan password (koneksi tanpa password ditolak). Menunggu host/port/username pengguna dan pemasukan password secara lokal melalui skrip; password tidak diminta di chat. Data lama belum dipindahkan ke layanan MySQL utama, dan tidak ada perubahan kredensial/akun pada layanan itu.

## Pembagian biodata pada 16 November 2026

Biodata mempunyai halaman ringkasan dan empat halaman khusus: Data Santri, Data Orang Tua, Alamat & Kontak, serta Sekolah Asal. Kolom mencakup nomor pendaftaran otomatis, nama, NISN, jenis kelamin, tempat/tanggal lahir, NIK, nomor KK, riwayat penyakit, identitas/pendidikan/pekerjaan ayah dan ibu, alamat/kode pos, telepon/WA, email kontak opsional, serta nama/alamat/NPSN sekolah asal. Menu layanan dan submenu Biodata pada sidebar dapat dibuka/ditutup dengan animasi yang mengikuti preferensi kurangi gerakan. HP menggunakan tab bagian dan menu ringkasan.

Setiap bagian disimpan sendiri tanpa menimpa bagian lain. Kelengkapan empat bagian menentukan tahap biodata pada progres penerimaan. NISN, NIK/KK, kode pos dan NPSN diperiksa jumlah digitnya; angka nol di depan dipertahankan. Pemeriksaan ini bersifat format, bukan verifikasi ke instansi resmi. MI boleh tidak memiliki NISN dan belum pernah sekolah; jika mulai mengisi sekolah asal, seluruh kolom sekolah perlu dilengkapi. Data orang tua yang tidak tersedia memerlukan keterangan; bila keduanya tidak tersedia, nama wali wajib diisi. Email kontak opsional disimpan terpisah dari email aktivasi akun.

Biodata lama tetap terbaca. Biodata lama yang belum terkunci perlu melengkapi kolom baru; kartu yang sudah diterbitkan tetap berlaku. Penguncian setelah penerbitan kartu dan koreksi oleh Pemberkasan dengan alasan/audit tetap berlaku. Admin tidak memperoleh izin mengubah biodata. PDF formulir baru menyertakan kelompok kolom baru; dokumen lama tetap menggunakan snapshot sebelumnya.

Pengujian otomatis: **63 passed in 68.62s**. Meliputi penyimpanan mandiri, kegagalan validasi tanpa kehilangan isian, larangan perubahan nomor, isolasi pemilik/peran, kompatibilitas data lama, penguncian dan audit, serta isi PDF. Integrasi eksternal tidak diuji; tidak ada pengiriman notifikasi nyata.

Pemeriksaan Chrome terisolasi lulus untuk lima peran pada desktop/HP, serta wali pada lebar 320, 390, 768 dan 1440 piksel. Empat halaman biodata, tab aktif, lebar halaman, dan buka/tutup sidebar diuji melalui `scripts/preview_dashboard.py`. Empat formulir Pemberkasan pada HP serta perubahan kolom wajib saat memilih data orang tua tidak tersedia juga diperiksa tanpa menyimpan perubahan ke data lokal. Pratinjau formulir dan submenu diperiksa visual di `test-results/dashboard-preview/`. Server dimulai ulang; alamat Wi-Fi saat pemeriksaan adalah `http://192.168.1.18:5000/login`. Akses dari HP fisik belum diuji dan alamat mengikuti jaringan komputer.

## Pembaruan dashboard aplikasi pada 14 November 2026

Area setelah login memakai palet hijau dengan kartu progres, ikon menu, navigasi bawah pada HP/tablet, dan sidebar pada desktop. Dashboard wali berisi ringkasan serta menu. Setiap layanan peserta membuka rute khusus `/peserta/<id>/menu/<bagian>`. Rincian progres juga dipindahkan ke halaman khusus. Progres enam tahap dihitung dari status pembayaran awal, biodata, jadwal/kartu, hasil terbaru, berkas, dan penyelesaian daftar ulang.

Dashboard Admin Utama, Bendahara, Pemberkasan, serta akun rangkap menyediakan menu sesuai izin. Formulir tunai, antrean verifikasi, riwayat pembayaran, biaya, akun petugas, dan pengaturan lembaga mempunyai halaman masing-masing. Pusat pekerjaan dan bantuan ditambahkan. QR serta tautan pemberitahuan baru mengarah ke halaman layanan terkait.

Hasil pengujian terakhir mencapai **46 passed in 46.36s**, termasuk isolasi halaman baru, pembatasan peran, redirect formulir, dan progres setelah koreksi hasil. Pemeriksaan browser lima peran pada ukuran desktop dan HP lulus. Pemeriksaan animasi, keyboard, klik cepat, validasi, unduhan, mode kurangi gerakan, dan JavaScript nonaktif juga lulus setelah penyesuaian rute formulir.

Rincian menu, progres, dan implementasi tersedia di `docs/desain-dashboard.md`. Pratinjau lokal berada di `test-results/dashboard-preview/`. Konfigurasi IP tetap memakai deteksi otomatis saat server dimulai.

Pada 13 November 2026, error startup WinError 10049 berhasil direproduksi karena LISTEN masih menunjuk IP Wi-Fi sebelumnya. Mode opt-in LISTEN=auto dan BASE_URL=auto ditambahkan untuk memilih IPv4 lokal aktif saat startup, dengan fallback loopback jika jaringan tidak tersedia. Konfigurasi lokal memakai mode ini. run.py menampilkan alamat komputer dan HP pada terminal. Jika jaringan berubah ketika server sudah berjalan, mulai ulang proses agar alamat dideteksi kembali.

Pada 13 November 2026, password seluruh akun yang sudah ada disamakan atas permintaan pengguna. Setiap akun tetap memakai hash scrypt tersendiri. Seluruh sesi lama dan token reset yang belum digunakan dibatalkan. Kredensial lokal diperbarui di instance/akun-demo.txt. Nilai password tidak dicatat dalam dokumentasi repository.

Diperbarui 12 November 2026. Acuan lengkap tersimpan di kebutuhan-sistem.md. Seluruh data pengembangan menggunakan identitas fiktif.

## Hasil yang tersedia

| Tahap | Implementasi | Hasil pemeriksaan |
| --- | --- | --- |
| 1. Fondasi | Flask, SQLite WAL, Jinja, CSS responsif, migrasi, dokumentasi, konfigurasi contoh | Server Waitress berjalan lokal, health dan halaman publik HTTP 200 |
| 2. Akun dan akses | Hash scrypt, sesi server, CSRF, aktivasi/reset sekali pakai, pembatasan permintaan, peran rangkap | Isolasi peserta, aktivasi/reset, sesi, izin peran, dan akses ekspor lulus |
| 3. Pendaftaran | Online/langsung, tautan pemantauan, unggah ulang, pembayaran tunai/transfer, nomor per jenjang, kuitansi | Persetujuan bersamaan, nomor di atas 99, idempotensi, dan alur HTTP lulus |
| 4. Biodata dan tes | Biodata, penguncian, formulir isi/kosong, jadwal Rabu/Minggu, pemindahan/pembatalan, kartu QR, absensi, pemindai kamera | Prasyarat, tanggal ditutup, penguncian, QR tanpa perubahan kehadiran, dan izin pemindai lulus |
| 5. Seleksi | Draf, publikasi per peserta, koreksi beralasan, surat PDF/Word, keabsahan versi | Draf tersembunyi, koreksi, dan pembatalan surat lulus |
| 6. Daftar ulang | Persyaratan per jenjang, KTP wali per dokumen, SKL, tagihan berversi, dua pembayaran, koreksi, bukti penyelesaian | Kelengkapan, cicilan, koreksi idempoten, perhitungan ulang, dan penerbitan bukti baru lulus |
| 7. Dokumen dan laporan | File privat, PDF ber-QR, verifikasi minimal, Excel, pengaturan petugas/biaya/template, riwayat versi berkas | PDF/Word/Excel terbentuk, pembatasan unduhan, formula Excel sebagai teks, dan rollback unggahan lulus |
| 8. Otomatisasi dan operasi | Outbox, simulasi/aktif, autentikasi, klaim sekali per percobaan, callback, rekonsiliasi, pengingat, workflow n8n, backup/restore | Klaim ganda, callback lama, penundaan pengingat, deduplikasi, struktur workflow, dan pemulihan database lulus |

## Pengujian akhir

Perintah `.venv\Scripts\python.exe -m pytest -q --junitxml=test-results\pytest.xml` menghasilkan **36 passed in 43.79s**. Hasil JUnit disimpan lokal di `test-results/pytest.xml`.

Pengujian alur HTTP mencakup pengajuan online, unggah transfer, persetujuan Bendahara, pembuatan akun, aktivasi, login, biodata, pemilihan tanggal, kartu/formulir PDF, absensi, draf/publikasi hasil, penetapan biaya, unggah/pemeriksaan berkas, pelunasan, dan bukti daftar ulang.

`scripts/smoke_local.py` memeriksa server Waitress yang berjalan dengan akun demo lokal. Login mencapai dashboard, dan `/health`, `/peserta`, `/keuangan`, `/pengaturan`, `/aktivitas`, serta ekspor pendaftaran menghasilkan HTTP 200.

`pip check` menghasilkan `No broken requirements found`. Modul Python berhasil dikompilasi. Perintah backup berhasil membuat snapshot database dan direktori unggahan. Pengujian pemulihan menghasilkan `PRAGMA integrity_check = ok` dan mempertahankan keabsahan dokumen.

## Pemeriksaan yang belum terverifikasi

- Halaman masuk telah diperiksa secara visual pada viewport desktop, HP, dan tablet melalui Chrome terisolasi. Pemeriksaan visual halaman lainnya, tata letak cetak PDF/Word, serta pembacaan QR melalui kamera perangkat fisik masih perlu dilakukan.
- Workflow n8n telah diperiksa struktur JSON dan referensi antarnode. Impor serta eksekusi pada instance n8n nyata belum diuji.
- Pengiriman SMTP dan WhatsApp Business API belum diuji karena kredensial, endpoint penyedia, dan template WhatsApp lembaga belum tersedia. Mode lokal memakai simulasi.
- Deployment HTTPS pada server/domain lembaga dan uji beban produksi belum dilakukan. Panduannya tersedia di deployment.md.

## Konfigurasi lembaga yang masih dibutuhkan

Tanggal buka/tutup, WhatsApp panitia, bank/rekening/pemilik, komponen serta nominal biaya daftar ulang setiap jenjang, tenggat cicilan pertama, kop, penandatangan, format nomor surat, dan template resmi diisi setelah ditetapkan lembaga. Formulir dan surat default bertanda DRAF.

Pembayaran transfer menunggu rekening. Pembayaran daftar ulang menunggu penetapan tagihan. Biodata dan pemberkasan dapat dilanjutkan sesuai prasyarat masing-masing.

## Pilihan implementasi untuk ditinjau

- SQLite digunakan pada satu server dengan disk lokal. Mutasi bisnis memakai BEGIN IMMEDIATE dan indeks unik.
- Tahun operasional saat ini 2027/2028. Pengalihan ke tahun berikutnya membutuhkan kebijakan penomoran dan migrasi tambahan.
- Data ayah, ibu, dan wali memakai bidang teks terpisah untuk nama, pekerjaan, serta keterangan yang relevan.
- Template resmi dikelola melalui isi teks, kop teks, penandatangan, dan pola nomor. Editor tata letak visual serta unggahan kop gambar belum tersedia.
- Kedatangan di luar tanggal menampilkan peringatan dan memerlukan konfirmasi petugas. Jadwal tetap mengikuti pemindahan yang dilakukan Pemberkasan.
- Kekurangan setelah dua pembayaran ditangani melalui koreksi transaksi terdahulu dengan alasan dan audit. Panitia masih perlu menetapkan kebijakan pengembalian dana.
- Pemindai kamera memakai BarcodeDetector pada browser yang mendukung. Pencarian manual serta QR bawaan ponsel tersedia sebagai jalur akses.
- Kasus timeout pengiriman yang ambigu membutuhkan rekonsiliasi penyedia sebelum retry. Klaim unik dan nomor percobaan melindungi aplikasi dari webhook/callback berulang, sementara tepat-satu-kali lintas penyedia bergantung pada dukungan penyedia.

## Melanjutkan lintas sesi

1. Baca kebutuhan-sistem.md, hak-akses.md, dan dokumen ini.
2. Gunakan database demo yang sudah ada atau DATA_DIR baru. Kredensial demo berada di instance/akun-demo.txt dan dikecualikan dari repository.
3. Jalankan pengujian setelah perubahan pada aturan bisnis.
4. Lengkapi pemeriksaan visual dan uji integrasi nyata ketika sarana serta kredensial tersedia.
5. Simpan perubahan dan hasil uji terbaru pada dokumen ini.

Server lokal dinyalakan dengan proses latar belakang. PID terakhir berada di instance/server.pid. Log berada di instance/server.stdout.log dan instance/server.stderr.log. Jika server berhenti, jalankan `.venv\Scripts\python.exe run.py` dari direktori proyek.

## Akses HP melalui Wi-Fi lokal

Pada 12 November 2026, akses jaringan lokal diaktifkan atas permintaan pengguna. Server mendengarkan pada `127.0.0.1:5000` dan alamat antarmuka Wi-Fi `192.168.1.57:5000`. Konfigurasi `LISTEN` dan `BASE_URL` tersimpan dalam `.env` lokal yang dikecualikan dari repository. Server sudah dimulai ulang.

Alamat untuk browser HP adalah `http://192.168.1.57:5000/login`. HP harus terhubung pada Wi-Fi yang sama dan komputer menjalankan server. Jika IP komputer berubah, perbarui `LISTEN` serta `BASE_URL` lalu mulai ulang aplikasi.

Pemeriksaan login melalui alamat Wi-Fi berhasil mencapai dashboard. Health, data peserta, keuangan, pengaturan, aktivitas, dan unduhan laporan menghasilkan HTTP 200. Akses loopback juga menghasilkan HTTP 200. Pemeriksaan tersebut dilakukan dari komputer server, sedangkan akses fisik melalui HP menunggu percobaan pengguna.

## Pembaruan desain halaman masuk

Pada 12 November 2026, halaman masuk diperbarui mengikuti referensi komposisi pengguna. Logo asli, foto pondok, serta potongan keenam santri dipasang sebagai aset terpisah. Foto santri diproses menggunakan imagegen bawaan untuk menghasilkan latar transparan. Template HTML dan CSS mengatur formulir krem, aksen emas, gradasi hijau, serta susunan responsif. Banner lingkungan demonstrasi dihapus sesuai permintaan pengguna.

Pengujian terbaru menghasilkan **36 passed in 84.69s**. Pemeriksaan browser terisolasi lulus pada 1440 × 960, 390 × 844, 320 × 740, dan 768 × 1024. Gambar, logo, tautan, tombol kata sandi, lebar halaman, dan jarak teks/foto sudah diperiksa. Pratinjau akhir diperiksa visual dan tersimpan lokal di `test-results/portal-preview/`. Login dan halaman utama juga diuji melalui alamat Wi-Fi.

Catatan aset, prompt imagegen, serta cara mengulang pemeriksaan tersedia di `docs/desain-login.md`. Server lokal telah dimulai ulang untuk menggunakan halaman terbaru.

## Animasi antarmuka dan pemulihan akses

Pada 12 November 2026, efek ringan ditambahkan melalui `static/motion.css` dan `static/motion.js`, lalu dimuat pada template dasar seluruh halaman. Konten tujuan muncul dengan perubahan opacity dan perpindahan vertikal 6 px selama 240 milidetik. Navigasi bagian dalam halaman memakai pengguliran halus. Formulir dalam elemen details membuka/menutup selama 220 milidetik. Tombol memberi respons tekan kecil selama 100 milidetik.

Preferensi `prefers-reduced-motion` menonaktifkan gerakan. Animasi details dapat diselesaikan saat klik berulang, perubahan ukuran layar, perubahan preferensi gerakan, dan perpindahan halaman. Halaman yang dipulihkan melalui riwayat browser mendapat efek masuk singkat. Implementasi memakai CSS dan API animasi browser. [Dokumentasi Web Animations](https://developer.mozilla.org/en-US/docs/Web/API/Element/animate), [dokumentasi pageshow](https://developer.mozilla.org/en-US/docs/Web/API/Window/pageshow_event)

Pengujian aplikasi menghasilkan **36 passed in 28.72s**. Skrip `scripts/check_motion.py` memeriksa perpindahan halaman, kembali, efek masuk, buka-tutup details, keyboard, klik cepat, validasi formulir, respons tombol, unduhan PDF, serta perubahan preferensi gerakan. Skrip juga memeriksa fungsi dasar ketika JavaScript dimatikan. Pemeriksaan tampilan empat ukuran melalui `scripts/preview_portal.py` tetap lulus.

Ketika pengguna melaporkan “failed to load page”, pemeriksaan menunjukkan proses server Python sudah berhenti. Kedua alamat loopback dan Wi-Fi gagal menerima koneksi, sementara log server tidak berisi traceback. IP Wi-Fi masih 192.168.1.57. Server dinyalakan kembali, dan halaman login pada alamat Wi-Fi kembali menghasilkan HTTP 200. Penyebab proses sebelumnya berhenti belum diketahui dari log yang tersedia.

Jika server lokal berhenti lagi, jalankan `.venv\Scripts\python.exe run.py` dari terminal pada direktori proyek dan biarkan proses tersebut berjalan selama aplikasi digunakan.

Pada pemeriksaan lanjutan, alamat Wi-Fi berubah menjadi **10.149.158.185/24** sementara server masih mendengarkan alamat lama. Hal ini menyebabkan timeout melalui 192.168.1.57 walaupun loopback tetap aktif. `BASE_URL` dan `LISTEN` pada `.env` sudah diperbarui, lalu server dimulai ulang. **Alamat aktif terbaru adalah `http://10.149.158.185:5000/login`.** Pemeriksaan login, health, data peserta, keuangan, pengaturan, aktivitas, dan ekspor berhasil dengan HTTP 200 melalui alamat baru. Jika komputer berpindah Wi-Fi lagi, alamat akses HP perlu mengikuti IP jaringan yang baru.

Pemeriksaan animasi akhir lulus pada desktop 1440 × 960 serta HP 390 × 844, termasuk mode kurangi gerakan dan JavaScript nonaktif. Efek tekan tombol, validasi formulir, unduhan PDF, keyboard, dan klik berulang telah diverifikasi melalui Chrome terisolasi.
