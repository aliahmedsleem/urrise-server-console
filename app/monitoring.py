import os, platform, socket, time, subprocess
from datetime import datetime, timezone
import psutil

_prev_net = None
_prev_time = None

def _temperature():
    try:
        sensors = psutil.sensors_temperatures(fahrenheit=False) or {}
        readings = []
        for name, entries in sensors.items():
            for entry in entries:
                if entry.current is not None:
                    readings.append(((entry.label or name).lower(), float(entry.current)))
        if not readings:
            return {"celsius": None, "source": "unavailable"}
        preferred = [x for x in readings if any(k in x[0] for k in ("cpu", "package", "core", "tctl", "tdie"))]
        label, value = max(preferred or readings, key=lambda x: x[1])
        return {"celsius": round(value, 1), "source": label}
    except (AttributeError, OSError, NotImplementedError):
        return {"celsius": None, "source": "unsupported"}

def snapshot():
    global _prev_net, _prev_time
    now = time.monotonic()
    net = psutil.net_io_counters()
    recv, sent = float(net.bytes_recv), float(net.bytes_sent)
    down = up = 0.0
    if _prev_net is not None and _prev_time is not None:
        elapsed = max(now - _prev_time, .001)
        down = max(0, recv - _prev_net["recv"]) / elapsed
        up = max(0, sent - _prev_net["sent"]) / elapsed
    _prev_net, _prev_time = {"recv": recv, "sent": sent}, now
    vm = psutil.virtual_memory()
    disk_rows, seen = [], set()
    for part in psutil.disk_partitions(all=False):
        if part.mountpoint in seen: continue
        seen.add(part.mountpoint)
        try:
            u = psutil.disk_usage(part.mountpoint)
            disk_rows.append({"device": part.device, "mount": part.mountpoint, "filesystem": part.fstype, "total": u.total, "used": u.used, "free": u.free, "percent": u.percent})
        except (PermissionError, OSError): continue
    try: load = list(os.getloadavg())
    except (AttributeError, OSError): load = []
    freq, boot = psutil.cpu_freq(), psutil.boot_time()
    interfaces, addrs, stats = [], psutil.net_if_addrs(), psutil.net_if_stats()
    for name, st in stats.items():
        ip4 = next((a.address for a in addrs.get(name, []) if a.family == socket.AF_INET), "")
        ip6 = next((a.address for a in addrs.get(name, []) if getattr(a.family, "name", "") == "AF_INET6"), "")
        interfaces.append({"name": name, "up": st.isup, "speed_mbps": st.speed or None, "mtu": st.mtu, "ipv4": ip4, "ipv6": ip6})
    return {"timestamp": datetime.now(timezone.utc).isoformat(), "host": socket.gethostname(), "platform": platform.platform(), "python": platform.python_version(), "uptime_seconds": max(0, int(time.time()-boot)), "cpu": {"percent": psutil.cpu_percent(interval=None), "cores_physical": psutil.cpu_count(logical=False), "cores_logical": psutil.cpu_count(logical=True), "frequency_mhz": round(freq.current, 0) if freq and freq.current else None, "temperature": _temperature(), "load_average": load}, "memory": {"total": vm.total, "used": vm.used, "available": vm.available, "percent": vm.percent, "swap_total": psutil.swap_memory().total, "swap_used": psutil.swap_memory().used, "swap_percent": psutil.swap_memory().percent}, "disks": disk_rows, "network": {"download_bps": down, "upload_bps": up, "bytes_received": net.bytes_recv, "bytes_sent": net.bytes_sent, "interfaces": interfaces}, "processes": len(psutil.pids())}

def safe_service_status(service):
    policy = read_policy()
    if service not in policy.get("services", {}): raise ValueError("Service is not allowlisted")
    try:
        p = subprocess.run(["/usr/bin/systemctl", "is-active", service], capture_output=True, text=True, timeout=3, check=False)
        return p.stdout.strip() or "unknown"
    except (OSError, subprocess.TimeoutExpired): return "unknown"

def read_policy():
    import json
    path = os.environ.get("URRISE_POLICY_PATH", "/etc/urrise-console/policy.json")
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except (OSError, ValueError): return {"services": {}, "apps": {}, "network_profiles": []}
