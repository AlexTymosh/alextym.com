"""Deterministic tests for the Stage 17 read-only release probe."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("site_release_probe.py")
spec = importlib.util.spec_from_file_location("site_release_probe", SCRIPT)
assert spec and spec.loader
probe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = probe
spec.loader.exec_module(probe)


class OriginTests(unittest.TestCase):
    def test_https_origin(self):
        self.assertEqual(probe.normalize_origin("https://example.com/"), "https://example.com")

    def test_local_http_origin(self):
        self.assertEqual(probe.normalize_origin("http://127.0.0.1:8000/"), "http://127.0.0.1:8000")

    def test_reject_remote_http(self):
        with self.assertRaises(ValueError):
            probe.normalize_origin("http://example.com")

    def test_reject_credentials(self):
        with self.assertRaises(ValueError):
            probe.normalize_origin("https://u:password@example.com")

    def test_reject_path_and_query(self):
        for origin in ("https://example.com/api", "https://example.com/?secret=1"):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                probe.normalize_origin(origin)


class HealthContractTests(unittest.TestCase):
    def test_live_status(self):
        self.assertEqual(probe.classify_health("/api/health/live", 200, {"status": "alive"})[0], True)
        self.assertFalse(probe.classify_health("/api/health/live", 503, {"status": "alive"})[0])

    def test_ready_strict_on_rag(self):
        healthy = {"status": "ready", "vector_db": "ready", "llm_config": "configured"}
        self.assertTrue(probe.classify_health("/api/health/ready", 200, healthy)[0])
        self.assertFalse(probe.classify_health("/api/health/ready", 200, {**healthy, "vector_db": "not_configured"})[0])
        self.assertFalse(probe.classify_health("/api/health/ready", 503, healthy)[0])

    def test_non_json_not_accepted(self):
        self.assertFalse(probe.classify_health("/api/health/ready", 200, None)[0])
        self.assertFalse(probe.classify_health("/api/health/ready", 200, "ready")[0])


if __name__ == "__main__":
    unittest.main()
