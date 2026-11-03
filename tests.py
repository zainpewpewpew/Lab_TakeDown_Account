"""Offline backend and loopback-only proxy contract tests. No Chromium required."""
import http.client
import json
import unittest

from lab import HOST, LabState, handler_for, proxy_handler_for, serve


class LabUnitTests(unittest.TestCase):
    def test_policy_transitions(self):
        for policy, result in (
            ("retain", "active"),
            ("challenge", "verification_required"),
            ("revoke", "logged_out"),
        ):
            state = LabState(policy=policy, owner_session=True)
            self.assertEqual(state.current_status(True), "active")
            state.failed_logins = 3
            state.forgot_requests = 2
            self.assertEqual(state.current_status(True), result)
            self.assertEqual(state.current_status(False), "logged_out")

    def test_proxy_forwards_only_embedded_mock(self):
        state = LabState(policy="challenge")
        app = serve(handler_for(state))
        stats = {"forwarded": 0}
        proxy = serve(proxy_handler_for(app.server_address[1], stats))
        port = proxy.server_address[1]
        base = f"http://{HOST}:{app.server_address[1]}"

        def request(method, url, payload=None, cookie=None):
            conn = http.client.HTTPConnection(HOST, port, timeout=5)
            headers = {"Content-Type": "application/json"}
            if cookie:
                headers["Cookie"] = cookie
            conn.request(method, url, body=payload, headers=headers)
            response = conn.getresponse()
            status = response.status
            headers_out = dict(response.getheaders())
            body = response.read()
            conn.close()
            return status, headers_out, body

        try:
            code, _, body = request("GET", base + "/")
            self.assertEqual(code, 200)
            self.assertIn(b"Session Security Lab", body)

            code, _, _ = request("GET", "http://www.instagram.com/")
            self.assertEqual(code, 403)
            self.assertEqual(stats["forwarded"], 1)

            code, headers, _ = request("POST", base + "/api/owner-login", b"{}")
            self.assertEqual(code, 200)
            cookie = headers["Set-Cookie"].split(";", 1)[0]

            code, _, body = request("GET", base + "/api/session", cookie=cookie)
            self.assertEqual(json.loads(body)["status"], "active")
            for _ in range(3):
                code, _, body = request("POST", base + "/api/login", b"{}")
                self.assertEqual(code, 401)
            for _ in range(2):
                code, _, body = request("POST", base + "/api/forgot", b"{}")
                self.assertEqual(code, 200)
            code, _, body = request("GET", base + "/api/session", cookie=cookie)
            self.assertEqual(json.loads(body)["status"], "verification_required")
            self.assertEqual((state.failed_logins, state.forgot_requests), (3, 2))
        finally:
            proxy.shutdown()
            proxy.server_close()
            app.shutdown()
            app.server_close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
