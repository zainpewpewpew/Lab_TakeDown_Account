# Ghoster.ai — Cyber Lab Terminal

Ghoster.ai adalah launcher Node.js untuk fitur lab yang sudah ada di repository ini. Mulai dari satu menu interaktif dengan `npm run setup`, tanpa tambahan dependensi npm.

## Prasyarat

Node.js 18+ dan Python 3.10+. Pada macOS, jalankan Terminal di root repository.

```bash
git pull origin main
npm run setup
```

Pilih **[1] INITIALIZE** pada pemakaian pertama agar Python virtual environment, paket pip, dan Playwright Chromium disiapkan.

## Menu

- **1 · INITIALIZE**: siapkan Python virtual environment dan Chromium
- **2 · SESSION LAB**: pengujian keamanan sesi pada simulator offline
- **3 · PRIVATE FLOW**: satu alur UI di website lab privat, dengan URL dan identifier dummy diminta di Terminal
- **4 · WEB DASHBOARD**: buka dashboard lama pada localhost
- **5 · DIAGNOSTICS**: cek lingkungan dan jalankan tes Python
- **0 · SHUTDOWN**: keluar

## Desain terminal

Banner Ghoster.ai, efek boot dengan progress bar, log timestamp, panel menu, warna cyan/pink/hijau, dan status success/error. Animasi hanya ditampilkan bila terminal mendukung ANSI. Pengguna dapat memilih `npm run setup -- --no-animation`; atau menjalankan `REDUCED_MOTION=1 npm run setup`. Output Python diteruskan secara langsung sehingga prompt verifikasi manual tetap terbaca.

## Perintah tambahan

```bash
npm run setup -- --check
npm run setup -- --help
npm run test:setup
```

## Batasan

Mode otomatis hanya untuk lab lokal atau jaringan privat yang Anda kendalikan. Runner tidak mengirim permintaan reset massal ke layanan Instagram asli. Tidak ada tugas background dari launcher. Konfigurasi proxy opsional tetap mengikuti variabel `LAB_PROXY_SERVER`, `LAB_PROXY_USERNAME`, dan `LAB_PROXY_PASSWORD` milik engine Python.
