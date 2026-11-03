#!/usr/bin/env python3
"""Offline Playwright session-security simulator; never sends Instagram requests."""
from __future__ import annotations

import argparse
import http.client
import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

HOST = "127.0.0.1"
POLICIES = ("retain", "challenge", "revoke")

HTML = """<!doctype html><html lang="id"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Session Security Lab — OFFLINE</title>
<style>
:root{font:15px system-ui,sans-serif;background:#0b1220;color:#e6efff}
body{max-width:1000px;margin:36px auto;padding:0 18px}
h1{font-size:28px}.muted{color:#a5b3c8}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:16px}
.panel{background:#142136;padding:22px;border:1px solid #34445e;border-radius:14px}
button{padding:12px;margin:5px 4px 5px 0;border:0;border-radius:8px;background:#3469d7;color:#fff;cursor:pointer}
pre{background:#081222;border-radius:8px;padding:14px;white-space:pre-wrap;min-height:60px}
small{color:#7ee0b0}input{padding:10px;border-radius:8px;background:#0b1220;color:white;border:1px solid #667}
</style></head><body>
<header><h1>Session Security Lab</h1><p class="muted">Local mock · bukan Instagram · hanya akun fiktif</p><small>OFFLINE / NO REAL ACCOUNT</small></header>
<div class="grid">
<section class="panel"><h2>📱 Sesi HP (simulasi)</h2>
<button id="start" onclick="post('/api/owner-login','owner-status')">Login demo</button>
<button id="check" onclick="check()">Periksa sesi</button>
<pre id="owner-status">Belum login</pre></section>
<section class="panel"><h2>🧪 Browser uji (simulasi)</h2><p class="muted">Username: demo_account</p>
<input id="fake-pass" value="wrong-demo-password" type="password"><br>
<button id="wrong" onclick="post('/api/login','test-status')">Password dummy salah</button>
<button id="forgot" onclick="post('/api/forgot','test-status')">Forgot Password dummy</button>
<pre id="test-status">Belum diuji</pre></section></div>
<p class="muted">Retain, challenge dan revoke adalah kebijakan buatan. Bukan aturan Instagram.</p>
<script>
async function post(path,target){let r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
let j=await r.json();document.getElementById(target).textContent=JSON.stringify(j,null,2)}
async function check(){let r=await fetch('/api/session');let j=await r.json();
document.getElementById('owner-status').textContent=JSON.stringify(j,null,2)}
</script></body></html>"""


@dataclass
class LabState:
    policy: str = "retain"
    failed_logins: int = 0
    forgot_requests: int = 0
    owner_session: bool = False

    def current_status(self, has_owner_cookie: bool) -> str:
        if not self.owner_session or not has_owner_cookie:
            return "logged_out"
        if self.policy == "challenge" and self.failed_logins >= 3:
            return "verification_required"
        if self.policy == "revoke" and self.failed_logins >= 3 and self.forgot_requests >= 2:
            return "logged_out"
        return "active"


def handler_for(state: LabState):
    class LabHandler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def json_response(self, code, obj, cookie=False):
            payload = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            if cookie:
                self.send_header("Set-Cookie", "lab_session=trusted; HttpOnly; SameSite=Lax; Path=/")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/":
                body = HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif path == "/api/session":
                cookie = "lab_session=trusted" in self.headers.get("Cookie", "")
                self.json_response(200, {"status": state.current_status(cookie), "policy": state.policy})
            else:
                self.json_response(404, {"error": "not_found"})

        def do_POST(self):
            path = urlsplit(self.path).path
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size < 0 or size > 4096:
                    return self.json_response(413, {"error": "invalid_body_size"})
                json.loads(self.rfile.read(size) or b"{}")
            except (ValueError, UnicodeDecodeError):
                return self.json_response(400, {"error": "invalid_json"})
            if path == "/api/owner-login":
                state.owner_session = True
                return self.json_response(200, {"status": "active"}, cookie=True)
            if path == "/api/login":
                state.failed_logins += 1
                code = 401 if state.failed_logins <= 4 else 429
                return self.json_response(code, {"status": "invalid_credentials" if code == 401 else "rate_limited"})
            if path == "/api/forgot":
                state.forgot_requests += 1
                code = 200 if state.forgot_requests <= 3 else 429
                return self.json_response(code, {"status": "generic_message" if code == 200 else "rate_limited"})
            self.json_response(404, {"error": "not_found"})
    return LabHandler


