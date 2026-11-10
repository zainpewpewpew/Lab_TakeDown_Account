"""Ghoster.ai: single-account status inspection for owned private lab APIs only.

No public Instagram requests, authentication attempts, account discovery, or reset operations.
The caller supplies an administrative API token as a server-side environment variable.
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
import ssl
import threading
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

USERNAME = re.compile(r"^[A-Za-z0-9._]{1,30}$")
ACCOUNT_STATES = {"active", "disabled", "verification_required", "unknown"}
SESSION_STATES = {"active", "expired", "revoked", "unknown"}
DEMO = {
    "demo_account": {"exists": True, "account_status": "active", "session_status": "active"},
    "needs.verify": {"exists": True, "account_status": "verification_required", "session_status": "expired"},
    "disabled.demo": {"exists": True, "account_status": "disabled", "session_status": "revoked"},
}
MAX_RESPONSE_BYTES = 8192


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean_username(value):
    if not isinstance(value, str) or not USERNAME.fullmatch(value.strip()):
        raise ValueError("Username lab harus 1-30 karakter (huruf, angka, titik, underscore)")
    return value.strip().lower()


def _validate_account_result(data, username):
    if not isinstance(data, dict):
        raise ValueError("Respons API akun harus berbentuk objek JSON")
    if data.get("username") != username or not isinstance(data.get("exists"), bool):
        raise ValueError("Respons API tidak sesuai dengan username atau format exists")
    if data.get("account_status") not in ACCOUNT_STATES:
        raise ValueError("Nilai account_status tidak dikenal")
    if data.get("session_status") not in SESSION_STATES:
        raise ValueError("Nilai session_status tidak dikenal")
    if not data["exists"] and (data["account_status"] != "unknown" or data["session_status"] != "unknown"):
        raise ValueError("Akun yang tidak ada harus mengembalikan status unknown")
    return {
        "username": username,
        "exists": data["exists"],
        "account_status": data["account_status"],
        "session_status": data["session_status"],
        "checked_at": utc_now(),
        "source": "private_lab_api",
    }


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirect endpoint akun tidak diizinkan")


def _scope_check(base_url):
    from dashboard import valid_private_target
    base = valid_private_target(base_url)
    parts = urlsplit(base)
    if parts.query or parts.fragment or parts.path not in ("", "/"):
        raise ValueError("Masukkan hanya alamat origin web lab (tanpa path atau query)")
    # Require an explicit private network target for sending a privileged token.
    host = parts.hostname or ""
    if host in ("localhost", "127.0.0.1", "::1"):
        return parts
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        raise ValueError("API checker ber-token harus memakai localhost atau IP privat, bukan hostname") from None
    if not addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_link_local or addr.is_multicast:
        raise ValueError("API checker hanya untuk alamat RFC1918/loopback yang valid")
    return parts


def check_owned_lab_api(base_url, username, token):
    if not token or len(token) > 1024 or any(c in token for c in "\r\n"):
        raise ValueError("Set LAB_ACCOUNT_CHECK_TOKEN di server sebelum memeriksa API lab privat")
    parts = _scope_check(base_url)
    origin = parts.scheme + "://" + parts.netloc
    url = origin + "/api/lab/account-status?" + urlencode({"username": username})
    request = Request(url, headers={"Authorization": "Bearer " + token, "Accept": "application/json",
                                    "User-Agent": "Ghoster-Lab-Checker/1.0"}, method="GET")
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=5) as response:
            if response.status != 200:
                raise ValueError("API lab tidak mengembalikan HTTP 200")
            content_type = response.headers.get("Content-Type", "")
            if "application/json" not in content_type.lower():
                raise ValueError("API lab harus mengembalikan JSON")
            data = response.read(MAX_RESPONSE_BYTES + 1)
            if len(data) > MAX_RESPONSE_BYTES:
                raise ValueError("Respons API lab terlalu besar")
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise ValueError("Token API lab ditolak (401/403)") from None
        raise ValueError("API lab mengembalikan HTTP " + str(exc.code)) from None
    except (OSError, URLError, TimeoutError) as exc:
        raise ValueError("Gagal mengakses API lab privat: " + type(exc).__name__) from None
    try:
        decoded = json.loads(data)
    except (ValueError, UnicodeDecodeError):
        raise ValueError("Respons API lab bukan JSON valid") from None
    return _validate_account_result(decoded, username)


class AccountChecker:
    def __init__(self, cooldown_seconds=4):
        self.lock = threading.Lock()
        self.last_check = 0.0
        self.cooldown_seconds = cooldown_seconds

    def check(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("Payload harus objek JSON")
        mode = payload.get("mode", "demo")
        if mode not in ("demo", "private"):
            raise ValueError("Mode hanya demo atau private")
        username = clean_username(payload.get("username", ""))
        with self.lock:
            if time.monotonic() - self.last_check < self.cooldown_seconds:
                raise RuntimeError("Tunggu sebelum pengecekan akun berikutnya")
            self.last_check = time.monotonic()
        if mode == "demo":
            data = DEMO.get(username, {"exists": False, "account_status": "unknown", "session_status": "unknown"})
            return {"username": username, **data, "checked_at": utc_now(), "source": "offline_demo"}
        token = os.environ.get("LAB_ACCOUNT_CHECK_TOKEN", "")
        url = payload.get("url", "")
        if not isinstance(url, str):
            raise ValueError("URL harus string")
        return check_owned_lab_api(url.strip(), username, token)
