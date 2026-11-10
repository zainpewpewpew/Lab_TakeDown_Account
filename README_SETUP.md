# Ghoster.ai — npm run setup

Ghoster.ai sekarang memakai **Terminal CLI saja** sebagai layar utama, bukan dashboard website.
Jalankan dari folder repository:

```bash
git pull origin main
npm run setup
```

## Menu

```text
╭──[ GHOSTER.AI // MAIN CONTROL ]────────────────────
 [1] URL TARGET     Buka URL web lab pribadi
 [2] CONFIG         Headless OFF / Proxy OFF
 [0] EXIT           Tutup Ghoster.ai
╰────────────────────────────────────────────────────
```

1. **URL TARGET** — masukkan domain atau URL (misalnya `labprivate.com`, `localhost:3000`, atau `192.168.1.10:8080`). Input tanpa skema diubah otomatis menjadi `https://` untuk domain biasa atau `http://` untuk localhost/IP privat. Setelah itu masukkan identifier **dummy** berupa username/email/nomor. Jika Proxy ON, program meminta URL proxy sebelum menjalankan Chromium.
2. **CONFIG** — submenu `1 HEADLESS ON/OFF`, `2 PROXY ON/OFF`, `0 BACK`. Default keduanya OFF. Pengaturan berlaku selama sesi menu berjalan.
0. **EXIT** — akhiri launcher.

Jika folder `.venv` belum tersedia, launcher otomatis membuat environment, memasang dependensi dan Chromium Playwright. Prasyarat: Node.js 18+ dan Python 3.10+.

## Proxy

Gunakan `host:port`, `http://host:port`, atau `socks5://host:port`. Format `http://user:password@host:port` juga didukung. Password proxy tidak dicetak di log. Proxy harus mempunyai jalur jaringan ke URL lab privat (remote proxy sering tidak bisa mencapai localhost perangkat Anda).

## Tampilan Terminal

Launcher memakai warna cyber cyan, magenta dan hijau, efek boot, spinner, status timestamp dan log setiap tahap. Animasi dimatikan bila output bukan TTY, `NO_COLOR` disetel, atau `REDUCED_MOTION=1`.

```bash
npm run setup -- --no-animation
npm run setup -- --check
npm run setup -- --preview
npm run test:setup
```

## Batasan

Automasi pemulihan dummy hanya boleh dijalankan sekali per pengujian pada localhost, IP privat atau host lab ber-resolusi privat. Domain publik dapat dibuka untuk **inspeksi manual saja**; script tidak menekan permintaan pemulihan pada domain publik. Domain layanan Instagram/Meta ditolak. Headless ON tidak cocok untuk tantangan verifikasi manual; pilih OFF bila pengujian menampilkan tantangan.

Identifier dikirim ke proses Python melalui environment sementara agar tidak muncul sebagai argumen command-line. Hasil uji ada di `output/web_lab_result.json` dan screenshot `output/web_lab_last.png`. Jangan memasukkan kredensial asli.
