# Integrasi n8n dan pemberitahuan

Database aplikasi menyimpan kejadian pada transaksi yang sama dengan perubahan bisnis. Email dan WhatsApp memiliki baris outbox berbeda dengan indeks unik `(event_key, channel)`. Pembayaran tetap tersimpan ketika penyedia pesan bermasalah.

## Mode pengoperasian

`.env` menyediakan `NOTIFICATION_MODE=simulation`. Jalankan `python manage.py worker` untuk mengubah kejadian yang memenuhi syarat menjadi `simulasi`. Pesan dapat diperiksa melalui halaman Aktivitas atau `python manage.py notifications`. Status ini berarti pesan hanya diproses lokal.

Mode `active` memerlukan URL webhook HTTPS, token webhook, token integrasi aplikasi, serta konfigurasi n8n dan penyedia. Respons HTTP webhook hanya menandakan kejadian diterima. Status `berhasil` baru diberikan setelah callback pengiriman membawa identitas penyedia. Pada email, keberhasilan berarti SMTP menerima pesan. Pada WhatsApp, keberhasilan berarti API menerima permintaan dan memberikan message ID. Status terkirim ke perangkat atau dibaca membutuhkan perluasan callback penyedia.

## Mengimpor workflow

Impor `n8n/psb-notifikasi.json` melalui Import from File. Workflow disimpan nonaktif. Struktur JSON diperiksa lokal, sedangkan impor dan eksekusi pada instance n8n nyata masih membutuhkan pengujian dengan kredensial lembaga.

Workflow menjalankan rangkaian webhook masuk, pemeriksaan status terkini di aplikasi, pemilihan kanal, pengiriman, dan callback. Pemeriksaan status membuat klaim unik untuk pasangan kejadian dan nomor percobaan. Duplikasi webhook pada percobaan yang sama memperoleh `send=false`.

Dokumentasi resmi n8n menjelaskan perbedaan URL webhook uji dan produksi serta pilihan Header Auth. Gunakan URL produksi setelah workflow diaktifkan. [Dokumentasi Webhook n8n](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/)

## Pemetaan kredensial

| Lokasi | Nilai yang harus diatur |
| --- | --- |
| Aplikasi `BASE_URL` | Alamat HTTPS portal yang dapat diakses wali dan n8n |
| Aplikasi `N8N_WEBHOOK_URL` | Production URL node Kejadian PSB |
| Aplikasi `N8N_WEBHOOK_TOKEN` | Rahasia acak khusus autentikasi webhook masuk |
| Aplikasi `INTEGRATION_TOKEN` | Rahasia acak lain untuk endpoint integrasi aplikasi |
| Node Kejadian PSB | Header Auth dengan nama `Authorization`, nilai `Bearer <N8N_WEBHOOK_TOKEN>` |
| Node Periksa status terbaru dan kedua callback | Header Auth dengan nama `Authorization`, nilai `Bearer <INTEGRATION_TOKEN>` |
| Node Kirim email SMTP | Kredensial SMTP lembaga dengan TLS |
| Node Kirim WhatsApp Business | Header Auth dengan nama `Authorization`, nilai `Bearer <token penyedia>` |
| Variabel n8n `PSB_BASE_URL` | Alamat portal yang sama dengan BASE_URL |
| Variabel n8n `PSB_EMAIL_FROM` | Alamat pengirim terverifikasi |
| Variabel n8n `PSB_WHATSAPP_MESSAGES_URL` | Endpoint messages WhatsApp Business API sesuai versi dan phone-number ID penyedia |
| Variabel n8n `PSB_WHATSAPP_TEMPLATE` | Nama template yang disetujui penyedia |
| Variabel n8n `PSB_WHATSAPP_LANGUAGE` | Kode bahasa template, default `id` |

Workflow menyediakan format permintaan template WhatsApp Cloud API dengan satu parameter body. Gunakan template yang disetujui untuk konten pemberitahuan lembaga. Sesuaikan node untuk template dengan beberapa parameter atau penyedia lain. Pengaturan tersebut memerlukan template dan kredensial nyata yang belum diberikan.

