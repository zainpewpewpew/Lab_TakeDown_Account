# Ghoster.ai — Web Dashboard

Website lokal untuk menjalankan pengujian **satu alur** recovery pada situs lab yang Anda miliki, dengan **Python + Playwright**. Dashboard sendiri berjalan di Mac Anda pada `http://127.0.0.1:8787` dan tidak memakai layanan cloud. Program ini bukan alat untuk mengirim reset password ke Instagram atau pihak ketiga.

## Fitur

- Dashboard futuristik tanpa instalasi npm/frontend terpisah.
- Input URL situs lab pribadi (`localhost`, IP LAN privat, atau hostname internal yang resolve privat).
- Tombol Start / Stop; maksimal **satu pekerjaan berjalan** dan cooldown 15 detik antar-start.
- Pilihan demo bawaan, termasuk email+SMS, email saja, SMS saja, dan tanpa opsi.
- Simulasi halaman "Forgot password?" → identifier dummy → "Continue" → email/SMS → konfirmasi → "OK".
- Jika terlihat "Help us confirm it's you", operator menyelesaikan pemeriksaan di Chromium, lalu menekan tombol **Verifikasi selesai — Lanjut** di dashboard.
- Log berurutan yang diperbarui tiap detik, status run, dan screenshot setelah run selesai.
- Server lokal hanya bind `127.0.0.1`; form kontrol dilindungi token sesi, validasi Host/Origin, dan penolakan URL publik.
- Dukungan proxy lewat variabel lingkungan `LAB_PROXY_SERVER`, `LAB_PROXY_USERNAME`, dan `LAB_PROXY_PASSWORD` dari runner sebelumnya. Proxy eksternal tidak selalu dapat menjangkau server di localhost.

## Memulai di macOS

```bash
cd ~/Desktop/Lab_TakeDown_Account
git pull origin main
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
python dashboard.py
```

Browser akan membuka `http://127.0.0.1:8787/`. Untuk tes pertama, gunakan **Demo lokal** dan identifier `demo@lab.test`.

Bisa juga menjalankan starter:

```bash
chmod +x START_DASHBOARD.command
./START_DASHBOARD.command
```

Starter membutuhkan Python 3 dan akan menginstal dependensi Chromium pada setup pertama. Jika macOS menolak menjalankan `.command`, jalankan melalui Terminal.

## Mode website lab privat

1. Jalankan web lab Anda di mesin sendiri atau jaringan privat.
2. Pilih **Web lab privat** dan masukkan URL misalnya `http://127.0.0.1:3000/` atau `http://192.168.1.20:3000/`.
3. Isi username/email/nomor HP **dummy** yang disediakan untuk tes lab.
4. Pilih jeda per langkah dan klik **Mulai Test**.
5. Awasi Chromium dan log. Jika dibutuhkan verifikasi manual, klik **Verifikasi selesai — Lanjut** setelah menyelesaikannya di browser yang dibuka worker.
6. Lihat hasil di `output/dashboard/<run_id>/web_lab_result.json` dan screenshot `web_lab_last.png`.

Dashboard tidak mengunggah log, cookie, atau screenshot ke cloud. Jangan memasukkan kredensial nyata. Jika web lab memakai API eksternal atau aset lintas-origin, runner yang ada memblokir permintaan tersebut; sediakan konten situs lab secara self-hosted dan pastikan semua interaksi tetap di origin lab.

## Pengujian

```bash
python tests.py
python tests_web_lab_flow.py
python tests_dashboard.py
```

Untuk menjalankan tanpa otomatis membuka dashboard: `python dashboard.py --no-open`. Untuk mengganti port: `python dashboard.py --port 8899`.

> Perlu Python backend berjalan untuk mengendalikan Chromium. Website statis saja tidak dapat mengendalikan browser lokal dan proxy secara langsung karena batasan keamanan browser.

## Catatan implementasi

