"""Offline regression tests: no hardware stress or real push delivery."""
import unittest
from app.alerts import classify, evaluate


class AlertRuleTests(unittest.TestCase):
    def test_ram_thresholds(self):
        self.assertIsNone(classify("ram", 79.9))
        self.assertEqual(classify("ram", 80).level, "warning")
        self.assertEqual(classify("ram", 90).level, "critical")

    def test_storage_thresholds(self):
        self.assertEqual(classify("storage", 80, "/").target, "/")
        self.assertEqual(classify("storage", 90).level, "critical")

    def test_cpu_thresholds(self):
        self.assertIsNone(classify("cpu_temperature", 74.9))
        self.assertEqual(classify("cpu_temperature", 75).level, "warning")
        self.assertEqual(classify("cpu_temperature", 85).level, "critical")

    def test_invalid_readings_are_not_alerts(self):
        for value in (None, float("nan"), float("inf"), -1, "invalid"):
            self.assertIsNone(classify("ram", value))

    def test_network_requires_known_capacity(self):
        sample = {
            "memory": {"percent": 20},
            "disks": [],
            "thermal": {"cpu": {"celsius": 30}},
            "network": {"download_bps": 11_250_000, "upload_bps": 0},
        }
        self.assertEqual(evaluate(sample), [])
        self.assertEqual(evaluate(sample, 100)[0].level, "critical")

    def test_storage_mounts_independent(self):
        sample = {
            "memory": {"percent": 90},
            "disks": [{"mount": "/", "percent": 85}, {"mount": "/data", "percent": 95}],
            "thermal": {"cpu": {"celsius": 80}},
            "network": {},
        }
        alerts = evaluate(sample)
        self.assertEqual({(a.metric, a.target, a.level) for a in alerts}, {
            ("ram", "", "critical"),
            ("storage", "/", "warning"),
            ("storage", "/data", "critical"),
            ("cpu_temperature", "", "warning"),
        })


if __name__ == "__main__":
    unittest.main()
