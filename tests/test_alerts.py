import unittest
from app.alerts import classify, evaluate

class AlertThresholdTests(unittest.TestCase):
    def test_boundaries(self):
        for metric, (warn, critical) in {
            "ram": (80, 90), "storage": (80, 90),
            "cpu_temperature": (75, 85), "network": (75, 90)
        }.items():
            self.assertIsNone(classify(metric, warn - 0.1))
            self.assertEqual(classify(metric, warn).level, "warning")
            self.assertEqual(classify(metric, critical).level, "critical")
    def test_missing_temperature_does_not_alert(self):
        self.assertEqual(evaluate({"memory": {"percent": 10}, "disks": [], "thermal": {"cpu": {"celsius": None}}, "network": {}}), [])
    def test_each_volume(self):
        data = {"memory": {"percent": 85}, "disks": [{"mount": "/", "percent": 95}, {"mount": "/data", "percent": 81}], "thermal": {"cpu": {"celsius": 80}}, "network": {}}
        self.assertEqual(len(evaluate(data)), 4)
    def test_network_requires_capacity(self):
        data = {"memory": {}, "disks": [], "thermal": {}, "network": {"download_bps": 11_250_000, "upload_bps": 0}}
        self.assertFalse(evaluate(data))
        self.assertEqual(evaluate(data, 100)[0].level, "critical")

if __name__ == "__main__":
    unittest.main()