def proxy_handler_for(allowed_port: int, stats: dict):
    class ProxyHandler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_CONNECT(self):
            self.send_error(403, "HTTPS disabled in offline lab")

        def do_GET(self):
            self.forward()

        def do_POST(self):
            self.forward()

        def forward(self):
            parsed = urlsplit(self.path)
            if parsed.scheme != "http" or parsed.hostname != HOST or parsed.port != allowed_port:
                return self.send_error(403, "Only local mock app allowed")
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size < 0 or size > 4096:
                    return self.send_error(413)
                body = self.rfile.read(size) if size else None
                path = (parsed.path or "/") + ("?" + parsed.query if parsed.query else "")
                headers = {k: v for k, v in self.headers.items()
                           if k.lower() not in ("host", "connection", "content-length", "proxy-connection", "transfer-encoding")}
                connection = http.client.HTTPConnection(HOST, allowed_port, timeout=5)
                try:
                    connection.request(self.command, path, body=body, headers=headers)
                    response = connection.getresponse()
                    payload = response.read()
                    stats["forwarded"] += 1
                    self.send_response(response.status)
                    for k, v in response.getheaders():
                        if k.lower() not in ("server", "date", "connection", "transfer-encoding", "content-length"):
                            self.send_header(k, v)
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                finally:
                    connection.close()
            except (OSError, http.client.HTTPException):
                self.send_error(502, "Mock server unavailable")
    return ProxyHandler


def serve(handler):
    server = ThreadingHTTPServer((HOST, 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def proxy_config(default_url):
    server = os.getenv("LAB_PROXY_SERVER", default_url).strip()
    if not server.startswith(("http://", "socks5://")):
        raise ValueError("Proxy must begin with http:// or socks5://")
    result = {"server": server}
    user = os.getenv("LAB_PROXY_USERNAME", "")
    if user:
        result["username"] = user
        result["password"] = os.getenv("LAB_PROXY_PASSWORD", "")
    return result


def run_scenario(playwright, policy, output, custom_chromium, headless):
    state = LabState(policy=policy)
    app = serve(handler_for(state))
    allowed_port = app.server_address[1]
    stats = {"forwarded": 0}
    proxy = serve(proxy_handler_for(allowed_port, stats))
    url = f"http://{HOST}:{allowed_port}/"
    try:
        launch = {"headless": headless, "proxy": proxy_config(f"http://{HOST}:{proxy.server_address[1]}"),
                  "args": ["--proxy-bypass-list=<-loopback>"]}
        if custom_chromium:
            launch["executable_path"] = custom_chromium
        browser = playwright.chromium.launch(**launch)
        try:
            phone = browser.new_context()
            tester = browser.new_context()
            def allow_lab(route):
                dest = urlsplit(route.request.url)
                if dest.scheme == "http" and dest.hostname == HOST and dest.port == allowed_port:
                    route.continue_()
                else:
                    route.abort()
            for context in (phone, tester):
                context.route("**/*", allow_lab)
            try:
                page = phone.new_page()
                page.goto(url, wait_until="domcontentloaded")
                with page.expect_response(lambda r: r.url.endswith("/api/owner-login")) as login:
                    page.locator("#start").click()
                assert login.value.status == 200
                with page.expect_response(lambda r: r.url.endswith("/api/session")) as check:
                    page.locator("#check").click()
                before = check.value.json()["status"]
                attack_page = tester.new_page()
                attack_page.goto(url, wait_until="domcontentloaded")
                for _ in range(3):
                    with attack_page.expect_response(lambda r: r.url.endswith("/api/login")) as attempt:
                        attack_page.locator("#wrong").click()
                    assert attempt.value.status == 401
                for _ in range(2):
                    with attack_page.expect_response(lambda r: r.url.endswith("/api/forgot")) as forgot:
                        attack_page.locator("#forgot").click()
                    assert forgot.value.status == 200
                with page.expect_response(lambda r: r.url.endswith("/api/session")) as check:
                    page.locator("#check").click()
                after = check.value.json()["status"]
                page.locator("#owner-status").get_by_text(after, exact=False).wait_for()
                image_file = output / f"{policy}.png"
                page.screenshot(path=str(image_file), full_page=True)
                expected = {"retain": "active", "challenge": "verification_required", "revoke": "logged_out"}[policy]
                passed = before == "active" and after == expected
                if "LAB_PROXY_SERVER" not in os.environ:
                    passed = passed and stats["forwarded"] > 0
                return {"policy": policy, "before": before, "after": after, "expected": expected,
                        "passed": passed, "failed_logins": state.failed_logins,
                        "forgot_requests": state.forgot_requests, "screenshot": image_file.name,
                        "builtin_proxy_forwarded": stats["forwarded"] if "LAB_PROXY_SERVER" not in os.environ else None}
            finally:
                tester.close()
                phone.close()
        finally:
            browser.close()
    finally:
        proxy.shutdown()
        proxy.server_close()
        app.shutdown()
        app.server_close()


def main():
    parser = argparse.ArgumentParser(description="Local-only session simulator (not Instagram)")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--chromium-path", default="")
    parser.add_argument("--output", default="output")
    args = parser.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as err:
        raise SystemExit("Install Playwright with pip install -r requirements.txt") from err
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as pw:
        for policy in POLICIES:
            row = run_scenario(pw, policy, output, args.chromium_path, args.headless)
            results.append(row)
            print(f"{policy}: {row['before']} -> {row['after']} ; passed={row['passed']}")
    report = {"mode": "OFFLINE_SIMULATION_NOT_INSTAGRAM", "time": datetime.now(timezone.utc).isoformat(),
              "proxy": "custom" if "LAB_PROXY_SERVER" in os.environ else "builtin_local",
              "results": results}
    file = output / "report.json"
    file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved {file}")
    if not all(x["passed"] for x in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
