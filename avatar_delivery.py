"""Image-only fetch for Instagram CDN avatars already found by the preview adapter.

This module never accepts untrusted arbitrary URLs from a browser request.
An allowlist prevents fetching private network resources or unexpected domains.
"""
from __future__ import annotations

from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from urllib.error import HTTPError, URLError

MAX_AVATAR_BYTES = 512 * 1024
ALLOWED_SUFFIXES = (".cdninstagram.com", ".fbcdn.net")
ALLOWED_TYPES = ("image/jpeg", "image/png", "image/webp")


class RejectRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def allowed_instagram_avatar_url(url):
    if not isinstance(url, str) or not url or len(url) > 2048:
        return False
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower().rstrip(".")
        return (
            parts.scheme == "https"
            and bool(host)
            and any(host.endswith(s) for s in ALLOWED_SUFFIXES)
            and parts.port in (None, 443)
            and parts.username is None
            and parts.password is None
            and not parts.fragment
        )
    except ValueError:
        return False


def fetch_instagram_avatar(url):
    if not allowed_instagram_avatar_url(url):
        raise ValueError("Foto tidak berasal dari Instagram CDN yang diizinkan")
    request = Request(url, headers={
        "Accept": "image/jpeg,image/png,image/webp",
        "User-Agent": "GhosterAI-ProfilePreview/1.0",
    })
    opener = build_opener(ProxyHandler({}), RejectRedirect())
    try:
        with opener.open(request, timeout=8) as response:
            mime = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if mime not in ALLOWED_TYPES:
                raise ValueError("Respons CDN bukan gambar yang didukung")
            body = response.read(MAX_AVATAR_BYTES + 1)
            if not body or len(body) > MAX_AVATAR_BYTES:
                raise ValueError("Foto profil kosong atau terlalu besar")
            return body, mime
    except (HTTPError, URLError, TimeoutError, OSError):
        raise ValueError("Foto profil tidak dapat diambil dari Instagram CDN") from None
