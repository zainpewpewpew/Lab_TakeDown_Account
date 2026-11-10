# Ghoster.ai — Recovery UI Lab Runner

Skrip ini menguji SATU KALI alur UI Forgot Password pada website lab pribadi (localhost/IP LAN privat). Tidak dipakai untuk Instagram/Meta atau situs publik. Identifier dummy dimasukkan dari Terminal dan disamarkan dalam log.

## Persiapan macOS

~~~bash
cd ~/Desktop/Lab_TakeDown_Account
git pull origin main
python3 -m venv .venv   # hanya jika belum ada
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
~~~

Membutuhkan Node.js >= 18 dan Python >= 3.10.

## Varian A — Chromium biasa

~~~bash
npm run recovery:lab
~~~

Terminal meminta URL lab privat (contoh: http://127.0.0.1:3000/) serta username/email/nomor HP dummy. Chromium menjalankan satu alur lalu menutup tab/browser. Tidak ada loop otomatis. Jika memerlukan verifikasi manusia, selesaikan secara manual dan tekan ENTER di Terminal.

Opsional, untuk pengujian tanpa verifikasi manual:

~~~bash
npm run recovery:lab -- --headless
~~~

## Varian B — Multilogin X

Buka Multilogin X dan jalankan terlebih dahulu SATU profil Mimic yang Anda kendalikan dengan automation_type=playwright. Catat port CDP lokal yang diberikan Start Browser Profile (data.port).

~~~bash
npm run recovery:multilogin:lab
~~~

Terminal meminta URL lab privat, identifier dummy, serta alamat CDP profil Multilogin yang sudah berjalan, misalnya http://127.0.0.1:50468 (sesuaikan port).

Atau gunakan variabel lingkungan:

~~~bash
export LAB_MULTILOGIN_CDP="http://127.0.0.1:50468"
npm run recovery:multilogin:lab
~~~

Varian ini memakai Playwright connect_over_cdp, membuat satu tab pengujian pada context yang sudah berjalan, lalu menutup tab serta melepas sambungan. Profil Multilogin utama tidak dihentikan. Tidak diperlukan App Secret atau password Multilogin dalam program ini. Alamat CDP dibatasi ke localhost/127.0.0.1 dan tidak menerima endpoint remote.

Catatan: proxy eksternal pada profil Multilogin mungkin tidak bisa menjangkau server lab yang berjalan pada localhost Mac. Gunakan routing jaringan privat yang benar; jangan menonaktifkan pembatasan domain.

Referensi: https://playwright.dev/python/docs/api/class-browsertype#browser-type-connect-over-cdp dan https://github.com/multilogin-automation/multilogin-x-getting-started/blob/main/docs/ARCHITECTURE.md

## Uji simulator offline

Fitur --demo menjalankan website simulator localhost secara otomatis. Simulasi tidak mengirim email/SMS sungguhan.

~~~bash
npm run recovery:lab -- --demo --identifier demo@lab.test
npm run recovery:lab -- --demo --demo-options sms --identifier demo@lab.test
npm run recovery:lab -- --demo --demo-options none --identifier demo@lab.test
npm run recovery:lab -- --demo --demo-challenge --identifier demo@lab.test
~~~

Untuk --demo-challenge, klik I completed verification di Chromium lalu tekan ENTER di Terminal.

## Alur yang dicatat ke Terminal

1. STEP 1: Mulai Chromium atau terhubung dengan CDP Multilogin.
2. STEP 2: Navigasi ke URL lab privat sampai DOM siap.
3. STEP 3: Klik Forgot password / Lupa kata sandi (prioritas role/teks, href cadangan).
4. STEP 4: Isi username/email/nomor HP dummy yang disamarkan di log.
5. STEP 5: Klik Continue / Lanjutkan pertama.
6. STEP 6a: Prioritas pilihan Get link via email.
7. STEP 6b: Fallback Get link via SMS ketika email tidak ada; berhenti jika keduanya absen.
8. STEP 6c: Klik Continue kedua untuk mengonfirmasi metode.
9. STEP 7: Pause verifikasi manusia sampai operator menyelesaikannya dan menekan ENTER.
10. STEP 8: Periksa teks konfirmasi kanal yang dipilih, klik OK/Done/Selesai jika ada.
11. FINISH: Tutup tab/browser dan simpan screenshot serta JSON.

Jeda antaraksi dipilih acak 1–3 detik agar pengujian UI berjalan bertahap, bukan untuk menghindari deteksi:

~~~bash
npm run recovery:lab -- --min-delay 1 --max-delay 3
~~~

Artefak pada folder output/recovery_lab:
- recovery_lab_result.json (status dan log berurutan, waktu UTC)
- recovery_lab_last.png (screenshot lokal)

Status CONFIRMATION_VISIBLE artinya teks sukses terlihat pada website lab; bukan bukti pengiriman email/SMS sungguhan. Status lain: NO_CHANNEL, UNCONFIRMED, ERROR, CANCELLED.

## Tes

~~~bash
python tests_recovery_lab_cli.py
python tests_web_lab_flow.py
npm run test:setup
~~~

Tes unit tidak mengakses Instagram. Untuk uji browser end-to-end gunakan --demo setelah Chromium Playwright tersedia.

## Batas keamanan

Skrip menolak domain publik, termasuk Instagram dan Meta, sebelum Chromium dibuka. Tidak ada loop reset, login otomatis, pemecahan verifikasi manusia, pengambilan cookie, rotasi proxy, maupun bypass batas platform.
