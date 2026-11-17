#!/usr/bin/env python3
"""Single-run Playwright recovery-flow tester for a privately hosted lab."""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

DENY = ("instagram.com", "cdninstagram.com", "facebook.com", "fbcdn.net", "meta.com", "threads.net", "messenger.com", "whatsapp.com")
USERNAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._]{0,28}[A-Za-z0-9])?$")
DEFAULT_LAB_BASE_URL = os.environ.get("LAB_BASE_URL", "http://127.0.0.1:3000")


def resolve_target_from_username(username, lab_base_url=None):
    name = (username or "").strip()
    if not name:
        raise ValueError("Username lab kosong")
    if "://" in name:
        raise ValueError("Kolom username tidak menerima URL")
    if not USERNAME_RE.fullmatch(name):
        raise ValueError("Username lab hanya huruf/angka/._ (1–30)")
    base = (lab_base_url or DEFAULT_LAB_BASE_URL).rstrip("/")
    parsed = urlsplit(base)
    host = (parsed.hostname or "").lower().rstrip(".")
    if any(host == d or host.endswith("." + d) for d in DENY):
        raise ValueError("LAB_BASE_URL menunjuk ke domain terlarang")
    return f"{base}/u/{name}"
GREEN = "\033[92m"
CYAN = "\033[96m"
AMBER = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"


def private_url(url):
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("URL harus menggunakan http(s), tanpa username/password di URL")
    host = parsed.hostname.lower().rstrip(".")
    if any(host == item or host.endswith("." + item) for item in DENY):
        raise ValueError("Domain Instagram/Meta tidak termasuk cakupan pengujian lab")
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        address = ipaddress.ip_address(host)
        return address.is_private or address.is_loopback
    except ValueError:
        pass
    # Lab hostnames must resolve exclusively to private addresses.
    if host.endswith((".test", ".internal", ".home.arpa")):
        try:
            addresses = {x[4][0] for x in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))}
            return bool(addresses) and all(ipaddress.ip_address(ip).is_private for ip in addresses)
        except OSError:
            return False
    return False


def same_origin(a, b):
    left, right = urlsplit(a), urlsplit(b)
    def origin(p):
        return (p.scheme, p.hostname, p.port or (443 if p.scheme == "https" else 80))
    return origin(left) == origin(right)


def conceal(value):
    if "@" in value:
        local, domain = value.rsplit("@", 1)
        return (local[:1] or "*") + "***@" + domain
    return value[:2] + "***" + value[-2:] if len(value) > 5 else "***"


class Log:
    def __init__(self):
        self.events = []
        self.number = 0

    def add(self, stage, message, kind="info"):
        self.number += 1
        row = {"at": datetime.now(timezone.utc).isoformat(), "step": self.number, "stage": stage, "message": message}
        self.events.append(row)
        colors = {"info": CYAN, "ok": GREEN, "warn": AMBER, "error": RED}
        color = colors.get(kind, CYAN) if sys.stdout.isatty() and not os.getenv("NO_COLOR") else ""
        end = RESET if color else ""
        print(f"{color}[{self.number:02}] [{stage.upper():<12}] {message}{end}", flush=True)


def find(*candidates, timeout=2000):
    """Select a visible locator, waiting briefly for asynchronous DOM changes."""
    for locator in candidates:
        try:
            locator.first.wait_for(state="visible", timeout=timeout)
            return locator.first
        except Exception:
            continue
    return None


def must_find(label, *locators):
    found = find(*locators)
    if found is None:
        raise RuntimeError("Elemen tidak ditemukan: " + label)
    return found


def wait(seconds):
    time.sleep(seconds)