- `dashboard.py`: server HTTP loopback, validasi, subprocess worker, dan API status.
- `dashboard_static/index.html`: UI responsif dengan tema cyber.
- `mock_recovery_lab.py`: situs demo lokal, **tidak mengirim email atau SMS**.
- `web_lab_flow.py`: runner Playwright yang sudah ada pada repository; tidak diubah oleh implementasi dashboard ini.
- `tests_dashboard.py`: pengujian validasi URL, penolakan akses, UI, dan demo.

Perbandingan open source: [Playwright](https://playwright.dev/python/docs/intro), [Playwright Trace Viewer](https://playwright.dev/python/docs/trace-viewer-intro), [Browserless](https://docs.browserless.io/enterprise/open-source), [Selenium Grid](https://www.selenium.dev/documentation/guides/docker_and_grid/), [AgentBrowser](https://github.com/smouj/agent-browser).

## Account Checker — pemeriksaan akun pada web lab pribadi

Panel **04 / Account Checker** kini tersedia pada halaman utama dashboard. Fitur ini *read-only* dan memeriksa **satu akun dummy per klik**. Tidak menguji password, mengirim email/SMS reset, atau memeriksa keberadaan username di Instagram sungguhan.

**Mode Demo lokal:** isi `demo_account` (active), `needs.verify` (verification_required), `disabled.demo` (disabled), atau nama lain (not found). Tidak membutuhkan Chromium atau koneksi jaringan.

**Mode API web lab privat:** pemilik website perlu menyediakan endpoint admin `GET /api/lab/account-status?username=<username>` yang memerlukan `Authorization: Bearer <token>`. Jalankan dashboard setelah menyetel environment token pada komputer lokal:

```bash
# Jangan commit token ke repo. Jalankan di terminal lokal.
read -s "LAB_ACCOUNT_CHECK_TOKEN?Token API admin lab: "
export LAB_ACCOUNT_CHECK_TOKEN
python dashboard.py
```

*Contoh respons API milik web lab Anda*:

```json
{
  "username": "demo_account",
  "exists": true,
  "account_status": "active",
  "session_status": "active"
}
```

Nilai yang diterima untuk `account_status`: `active`, `disabled`, `verification_required`, `unknown`.
Nilai untuk `session_status`: `active`, `expired`, `revoked`, `unknown`.
Jika akun tidak ditemukan, isi `exists: false` dan kedua status `unknown`. Username harus sama persis dengan yang diminta (huruf kecil).

Masukkan hanya **origin localhost atau alamat IP privat** (misalnya `http://127.0.0.1:3000/` atau `https://192.168.1.20/`), bukan nama domain publik. Redirect, proxy, dan respons non-JSON ditolak. Token hanya berada di backend Python; tidak dikirim ke browser dashboard. Jika situs Anda belum memiliki endpoint tersebut, mode privat belum dapat mengecek status akun sampai backend situs lab menambahkannya. **Account Checker tidak dapat menentukan status akun Instagram asli.**

Uji fungsinya:

```bash
python tests_account_checker.py
```


## Live Profile Preview — Ghoster.ai

Saat memilih **Web lab privat**, ketik satu username Instagram atau akun lab pada field identifier. Di sisi kanan dashboard muncul preview otomatis setelah input berhenti sekitar 1,25 detik. Preview adalah pemeriksaan read-only, terpisah dari Recovery Flow, dan tidak mengirim Forgot Password maupun login ke Instagram.

### Tiga sumber profil

1. **API web lab privat**: server lab Anda sendiri di localhost atau IP privat.
2. **Instagram resmi · akun terhubung**: profil Professional (Business/Creator) yang sudah memberikan izin melalui Meta Instagram API with Instagram Login. Hanya akun pemilik token yang bisa dibaca dari pilihan ini.
3. **Demo**: hanya akun dummy seperti demo_account, needs.verify, disabled.demo. Input username nyata, termasuk rizky_asepsutrisna, tidak menghasilkan angka statistik asli pada mode demo.

### API privat yang harus disediakan web lab

Method: GET

Path: /api/lab/account-profile?username=demo_account

Header: Authorization: Bearer <token-admin-lab>

Contoh respons JSON dummy (bukan statistik akun nyata):

```json
{
  "username": "demo_account",
  "exists": true,
  "full_name": "Nama Akun Lab",
  "biography": "Akun simulasi pengujian",
  "profile_picture_url": "https://cdn-contoh-milik-lab.invalid/avatar.png",
  "followers_count": 1250,
  "following_count": 135,
  "media_count": 23,
  "account_status": "active",
  "session_status": "active"
}
```

Avatar harus menggunakan URL HTTPS yang browser bisa akses. Tanpa gambar, UI menampilkan avatar cadangan. Angka yang tidak tersedia ditampilkan —, bukan 0.

### Akun Instagram Business/Creator milik Anda

Buat aplikasi resmi di Meta for Developers menggunakan Instagram API with Instagram Login; minta permission instagram_business_basic dan dapatkan token setelah pemilik akun memberikan persetujuan. Jangan unggah token ke GitHub atau frontend.

```bash
export IG_PROFILE_ACCESS_TOKEN="TOKEN_AKUN_PROFESSIONAL_MILIK_ANDA"
npm run web
```

Backend menggunakan endpoint resmi GET https://graph.instagram.com/v26.0/me dengan fields username,name,biography,followers_count,follows_count,media_count,profile_picture_url. Username input wajib cocok dengan akun milik token. Akun Instagram Personal biasa tidak didukung oleh API profesional tersebut.

### Pengujian

```bash
git pull origin main
python tests_profile_preview.py
npm run web
```

Referensi: Meta Instagram API [Postman](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api), [Instaloader](https://instaloader.github.io/module/structures.html). Instaloader adalah library tidak resmi dan tidak digunakan pada fitur ini; akses anonim terhadap profil bisa dibatasi Instagram.


## Preview Instagram publik tanpa token Meta — Instaloader

Sumber profil di Ghoster.ai sekarang memiliki pilihan default **Instagram publik · Instaloader (tanpa token)**. Ini adalah library open-source, bukan API resmi Meta. Fitur hanya membaca **satu profil publik per input** dan tidak menjalankan login, Forgot Password, atau automasi interaksi.

Setup setelah memperbarui repo:

```bash
cd ~/Desktop/Lab_TakeDown_Account
git pull origin main
source .venv/bin/activate
python -m pip install -r requirements.txt
npm run web
```

Di halaman `http://127.0.0.1:8787/`, pilih **Web lab privat** lalu pada bagian sumber preview pilih **Instagram publik · Instaloader (tanpa token)**. Isi username `rizkyasep_sutrisna` (tanpa @) pada kolom identifier. URL lab **tidak diperlukan** untuk sumber Instaloader; URL lab masih digunakan apabila Anda mengeksekusi Recovery Flow pada website privat.

UI menampilkan nama, bio, foto profil HTTPS (jika tersedia), jumlah followers, following, dan postingan. Instaloader bisa mengembalikan `None` pada jumlah postingan; UI menampilkan `—` (bukan nol). Metadata disimpan dalam cache selama **5 menit**, dan lookup username berbeda memiliki jeda minimal **15 detik**. Input pada UI memakai debounce sekitar 1,25 detik.

Saat Instagram menolak metadata, preview menampilkan status tidak tersedia. Pesan Instaloader `does not exist` sendiri bukan bukti akun benar-benar tidak ada. Angka follower dapat berubah sejak query terakhir. Link foto CDN Instagram juga dapat kedaluwarsa.

Tes unit tanpa koneksi Instagram:

```bash
python tests_profile_preview.py
```

Untuk versi library dan ketentuan penggunaan: https://github.com/instaloader/instaloader
