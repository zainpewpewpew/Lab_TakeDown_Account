#!/usr/bin/env python3
"""Ghoster.ai: one-shot recovery UI test on an owned localhost/LAN lab.

Two browser transports:
* chromium: launch a local Playwright Chromium instance
* multilogin: attach to an ALREADY RUNNING local Multilogin Chromium CDP port

Never operates on Instagram, Meta or other public websites.
Never solves human challenges, repeats attempts, or uses third-party accounts.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from web_lab_flow import private_url, same_origin, conceal

COLORS = {
    "cyan": "\033[96m", "green": "\033[92m", "pink": "\033[95m",
    "amber": "\033[93m", "red": "\033[91m", "dim": "\033[90m",
}
RESET = "\033[0m"
EMAIL_DONE = re.compile(
    r"We sent an email to .* with a link to get back into your account", re.I
)
SMS_DONE = re.compile(r"We texted a password reset link to ", re.I)
FORGOT = re.compile(r"(?:forgot password\?|lupa kata sandi\??)", re.I)
CONTINUE = re.compile(r"^(?:continue|lanjutkan)$", re.I)
CHALLENGE = re.compile(r"(?:Help us confirm it's you|Bantu kami memastikan)", re.I)


class Terminal:
    def __init__(self):
        self.entries = []
        self.tty = sys.stdout.isatty() and not os.getenv("NO_COLOR")

    def line(self, stage, message, tone="cyan"):
        clock = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.entries.append({"time": clock, "stage": stage, "message": message})
        color = COLORS.get(tone, "") if self.tty else ""
        reset = RESET if color else ""
        print(f"{color}[{clock[11:19]} UTC] [{stage:>12}] {message}{reset}", flush=True)

    def banner(self, variant):
        art = """
