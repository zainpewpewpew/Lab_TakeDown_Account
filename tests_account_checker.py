"""Ghoster.ai Account Checker tests (offline / loopback)."""
from __future__ import annotations

import http.client
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from account_checker import AccountChecker, _validate_account_result, check_owned_lab_api, clean_username
from dashboard import DashboardHTTP, LabJobs


class AccountValidationTests(unittest.TestCase):
    def test_username(self):
        self.assertEqual(clean_username("Lab.Demo_01"), "lab.demo_01")
        for value in ("", "@target", "user@example.com", "bad name", "../secret", "x"*31):
            with self.subTest(value=value), self.assertRaises(ValueError):
                clean_username(value)

    def test_demo_statuses(self):
        for username, status in (("demo_account", "active"), ("needs.verify", "verification_required"),
                                 ("disabled.demo", "disabled")):
            checker = AccountChecker(cooldown_seconds=0)
            response = checker.check({"mode": "demo", "username": username})
            self.assertTrue(response["exists"])
            self.assertEqual(response["account_status"], status)
            self.assertEqual(response["source"], "offline_demo")
        missing = AccountChecker(cooldown_seconds=0).check({"mode": "demo", "username": "missing"})
        self.assertFalse(missing["exists"])
        self.assertEqual(missing["account_status"], "unknown")

    def test_cooldown(self):
        checker = AccountChecker(cooldown_seconds=10)
        checker.check({"mode": "demo", "username": "demo_account"})
        with self.assertRaises(RuntimeError):
            checker.check({"mode": "demo", "username": "demo_account"})

    def test_contract(self):
        sample = {"username": "demo_account", "exists": True, "account_status": "active",
                  "session_status": "active"}
        self.assertEqual(_validate_account_result(sample, "demo_account")["source"], "private_lab_api")
        with self.assertRaises(ValueError):
            _validate_account_result({**sample, "username": "someone_else"}, "demo_account")
        with self.assertRaises(ValueError):
            _validate_account_result({**sample, "account_status": "suspended_from_instagram"}, "demo_account")

    def test_no_public_or_unauthenticated_requests(self):
        with self.assertRaises(ValueError):
            check_owned_lab_api("https://instagram.com/", "demo_account", "token")
        with self.assertRaises(ValueError):
            check_owned_lab_api("https://example.org/", "demo_account", "token")
        with self.assertRaises(ValueError):
            check_owned_lab_api("http://127.0.0.1:3000/", "demo_account", "")


class StubAdminAPI(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        from urllib.parse import urlsplit, parse_qs
        path = urlsplit(self.path)
        if path.path != "/api/lab/account-status":
            self.send_error(404)
            return
        if self.headers.get("Authorization") != "Bearer mock-admin-token":
            self.send_error(403)
            return
        username = parse_qs(path.query).get("username", [""])[0]
        payload = json.dumps({"username": username, "exists": True, "account_status": "active",
                              "session_status": "active"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class PrivateAPITests(unittest.TestCase):
    def test_loopback_api_contract(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), StubAdminAPI)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = check_owned_lab_api("http://127.0.0.1:%s/" % server.server_address[1],
                                         "demo_account", "mock-admin-token")
            self.assertEqual(result["account_status"], "active")
            self.assertEqual(result["source"], "private_lab_api")
        finally:
            server.shutdown()
            server.server_close()


class DashboardAccountAPITests(unittest.TestCase):
    def test_post_uses_local_token(self):
        server = DashboardHTTP(("127.0.0.1", 0), LabJobs())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        try:
            def post(token):
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                body = json.dumps({"mode": "demo", "username": "demo_account"})
                headers = {"Content-Type": "application/json", "Host": "127.0.0.1:%s" % port}
                if token:
                    headers["X-Lab-Token"] = token
                conn.request("POST", "/api/account-check", body, headers)
                res = conn.getresponse()
                result = (res.status, json.loads(res.read()))
                conn.close()
                return result
            self.assertEqual(post(None)[0], 403)
            status, body = post(server.token)
            self.assertEqual(status, 200)
            self.assertEqual(body["account_status"], "active")
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
