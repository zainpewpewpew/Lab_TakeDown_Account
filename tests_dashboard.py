"""Local-only tests for dashboard security and demo web interface."""
from __future__ import annotations

import http.client
import json
import re
import sys
import time
import types
import unittest
from unittest.mock import patch
from urllib.request import urlopen

# The real repository has web_lab_flow.py. These tests also work in an isolated
# folder where only the new dashboard files have been staged.
try:
    import web_lab_flow  # noqa: F401
except ImportError:
    from urllib.parse import urlsplit
    import ipaddress
    def stub_private_url(url):
        p = urlsplit(url)
        if p.scheme not in ("http", "https") or not p.hostname:
            raise ValueError("invalid")
        if any(p.hostname.endswith(x) for x in ("instagram.com", "facebook.com")):
            raise ValueError("blocked")
        if p.hostname == "localhost":
            return True
        try:
            return ipaddress.ip_address(p.hostname).is_private
        except ValueError:
            return False
    sys.modules["web_lab_flow"] = types.SimpleNamespace(private_url=stub_private_url)

from dashboard import DashboardHTTP, LabJobs, valid_private_target
from mock_recovery_lab import start_mock_server


class ValidationTests(unittest.TestCase):
    def test_valid_private_urls(self):
        self.assertEqual(valid_private_target("http://127.0.0.1:3000/"), "http://127.0.0.1:3000/")
        self.assertEqual(valid_private_target("http://192.168.1.20:3000/"), "http://192.168.1.20:3000/")

    def test_denied_urls(self):
        for url in ["https://instagram.com", "https://www.instagram.com/accounts/password/reset/", "https://example.org", "file:///etc/passwd", "http://0.0.0.0:9999", "http://169.254.1.1"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                valid_private_target(url)

    def test_mock_screen_contains_requested_elements(self):
        server, url = start_mock_server(options="email", challenge=True)
        try:
            html = urlopen(url).read().decode()
            for term in ("Forgot password?", "Get link via email", "Help us confirm it's you", "We sent an email"):
                self.assertIn(term, html)
        finally:
            server.shutdown()
            server.server_close()


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = LabJobs()
        cls.server = DashboardHTTP(("127.0.0.1", 0), cls.engine)
        import threading
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.engine = LabJobs()
        self.server.engine = self.engine

    def request(self, method, path, data=None, token=None, host=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {"Host": host or f"127.0.0.1:{self.port}"}
        if token:
            headers["X-Lab-Token"] = token
        if data is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(data)
        conn.request(method, path, body=data, headers=headers)
        res = conn.getresponse()
        code, body = res.status, res.read()
        conn.close()
        return code, body

    def test_ui_and_state(self):
        code, body = self.request("GET", "/")
        self.assertEqual(code, 200)
        self.assertIn(b"Browser", body)
        self.assertIn(b"Web lab privat", body)
        self.assertNotIn(b"__LOCAL_LAB_TOKEN__", body)
        code, body = self.request("GET", "/api/state")
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["status"], "idle")

    def test_host_and_token_protection(self):
        code, _ = self.request("GET", "/", host="attacker.invalid")
        self.assertEqual(code, 403)
        code, _ = self.request("POST", "/api/start", data={"mode": "demo"})
        self.assertEqual(code, 403)

    def test_public_automation_denied(self):
        code, body = self.request("POST", "/api/start",
                                  data={"mode": "private", "url": "https://www.instagram.com", "identifier": "demo@lab.test"},
                                  token=self.server.token)
        self.assertEqual(code, 400)
        self.assertTrue(json.loads(body)["error"])

    def test_demo_job_accepted_and_singleton(self):
        with patch.object(self.engine, "_run", lambda *args, **kwargs: time.sleep(.2)):
            code, body = self.request("POST", "/api/start", data={"mode": "demo", "identifier": "demo@lab.test"},token=self.server.token)
            self.assertEqual(code, 200)
            data = json.loads(body)
            self.assertEqual(data["run"]["mode"], "demo")
            self.assertNotIn("demo@lab.test", json.dumps(data))
            code, _ = self.request("POST", "/api/start", data={"mode": "demo", "identifier": "another@lab.test"},token=self.server.token)
            self.assertEqual(code, 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)