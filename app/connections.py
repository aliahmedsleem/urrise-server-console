"""Read-only network and Nginx connection observations.

No elevated commands, reverse DNS lookups, or user-controlled log paths.
"""
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psutil

LOG_PATH = Path("/var/log/nginx/urrise-console.access.log")
LOG_RE = re.compile(r'^(?P<ip>\S+) \S+ \S+ \[(?P<time>[^]]+)\] "(?P<method>\S+) (?P<path>\S+) [^"]+" (?P<status>\d{3}) \S+ "(?:[^"]*)" "(?P<agent>[^"]*)"')
MAX_READ_BYTES = 2_000_000


def describe_agent(agent):
    a = agent.lower()
    browser = ("Edge" if "edg/" in a else "Opera" if "opr/" in a else
               "Chrome" if "chrome/" in a else "Firefox" if "firefox/" in a else
               "Safari" if "safari/" in a else "Unknown")
    system = ("Windows" if "windows" in a else "Android" if "android" in a else
              "iOS" if "iphone" in a or "ipad" in a else "macOS" if "mac os" in a else
              "Linux" if "linux" in a else "Unknown")
    device = ("Mobile" if "iphone" in a or "android" in a and "mobile" in a else
              "Tablet" if "ipad" in a or "android" in a else "Computer" if system in ("Windows", "macOS", "Linux") else "Unknown")
    return {"browser": browser, "os": system, "device_type": device, "device_name": None}


def recent_web(limit=100, minutes=5):
    """Return grouped request activity, not authenticated session presence."""
    now = datetime.now(timezone.utc)
    groups = {}
    try:
        with LOG_PATH.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - MAX_READ_BYTES))
            if size > MAX_READ_BYTES:
                f.readline()
            lines = f.readlines()
    except (OSError, PermissionError):
        return {"available": False, "reason": "Log file not readable by service account", "items": []}
    for raw in lines:
        match = LOG_RE.match(raw.decode("utf-8", errors="replace").strip())
        if not match:
            continue
        row = match.groupdict()
        try:
            when = datetime.strptime(row["time"], "%d/%b/%Y:%H:%M:%S %z")
        except ValueError:
            continue
        if when < now - timedelta(minutes=minutes) or when > now + timedelta(minutes=1):
            continue
        agent = row["agent"][:512]
        key = (row["ip"], agent)
        item = groups.get(key)
        if item is None:
            item = {"ip": row["ip"], **describe_agent(agent), "first_seen": when.isoformat(),
                    "last_seen": when.isoformat(), "requests": 0, "last_path": ""}
            groups[key] = item
        item["requests"] += 1
        if when.isoformat() >= item["last_seen"]:
            item["last_seen"] = when.isoformat()
            item["last_path"] = row["path"][:200].split("?")[0]
    items = sorted(groups.values(), key=lambda x: x["last_seen"], reverse=True)[:limit]
    return {"available": True, "classification": "recent_http_activity", "window_minutes": minutes, "items": items}


def tcp_connections(limit=150):
    """Kernel TCP socket snapshot; may be incomplete without elevated permissions."""
    rows = []
    try:
        sockets = psutil.net_connections(kind="tcp")
    except (psutil.AccessDenied, OSError) as exc:
        return {"available": False, "reason": type(exc).__name__, "items": []}
    for conn in sockets:
        if conn.status != psutil.CONN_ESTABLISHED or not conn.raddr:
            continue
        rows.append({"local_ip": conn.laddr.ip, "local_port": conn.laddr.port,
                     "remote_ip": conn.raddr.ip, "remote_port": conn.raddr.port,
                     "state": conn.status, "pid": conn.pid})
    return {"available": True, "classification": "tcp_sockets_not_users",
            "items": rows[:limit], "truncated": len(rows) > limit}


def connection_history(days=7, limit=200):
    """Summarize observed HTTP clients from current and rotated Console logs.

    This is request history, not an authentication or session history.
    Rotated files must be readable by the service account.
    """
    import gzip
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(1, min(int(days), 30)))
    paths = [LOG_PATH]
    paths.extend(LOG_PATH.parent.glob(LOG_PATH.name + ".[0-9]*"))
    groups = {}
    readable = 0
    skipped = 0
    for path in sorted(paths, key=lambda p: p.name)[:40]:
        try:
            opener = gzip.open if path.suffix == ".gz" else open
            with opener(path, "rb") as stream:
                readable += 1
                # Limit work per file; newest records are at the end for plain logs.
                if path.suffix != ".gz":
                    stream.seek(0, os.SEEK_END)
                    size = stream.tell()
                    stream.seek(max(0, size - 8_000_000))
                    if size > 8_000_000:
                        stream.readline()
                count = 0
                for raw in stream:
                    count += 1
                    if count > 100_000:
                        break
                    match = LOG_RE.match(raw.decode("utf-8", errors="replace").strip())
                    if not match:
                        continue
                    row = match.groupdict()
                    try:
                        when = datetime.strptime(row["time"], "%d/%b/%Y:%H:%M:%S %z")
                    except ValueError:
                        continue
                    if when < cutoff or when > now + timedelta(minutes=1):
                        continue
                    agent = row["agent"][:512]
                    key = (row["ip"], agent)
                    item = groups.get(key)
                    if item is None:
                        item = {"ip": row["ip"], **describe_agent(agent),
                                "first_seen": when.isoformat(), "last_seen": when.isoformat(),
                                "requests": 0}
                        groups[key] = item
                    item["requests"] += 1
                    if when.isoformat() < item["first_seen"]:
                        item["first_seen"] = when.isoformat()
                    if when.isoformat() > item["last_seen"]:
                        item["last_seen"] = when.isoformat()
        except (OSError, EOFError):
            skipped += 1
    return {"available": readable > 0, "classification": "http_request_history",
            "days": days, "readable_files": readable, "skipped_files": skipped,
            "partial": skipped > 0,
            "items": sorted(groups.values(), key=lambda x: x["last_seen"], reverse=True)[:limit]}
