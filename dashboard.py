#!/usr/bin/env python3
"""Loopback-only browser testing dashboard for privately controlled test websites.

Run: python dashboard.py
Requires sibling web_lab_flow.py.  Never exposes a public listener.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from mock_recovery_lab import start_mock_server
from account_checker import AccountChecker
from profile_preview import ProfilePreview

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "dashboard_static" / "index.html"
OUTPUT = ROOT / "output" / "dashboard"
HOST = "127.0.0.1"
MAX_JSON = 4096
MAX_LOGS = 300
COOLDOWN_SECONDS = 15
BLOCKED_DOMAINS = ("instagram.com", "facebook.com", "meta.com", "threads.net", "messenger.com")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def valid_private_target(url):
    """Conservative local test scope; public websites are never automated.

    Private hostname resolution is also checked by web_lab_flow.py before use.
    """
    from web_lab_flow import private_url

    raw = url.strip()
    parts = urlsplit(raw)
    if len(raw) > 2048 or not raw or not parts.hostname or parts.scheme not in ("http", "https"):
        raise ValueError("Masukkan URL http(s) website lab yang valid")
    if not private_url(raw):
        raise ValueError("Pengujian otomatis hanya untuk localhost atau host jaringan privat")
    host = parts.hostname.lower().rstrip(".")
    if any(host == domain or host.endswith("." + domain) for domain in BLOCKED_DOMAINS):
        raise ValueError("Layanan publik Instagram/Meta tidak termasuk lingkup lab")
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_unspecified or ip.is_multicast or ip.is_link_local or ip.is_reserved:
            raise ValueError("Alamat tidak sesuai untuk pengujian privat")
    except ValueError as error:
        if str(error) == "Alamat tidak sesuai untuk pengujian privat":
            raise
    if parts.fragment:
        raise ValueError("Hilangkan fragment (#) dari URL lab")
    return raw


def masked_identifier(value):
    value = str(value).strip()
    if "@" in value:
        first, domain = value.rsplit("@", 1)
        return f"{first[:1]}***@{domain}"
    return value[:2] + "***" + value[-2:] if len(value) >= 6 else "***"


class LabJobs:
    def __init__(self):
        self.lock = threading.RLock()
        self.job = None
        self.process = None
        self.mock_server = None
        self.last_start = 0.0

    def snapshot(self):
        with self.lock:
            if self.job is None:
                return {"status": "idle", "run": None, "current_time": now()}
            data = dict(self.job)
            data["logs"] = list(self.job["logs"])
            data["current_time"] = now()
            return {"status": data["status"], "run": data}

    def start(self, data):
        if not isinstance(data, dict):
            raise ValueError("Permintaan harus berupa JSON")
        mode = data.get("mode", "demo")
        if mode not in ("demo", "private"):
            raise ValueError("Pilih mode demo atau private")
        value = data.get("identifier", "demo@lab.test")
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 128 or "\n" in value:
            raise ValueError("Isi identifier dummy yang valid (maksimal 128 karakter)")
        identifier = value.strip()
        try:
            delay = float(data.get("delay", 0.7))
        except (TypeError, ValueError):
            raise ValueError("Jeda langkah tidak valid") from None
        if not 0.2 <= delay <= 3.0:
            raise ValueError("Jeda harus antara 0,2 dan 3 detik")
        options = data.get("demo_options", "both")
        if options not in ("both", "email", "sms", "none"):
            raise ValueError("Pilihan channel demo tidak valid")
        challenge = data.get("demo_challenge", False) is True
        headless = data.get("headless", False) is True
        if challenge and headless and mode == "demo":
            raise ValueError("Verifikasi manual memerlukan Chromium yang terlihat")
        with self.lock:
            if self.job and self.job["status"] in ("starting", "running", "awaiting_manual", "stopping"):
                raise RuntimeError("Satu pengujian masih berjalan")
            if time.monotonic() - self.last_start < COOLDOWN_SECONDS:
                raise RuntimeError("Tunggu sebentar sebelum menjalankan pengujian berikutnya")
            if mode == "private":
                url = valid_private_target(str(data.get("url", "")))
            else:
                # Demo is bound to loopback, and never sends actual email/SMS.
                url = "(built-in local mock)"
            run_id = secrets.token_hex(6)
            self.last_start = time.monotonic()
            self.job = {"id": run_id, "mode": mode, "url": url, "identifier": masked_identifier(identifier),
                        "delay": delay, "headless": headless, "status": "starting", "started_at": now(),
                        "finished_at": None, "logs": [], "result": None, "has_screenshot": False}
            thread = threading.Thread(target=self._run, args=(run_id, mode, url, identifier, delay, headless, options, challenge), daemon=True)
            thread.start()
            return self.snapshot()

    def _update(self, run_id, **changes):
        with self.lock:
            if self.job and self.job["id"] == run_id:
                self.job.update(changes)

    def _log(self, run_id, line):
        # Redact common identifier-echo forms and strip terminal styling.
        line = re.sub(r"\x1b\[[0-9;]*m", "", line).strip()[:600]
        if not line:
            return
        with self.lock:
            if self.job and self.job["id"] == run_id:
                self.job["logs"].append({"time": now(), "text": line})
                self.job["logs"] = self.job["logs"][-MAX_LOGS:]
                if "Selesaikan verifikasi secara MANUAL" in line:
                    self.job["status"] = "awaiting_manual"

    def _run(self, run_id, mode, url, identifier, delay, headless, options, challenge):
        output = OUTPUT / run_id
        server = None
        proc = None
        try:
            output.mkdir(parents=True, exist_ok=True)
            if mode == "demo":
                server, url = start_mock_server(options=options, challenge=challenge)
                with self.lock:
                    self.mock_server = server
                self._update(run_id, url=url)
            runner = ROOT / "web_lab_flow.py"
            if not runner.is_file():
                raise FileNotFoundError("web_lab_flow.py tidak ditemukan di folder repository")
            command = [sys.executable, "-u", str(runner), "--url", url,
                       "--identifier", identifier, "--delay", str(delay), "--output", str(output)]
            if headless:
                command.append("--headless")
            env = dict(os.environ, NO_COLOR="1", PYTHONUNBUFFERED="1")
            # The engine already understands optional LAB_PROXY_SERVER env configuration.
            proc = subprocess.Popen(command, cwd=str(ROOT), env=env,
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, bufsize=1)
            with self.lock:
                self.process = proc
            self._update(run_id, status="running")
            self._log(run_id, "[DASHBOARD] Chromium runner started · one-shot · private scope")
            assert proc.stdout is not None
            for line in proc.stdout:
                self._log(run_id, line)
            exit_code = proc.wait(timeout=20)
            report_file = output / "web_lab_result.json"
            screenshot_file = output / "web_lab_last.png"
            result = None
            if report_file.is_file():
                try:
                    result = json.loads(report_file.read_text(encoding="utf-8")).get("status")
                except (ValueError, OSError):
                    result = {"status": "INVALID_REPORT"}
            status = "completed" if exit_code == 0 and result and result.get("status") not in ("ERROR", "NOT_STARTED") else "failed"
            with self.lock:
                if self.job and self.job["id"] == run_id and self.job["status"] == "stopping":
                    status = "cancelled"
            self._update(run_id, status=status, result=result or {"status": "NO_REPORT", "exit_code": exit_code},
                         has_screenshot=screenshot_file.is_file(), finished_at=now())
            self._log(run_id, f"[DASHBOARD] Finished: {status} (exit {exit_code})")
        except Exception as exc:
            self._update(run_id, status="failed", finished_at=now(), result={"status": "ERROR"})
            self._log(run_id, f"[DASHBOARD] Error: {type(exc).__name__}: {str(exc)[:150]}")
        finally:
            with self.lock:
                if self.process is proc:
                    self.process = None
                if self.mock_server is server:
                    self.mock_server = None
            if server:
                server.shutdown()
                server.server_close()

    def resume(self):
        with self.lock:
            if not self.job or self.job["status"] != "awaiting_manual" or self.process is None or self.process.stdin is None:
                raise RuntimeError("Tidak ada verifikasi manual yang menunggu")
            self.process.stdin.write("\n")
            self.process.stdin.flush()
            self.job["status"] = "running"
            return self.snapshot()

    def stop(self):
        with self.lock:
            if not self.job or self.job["status"] not in ("running", "starting", "awaiting_manual"):
                raise RuntimeError("Tidak ada proses aktif yang bisa dibatalkan")
            self.job["status"] = "stopping"
            if self.process:
                self.process.terminate()
            return self.snapshot()

    def screenshot(self):
        with self.lock:
            if not self.job or not self.job["has_screenshot"]:
                return None
            path = OUTPUT / self.job["id"] / "web_lab_last.png"
        return path.read_bytes() if path.is_file() else None


class DashboardHTTP(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr, engine):
        super().__init__(addr, self.Handler)
        self.engine = engine
        self.account_checker = AccountChecker()
        self.profile_preview = ProfilePreview()
        self.token = secrets.token_urlsafe(24)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            if os.getenv("LAB_VERBOSE_HTTP"):
                super().log_message(fmt, *args)

        def _headers(self, code, mime, length):
            self.send_response(code)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()

        def send_body(self, code, body, mime="application/json; charset=utf-8"):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            elif isinstance(body, str):
                body = body.encode("utf-8")
            self._headers(code, mime, len(body))
            self.wfile.write(body)

        def _valid_host(self):
            host = self.headers.get("Host", "").lower()
            port = self.server.server_address[1]
            if host not in (f"127.0.0.1:{port}", f"localhost:{port}"):
                return False
            origin = self.headers.get("Origin")
            return not origin or origin.lower() in (f"http://127.0.0.1:{port}", f"http://localhost:{port}")

        def do_GET(self):
            if not self._valid_host():
                return self.send_body(403, {"error": "host_or_origin_denied"})
            path = urlsplit(self.path).path
            if path == "/":
                raw = INDEX.read_text(encoding="utf-8")
                page = raw.replace("__LOCAL_LAB_TOKEN__", json.dumps(self.server.token))
                return self.send_body(200, page, "text/html; charset=utf-8")
            if path == "/api/state":
                return self.send_body(200, self.server.engine.snapshot())
            if path == "/api/screenshot":
                raw = self.server.engine.screenshot()
                if raw is None:
                    return self.send_body(404, {"error": "no_screenshot_yet"})
                return self.send_body(200, raw, "image/png")
            if path == "/api/health":
                return self.send_body(200, {"ok": True, "scope": "local_private_only", "version": "1.0"})
            return self.send_body(404, {"error": "not_found"})

        def do_POST(self):
            if not self._valid_host():
                return self.send_body(403, {"error": "host_or_origin_denied"})
            if self.headers.get("X-Lab-Token") != self.server.token:
                return self.send_body(403, {"error": "invalid_local_token"})
            if self.headers.get("Content-Type", "").split(";", 1)[0].lower().strip() != "application/json":
                return self.send_body(415, {"error": "json_only"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size < 2 or size > MAX_JSON:
                    return self.send_body(413, {"error": "body_size_invalid"})
                body = json.loads(self.rfile.read(size))
                path = urlsplit(self.path).path
                if path == "/api/start":
                    result = self.server.engine.start(body)
                elif path == "/api/resume":
                    result = self.server.engine.resume()
                elif path == "/api/stop":
                    result = self.server.engine.stop()
                elif path == "/api/account-check":
                    result = self.server.account_checker.check(body)
                elif path == "/api/profile-preview":
                    result = self.server.profile_preview.lookup(body)
                else:
                    return self.send_body(404, {"error": "not_found"})
                return self.send_body(200, result)
            except (ValueError, RuntimeError) as exc:
                return self.send_body(400, {"error": str(exc)})
            except Exception as exc:
                return self.send_body(500, {"error": "internal_error", "type": type(exc).__name__})


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local test dashboard · browser automation on owned labs")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--no-open", action="store_true", help="Do not open dashboard browser")
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")
    engine = LabJobs()
    server = DashboardHTTP((HOST, args.port), engine)
    url = f"http://127.0.0.1:{args.port}/"
    print("\n  ⟡ LAB CONSOLE / WEB DASHBOARD")
    print("  URL:", url)
    print("  Scope: loopback-only dashboard; private test sites")
    print("  CTRL+C to stop dashboard\n")
    if not args.no_open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nClosing dashboard")
    finally:
        if engine.process:
            engine.process.terminate()
        server.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())