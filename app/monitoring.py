import json
import os
import platform
import socket
import subprocess
import time
from datetime import datetime, timezone

import psutil

_prev_net = None
_prev_time = None


def _safe_call(function, default=None, *args, **kwargs):
    """Run an optional system probe without breaking the whole telemetry response."""
    try:
        return function(*args, **kwargs)
    except (OSError, PermissionError, NotImplementedError, AttributeError):
        return default


def _thermal_sensors():
    """Collect CPU and other thermal sensor readings exposed by Linux."""
    readings = []
    cpu_readings = []

    sensors = _safe_call(psutil.sensors_temperatures, {}, fahrenheit=False) or {}

    for chip, entries in sensors.items():
        for entry in entries:
            if entry.current is None:
                continue

            label = (entry.label or chip).strip()
            normalized = f"{chip} {label}".lower()
            value = round(float(entry.current), 1)
            item = {
                "name": label,
                "sensor": chip,
                "celsius": value,
                "high": entry.high,
                "critical": entry.critical,
            }
            readings.append(item)

            if "coretemp" in chip.lower() or any(
                key in normalized
                for key in ("cpu", "package", "core", "tctl", "tdie")
            ):
                cpu_readings.append(item)

    package = next(
        (item for item in cpu_readings if "package" in item["name"].lower()),
        None,
    )
    if package is None and cpu_readings:
        package = max(cpu_readings, key=lambda item: item["celsius"])

    # ACPI readings are shown separately from CPU package/core readings.
    system_readings = [
        item for item in readings
        if item not in cpu_readings
        and not any(word in f"{item['sensor']} {item['name']}".lower()
                    for word in ("battery", "bat", "acad"))
    ]

    return {
        "cpu": {
            "celsius": package["celsius"] if package else None,
            "source": package["name"] if package else "unavailable",
        },
        "sensors": readings,
        "system": {
            "celsius": max(
                (item["celsius"] for item in system_readings),
                default=None,
            ),
            "source": (
                max(system_readings, key=lambda item: item["celsius"])["name"]
                if system_readings else "unavailable"
            ),
        },
    }


def _temperature():
    """Keep the legacy CPU temperature field for existing clients."""
    return _thermal_sensors()["cpu"]


def _fan_speeds():
    """Return real fan RPM readings when the OS exposes fan sensors."""
    fans = _safe_call(psutil.sensors_fans, {}) or {}
    result = []

    for chip, entries in fans.items():
        for entry in entries:
            if entry.current is None:
                continue
            result.append({
                "name": entry.label or chip,
                "sensor": chip,
                "rpm": int(entry.current),
            })

    return result


def snapshot():
    global _prev_net, _prev_time

    now = time.monotonic()
    net = _safe_call(psutil.net_io_counters, None)
    recv = float(net.bytes_recv) if net else 0.0
    sent = float(net.bytes_sent) if net else 0.0
    down = up = None

    if net and _prev_net is not None and _prev_time is not None:
        elapsed = max(now - _prev_time, 0.001)
        down = max(0.0, recv - _prev_net["recv"]) / elapsed
        up = max(0.0, sent - _prev_net["sent"]) / elapsed

    if net:
        _prev_net = {"recv": recv, "sent": sent}
        _prev_time = now

    vm = _safe_call(psutil.virtual_memory, None)
    disk_rows, seen = [], set()
    partitions = _safe_call(psutil.disk_partitions, [], all=False) or []

    for part in partitions:
        if part.mountpoint in seen:
            continue
        seen.add(part.mountpoint)
        usage = _safe_call(psutil.disk_usage, None, part.mountpoint)
        if usage is None:
            continue
        disk_rows.append({
            "device": part.device,
            "mount": part.mountpoint,
            "filesystem": part.fstype,
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "percent": usage.percent,
        })

    load = _safe_call(os.getloadavg, []) or []
    freq = _safe_call(psutil.cpu_freq, None)
    boot = _safe_call(psutil.boot_time, time.time())
    interfaces, addrs, stats = [], {}, {}

    # Network inspection is optional: failures must not hide CPU/RAM/storage.
    addrs = _safe_call(psutil.net_if_addrs, {}) or {}
    stats = _safe_call(psutil.net_if_stats, {}) or {}
    for name in sorted(set(addrs) | set(stats)):
        status = stats.get(name)
        ip4 = next(
            (a.address for a in addrs.get(name, [])
             if a.family == socket.AF_INET),
            "",
        )
        ip6 = next(
            (a.address for a in addrs.get(name, [])
             if getattr(a.family, "name", "") == "AF_INET6"),
            "",
        )
        interfaces.append({
            "name": name,
            "up": status.isup if status else None,
            "speed_mbps": (status.speed or None) if status else None,
            "mtu": status.mtu if status else None,
            "ipv4": ip4,
            "ipv6": ip6,
        })

    swap = _safe_call(psutil.swap_memory, None)
    thermal = _thermal_sensors()
    process_ids = _safe_call(psutil.pids, []) or []

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "host": socket.gethostname(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "uptime_seconds": max(0, int(time.time() - boot)) if boot else None,
        "cpu": {
            "percent": _safe_call(psutil.cpu_percent, 0.0, interval=None),
            "cores_physical": _safe_call(psutil.cpu_count, None, logical=False),
            "cores_logical": _safe_call(psutil.cpu_count, None, logical=True),
            "frequency_mhz": round(freq.current, 0) if freq and freq.current else None,
            "temperature": thermal["cpu"],
            "load_average": load,
        },
        "thermal": thermal,
        "fans": _fan_speeds(),
        "memory": {
            "total": vm.total if vm else 0,
            "used": vm.used if vm else 0,
            "available": vm.available if vm else 0,
            "percent": vm.percent if vm else None,
            "swap_total": swap.total if swap else 0,
            "swap_used": swap.used if swap else 0,
            "swap_percent": swap.percent if swap else 0,
        },
        "disks": disk_rows,
        "network": {
            "download_bps": down,
            "upload_bps": up,
            "bytes_received": int(recv),
            "bytes_sent": int(sent),
            "interfaces": interfaces,
        },
        "processes": len(process_ids),
    }


def safe_service_status(service):
    policy = read_policy()
    if service not in policy.get("services", {}):
        raise ValueError("Service is not allowlisted")
    try:
        result = subprocess.run(
            ["/usr/bin/systemctl", "is-active", service],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        return result.stdout.strip() or "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def read_policy():
    path = os.environ.get("URRISE_POLICY_PATH", "/etc/urrise-console/policy.json")
    try:
        with open(path, encoding="utf-8") as policy_file:
            policy = json.load(policy_file)
        return policy if isinstance(policy, dict) else {
            "services": {}, "apps": {}, "network_profiles": []
        }
    except (OSError, ValueError, TypeError):
        return {"services": {}, "apps": {}, "network_profiles": []}