╔════════════════════════════════════════════════════════════════════╗
║                 G H O S T E R  .  A I                              ║
║                 C Y B E R  /  R E C O V E R Y                      ║
║                                                                    ║
║      ONE-SHOT  ◆  PRIVATE LAB ONLY  ◆  HUMAN-IN-THE-LOOP          ║
╚════════════════════════════════════════════════════════════════════╝"""
        print((COLORS["cyan"] + art + RESET) if self.tty else art, flush=True)
        if self.tty and os.getenv("REDUCED_MOTION") != "1":
            for count in range(0, 21, 4):
                bar = "█" * count + "░" * (20 - count)
                sys.stdout.write("\r" + COLORS["pink"] + "  BOOT SEQUENCE  " + bar + RESET)
                sys.stdout.flush()
                time.sleep(0.045)
            sys.stdout.write("\n")
        self.line("BOOT", "Browser mode: " + variant.upper(), "green")


class Pacer:
    def __init__(self, minimum=1.0, maximum=3.0, sleeper=time.sleep, rng=random.uniform):
        if not (0 <= minimum <= maximum <= 5.0):
            raise ValueError("Rentang jeda harus 0–5 detik dengan minimum <= maksimum")
        self.minimum, self.maximum = minimum, maximum
        self.sleeper, self.rng = sleeper, rng

    def between(self, terminal, next_action):
        value = self.rng(self.minimum, self.maximum)
        terminal.line("PACE", f"Jeda {value:.2f}s sebelum {next_action}", "dim")
        self.sleeper(value)


def validate_owned_lab_url(url):
    """Never automate public domains, including public vanity names for a lab."""
    if not isinstance(url, str) or len(url) > 2048:
        raise ValueError("URL lab tidak valid")
    raw = url.strip()
    parts = urlsplit(raw)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
        raise ValueError("URL wajib http(s) dan tidak boleh mengandung kredensial")
    if parts.fragment:
        raise ValueError("Hapus fragment URL (#...)")
    if not private_url(raw):
        raise ValueError("Automasi hanya pada localhost, IP privat, atau host .test/.internal")
    try:
        ip = ipaddress.ip_address(parts.hostname)
    except ValueError:
        ip = None
    if ip is not None and (
        ip.is_unspecified or ip.is_multicast or ip.is_link_local or ip.is_reserved
    ):
        raise ValueError("Alamat IP tersebut bukan target lab privat yang valid")
    return raw


def validate_local_cdp(endpoint):
    """Only attach to a locally-running user-started browser profile."""
    if not isinstance(endpoint, str) or len(endpoint) > 1024:
        raise ValueError("Masukkan alamat CDP Multilogin lokal")
    raw = endpoint.strip()
    parsed = urlsplit(raw)
    if parsed.scheme not in ("http", "ws") or parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("Alamat CDP harus lokal: http://127.0.0.1:PORT atau ws://127.0.0.1:PORT/devtools/browser/...")
    try:
        port = parsed.port
    except ValueError:
        port = None
    if not port or not 1 <= port <= 65535 or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Port CDP lokal tidak valid atau URL mengandung parameter terlarang")
    if parsed.scheme == "http" and parsed.path not in ("", "/"):
        raise ValueError("URL HTTP CDP hanya boleh memuat host dan port")
    if parsed.scheme == "ws" and not parsed.path.startswith("/devtools/browser/"):
        raise ValueError("WebSocket CDP harus memakai path /devtools/browser/...")
    return raw


def locate(*candidates, timeout=1600):
    for candidate in candidates:
        try:
            candidate.first.wait_for(state="visible", timeout=timeout)
            return candidate.first
        except Exception:
            pass
    return None


def required(label, *locators):
    item = locate(*locators)
    if item is None:
        raise RuntimeError("Elemen tidak ditemukan: " + label)
    return item


def run_flow(page, url, identifier, terminal, pacer, manual=True):
    """Return a summary after exactly one recovery request on the private lab."""
    terminal.line("STEP 1", "Chromium siap; tab pengujian dibuat", "green")
    pacer.between(terminal, "navigasi")
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    terminal.line("STEP 2", "Halaman website lab dimuat: " + url, "green")

    pacer.between(terminal, "klik Forgot password")
    forgot = required(
        "Forgot password / Lupa kata sandi",
        page.get_by_role("link", name=FORGOT),
        page.locator('a[href="/accounts/password/reset/"]'),
        page.get_by_text(FORGOT),
    )
    forgot.click()
    terminal.line("STEP 3", "Mengklik tautan Lupa Kata Sandi", "green")

    pacer.between(terminal, "mengisi identifier")
    field = required(
        "input username/email/nomor HP",
        page.locator('input[id="_r_s_"]'),
        page.get_by_role("textbox"),
        page.locator('input[type="text"]'),
        page.locator('input[autocomplete="username"]'),
    )
    field.fill(identifier)
    terminal.line("STEP 4", "Mengisi identitas: " + conceal(identifier), "green")

    pacer.between(terminal, "Continue pertama")
    required(
        "Continue / Lanjutkan",
        page.get_by_role("button", name=CONTINUE),
        page.get_by_text(CONTINUE),
    ).click()
    terminal.line("STEP 5", "Mengklik Lanjutkan pertama", "green")

    pacer.between(terminal, "mengecek opsi pemulihan")
    email = locate(page.get_by_text("Get link via email", exact=True), timeout=1800)
    if email is not None:
        email.click()
        method = "email"
        terminal.line("STEP 6a", "Memilih: Kirim tautan via Email", "green")
        terminal.line("STEP 6b", "SMS tidak dipilih; email diprioritaskan", "dim")
    else:
        terminal.line("STEP 6a", "Opsi email tidak tersedia", "amber")
        sms = locate(page.get_by_text("Get link via SMS", exact=True), timeout=1800)
        if sms is None:
            terminal.line("STEP 6b", "Email/SMS tidak tersedia; pengujian berhenti", "amber")
            return {"status": "NO_CHANNEL", "channel": None}
        sms.click()
        method = "sms"
        terminal.line("STEP 6b", "Memilih: Kirim tautan via SMS", "green")

    pacer.between(terminal, "Continue metode")
    required(
        "Continue kedua / Lanjutkan",
        page.get_by_role("button", name=CONTINUE),
        page.get_by_text(CONTINUE),
    ).click()
    terminal.line("STEP 6c", "Mengonfirmasi metode pemulihan", "green")

    pacer.between(terminal, "pemeriksaan verifikasi")
    challenge = locate(page.get_by_text(CHALLENGE), timeout=1400)
    if challenge is not None:
        terminal.line("STEP 7", "Verifikasi manusia terdeteksi", "amber")
        if not manual:
            raise RuntimeError("Verifikasi manusia membutuhkan browser terlihat; jalankan tanpa --headless")
        terminal.line("MANUAL", "Selesaikan verifikasi di browser. Proses dijeda hingga ENTER.", "amber")
        input("\n[PERLU INTERVENSI] Setelah verifikasi manual selesai, tekan ENTER... ")
        terminal.line("STEP 7", "Operator menekan ENTER; pengecekan dilanjutkan", "green")
    else:
        terminal.line("STEP 7", "Tidak terdeteksi verifikasi manusia", "dim")

    pattern = EMAIL_DONE if method == "email" else SMS_DONE
    try:
        page.get_by_text(pattern).first.wait_for(state="visible", timeout=12000)
    except Exception:
        terminal.line("STEP 8", "Pesan konfirmasi belum terlihat; status tidak dipastikan", "amber")
        return {"status": "UNCONFIRMED", "channel": method}
    terminal.line("STEP 8", "Pesan konfirmasi " + method.upper() + " terlihat pada halaman lab", "green")

    pacer.between(terminal, "OK / Selesai")
    done = locate(
        page.get_by_role("button", name=re.compile(r"^(OK|Done|Selesai)$", re.I)),
        page.get_by_text(re.compile(r"^(OK|Done|Selesai)$", re.I)),
        timeout=1200,
    )
    if done is not None:
        done.click()
        terminal.line("STEP 8", "Mengklik OK / Selesai", "green")
    else:
        terminal.line("STEP 8", "Tidak ada tombol OK / Selesai; konfirmasi sudah terlihat", "amber")
    return {"status": "CONFIRMATION_VISIBLE", "channel": method}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Ghoster.ai recovery UI test — PRIVATE LAB ONLY")
    parser.add_argument("--url", help="Alamat localhost/LAN lab; jika kosong, diminta di terminal")
    parser.add_argument("--identifier", help="Identifier dummy untuk CI saja; bila kosong, diminta lewat terminal")
    parser.add_argument("--browser-mode", choices=("chromium", "multilogin"), default="chromium")
    parser.add_argument("--cdp-endpoint", help="Local CDP port browser Multilogin yang sudah berjalan")
    parser.add_argument("--headless", action="store_true", help="Hanya mode Chromium biasa")
    parser.add_argument("--min-delay", type=float, default=1.0)
    parser.add_argument("--max-delay", type=float, default=3.0)
    parser.add_argument("--output", default="output/recovery_lab")
    parser.add_argument("--demo", action="store_true", help="Gunakan simulator offline bawaan")
    parser.add_argument("--demo-options", choices=("both", "email", "sms", "none"), default="both")
    parser.add_argument("--demo-challenge", action="store_true", help="Simulasikan verifikasi manual")
    args = parser.parse_args(argv)
    if args.browser_mode == "multilogin" and args.headless:
        parser.error("Headless ditentukan oleh profil Multilogin, bukan oleh script ini")

    terminal = Terminal()
    terminal.banner(args.browser_mode)
    try:
        pacer = Pacer(args.min_delay, args.max_delay)
    except ValueError as exc:
        parser.error(str(exc))
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    result = {"status": "NOT_STARTED", "channel": None}
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    mock_server = None
    try:
        if args.demo:
            from mock_recovery_lab import start_mock_server
            mock_server, url = start_mock_server(options=args.demo_options, challenge=args.demo_challenge)
            terminal.line("SIMULATOR", "Simulator offline lokal dimulai; tidak mengirim SMS/email", "green")
        else:
            url = args.url if args.url is not None else input("Masukkan URL website lab privat: ")
        url = validate_owned_lab_url(url)
        terminal.line("SCOPE", "Target lab privat tervalidasi", "green")
        identifier = args.identifier if args.identifier is not None else input(
            "Masukkan username/email/nomor HP akun dummy: "
        )
        if not identifier or not identifier.strip() or len(identifier) > 128 or "\n" in identifier:
            raise ValueError("Identifier dummy tidak valid (1–128 karakter)")
        identifier = identifier.strip()
        terminal.line("INPUT", "Identifier diterima: " + conceal(identifier))
        endpoint = None
        if args.browser_mode == "multilogin":
            endpoint = args.cdp_endpoint or os.getenv("LAB_MULTILOGIN_CDP") or input(
                "Alamat CDP profil Multilogin yang sudah berjalan (contoh http://127.0.0.1:9222): "
            )
            endpoint = validate_local_cdp(endpoint)
            terminal.line("MULTILOGIN", "Menghubungkan ke CDP profil lokal; tidak membuat profil baru")
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            if endpoint is not None:
                browser = playwright.chromium.connect_over_cdp(endpoint, timeout=15000)
                if not browser.contexts:
                    browser.close()
                    raise RuntimeError("Profil Multilogin tidak memiliki context browser aktif")
                context = browser.contexts[0]
                owns_context = False
                terminal.line("STEP 1", "Terhubung ke profil Multilogin Chromium", "green")
            else:
                terminal.line("STEP 1", "Memulai Chromium Playwright...", "cyan")
                browser = playwright.chromium.launch(headless=args.headless)
                context = browser.new_context()
                owns_context = True
            page = None
            try:
                page = context.new_page()
                page.set_default_timeout(6000)
                page.route(
                    "**/*",
                    lambda route: route.continue_()
                    if same_origin(url, route.request.url)
                    else route.abort(),
                )
                page.on("popup", lambda popup: popup.close())
                result = run_flow(
                    page, url, identifier, terminal, pacer, manual=not args.headless
                )
                terminal.line("RESULT", "Status akhir: " + result["status"], "green")
            finally:
                if page is not None:
                    try:
                        screenshot = output / "recovery_lab_last.png"
                        page.screenshot(path=str(screenshot), full_page=True, timeout=8000)
                        terminal.line("EVIDENCE", "Screenshot lokal: " + str(screenshot), "green")
                    except Exception:
                        terminal.line("EVIDENCE", "Screenshot tidak tersedia", "amber")
                    try:
                        page.close()
                        terminal.line("CLEANUP", "Tab pengujian ditutup", "dim")
                    except Exception:
                        pass
                if owns_context:
                    context.close()
                # For an attached CDP browser, this only disconnects Playwright.
                # Do not stop the running Multilogin profile.
                browser.close()
                terminal.line("CLEANUP", "Chromium ditutup / koneksi CDP dilepas", "dim")
    except (EOFError, KeyboardInterrupt):
        result = {"status": "CANCELLED", "channel": None}
        terminal.line("CANCEL", "Pengujian dibatalkan operator", "amber")
    except Exception as exc:
        result = {"status": "ERROR", "channel": None}
        terminal.line("ERROR", type(exc).__name__ + ": " + str(exc)[:180], "red")
    finally:
        report = {
            "mode": "RECOVERY_PRIVATE_LAB_ONE_SHOT",
            "browser_mode": args.browser_mode,
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": result,
            "events": terminal.entries,
        }
        path = output / "recovery_lab_result.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        terminal.line("REPORT", str(path), "green")
        terminal.line("FINISH", "Satu pengujian selesai; tidak ada retry otomatis", "green")
        if mock_server is not None:
            mock_server.shutdown()
            mock_server.server_close()
    return 0 if result["status"] in ("CONFIRMATION_VISIBLE", "NO_CHANNEL", "UNCONFIRMED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
