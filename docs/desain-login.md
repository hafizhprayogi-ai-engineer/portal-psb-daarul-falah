# Desain halaman masuk

Pembaruan 12 November 2026 mengikuti komposisi referensi pertama pengguna. Teks, navigasi, formulir, dan tombol dirender sebagai HTML. Susunan desktop memakai sambutan di kiri dan kotak login di kanan. Pada lebar hingga 900 px, sambutan, foto santri, dan formulir disusun vertikal.

## Aset yang digunakan

| Input pengguna | Peran | Aset tersimpan |
| --- | --- | --- |
| Daarul Falah Student Admissions Portal.png | Referensi komposisi dan warna | Acuan visual saat implementasi |
| logo_daarul_falah_2 (1).png | Logo asli pada header dan ikon tab | static/images/logo-daarul-falah.png |
| WhatsApp Image 2026-07-05 at 18.42.25.jpeg | Foto pondok sebagai latar | static/images/pondok-original.jpeg |
| IMG-20260107-WA0039.jpg.jpeg | Keenam santri sebagai objek depan | static/images/santri-cutout.png |

Foto pondok memiliki orientasi menyamping pada berkas asal. CSS memutar tampilannya 90 derajat berlawanan arah jarum jam. Gradasi hijau di kiri membantu keterbacaan teks. Gradasi radial hijau dan krem memberi pemisahan visual di belakang kotak login.

Logo disalin dari berkas pengguna dengan transparansi aslinya. Potongan keenam santri dibuat menggunakan tool imagegen bawaan dalam mode penyuntingan `background-extraction`. PNG hasilnya berukuran 1736 × 906 dengan kanal alpha 0–255. Aset hasil disimpan di dalam proyek.

## Prompt akhir pengolahan foto santri

```text
Use case: background-extraction. Asset type: transparent foreground cutout for a school admissions website. Input image is the edit target, an original group photo of six Indonesian female students wearing black hijabs and green or blue batik, holding brochures. Remove ONLY the background (sky, trees, building, path and plants), including spaces between the people. Retain all six people in their original left-to-right order, exact faces, expressions, identities, original clothing, hands, poses and brochures. Preserve photographic detail and original proportions without beautification or redrawing. Crop away the large empty sky and trim close to the group. Show the same visible people from the tops of their heads down to the original lower crop, no added feet. Output a wide landscape cutout with an actual transparent alpha background. No colored backdrop, no checkerboard baked into pixels, no shadows, no added text, no watermark. This is a faithful cutout extraction, not a new group photograph.
```

## Perubahan antarmuka

- Halaman `/login` menggunakan `templates/login.html` dan `static/portal.css`.
- Logo asli tersedia pada header semua halaman.
- Banner lingkungan demonstrasi dihapus dari template dasar sesuai permintaan pengguna.
- Kotak login berwarna krem dengan aksen emas, tombol hijau, dan ikon input yang dibuat menggunakan CSS.
- Tombol mata menampilkan atau menyembunyikan kata sandi dan menyediakan label aksesibilitas.
- Header HP menampilkan logo, nama lembaga, Informasi PSB, Daftar akun, dan Masuk portal.
- Formulir menyediakan autocomplete username/password dan ukuran teks input 16 px.
- Tautan bantuan, pemulihan, aktivasi, dan pembuatan akun tersedia pada ukuran layar kecil.

## Verifikasi

Pengujian aplikasi menghasilkan 36 lulus. Pemeriksaan login melalui alamat Wi-Fi berhasil mencapai dashboard dan halaman utama menghasilkan HTTP 200.

`scripts/preview_portal.py` menggunakan Chrome terisolasi melalui Playwright. Skrip memeriksa pemuatan gambar, logo, heading login, penghapusan banner, lebar halaman, pemisahan teks/foto, serta tombol tampil/sembunyi kata sandi. Hasil diperiksa pada ukuran 1440 × 960, 390 × 844, 320 × 740, dan 768 × 1024. Pratinjau akhir tersimpan di `test-results/portal-preview/` dan telah diperiksa secara visual.

Untuk mengulang pemeriksaan, pasang `requirements-dev.txt`, lalu jalankan perintah berikut saat server aktif.

```powershell
.\.venv\Scripts\python.exe scripts\preview_portal.py
```

Halaman dapat dibuka melalui `http://127.0.0.1:5000/login` pada komputer atau alamat Wi-Fi yang tercatat sebagai `BASE_URL` pada `.env`. Alamat Wi-Fi terakhir adalah `http://10.149.158.185:5000/login`. Pemeriksaan viewport memakai browser desktop terisolasi. Pengujian langsung pada perangkat HP fisik dapat dilakukan pengguna melalui alamat Wi-Fi tersebut.
