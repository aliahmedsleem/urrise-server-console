import ipaddress, json, os, re, subprocess

HELPER = os.environ.get("URRISE_HELPER_PATH", "/usr/local/sbin/urrise-console-helper")
KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
SERVICE_RE = re.compile(r"^[A-Za-z0-9_.@:-]{1,128}$")
APP_RE = re.compile(r"^[a-zA-Z0-9_-]{1,48}$")

def call_helper(*args, timeout=15):
    if not os.path.isfile(HELPER):
        raise RuntimeError("Privileged helper is not installed; administrative actions are disabled.")
    try:
        p = subprocess.run(["sudo", "-n", HELPER, *[str(a) for a in args]], capture_output=True, text=True, timeout=timeout, check=False, env={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin", "LANG":"C.UTF-8"})
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError("Could not run the administrative helper.") from e
    if p.returncode != 0:
        raise RuntimeError("Operation rejected or failed. Check the server's protected system journal.")
    try:
        return json.loads(p.stdout)
    except ValueError:
        return {"ok": True, "message": "Operation completed."}

def manage_service(service, action):
    if not SERVICE_RE.fullmatch(service) or action not in {"start", "stop", "restart"}:
        raise ValueError("Invalid service or action")
    return call_helper("service", action, service)

def update_app_env(app_id, key, value):
    if not APP_RE.fullmatch(app_id) or not KEY_RE.fullmatch(key):
        raise ValueError("Invalid app or environment key")
    if len(value) > 2048 or "\x00" in value or "\n" in value or "\r" in value:
        raise ValueError("Values must be single-line and at most 2048 characters")
    return call_helper("env-set", app_id, key, value, timeout=25)

def change_network_profile(profile, mode, address="", gateway="", dns=""):
    if not profile or len(profile) > 80 or any(c in profile for c in "\x00\n\r"):
        raise ValueError("Invalid profile")
    if mode == "auto":
        return call_helper("network", profile, "auto")
    if mode != "manual":
        raise ValueError("Invalid network mode")
    iface = ipaddress.ip_interface(address)
    gw = ipaddress.ip_address(gateway)
    if iface.version != 4 or gw.version != 4 or gw not in iface.network:
        raise ValueError("Gateway must be in the configured IP subnet")
    dns_items = [x.strip() for x in dns.split(",") if x.strip()]
    if not 1 <= len(dns_items) <= 3:
        raise ValueError("Provide one to three DNS servers")
    for item in dns_items:
        ipaddress.ip_address(item)
    return call_helper("network", profile, "manual", str(iface), str(gw), ",".join(dns_items))
