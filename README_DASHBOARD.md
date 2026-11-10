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