# Session Security Lab — offline simulator

A controlled lab to observe how **an already-signed-in simulated mobile session** reacts when a separate browser submits invalid logins and forgot-password requests. This is **not Instagram**. Results are hypothetical test policies, not measurements of Meta systems.

## Safety model

- Local mock web application and proxy, both bound to `127.0.0.1`.
- Two independent Playwright browser contexts: simulated phone and test client.
- No requests, passwords, resets, reports, or account actions against Instagram or third-party websites.
- The built-in proxy denies outbound hosts; browser routing allows only the mock server.
- Three policies: `retain` (keep session), `challenge` (require verification), and `revoke` (log out).
- Outputs `output/report.json` and screenshots; no real credentials are required.

## Setup

Requires Python 3.10+ and Playwright Chromium.

```sh
git clone https://github.com/zainpewpewpew/Lab_TakeDown_Account.git
cd Lab_TakeDown_Account
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
python lab.py --headless
```

For a visible browser, omit `--headless`. On Windows, use `py -m venv .venv` and `.venv\\Scripts\\Activate.ps1`.

## Custom proxy

The built-in local proxy is used by default. To use a compatible HTTP/SOCKS5 proxy running **on the same machine**:

```sh
export LAB_PROXY_SERVER=http://127.0.0.1:8080
export LAB_PROXY_USERNAME=
export LAB_PROXY_PASSWORD=
python lab.py --headless
```

A remote proxy cannot normally reach your local mock app at `127.0.0.1`. Proxy credentials are not stored in reports.

## Tests

```sh
python tests.py
```

These tests validate the backend/proxy without running Chromium. End-to-end browser tests require a machine permitting Chromium access to localhost.

## Interpretation

The simulator uses a small number of **dummy** requests to illustrate policy differences; it does **not** discover Instagram's rate limits or prove whether real Instagram sessions log out.

References: [OWASP session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html), [OWASP forgot password](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html), [Playwright](https://playwright.dev/python/docs/intro).


## Mode website lab pribadi (baru): `web_lab_flow.py`

Runner ini menerima URL website lab dari Terminal, membuka Chromium, dan menjalankan satu alur pemulihan dummy. URL publik hanya untuk inspeksi manual; domain Meta/Instagram ditolak. Otomasi hanya aktif untuk localhost, IP privat, dan hostname lab khusus yang resolve ke IP privat.

1. Klik `Forgot password?` dari href `/accounts/password/reset/` atau label teks.
2. Input username/email/nomor HP dummy melalui Terminal dan klik `Continue`.
3. Pilih `Get link via email` bila ada; fallback `Get link via SMS`. Hentikan jika keduanya tidak tersedia.
4. Klik `Continue` kedua sekali.
5. Jika terlihat `Help us confirm it's you`, verifikasi manual di Chromium dan tekan Enter pada Terminal.
6. Deteksi pesan sukses email/SMS yang sesuai, lalu klik `OK`/`Done` apabila ada.
7. Simpan log berurutan dan screenshot ke `output/web_lab_result.json` serta `output/web_lab_last.png`.

Locator mengutamakan role/teks dan href agar tidak tergantung class CSS acak. Jeda antar-step default 0,7 detik; tidak ada perulangan permintaan reset.

### macOS

```bash
git pull origin main
source .venv/bin/activate
python web_lab_flow.py
```

Isi URL ketika diminta, misalnya `http://127.0.0.1:3000/` atau `http://192.168.1.50:3000/`, lalu masukkan akun dummy.

Alternatif tanpa prompt:

```bash
python web_lab_flow.py --url http://127.0.0.1:3000/ --identifier demo@lab.test
```

Proxy HTTP/SOCKS5 lab opsional memakai `LAB_PROXY_SERVER`, `LAB_PROXY_USERNAME`, dan `LAB_PROXY_PASSWORD`. Proxy harus dapat mengakses server privat. Aset di luar origin lab diblokir; sediakan aset self-hosted. `--headless` tidak cocok untuk verifikasi yang perlu diselesaikan manual.

Catatan: `python tests.py` tetap memeriksa simulator sesi lama. Uji browser end-to-end untuk website lab Anda perlu dilakukan di mesin Anda, karena struktur DOM dan konfigurasi situs dapat berbeda.
