"""Offline tests for Ghoster.ai Instagram profile avatar delivery."""
from __future__ import annotations

import http.client
import time
import threading
import unittest
from unittest.mock import patch

from avatar_delivery import allowed_instagram_avatar_url, fetch_instagram_avatar
from dashboard import DashboardHTTP, LabJobs
from profile_preview import ProfilePreview


class AvatarValidationTests(unittest.TestCase):
    def test_allow_instagram_cdn_only(self):
        allowed = [
            "https://scontent.cdninstagram.com/v/t51.2885-19/a.jpg?oh=abc",
            "https://scontent-cgk1-1.cdninstagram.com/example.jpg",
            "https://scontent.xx.fbcdn.net/a.jpg",
        ]
        denied = [
            "http://scontent.cdninstagram.com/pic.jpg",
            "https://cdninstagram.com.evil.example/pic.jpg",
            "https://127.0.0.1/pic.jpg",
            "https://example.org/pic.jpg",
            "https://user:pass@scontent.cdninstagram.com/pic.jpg",
            "https://scontent.cdninstagram.com:444/pic.jpg",
            "file:///tmp/private",
        ]
        for url in allowed:
            with self.subTest(url=url):
                self.assertTrue(allowed_instagram_avatar_url(url))
        for url in denied:
            with self.subTest(url=url):
                self.assertFalse(allowed_instagram_avatar_url(url))

    def test_reject_untrusted_destination_before_http(self):
        with patch("avatar_delivery.build_opener") as opener:
            with self.assertRaises(ValueError):
                fetch_instagram_avatar("https://169.254.169.254/latest/meta-data")
            opener.assert_not_called()

    def test_cache_serves_photo_without_second_download(self):
        preview = ProfilePreview(cooldown_seconds=0)
        username = "rizkyasep_sutrisna"
        url = "https://scontent.cdninstagram.com/avatar.jpg?oh=abc"
        preview.instaloader_cache[username] = (
            time.monotonic() + 300,
            {"username": username, "source": "instaloader_public", "profile_picture_url": url},
        )
        image = b"\xff\xd8\xff\xe0mockjpeg"
        with patch("profile_preview.fetch_instagram_avatar", return_value=(image, "image/jpeg")) as fetch:
            first = preview.avatar(username)
            second = preview.avatar(username)
        self.assertEqual(first, (image, "image/jpeg"))
        self.assertEqual(second, first)
        fetch.assert_called_once_with(url)

    def test_uncached_avatar_is_not_fetched(self):
        preview = ProfilePreview(cooldown_seconds=0)
        with patch("profile_preview.fetch_instagram_avatar") as fetch:
            self.assertIsNone(preview.avatar("rizkyasep_sutrisna"))
            fetch.assert_not_called()


class HTTPAvatarTests(unittest.TestCase):
    def test_same_origin_image_and_csp(self):
        server = DashboardHTTP(("127.0.0.1", 0), LabJobs())
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            port = server.server_address[1]
            with patch.object(server.profile_preview, "avatar", return_value=(b"\xff\xd8\xffmock", "image/jpeg")):
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                conn.request("GET", "/api/profile-avatar?username=rizkyasep_sutrisna",
                             headers={"Host": "127.0.0.1:%d" % port})
                res = conn.getresponse()
                body = res.read()
                self.assertEqual(res.status, 200)
                self.assertEqual(res.getheader("Content-Type"), "image/jpeg")
                self.assertEqual(body, b"\xff\xd8\xffmock")
                conn.close()

            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", "/", headers={"Host": "127.0.0.1:%d" % port})
            res = conn.getresponse()
            csp = res.getheader("Content-Security-Policy") or ""
            self.assertIn("img-src 'self' data: https:", csp)
            res.read()
            conn.close()

        finally:
            server.shutdown()
            server.server_close()

    def test_avatar_route_does_not_accept_url(self):
        server = DashboardHTTP(("127.0.0.1", 0), LabJobs())
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            port = server.server_address[1]
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", "/api/profile-avatar?url=https://example.org/not-trusted.jpg",
                         headers={"Host": "127.0.0.1:%d" % port})
            res = conn.getresponse()
            self.assertEqual(res.status, 404)
            res.read()
            conn.close()
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
