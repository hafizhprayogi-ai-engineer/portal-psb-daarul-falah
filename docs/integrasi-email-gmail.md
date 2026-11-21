# Pengiriman email Gmail

Portal dapat mengirim email aktivasi dan pemulihan kata sandi langsung ke alamat wali melalui akun Gmail lembaga. Pengiriman WhatsApp tetap simulasi sampai penyedia WhatsApp diaktifkan terpisah.

## Yang disiapkan

Gunakan satu akun Gmail khusus, misalnya akun PSB lembaga. Aktifkan Verifikasi 2 Langkah pada akun tersebut, lalu buka halaman Google Account → Security → App passwords. Buat App Password baru dengan nama `Portal PSB`, salin kode yang diberikan Google, dan simpan di tempat aman. Kode ini berbeda dari kata sandi Gmail utama.

Jangan menempelkan App Password ke chat, Google Sheets, repository, atau file selain `.env` lokal.

## Mengaktifkan di aplikasi

Buka file `.env` pada folder proyek dan tambahkan atau lengkapi bagian berikut. Ganti hanya nilai di sebelah kanan tanda sama dengan.

```dotenv
EMAIL_DELIVERY_MODE=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=alamat-gmail-pengirim@gmail.com
SMTP_PASSWORD=app_password_16_karakter_dari_google
SMTP_FROM=alamat-gmail-pengirim@gmail.com
SMTP_STARTTLS=true
```

Simpan file. Jangan mengubah `NOTIFICATION_MODE=simulation`; nilai tersebut tetap menjaga WhatsApp dan webhook lain dalam mode simulasi. Email dikirim langsung hanya karena `EMAIL_DELIVERY_MODE=smtp`.

Mulai ulang portal dan worker agar konfigurasi baru terbaca:

```powershell
.\.venv\Scripts\python.exe scripts\startup_portal.py --restart
```

Peluncur menjalankan worker notifikasi setiap 30 detik. Lognya berada di `instance/notifications.stdout.log` dan `instance/notifications.stderr.log`.

## Memeriksa hasil

1. Buat akun wali menggunakan alamat email yang dapat Anda buka, atau gunakan menu **Kirim ulang aktivasi**.
2. Tunggu maksimal 30 detik, lalu periksa Kotak Masuk dan folder Spam Gmail penerima.
3. Login sebagai Admin Utama, buka **Aktivitas**, lalu pastikan baris kanal `email` berstatus `berhasil`.

Status `berhasil` berarti server SMTP Gmail menerima pesan. Penerimaan di perangkat penerima dapat tertunda atau masuk Spam. Jika status `gagal` atau `diproses`, buka detail pada Aktivitas dan periksa konfigurasi tanpa membagikan rahasia. Kesalahan yang berpotensi sudah diterima Gmail tidak dikirim ulang otomatis agar wali tidak menerima email ganda; Admin dapat melakukan rekonsiliasi dari halaman tersebut.

Untuk berhenti mengirim email nyata, ubah kembali menjadi:

```dotenv
EMAIL_DELIVERY_MODE=simulation
```

Kemudian jalankan ulang peluncur yang sama.