def execute(page, url, identifier, pace, log, manual_allowed=True):
    from playwright.sync_api import expect, TimeoutError as PWTimeout

    log.add("chromium", "Browser lokal berhasil dibuka")
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    log.add("navigate", "Halaman web lab terbuka")
    wait(pace)

    forgot = must_find(
        "Forgot password",
        page.locator('a[href="/accounts/password/reset/"]'),
        page.get_by_role("link", name=re.compile("forgot password", re.I)),
        page.get_by_text("Forgot password?", exact=True),
    )
    forgot.click()
    log.add("forgot", "Klik Forgot password? satu kali")
    wait(pace)

    textbox = must_find(
        "username/email/phone",
        page.locator('input#_r_s_'),
        page.locator('input[type="text"]'),
        page.get_by_role("textbox"),
        page.locator('input[autocomplete="username"]'),
    )
    textbox.fill(identifier)
    log.add("identifier", "Mengisi identifier: " + conceal(identifier))
    wait(pace)

    button = must_find(
        "Continue awal",
        page.get_by_role("button", name=re.compile(r"^continue$", re.I)),
        page.get_by_text("Continue", exact=True),
    )
    button.click()
    log.add("continue-1", "Klik Continue pertama")
    wait(pace)

    email = find(page.get_by_text("Get link via email", exact=True))
    sms = find(page.get_by_text("Get link via SMS", exact=True), timeout=900) if email is None else None
    if email is not None:
        email.click()
        channel = "email"
        log.add("channel", "Email tersedia; prioritas email dipilih")
    elif sms is not None:
        sms.click()
        channel = "sms"
        log.add("channel", "Email tidak tersedia; SMS dipilih")
    else:
        log.add("channel", "Email dan SMS tidak tersedia", "warn")
        return {"status": "NO_OPTION", "channel": None}
    wait(pace)

    button = must_find(
        "Continue kedua",
        page.get_by_role("button", name=re.compile(r"^continue$", re.I)),
        page.get_by_text("Continue", exact=True),
    )
    button.click()
    log.add("continue-2", "Klik Continue kedua (satu pengujian)")
    wait(pace)

    if find(page.get_by_text("Help us confirm it's you", exact=False), timeout=1400):
        log.add("human", "Verifikasi manusia muncul; menghentikan otomasi", "warn")
        if not page.context.browser.is_connected():
            raise RuntimeError("Browser terputus selama verifikasi")
        if not manual_allowed:
            raise RuntimeError("Verifikasi manual diperlukan; jalankan tanpa --headless")
        print("\nSelesaikan verifikasi secara MANUAL di browser, lalu kembali ke terminal.")
        input("Tekan ENTER setelah selesai: ")
        log.add("human", "Operator melanjutkan pengujian")
        wait(pace)

    confirmation = (
        re.compile(r"We sent an email to .* with a link to get back into your account", re.I)
        if channel == "email"
        else re.compile(r"We texted a password reset link to ", re.I)
    )
    try:
        expect(page.get_by_text(confirmation).first).to_be_visible(timeout=10000)
    except (AssertionError, PWTimeout):
        log.add("verify", "Teks konfirmasi tidak terdeteksi", "warn")
        return {"status": "NOT_CONFIRMED", "channel": channel}
    log.add("verify", "Teks konfirmasi " + channel + " terdeteksi", "ok")
    wait(pace)

    done = find(
        page.get_by_role("button", name=re.compile(r"^(OK|Done)$", re.I)),
        page.get_by_text("OK", exact=True),
        page.get_by_text("Done", exact=True),
        timeout=1000,
    )
    if done is not None:
        done.click()
        log.add("complete", "Klik OK / Done", "ok")
    else:
        log.add("complete", "Pesan sukses muncul tanpa tombol OK / Done", "warn")
    wait(pace)
    return {"status": "CONFIRMATION_VISIBLE", "channel": channel}


