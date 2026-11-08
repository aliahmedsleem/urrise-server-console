"""Unit tests for service transition monitoring (no systemd or push required)."""
import unittest
from types import SimpleNamespace
from app.alert_worker import monitored_service_states, service_transitions


class ServiceAlertTests(unittest.TestCase):
    def test_monitor_allowlisted_only(self):
        called = []
        def runner(cmd, **kwargs):
            called.append(cmd[-1])
            return SimpleNamespace(stdout="active\n")
        result = monitored_service_states({"services": {
            "portexa.service": {}, "urrise-alert-worker.service": {}, "bad": {}
        }}, runner=runner)
        self.assertEqual(result, {"portexa.service": "active"})
        self.assertEqual(called, ["portexa.service"])

    def test_confirm_down_then_recover(self):
        states, down, up = {}, {}, {}
        def sample(value):
            return service_transitions(states, {"portexa.service": value}, down, up)
        self.assertEqual(sample("active"), [])
        self.assertEqual(sample("active"), [])
        self.assertEqual(sample("failed"), [])
        self.assertEqual(sample("failed"), [("portexa.service", "critical")])
        self.assertEqual(sample("failed"), [])
        self.assertEqual(sample("active"), [])
        self.assertEqual(sample("active"), [("portexa.service", "recovered")])

    def test_initially_inactive_no_false_alarm(self):
        states, down, up = {}, {}, {}
        self.assertEqual(service_transitions(states, {"portexa.service": "inactive"}, down, up), [])
        self.assertEqual(service_transitions(states, {"portexa.service": "inactive"}, down, up), [])
        self.assertEqual(states, {})

    def test_unknown_not_reported(self):
        states, down, up = {"portexa.service": "up"}, {}, {}
        service_transitions(states, {"portexa.service": "failed"}, down, up)
        self.assertEqual(service_transitions(states, {}, down, up), [])
        self.assertEqual(service_transitions(states, {"portexa.service": "active"}, down, up), [])


if __name__ == "__main__":
    unittest.main()
