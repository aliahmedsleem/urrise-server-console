"""Resource alert evaluation. Safe to use from a separate background monitor."""
from dataclasses import dataclass
from typing import Optional

THRESHOLDS = {
    "ram": (80.0, 90.0),
    "storage": (80.0, 90.0),
    "cpu_temperature": (75.0, 85.0),
    "network": (75.0, 90.0),
}

@dataclass(frozen=True)
class Alert:
    metric: str
    level: str
    value: float
    unit: str
    target: str = ""

def classify(metric: str, value: Optional[float], target: str = "") -> Optional[Alert]:
    """Return warning/critical; None means normal or sensor unavailable."""
    if metric not in THRESHOLDS or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    import math
    if not math.isfinite(number) or number < 0:
        return None
    warning, critical = THRESHOLDS[metric]
    level = "critical" if number >= critical else "warning" if number >= warning else None
    return Alert(metric, level, number, "°C" if metric == "cpu_temperature" else "%", target) if level else None

def evaluate(snapshot: dict, network_capacity_mbps: Optional[float] = None) -> list[Alert]:
    """Evaluate a telemetry snapshot; network utilization needs a verified link capacity."""
    result = []
    def add(metric, value, target=""):
        alert = classify(metric, value, target)
        if alert:
            result.append(alert)
    add("ram", snapshot.get("memory", {}).get("percent"))
    for disk in snapshot.get("disks", []):
        add("storage", disk.get("percent"), disk.get("mount", ""))
    cpu = snapshot.get("thermal", {}).get("cpu", {}).get("celsius")
    if cpu is None:
        cpu = snapshot.get("cpu", {}).get("temperature", {}).get("celsius")
    add("cpu_temperature", cpu)
    if network_capacity_mbps is not None and network_capacity_mbps > 0:
        net = snapshot.get("network", {})
        # Full duplex: compare the higher direction, not the sum.
        peak_bps = max(net.get("download_bps") or 0, net.get("upload_bps") or 0)
        utilization = 100 * (peak_bps * 8) / (network_capacity_mbps * 1_000_000)
        add("network", utilization)
    return result
