"""Unit tests for the private lab scope guard; no network requests are sent."""
import unittest
from web_lab_flow import private_url, same_origin, conceal


class UrlScopeTests(unittest.TestCase):
    def test_private_urls_allowed(self):
        self.assertTrue(private_url("http://127.0.0.1:3000/"))
        self.assertTrue(private_url("http://localhost:8000/"))
        self.assertTrue(private_url("http://192.168.10.20:3000/"))

    def test_public_urls_are_inspection_only(self):
        self.assertFalse(private_url("https://example.org/"))
        self.assertFalse(private_url("https://8.8.8.8/"))

    def test_meta_domains_are_denied(self):
        for url in ("https://instagram.com/", "https://www.instagram.com/",
                    "https://m.facebook.com/", "https://meta.com/"):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    private_url(url)

    def test_origin_and_masking(self):
        self.assertTrue(same_origin("http://localhost:3000/", "http://localhost:3000/accounts/password/reset/"))
        self.assertFalse(same_origin("http://localhost:3000/", "http://localhost:4000/"))
        self.assertEqual(conceal("demo@lab.test"), "d***@lab.test")
        self.assertEqual(conceal("1234567890"), "12***90")


if __name__ == "__main__":
    unittest.main(verbosity=2)