Jangan meletakkan token dalam repository, URL publik, atau payload webhook. Node tujuan aplikasi menggunakan `PSB_BASE_URL` yang dikonfigurasi administrator, sehingga alamat tujuan tidak mengikuti input webhook.

## Endpoint integrasi

Semua endpoint integrasi memakai `Authorization: Bearer <INTEGRATION_TOKEN>` dan hanya dapat dipanggil melalui layanan tepercaya.

`POST /integrasi/event/<event_id>` mengambil data pengiriman satu kali per percobaan. Respons berisi `send`, `event_id`, `attempt`, `channel`, `destination`, `message`, dan `idempotency_key`. Jika status berubah atau sudah pernah diklaim, `send=false`.

`POST /integrasi/callback` menerima contoh berikut.

```json
{
  "event_id": "UUID kejadian",
  "attempt": 1,
  "status": "berhasil",
  "delivery_id": "identitas dari penyedia"
}
```

Untuk kegagalan yang dipastikan terjadi sebelum penyedia menerima pesan, kirim `status=gagal`, `safe_to_retry=true`, serta `error`. Worker melakukan maksimal lima percobaan dengan jeda eksponensial. Kegagalan yang belum pasti memakai `safe_to_retry=false`, dan memerlukan pemeriksaan melalui riwayat penyedia.

Callback keberhasilan berulang idempoten. Nomor `attempt` wajib sesuai percobaan yang aktif untuk mencegah callback lama mengubah percobaan baru. Percobaan webhook/pengiriman menggunakan event ID tetap. Worker mengklaim kejadian di dalam transaksi SQLite sebelum melakukan jaringan. Pesan yang sudah berhasil tidak diproses lagi.

## Pemulihan dan duplikasi

Timeout setelah pengiriman dapat terjadi ketika penyedia sudah menerima pesan. Kejadian tersebut tetap berstatus `diproses` disertai catatan. Administrator memeriksa log n8n dan penyedia, lalu memakai rekonsiliasi pada halaman Aktivitas untuk mencatat berhasil atau mengizinkan percobaan ulang dengan alasan.

Workflow mematikan retry otomatis pada node pengiriman. Retry callback aman karena endpoint idempoten. Klaim unik mencegah dua eksekusi n8n mengirim kejadian pada percobaan yang sama. Jaminan tepat-satu-kali lintas jaringan tetap bergantung pada dukungan idempotensi penyedia dan rekonsiliasi hasil yang ambigu.

## Pengingat

Jalankan `python manage.py reminders` setiap hari setelah 00.05 WIB, atau setiap jam agar kejadian tetap dibuat setelah gangguan server. Indeks unik menghindari penambahan berulang. Jalankan worker setiap menit menggunakan penjadwal sistem.

- H-1 tes dihitung dari tanggal terpilih. Pembatalan atau pemindahan diperiksa ulang sebelum pengiriman.
- H-7 pelunasan dijadwalkan 23 September 2027.
- H-1 pelunasan dijadwalkan 29 September 2027.
- Peserta harus masih Lulus dan memiliki sisa tagihan.
- Bukti yang menunggu verifikasi menunda pengingat satu jam. Worker memeriksa ulang sampai status jelas.
- Sisa tagihan dibaca ulang saat n8n meminta data pengiriman.

## Pemetaan kejadian

| Kejadian | Kanal |
| --- | --- |
| Pengajuan online dan nomor diterbitkan | Email dan WhatsApp |
| Penolakan transfer pendaftaran/daftar ulang | Email dan WhatsApp |
| Aktivasi dan reset | Email |
| Jadwal pertama | WhatsApp |
| Pemindahan/pembatalan dan H-1 tes | Email dan WhatsApp |
| Publikasi hasil | WhatsApp |
| Koreksi hasil | Email dan WhatsApp |
| Berkas perlu diperbaiki | WhatsApp |
| Koreksi pembayaran | Email dan WhatsApp |
| Pengingat pelunasan | Email dan WhatsApp |
| Daftar ulang selesai | Email dan WhatsApp |

Setiap pesan menyertakan nama peserta dan nomor pendaftaran. Sebelum nomor diterbitkan, pesan menyebut referensi pengajuan serta keterangan nomor belum diterbitkan.
