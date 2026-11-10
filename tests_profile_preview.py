"""Unit and integration tests for Ghoster.ai read-only profile preview."""
from __future__ import annotations
import http.client
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from profile_preview import ProfilePreview, shape, official_own_profile, private_profile
from dashboard import DashboardHTTP, LabJobs


class SampleTests(unittest.TestCase):
    def test_demo_profile_and_metrics(self):
        profile = ProfilePreview(cooldown_seconds=0).lookup({"mode": "demo", "username": "demo_account"})
        self.assertTrue(profile["exists"])
        self.assertEqual(profile["followers_count"], 1280)
        self.assertEqual(profile["media_count"], 17)
        self.assertIsNone(profile["profile_picture_url"])
        self.assertEqual(profile["source"], "offline_demo")

    def test_missing_stats_are_not_zero(self):
        profile = ProfilePreview(cooldown_seconds=0).lookup({"mode": "demo", "username": "rizky_asepsutrisna"})
        self.assertFalse(profile["exists"])
        self.assertIsNone(profile["followers_count"])
        self.assertIsNone(profile["media_count"])
        self.assertIsNone(profile["following_count"])

    def test_username_validation(self):
        for username in ("", "@name", "bad name", "x" * 31, "bad@example.org"):
            with self.subTest(username=username), self.assertRaises(ValueError):
                ProfilePreview(cooldown_seconds=0).lookup({"mode": "demo", "username": username})

    def test_sanitize_response(self):
        profile = shape({
            "username": "rizky_asepsutrisna", "followers_count": None,
            "media_count": True, "follows_count": 20,
            "biography": "hello", "profile_picture_url": "javascript:alert(1)",
        }, "rizky_asepsutrisna", "meta_official_own_account")
        self.assertIsNone(profile["followers_count"])
        self.assertIsNone(profile["media_count"])
        self.assertEqual(profile["following_count"], 20)
        self.assertIsNone(profile["profile_picture_url"])
        self.assertIsNone(profile["account_status"])

    def test_own_account_cannot_lookup_arbitrary_username(self):
        with patch.dict(os.environ, {"IG_PROFILE_ACCESS_TOKEN": "fake-token"}):
            with patch("profile_preview.read_json", return_value={
                "username": "connected_professional", "followers_count": 10,
            }) as read:
                with self.assertRaises(ValueError):
                    official_own_profile("rizky_asepsutrisna")
                self.assertIn("graph.instagram.com/v26.0/me", read.call_args.args[0])

    def test_missing_official_token(self):
        with patch.dict(os.environ, {"IG_PROFILE_ACCESS_TOKEN": ""}):
            with self.assertRaises(ValueError):
                official_own_profile("rizky_asepsutrisna")


class MockPrivateAPI(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        if not self.path.startswith("/api/lab/account-profile?"):
            self.send_error(404)
            return
        if self.headers.get("Authorization") != "Bearer lab-admin-token":
            self.send_error(403)
            return
        payload = json.dumps({
            "username": "demo_account", "exists": True,
            "name": "Test Lab User", "biography": "Owned lab only",
            "followers_count": 99, "follows_count": 12, "media_count": 5,
            "account_status": "active", "session_status": "active",
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class PrivateAPITests(unittest.TestCase):
    def test_owned_lab_api_with_admin_token(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), MockPrivateAPI)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            url = "http://127.0.0.1:%d/" % server.server_address[1]
            with patch.dict(os.environ, {"LAB_ACCOUNT_CHECK_TOKEN": "lab-admin-token"}):
                profile = private_profile(url, "demo_account")
            self.assertEqual(profile["followers_count"], 99)
            self.assertEqual(profile["full_name"], "Test Lab User")
            self.assertEqual(profile["source"], "private_lab_api")
        finally:
            server.shutdown()
            server.server_close()

    def test_public_url_rejected(self):
        with patch.dict(os.environ, {"LAB_ACCOUNT_CHECK_TOKEN": "lab-admin-token"}):
            with self.assertRaises(ValueError):
                private_profile("https://instagram.com", "demo_account")


class HTTPTests(unittest.TestCase):
    def test_dashboard_endpoint_protected(self):
        server = DashboardHTTP(("127.0.0.1", 0), LabJobs())
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            port = server.server_address[1]
            def post(token):
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                headers = {"Content-Type": "application/json", "Host": "127.0.0.1:%d" % port}
                if token:
                    headers["X-Lab-Token"] = token
                body = json.dumps({"mode": "demo", "username": "demo_account"})
                conn.request("POST", "/api/profile-preview", body=body, headers=headers)
                res = conn.getresponse()
                data = (res.status, json.loads(res.read()))
                conn.close()
                return data
            self.assertEqual(post(None)[0], 403)
            code, data = post(server.token)
            self.assertEqual(code, 200)
            self.assertEqual(data["followers_count"], 1280)
        finally:
            server.shutdown()
            server.server_close()

    def test_preview_template_exists(self):
        html = (Path(__file__).parent / "dashboard_static" / "index.html").read_text(encoding="utf-8")
        for field in ('id="profile-preview"', 'id="profile-followers"', 'id="profile-posts"',
                      'id="profile-photo"', 'id="profile-source"', '/api/profile-preview'):
            self.assertIn(field, html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
