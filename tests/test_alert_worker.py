import unittest
from unittest.mock import patch
from app.alerts import evaluate

class MonitorEvaluationTests(unittest.TestCase):
    def test_storage_thresholds_per_mount(self):
        data = {"memory": {"percent": 79}, "disks": [{"mount": "/", "percent": 80}, {"mount": "/mnt/data", "percent": 90}], "thermal": {"cpu": {"celsius": 75}}, "network": {}}
        levels = {(a.metric, a.target): a.level for a in evaluate(data)}
        self.assertEqual(levels[("storage", "/")], "warning")
        self.assertEqual(levels[("storage", "/mnt/data")], "critical")
        self.assertEqual(levels[("cpu_temperature", "")], "warning")
    def test_network_full_duplex_peak(self):
        data = {"memory": {}, "disks": [], "thermal": {}, "network": {"download_bps": 10_000_000, "upload_bps": 10_000_000}}
        result = evaluate(data, 100)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].level, "warning")
    def test_bad_readings_ignored(self):
        data = {"memory": {"percent": None}, "disks": [{"mount": "/", "percent": "not available"}], "thermal": {"cpu": {"celsius": None}}, "network": {}}
        self.assertEqual(evaluate(data), [])

if __name__ == "__main__":
    unittest.main()
