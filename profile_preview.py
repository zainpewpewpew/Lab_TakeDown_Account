"""Ghoster.ai read-only profile previews from mock data, private lab API or official Meta.

Never scrapes Instagram, guesses passwords, changes accounts, or sends reset requests.
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from account_checker import _scope_check, clean_username

GRAPH_HOST = "https://graph.instagram.com"
GRAPH_VERSION = "v26.0"
GRAPH_FIELDS = "username,name,biography,followers_count,follows_count,media_count,profile_picture_url"
MAX_BODY = 16384
SAMPLES = {
    "demo_account": {
        "full_name": "Ghoster Demo Account",
        "biography": "Demo profile for private, local testing.",
        "followers_count": 1280, "following_count": 206, "media_count": 17,
        "account_status": "active", "session_status": "active",
    },
    "needs.verify": {
        "full_name": "Verification Demo", "biography": "Account requiring verification in this lab.",
        "followers_count": 330, "following_count": 49, "media_count": 8,
        "account_status": "verification_required", "session_status": "expired",
    },
    "disabled.demo": {
        "full_name": "Disabled Demo", "biography": "Disabled lab profile.",
        "followers_count": 0, "following_count": 0, "media_count": 0,
        "account_status": "disabled", "session_status": "revoked",
    },
}

def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def valid_count(value):
    return value if type(value) is int and value >= 0 else None

def safe_picture(value):
    # Only HTTPS images: never return javascript:, data:, file: or private HTTP URLs.
    if isinstance(value, str) and value.startswith("https://") and len(value) < 2000 and not any(c.isspace() for c in value):
        return value
    return None

def shape(raw, username, source):
    if not isinstance(raw, dict) or not isinstance(raw.get("username"), str) or raw["username"].lower() != username:
        raise ValueError("Username respons API tidak sesuai dengan permintaan")
    exists = raw.get("exists", True)
    if type(exists) is not bool:
        raise ValueError("exists harus boolean")
    name = raw.get("full_name", raw.get("name"))
    if not isinstance(name, str) or len(name) > 150:
        name = None
    bio = raw.get("biography")
    if not isinstance(bio, str):
        bio = ""
    status = raw.get("account_status") if source != "meta_official_own_account" else None
    if status not in ("active", "disabled", "verification_required", "unknown"):
        status = None
    session = raw.get("session_status") if source != "meta_official_own_account" else None
    if session not in ("active", "expired", "revoked", "unknown"):
        session = None
    return {
        "username": username,
        "full_name": name,
        "biography": bio[:500],
        "profile_picture_url": safe_picture(raw.get("profile_picture_url")),
        "followers_count": valid_count(raw.get("followers_count")),
        "following_count": valid_count(raw.get("following_count", raw.get("follows_count"))),
        "media_count": valid_count(raw.get("media_count")),
        "exists": exists,
        "account_status": status,
        "session_status": session,
        "is_verified": raw.get("is_verified") is True,
        "checked_at": stamp(),
        "source": source,
    }

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirect API tidak diizinkan")

def read_json(url, token):
    if not isinstance(token, str) or not token or len(token) > 2048 or "\n" in token or "\r" in token:
        raise ValueError("Token API belum dikonfigurasi")
    request = Request(url, headers={"Authorization": "Bearer " + token,
                                    "Accept": "application/json", "User-Agent": "Ghoster-ProfilePreview/1.0"}, method="GET")
    # Do not use a user-supplied proxy or redirect with an admin API token.
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=6) as response:
            if response.status != 200:
                raise ValueError("API profil tidak mengembalikan HTTP 200")
            if "application/json" not in response.headers.get("Content-Type", "").lower():
                raise ValueError("API profil tidak mengembalikan JSON")
            raw = response.read(16385)
            if len(raw) > 16384:
                raise ValueError("Respons API profil terlalu besar")
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise ValueError("Token API ditolak; periksa izin akun") from None
        raise ValueError("API gagal (HTTP " + str(exc.code) + ")") from None
    except (OSError, URLError, TimeoutError) as exc:
        raise ValueError("Koneksi API gagal: " + type(exc).__name__) from None
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise ValueError("Respons API bukan JSON valid") from None
    if not isinstance(body, dict) or "error" in body:
        raise ValueError("API tidak mengembalikan data profil yang valid")
    return body

def private_profile(origin, username):
    parts = _scope_check(origin)
    token = os.getenv("LAB_ACCOUNT_CHECK_TOKEN", "")
    if not token:
        raise ValueError("Set LAB_ACCOUNT_CHECK_TOKEN untuk API admin web lab")
    url = parts.scheme + "://" + parts.netloc + "/api/lab/account-profile?" + urlencode({"username": username})
    return shape(read_json(url, token), username, "private_lab_api")

def official_own_profile(username):
    """Read *only* the professional Instagram account that owns the token."""
    token = os.getenv("IG_PROFILE_ACCESS_TOKEN", "")
    if not token:
        raise ValueError("Hubungkan akun Business/Creator melalui Meta: IG_PROFILE_ACCESS_TOKEN belum tersedia")
    url = GRAPH_HOST + "/" + GRAPH_VERSION + "/me?" + urlencode({"fields": GRAPH_FIELDS})
    body = read_json(url, token)
    if not isinstance(body.get("username"), str) or body["username"].lower() != username:
        raise ValueError("Username bukan akun profesional yang terhubung ke token Meta")
    return shape(body, username, "meta_official_own_account")

class ProfilePreview:
    def __init__(self, cooldown_seconds=2):
        self.lock = threading.Lock()
        self.cooldown_seconds = cooldown_seconds
        self.last_check = 0.0

    def lookup(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("Permintaan profil harus objek JSON")
        mode = payload.get("mode", "demo")
        if mode not in ("demo", "private", "instagram_own"):
            raise ValueError("Pilih demo, private, atau instagram_own")
        username = clean_username(payload.get("username", ""))
        with self.lock:
            if time.monotonic() - self.last_check < self.cooldown_seconds:
                raise RuntimeError("Tunggu sebentar sebelum memperbarui preview")
            self.last_check = time.monotonic()
        if mode == "demo":
            sample = SAMPLES.get(username)
            if sample is None:
                return shape({"username": username, "exists": False}, username, "offline_demo")
            return shape({"username": username, "exists": True, **sample}, username, "offline_demo")
        if mode == "private":
            origin = payload.get("url")
            if not isinstance(origin, str):
                raise ValueError("Masukkan URL web lab privat")
            return private_profile(origin.strip(), username)
        return official_own_profile(username)
