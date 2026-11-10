"""Anonymous, read-only Instagram public profile metadata adapter for Ghoster.ai.

Does not load cookies, use logins, invoke private APIs directly, or retry blocked
requests. Only one public profile is queried when explicitly selected in UI.
"""
from __future__ import annotations


def public_profile(username: str) -> dict:
    """Load public profile metadata via Instaloader, or raise a safe error."""
    try:
        import instaloader
    except ImportError:
        raise ValueError(
            "Instaloader belum terpasang. Jalankan: python -m pip install -r requirements.txt"
        ) from None

    loader = instaloader.Instaloader(
        quiet=True,
        max_connection_attempts=1,
        request_timeout=10,
        download_pictures=False,
        download_videos=False,
        save_metadata=False,
    )
    try:
        profile = instaloader.Profile.from_username(loader.context, username)
        # Instaloader returns None for unavailable media_count on some sessions.
        return {
            "username": profile.username,
            "exists": True,
            "full_name": profile.full_name,
            "biography": profile.biography,
            "followers_count": profile.followers,
            "following_count": profile.followees,
            "media_count": profile.mediacount,
            "profile_picture_url": str(profile.profile_pic_url) if profile.profile_pic_url else None,
        }
    except instaloader.exceptions.ProfileNotExistsException:
        # Past anonymous 403 responses have been misreported as missing profiles.
        raise ValueError(
            "Instaloader tidak berhasil mengonfirmasi profil. "
            "Periksa ejaan username atau coba lagi nanti; ini bukan bukti akun tidak ada."
        ) from None
    except instaloader.exceptions.InstaloaderException as exc:
        raise ValueError(
            "Metadata Instagram sementara tidak tersedia (" + type(exc).__name__ + "). "
            "Coba lagi nanti tanpa mengulangi request terus-menerus."
        ) from None