def main():
    p = argparse.ArgumentParser(description="Recovery Flow / PRIVATE LAB ONLY")
    p.add_argument("--url", help="Alamat website lab (default: input terminal)")
    p.add_argument("--username", help="Username lab; otomatis dipetakan ke LAB_BASE_URL/u/<username>")
    p.add_argument("--lab-base-url", default=DEFAULT_LAB_BASE_URL, help="Base URL lab privat (default: %(default)s)")
    p.add_argument("--identifier", help="Identifier dummy untuk lab (default: input terminal)")
    p.add_argument("--delay", type=float, default=0.7)
    p.add_argument("--headless", action="store_true", help="Tidak cocok untuk verifikasi manual")
    p.add_argument("--chromium-path", default="", help="Path Chromium lokal jika diperlukan")
    p.add_argument("--output", default="output")
    args = p.parse_args()
    if not 0.2 <= args.delay <= 3.0:
        p.error("--delay harus 0.2–3.0 detik")
    if args.username and not args.url:
        try:
            args.url = resolve_target_from_username(args.username, args.lab_base_url)
        except ValueError as err:
            p.error(str(err))
        if not args.identifier:
            args.identifier = args.username

    print("""
╔════════════════════════════════════════════════════════╗
║   R E C O V E R Y    F L O W   / /   C Y B E R  L A B ║
║     LOCAL CHROMIUM  •  ONE SHOT  •  PRIVATE SCOPE       ║
╚════════════════════════════════════════════════════════╝""")
    log = Log()
    result = {"status": "NOT_STARTED", "channel": None}
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    if args.url is not None:
        url = args.url.strip()
    else:
        raw = input("Username lab (atau URL privat): ").strip()
        try:
            url = resolve_target_from_username(raw, args.lab_base_url)
            if not args.identifier:
                args.identifier = raw
        except ValueError:
            # Bukan username valid — perlakukan sebagai URL dan biarkan private_url() memvalidasi.
            url = raw
    try:
        authorized_scope = private_url(url)
        if not authorized_scope:
            log.add("scope", "URL publik: mode inspeksi saja, tidak mengirim reset", "warn")
        else:
            log.add("scope", "URL privat terverifikasi untuk pengujian satu kali", "ok")

        identifier = ""
        if authorized_scope:
            # npm run setup passes the dummy identifier through the environment, not argv.
            provided = args.identifier if args.identifier is not None else os.getenv("LAB_TEST_IDENTIFIER")
            identifier = (provided if provided is not None else input("Username/email/nomor HP dummy: ")).strip()
            if not identifier or len(identifier) > 256:
                raise ValueError("Identifier kosong atau terlalu panjang")

        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            launch = {"headless": args.headless}
            if args.chromium_path:
                launch["executable_path"] = args.chromium_path
            if os.getenv("LAB_PROXY_SERVER"):
                launch["proxy"] = {"server": os.environ["LAB_PROXY_SERVER"]}
                if os.getenv("LAB_PROXY_USERNAME"):
                    launch["proxy"].update({
                        "username": os.environ["LAB_PROXY_USERNAME"],
                        "password": os.getenv("LAB_PROXY_PASSWORD", ""),
                    })
            browser = pw.chromium.launch(**launch)
            try:
                context = browser.new_context()
                def scoped(route):
                    if same_origin(url, route.request.url):
                        route.continue_()
                    else:
                        route.abort()
                context.route("**/*", scoped)
                page = context.new_page()
                if authorized_scope:
                    if args.headless:
                        log.add("human", "Mode headless: challenge manual akan memerlukan eksekusi ulang", "warn")
                    result = execute(page, url, identifier, args.delay, log, manual_allowed=not args.headless)
                else:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    result = {"status": "INSPECT_ONLY", "channel": None}
                    log.add("inspect", "Website dibuka tanpa interaksi otomatis", "ok")
                    if not args.headless:
                        input("Tekan ENTER untuk menutup Chromium: ")
                screenshot = output / "web_lab_last.png"
                page.screenshot(path=str(screenshot), full_page=True)
                log.add("screenshot", "Screenshot lokal: " + str(screenshot), "ok")
                context.close()
            finally:
                browser.close()
    except Exception as err:
        result = {"status": "ERROR", "error": str(err)[:350]}
        log.add("error", str(err)[:200], "error")
    report = {
        "mode": "PRIVATE_LAB_ONE_SHOT",
        "status": result,
        "events": log.events,
    }
    filepath = output / "web_lab_result.json"
    filepath.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Report:", filepath)
    return 1 if result["status"] == "ERROR" else 0


if __name__ == "__main__":
    raise SystemExit(main())
