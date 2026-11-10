"""Offline tests for Ghoster.ai private-lab Chromium/Multilogin recovery runner.

Tests never visit public websites or request real password resets.
"""
from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

from recovery_lab_cli import (
    Pacer, Terminal, run_flow, validate_local_cdp, validate_owned_lab_url,
)


class ScopeTests(unittest.TestCase):
    def test_owned_lab_only(self):
        self.assertEqual(validate_owned_lab_url("http://127.0.0.1:3000/"), "http://127.0.0.1:3000/")
        self.assertEqual(validate_owned_lab_url("http://localhost:8000/"), "http://localhost:8000/")
        self.assertEqual(validate_owned_lab_url("http://192.168.1.10:3000/"), "http://192.168.1.10:3000/")
        for url in (
            "https://instagram.com/", "https://www.instagram.com/",
            "https://example.org/", "http://8.8.8.8/", "http://0.0.0.0/",
            "http://169.254.1.10/", "file:///etc/passwd",
            "https://user:password@localhost:3000/",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_owned_lab_url(url)

    def test_local_multilogin_cdp_only(self):
        valid = (
            "http://127.0.0.1:50468",
            "http://localhost:9222/",
            "ws://127.0.0.1:50468/devtools/browser/abc123",
        )
        for endpoint in valid:
            self.assertEqual(validate_local_cdp(endpoint), endpoint)
        denied = (
            "https://launcher.mlx.yt:45001",
            "http://example.com:9222",
            "ws://8.8.8.8:9222/devtools/browser/id",
            "ws://127.0.0.1:9222/other/path",
            "http://user:pass@127.0.0.1:9222",
            "http://127.0.0.1",
            "http://127.0.0.1:9222/other",
        )
        for endpoint in denied:
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                validate_local_cdp(endpoint)

    def test_pacing_is_bounded_and_logged(self):
        sleeps = []
        terminal = Terminal()
        pacer = Pacer(1, 3, sleeper=sleeps.append, rng=lambda low, high: 2.1)
        with redirect_stdout(io.StringIO()):
            pacer.between(terminal, "mengklik Continue")
        self.assertEqual(sleeps, [2.1])
        self.assertEqual(terminal.entries[-1]["stage"], "PACE")
        for args in ((3, 1), (-1, 2), (1, 10)):
            with self.assertRaises(ValueError):
                Pacer(*args)


class FakeTerminal:
    def __init__(self):
        self.entries = []

    def line(self, stage, message, tone="cyan"):
        self.entries.append((stage, message, tone))


def run_mocked_flow(decision):
    page = MagicMock()
    terminal = FakeTerminal()
    pacer = Pacer(0, 0, sleeper=lambda _: None)
    forgotten, textfield, first_continue, second_continue = [MagicMock() for _ in range(4)]
    email, sms, challenge, done = [MagicMock() for _ in range(4)]
    base = [forgotten, textfield, first_continue, second_continue]
    if decision == "email":
        optional = [email, None, done]
    elif decision == "sms":
        optional = [None, sms, None, done]
    elif decision == "none":
        optional = [None, None]
        base = base[:3]
    elif decision == "human":
        optional = [email, challenge, done]
    else:
        raise AssertionError(decision)

    with patch("recovery_lab_cli.required", side_effect=base) as required:
        with patch("recovery_lab_cli.locate", side_effect=optional):
            with patch("builtins.input", return_value=""):
                result = run_flow(page, "http://127.0.0.1:3000/", "dummy@lab.test",
                                  terminal, pacer, manual=True)
    return result, terminal, page, textfield, email, sms, done, required


class WorkflowTests(unittest.TestCase):
    def test_email_priority_and_success(self):
        result, log, page, textfield, email, sms, done, required = run_mocked_flow("email")
        self.assertEqual(result, {"status": "CONFIRMATION_VISIBLE", "channel": "email"})
        self.assertEqual(required.call_count, 4)
        textfield.fill.assert_called_once_with("dummy@lab.test")
        email.click.assert_called_once()
        sms.click.assert_not_called()
        done.click.assert_called_once()
        self.assertTrue(any(stage == "STEP 6a" for stage, _, _ in log.entries))
        self.assertFalse(any("dummy@lab.test" in message for _, message, _ in log.entries))

    def test_sms_fallback(self):
        result, log, _, _, email, sms, done, _ = run_mocked_flow("sms")
        self.assertEqual(result["channel"], "sms")
        sms.click.assert_called_once()
        done.click.assert_called_once()
        self.assertTrue(any(stage == "STEP 6b" for stage, _, _ in log.entries))

    def test_no_channel_stops_without_second_continue(self):
        result, log, _, _, _, _, _, required = run_mocked_flow("none")
        self.assertEqual(result["status"], "NO_CHANNEL")
        self.assertEqual(required.call_count, 3)
        self.assertTrue(any("berhenti" in message for _, message, _ in log.entries))

    def test_human_verification_needs_operator_enter(self):
        result, log, _, _, _, _, _, _ = run_mocked_flow("human")
        self.assertEqual(result["status"], "CONFIRMATION_VISIBLE")
        self.assertTrue(any(stage == "MANUAL" for stage, _, _ in log.entries))


if __name__ == "__main__":
    unittest.main(verbosity=2)
