"""ME HOME (team ME1, 2026-11-14, docs/ME_HUB.md): your home internet, the devices on your Wi-Fi and this PC's health, for the Me hub.
PC side, read only: it changes nothing on the router or the network. Runs by itself with the PC report (tools/pc_report.py, every 15
minutes, through tools/me_hub.maybe_run); free, no account, no key.

  every run   is the internet up (two tiny GETs: Microsoft's own connection test and Cloudflare's), the outage log; the devices on
              your network (one empty UDP packet to each address of your /24 so they answer, then Windows' own `arp -a`; vendors from an
              offline IEEE table, tools/me_oui.json; names you set); this PC: disk, uptime, memory, CPU temperature when Windows gives it
  every 4 h   a light speed test against speed.cloudflare.com (Cloudflare's own free speed endpoints: 6 pings, 2-25 MB down grown
              until one takes a second, 1-4 MB up)
  pushes      (tools/me_hub.py sends them through the PC report's private ntfy topic) a new device joined, the internet is back after
              an outage of 15+ minutes, the disk is almost full

  python tools/me_home.py                  one run now (speed test only when due) and the card
  python tools/me_home.py --speed          a speed test now
  python tools/me_home.py --devices        the devices with their ids (to name them)
  python tools/me_home.py --name 3f2a91="Mom's iPad"     a friendly name (the id from --devices, or the MAC)
  python tools/me_home.py --forget 3f2a91  forget a device (it shows as new again if it comes back)
  python tools/me_home.py --oui-build oui.csv           rebuild tools/me_oui.json from the IEEE list (standards-oui.ieee.org/oui/oui.csv)

Private: %USERPROFILE%\\.olympus\\me\\home_state.json (devices with their MACs, the outage log, the tests) and devices.json (your names);
the phone gets data/me/home.json with each device's vendor, name, IP and only the last 2 bytes of its MAC. The speed test sends no IP,
no name and no cookie (a generic User-Agent); the pushes never carry an IP or a MAC.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import http.client
import json
import os
import re
import shutil
import socket
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools import me_core as M  # noqa: E402

OUT_NAME = "home.json"
STATE = "home_state.json"
NAMES = "devices.json"
OUI_FILE = os.path.join(ROOT, "tools", "me_oui.json")
SPEED_HOST = "speed.cloudflare.com"
SPEED_EVERY_S = 4 * 3600
TEMP_EVERY_S = 3600
CHECK_URLS = ("https://www.msftconnecttest.com/connecttest.txt", "https://speed.cloudflare.com/__down?bytes=0")
DOWN_SIZES = (2_000_000, 10_000_000, 25_000_000)
UP_SIZES = (1_000_000, 4_000_000)
GROW_UNTIL_S = 1.0
OUTAGE_MIN_S = 15 * 60
NEW_FOR_S = 24 * 3600
DISK_LOW_PCT = 10.0
UA = "olympus-me-home/1"
KEEP_TESTS, KEEP_OUTAGES, KEEP_CHECKS = 120, 60, 200
CONNECT = "Nothing to type: it runs with the PC report every 15 minutes once this PC has the update (BOTS_BACK.bat set that up)"

# the vendors worth naming on a home network: (pattern on the IEEE organization name, the name shown, what it usually is)
VENDORS = [
    (r"^apple\b", "Apple", "iPhone, iPad, Mac, Apple TV or Watch"), (r"samsung", "Samsung", "phone, TV or appliance"),
    (r"nest labs", "Google Nest", "thermostat, camera or speaker"), (r"^google\b", "Google", "Pixel, Nest or Chromecast"),
    (r"^eero", "eero", "Wi-Fi router"), (r"^ring\b", "Ring", "doorbell or camera"), (r"^amazon", "Amazon", "Echo, Fire TV, Ring or Kindle"),
    (r"microsoft", "Microsoft", "Xbox, Surface or PC"), (r"^sony", "Sony", "PlayStation or TV"), (r"nintendo", "Nintendo", "Switch"),
    (r"lg electronics|lg innotek", "LG", "TV or appliance"), (r"^roku", "Roku", "streaming player or TV"), (r"^sonos", "Sonos", "speaker"),
    (r"signify|philips lighting", "Philips Hue", "smart lights"), (r"tp-link|tp link", "TP-Link", "router, plug or camera (Kasa / Tapo)"),
    (r"netgear", "Netgear", "router or Wi-Fi"), (r"linksys|belkin", "Linksys / Belkin", "router or smart plug"), (r"asustek", "ASUS", "router or PC"),
    (r"ubiquiti", "Ubiquiti", "Wi-Fi or network gear"), (r"arris|commscope", "ARRIS", "cable modem or router"),
    (r"technicolor|vantiva", "Technicolor", "internet gateway"), (r"sagemcom", "Sagemcom", "internet gateway"), (r"^nokia", "Nokia", "internet gateway"),
    (r"^cisco|meraki", "Cisco", "network gear"), (r"intel corporate|^intel corp", "Intel", "laptop or PC Wi-Fi"), (r"realtek", "Realtek", "PC or TV network chip"),
    (r"^dell", "Dell", "PC"), (r"hewlett packard|^hp inc", "HP", "printer or PC"), (r"lenovo", "Lenovo", "PC or tablet"),
    (r"brother industries", "Brother", "printer"), (r"^canon", "Canon", "printer or camera"), (r"seiko epson", "Epson", "printer"),
    (r"raspberry pi", "Raspberry Pi", "small computer"), (r"espressif", "Espressif", "smart-home gadget (plug, bulb, sensor)"),
    (r"tuya", "Tuya", "smart-home gadget"), (r"wyze", "Wyze", "camera or plug"), (r"^arlo", "Arlo", "camera"), (r"ecobee", "ecobee", "thermostat"),
    (r"^vizio", "Vizio", "TV"), (r"^tcl\b|tcl king|tcl technology", "TCL", "TV"), (r"hisense", "Hisense", "TV"), (r"xiaomi", "Xiaomi", "phone or smart-home gadget"),
    (r"huawei", "Huawei", "phone or router"), (r"oneplus", "OnePlus", "phone"), (r"motorola", "Motorola", "phone or modem"), (r"^garmin", "Garmin", "watch or GPS"),
    (r"fitbit", "Fitbit", "watch"), (r"^bose", "Bose", "speaker or headphones"), (r"logitech", "Logitech", "camera, keyboard or hub"),
    (r"nvidia", "NVIDIA", "Shield or PC"), (r"valve corp", "Valve", "Steam Deck"), (r"irobot", "iRobot", "Roomba"), (r"chamberlain", "Chamberlain", "garage opener (myQ)"),
    (r"hon hai|foxconn", "Foxconn", "a TV, console or PC built by Foxconn"), (r"azurewave", "AzureWave", "laptop or TV Wi-Fi chip"),
    (r"liteon|lite-on", "Lite-On", "laptop Wi-Fi chip"), (r"murata", "Murata", "smart-home Wi-Fi module"), (r"silicon lab", "Silicon Labs", "smart-home module"),
    (r"texas instruments", "Texas Instruments", "smart-home module"), (r"^vivint", "Vivint", "security system"), (r"simplisafe", "SimpliSafe", "security system"),
    (r"^tesla", "Tesla", "car or Powerwall"), (r"peloton", "Peloton", "bike or tread"), (r"oculus|meta platforms|^facebook", "Meta", "Quest headset"),
]
PRIVATE_HINT = "a phone, tablet or laptop with a private Wi-Fi address"


# ------------------------------------------------------------------------------------------------ the vendor table (offline)
def build_oui(csv_path: str, out_path: str = OUI_FILE) -> dict:
    """the IEEE MA-L list -> tools/me_oui.json: {vendor: {hint, oui: "A4C3F0 ..."}} for the vendors above only"""
    pats = [(re.compile(p, re.I), name, hint) for p, name, hint in VENDORS]
    found: dict = {}
    with open(csv_path, encoding="utf-8", errors="replace", newline="") as fh:
        for r in csv.DictReader(fh):
            a = str(r.get("Assignment") or "").strip().upper()
            org = str(r.get("Organization Name") or "").strip()
            if (r.get("Registry") or "MA-L") != "MA-L" or not re.fullmatch(r"[0-9A-F]{6}", a):
                continue
            for rx, name, hint in pats:
                if rx.search(org):
                    found.setdefault(name, {"hint": hint, "oui": set()})["oui"].add(a)
                    break
    doc = {"v": 1, "source": "IEEE MA-L (standards-oui.ieee.org/oui/oui.csv), the home-network vendors of tools/me_home.py VENDORS only",
           "built": time.strftime("%Y-%m-%d"), "vendors": {k: {"hint": v["hint"], "oui": " ".join(sorted(v["oui"]))} for k, v in sorted(found.items())}}
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, separators=(",", ":"))
        fh.write("\n")
    return doc


_OUI: dict = {}


def oui_table(path: str = OUI_FILE) -> dict:
    """{prefix: (vendor, hint)}"""
    if _OUI.get(path) is None:
        t = {}
        for name, v in M.obj(M.obj(M.read_json(path, {})).get("vendors")).items():
            for p in str(v.get("oui") or "").split():
                t[p] = (name, v.get("hint") or "")
        _OUI[path] = t
    return _OUI[path]


def norm_mac(s) -> str | None:
    h = re.sub(r"[^0-9a-fA-F]", "", str(s or ""))
    if len(h) != 12:
        return None
    return ":".join(h[i:i + 2] for i in range(0, 12, 2)).lower()


def private_mac(mac: str) -> bool:
    """a locally administered (random, 'private Wi-Fi address') MAC: the second bit of the first byte"""
    try:
        return bool(int(mac[:2], 16) & 0x02)
    except ValueError:
        return False


def vendor_of(mac: str, table: dict | None = None) -> tuple:
    """-> (vendor, hint)"""
    if private_mac(mac):
        return "Private address", PRIVATE_HINT
    t = oui_table() if table is None else table
    return t.get(mac.replace(":", "")[:6].upper(), ("Unknown maker", "not in the offline list"))


def dev_id(mac: str) -> str:
    return hashlib.sha1(("olympus-me|" + mac).encode("utf-8")).hexdigest()[:6]


# ------------------------------------------------------------------------------------------------ the devices: arp -a
ARP_RX = re.compile(r"(?<![\d.])((?:\d{1,3}\.){3}\d{1,3})(?![\d.])[^\n]*?\b([0-9A-Fa-f]{1,2}(?:[:-][0-9A-Fa-f]{1,2}){5})\b([^\n]*)")


def private_ip(ip: str) -> bool:
    try:
        a = [int(x) for x in ip.split(".")]
    except ValueError:
        return False
    if len(a) != 4 or any(x < 0 or x > 255 for x in a):
        return False
    return a[0] == 10 or (a[0] == 172 and 16 <= a[1] <= 31) or (a[0] == 192 and a[1] == 168)


def parse_arp(text: str) -> list:
    """Windows `arp -a`, Linux `ip neigh` / `arp -an` -> [{ip, mac}] of real neighbours (dynamic, private IPv4, no broadcast / multicast)"""
    out, seen = [], set()
    for ln in str(text or "").splitlines():
        m = ARP_RX.search(ln)
        if not m:
            continue
        ip, rest = m.group(1), m.group(3).lower()
        mac = norm_mac("".join(x.zfill(2) for x in re.split(r"[:-]", m.group(2))))
        if not mac or not private_ip(ip) or ip.endswith(".255") or ip.endswith(".0"):
            continue
        if mac in ("ff:ff:ff:ff:ff:ff", "00:00:00:00:00:00") or mac.startswith(("01:00:5e", "33:33")) or "static" in rest or "permanent" in rest:
            continue
        if "failed" in rest or "incomplete" in rest:
            continue
        if (ip, mac) in seen:
            continue
        seen.add((ip, mac))
        out.append({"ip": ip, "mac": mac})
    return out


def parse_gateway(text: str):
    """the router's address from `ipconfig` (Default Gateway) or `ip route` (default via)"""
    lines = str(text or "").splitlines()
    for i, ln in enumerate(lines):
        if not re.search(r"Default Gateway|default via", ln):
            continue
        for cand in [ln] + [x for x in lines[i + 1:i + 3] if re.fullmatch(r"\s+[\d.:a-fA-F%]+\s*", x)]:   # ipconfig puts the IPv4 one under an IPv6 one
            m = re.search(r"(?<![\d.])((?:\d{1,3}\.){3}\d{1,3})(?![\d.])", cand)
            if m and private_ip(m.group(1)):
                return m.group(1)
    return None


def run_cmd(args, timeout=10) -> str:
    exe = shutil.which(args[0])
    if not exe:
        return ""
    try:
        r = subprocess.run([exe] + list(args[1:]), capture_output=True, text=True, timeout=timeout,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.stdout or ""
    except (OSError, subprocess.SubprocessError):
        return ""


def lan_ip():
    """this PC's address on the home network (connect() on a UDP socket sends nothing)"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("192.0.2.1", 9))
            ip = s.getsockname()[0]
        finally:
            s.close()
        return ip if private_ip(ip) else None
    except OSError:
        return None


def nudge(ip: str, wait_s: float = 1.5) -> int:
    """one empty UDP packet to the discard port of every address of this /24, so the devices answer the PC's ARP and land in `arp -a`"""
    if not ip or not private_ip(ip):
        return 0
    base = ip.rsplit(".", 1)[0] + "."
    n = 0
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            for i in range(1, 255):
                try:
                    s.sendto(b"", (base + str(i), 9))
                    n += 1
                except OSError:
                    pass
        finally:
            s.close()
    except OSError:
        return 0
    time.sleep(wait_s)
    return n


def scan(runner=run_cmd, sweep=True) -> dict:
    ip = lan_ip()
    if sweep:
        nudge(ip)
    text = runner(["arp", "-a"]) or runner(["ip", "neigh"])
    gw = parse_gateway(runner(["ipconfig"]) if os.name == "nt" else runner(["ip", "route"]))
    return {"ip": ip, "gateway": gw, "devices": parse_arp(text)}


# ------------------------------------------------------------------------------------------------ the internet: up / down, speed
def default_http(url: str, timeout: float = 6.0) -> int:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read(2048)
            return int(r.status)
    except urllib.error.HTTPError as e:
        return int(e.code)
    except Exception:  # noqa: BLE001
        return 0


def online_check(http=default_http) -> bool:
    for u in CHECK_URLS:
        if 200 <= http(u) < 400:
            return True
    return False


def server_ms(header) -> float:
    """Cloudflare's Server-Timing 'cfRequestDuration;dur=12.3' -> 12.3 (the time the server itself took), else 0"""
    m = re.search(r"dur=([\d.]+)", str(header or ""))
    try:
        return float(m.group(1)) if m else 0.0
    except ValueError:
        return 0.0


def colo_of(ray) -> str:
    """the Cloudflare city code at the end of the CF-RAY header ('8e2f...-EWR' -> 'EWR')"""
    m = re.search(r"-([A-Z]{3})$", str(ray or "").strip())
    return m.group(1) if m else ""


def mbps(nbytes: float, seconds: float) -> float:
    return round(nbytes * 8 / max(seconds, 1e-3) / 1e6, 1)


def parse_result(pings_ms: list, downs: list, ups: list, colo: str = "") -> dict:
    """the raw timings -> the result. pings_ms: [ms] (the first one holds the TLS handshake and is dropped); downs / ups: [(bytes, seconds,
    server ms)]; speed = the biggest transfer, its time less one round trip and the server's own time"""
    p = [x for x in pings_ms[1:] if x is not None] or [x for x in pings_ms if x is not None]
    ping = round(statistics.median(p), 1) if p else None
    jit = round(statistics.mean(abs(a - b) for a, b in zip(p, p[1:])), 1) if len(p) > 1 else None
    rtt = (ping or 0.0) / 1000.0

    def best(rows):
        if not rows:
            return None
        n, s, srv = max(rows, key=lambda r: r[0])
        return mbps(n, s - rtt - srv / 1000.0 if s - rtt - srv / 1000.0 > 0.05 else s)
    return {"ok": ping is not None and bool(downs), "ping_ms": ping, "jitter_ms": jit, "down_mbps": best(downs), "up_mbps": best(ups), "colo": colo,
            "mb_used": round((sum(r[0] for r in downs) + sum(r[0] for r in ups)) / 1e6, 1)}


def speed_test(conn_factory=None, clock=time.perf_counter) -> dict:
    """the light speed test against speed.cloudflare.com on one kept-alive connection. Never raises."""
    pings, downs, ups, colo = [], [], [], ""
    try:
        conn = conn_factory() if conn_factory else http.client.HTTPSConnection(SPEED_HOST, timeout=30)
        hdr = {"User-Agent": UA, "Accept": "*/*"}
        for _ in range(6):
            t0 = clock()
            conn.request("GET", "/__down?bytes=0", headers=hdr)
            r = conn.getresponse()
            r.read()
            t1 = clock()
            colo = colo or colo_of(r.getheader("CF-RAY"))
            pings.append(max(0.0, (t1 - t0) * 1000.0 - server_ms(r.getheader("Server-Timing"))))
        for n in DOWN_SIZES:
            t0 = clock()
            conn.request("GET", f"/__down?bytes={n}", headers=hdr)
            r = conn.getresponse()
            got = 0
            while True:
                b = r.read(1 << 16)
                if not b:
                    break
                got += len(b)
            s = clock() - t0
            downs.append((got, s, server_ms(r.getheader("Server-Timing"))))
            if s >= GROW_UNTIL_S:
                break
        for n in UP_SIZES:
            body = b"0" * n
            t0 = clock()
            conn.request("POST", "/__up", body=body, headers={**hdr, "Content-Type": "application/octet-stream"})
            r = conn.getresponse()
            r.read()
            s = clock() - t0
            ups.append((n, s, server_ms(r.getheader("Server-Timing"))))
            if s >= GROW_UNTIL_S:
                break
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
    except Exception as e:  # noqa: BLE001
        out = parse_result(pings, downs, ups, colo) if pings and downs else {"ok": False}
        out["error"] = f"{e.__class__.__name__}"[:60]
        return out
    return parse_result(pings, downs, ups, colo)


# ------------------------------------------------------------------------------------------------ this PC
def pc_health(env=None, temp=None) -> dict:
    out = {"name": M.clean(socket.gethostname(), 40)}
    try:
        root = (os.environ.get("SystemDrive") or "C:") + "\\" if os.name == "nt" else "/"
        du = shutil.disk_usage(root)
        out.update(disk_total_gb=round(du.total / 1e9, 1), disk_free_gb=round(du.free / 1e9, 1), disk_free_pct=round(du.free / du.total * 100.0, 1), disk=root)
    except OSError:
        pass
    up = None
    try:
        if os.name == "nt":
            import ctypes
            k = ctypes.windll.kernel32
            k.GetTickCount64.restype = ctypes.c_ulonglong
            up = k.GetTickCount64() / 1000.0

            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("a", ctypes.c_ulonglong), ("b", ctypes.c_ulonglong),
                            ("c", ctypes.c_ulonglong), ("d", ctypes.c_ulonglong), ("e", ctypes.c_ulonglong), ("f", ctypes.c_ulonglong), ("g", ctypes.c_ulonglong)]
            ms = MS()
            ms.dwLength = ctypes.sizeof(MS)
            if k.GlobalMemoryStatusEx(ctypes.byref(ms)):
                out["mem_used_pct"] = int(ms.dwMemoryLoad)
        else:
            with open("/proc/uptime", encoding="ascii") as fh:
                up = float(fh.read().split()[0])
            mi = {}
            with open("/proc/meminfo", encoding="ascii") as fh:
                for ln in fh:
                    k2, _, v = ln.partition(":")
                    mi[k2] = float(v.split()[0]) if v.split() else 0.0
            if mi.get("MemTotal"):
                out["mem_used_pct"] = round(100.0 * (1 - mi.get("MemAvailable", 0.0) / mi["MemTotal"]))
    except Exception:  # noqa: BLE001
        pass
    if up is not None:
        out["uptime_h"] = round(up / 3600.0, 1)
        out["boot_t"] = int(time.time() - up)
    out["cpu_temp_c"] = temp
    return out


def cpu_temp(runner=run_cmd):
    """the CPU (ACPI thermal zone) temperature in C, or None: Linux /sys, Windows through PowerShell's CIM (often not given without admin)"""
    try:
        if os.name != "nt":
            vals = []
            base = "/sys/class/thermal"
            for z in sorted(os.listdir(base)) if os.path.isdir(base) else []:
                try:
                    with open(os.path.join(base, z, "temp"), encoding="ascii") as fh:
                        vals.append(int(fh.read().strip()) / 1000.0)
                except (OSError, ValueError):
                    pass
            vals = [v for v in vals if 5 < v < 120]
            return round(max(vals), 1) if vals else None
        txt = runner(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                      "(Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop | Select-Object -First 1).CurrentTemperature"], timeout=12)
        v = M.num(txt.strip().splitlines()[0]) if txt.strip() else None
        c = round(v / 10.0 - 273.15, 1) if v else None
        return c if c is not None and 5 < c < 120 else None
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------------------------------------ the run
def names_of(env=None) -> dict:
    d = M.obj(M.read_json(os.path.join(M.me_dir(env), NAMES), {}))
    return {"names": {k: M.clean(v, 40) for k, v in M.obj(d.get("names")).items() if norm_mac(k)}, "ignore": [x for x in M.arr(d.get("ignore")) if norm_mac(x)]}


def update(state: dict, now_s: float, online: bool | None = None, found: dict | None = None, speed: dict | None = None, pc: dict | None = None,
           table: dict | None = None) -> tuple:
    """(new state, events). Pure: no clock, no network. state = home_state.json."""
    st = json.loads(json.dumps(M.obj(state)))
    ev = []
    now = int(now_s)
    if online is not None:
        o = M.obj(st.get("online"))
        checks = M.arr(st.get("checks")) + [{"t": now, "ok": bool(online)}]
        st["checks"] = checks[-KEEP_CHECKS:]
        outs = M.arr(st.get("outages"))
        if not online and o.get("ok", True):                 # just went down: it started after the last good check
            outs.append({"from": int(o.get("t") or now), "to": None, "seen_t": now})
        if online and o.get("ok") is False and outs and outs[-1].get("to") is None:
            last = outs[-1]
            last["to"] = now
            mins = round((now - last["from"]) / 60.0)
            if now - last["from"] >= OUTAGE_MIN_S:
                ev.append({"key": f"home:out:{last['from']}", "title": "Internet back",
                           "body": f"Your internet was down about {mins} min ({M.ny_dt(last['from']).strftime('%H:%M')} to {M.ny_dt(now).strftime('%H:%M')} New York). It is back.",
                           "priority": "default", "tags": "globe_with_meridians"})
        st["outages"] = outs[-KEEP_OUTAGES:]
        st["online"] = {"ok": bool(online), "t": now, "since": now if bool(online) != o.get("ok") else o.get("since", now)}
    if found is not None:
        devs = M.obj(st.get("devices"))
        seeded = bool(st.get("seeded"))
        for d in M.arr(found.get("devices")):
            mac = d["mac"]
            v, hint = vendor_of(mac, table)
            cur = devs.get(mac)
            if cur is None:
                devs[mac] = {"first_t": now, "last_t": now, "ip": d["ip"], "vendor": v}
                if seeded:
                    ev.append({"key": f"home:dev:{mac}", "title": "New device on your Wi-Fi",
                               "body": f"A new device joined your home network: {v} ({hint}). If you do not know it, check your router's device list. "
                                       f"Name it on the PC: python tools\\me_home.py --name {dev_id(mac)}=\"...\"",
                               "priority": "default", "tags": "satellite"})
            else:
                cur.update(last_t=now, ip=d["ip"], vendor=v)
        st["devices"] = devs
        st["seen_now"] = sorted(d["mac"] for d in M.arr(found.get("devices")))
        st["gateway"] = found.get("gateway")
        st["lan_ip"] = found.get("ip")
        st["scan_t"] = now
        st["seeded"] = True
    if speed is not None:
        st["speed"] = (M.arr(st.get("speed")) + [{"t": now, **{k: speed.get(k) for k in ("ok", "down_mbps", "up_mbps", "ping_ms", "jitter_ms", "colo", "mb_used", "error")}}])[-KEEP_TESTS:]
        st["speed_t"] = now
    if pc is not None:
        st["pc"] = pc
        f = M.num(pc.get("disk_free_pct"))
        if f is not None and f < DISK_LOW_PCT:
            day = M.ny_day(now_s)
            ev.append({"key": f"home:disk:{day}", "title": "PC disk almost full",
                       "body": f"The PC has {pc.get('disk_free_gb')} GB free ({f:.0f}%). Double-click CLEAN_STORAGE.bat on the PC.", "priority": "default", "tags": "floppy_disk"})
    return st, ev


def build(state: dict, now_s: float, names: dict | None = None, table: dict | None = None) -> dict:
    """data/me/home.json for the phone (no full MAC, no PC IP)"""
    st = M.obj(state)
    nm = M.obj(M.obj(names).get("names"))
    ign = set(M.arr(M.obj(names).get("ignore")))
    now = int(now_s)
    o = M.obj(st.get("online"))
    tests = [x for x in M.arr(st.get("speed")) if x.get("ok")]
    wk = [x for x in tests if now - int(x["t"]) <= 7 * 86400]
    last = tests[-1] if tests else None
    med = lambda k: round(statistics.median([x[k] for x in wk if M.num(x.get(k)) is not None]), 1) if [x for x in wk if M.num(x.get(k)) is not None] else None  # noqa: E731
    avg7 = {"down_mbps": med("down_mbps"), "up_mbps": med("up_mbps"), "ping_ms": med("ping_ms"), "n": len(wk)}
    outs = M.arr(st.get("outages"))
    today = M.ny_day(now_s)
    o_list = [{"from": x["from"], "to": x.get("to"), "open": x.get("to") is None,
               "mins": round(((x.get("to") or now) - x["from"]) / 60.0)} for x in outs if now - int(x["from"]) <= 7 * 86400]
    o_today = [x for x in o_list if M.ny_day(x["from"]) == today]
    seen_now = set(M.arr(st.get("seen_now")))
    gw = st.get("gateway")
    devs = []
    for mac, d in M.obj(st.get("devices")).items():
        if mac in ign:
            continue
        v, hint = vendor_of(mac, table)
        name = nm.get(mac) or ("Router" if gw and d.get("ip") == gw else (f"{v} device" if v not in ("Unknown maker", "Private address") else ("Private-address device" if v == "Private address" else "Unknown device")))
        devs.append({"id": dev_id(mac), "name": name, "named": mac in nm, "vendor": v, "hint": hint, "ip": d.get("ip"), "mac_tail": mac[-5:],
                     "first_t": d.get("first_t"), "last_t": d.get("last_t"), "online": mac in seen_now, "router": bool(gw and d.get("ip") == gw),
                     "new": bool(now - int(d.get("first_t") or 0) <= NEW_FOR_S and st.get("seeded_t", 0) < int(d.get("first_t") or 0) and mac not in nm)})
    devs.sort(key=lambda x: (not x["online"], not x["new"], x["name"].lower()))
    new = [x for x in devs if x["new"]]
    pc = M.obj(st.get("pc"))
    lvl, text, short = "ok", "Home OK", "Home OK"
    slow = last and avg7["down_mbps"] and last.get("down_mbps") is not None and last["down_mbps"] < 0.5 * avg7["down_mbps"]
    if o and o.get("ok") is False:
        lvl, text, short = "bad", f"Internet down since {M.ny_dt(o.get('since') or now).strftime('%H:%M')}", "Internet down"
    elif len(o_today) >= 2:
        lvl, text, short = "warn", f"Internet dropped {len(o_today)} times today", f"{len(o_today)} drops today"
    elif new:
        lvl, text, short = "warn", f"New device: {new[0]['name']}" + (f" and {len(new) - 1} more" if len(new) > 1 else ""), "New device"
    elif slow:
        lvl, text, short = "warn", f"Internet slow: {last['down_mbps']:g} Mbps (usually {avg7['down_mbps']:g})", "Internet slow"
    elif M.num(pc.get("disk_free_pct")) is not None and pc["disk_free_pct"] < DISK_LOW_PCT:
        lvl, text, short = "warn", f"PC disk almost full ({pc['disk_free_pct']:.0f}% free)", "Disk almost full"
    elif not o:
        lvl, text, short = "", "No check yet", "No check yet"
    elif last:
        text = f"Home OK · {last['down_mbps']:g} Mbps down"
    doc = {"v": 1, "kind": "olympus-home", "t": now, "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)), "private": True,
           "about": "Your home internet, the devices on your Wi-Fi and this PC, checked by the PC itself. Private: only the PC's own link serves it.",
           "status": {"lvl": lvl, "text": text, "short": short},
           "internet": {"online": o.get("ok"), "checked_t": o.get("t"), "since": o.get("since"), "last": last, "avg7": avg7,
                        "tests": [{k: x.get(k) for k in ("t", "down_mbps", "up_mbps", "ping_ms")} for x in wk][-42:],
                        "next_test_t": (int(st.get("speed_t") or 0) + SPEED_EVERY_S) if st.get("speed_t") else None},
           "outages": {"today": len(o_today), "week": len(o_list), "list": list(reversed(o_list))[:20]},
           "devices": {"n": len(devs), "online": sum(1 for x in devs if x["online"]), "new": len(new), "scan_t": st.get("scan_t"), "list": devs[:80]},
           "pc": {k: pc.get(k) for k in ("name", "disk_total_gb", "disk_free_gb", "disk_free_pct", "uptime_h", "boot_t", "cpu_temp_c", "mem_used_pct")}}
    return M.scrub_doc(doc)


def maybe_run(now_s: float | None = None, env=None, http=default_http, runner=run_cmd, speed_fn=speed_test, sweep=True, force_speed=False, say=print) -> tuple:
    """one PC-report run: (home.json doc, events). Soft: a failing part is skipped. LE_ME_HOME=0 turns it off."""
    e = os.environ if env is None else env
    if str(e.get("LE_ME_HOME", "1")) == "0":
        return None, []
    now_s = time.time() if now_s is None else now_s
    sp = os.path.join(M.me_dir(env), STATE)
    st = M.obj(M.read_json(sp, {}))
    if not st.get("seeded_t"):
        st["seeded_t"] = int(now_s)
    events = []
    try:
        on = online_check(http)
    except Exception:  # noqa: BLE001
        on = None
    try:
        found = scan(runner, sweep)
    except Exception:  # noqa: BLE001
        found = None
    sp_res = None
    if on and (force_speed or now_s - (M.num(st.get("speed_t")) or 0) >= SPEED_EVERY_S):
        sp_res = speed_fn()
    temp = st.get("temp")
    if now_s - (M.num(st.get("temp_t")) or 0) >= TEMP_EVERY_S:
        temp = cpu_temp(runner)
        st["temp"], st["temp_t"] = temp, int(now_s)
    st, ev = update(st, now_s, online=on, found=found, speed=sp_res, pc=pc_health(env, temp))
    if sp_res is not None and not sp_res.get("ok"):
        st["speed_t"] = int(now_s) - SPEED_EVERY_S + 1800           # a failed test is tried again in 30 minutes, not in 4 hours
    events += ev
    M.write_json(sp, st, compact=True)
    doc = build(st, now_s, names_of(env))
    M.write_json(os.path.join(M.out_dir(env), OUT_NAME), doc, compact=True)
    return doc, events


def card_text(doc: dict) -> str:
    if not doc:
        return "  Home: not checked yet."
    s, i, d, p = M.obj(doc.get("status")), M.obj(doc.get("internet")), M.obj(doc.get("devices")), M.obj(doc.get("pc"))
    last = M.obj(i.get("last"))
    return (f"  Home: {s.get('text')}. Internet {'up' if i.get('online') else 'DOWN' if i.get('online') is False else '?'}"
            + (f", last test {last.get('down_mbps')} down / {last.get('up_mbps')} up Mbps, ping {last.get('ping_ms')} ms" if last else "")
            + f"; {d.get('n', 0)} devices ({d.get('online', 0)} online, {d.get('new', 0)} new); disk {p.get('disk_free_gb')} GB free")


def main(argv=None, env=None, say=print) -> int:
    ap = argparse.ArgumentParser(description="Your home internet, devices and this PC for the Me hub (read only, private).")
    ap.add_argument("--speed", action="store_true")
    ap.add_argument("--devices", action="store_true")
    ap.add_argument("--name", action="append", default=[], metavar="ID=NAME")
    ap.add_argument("--forget", action="append", default=[], metavar="ID")
    ap.add_argument("--no-sweep", action="store_true", help="do not nudge the network before arp -a")
    ap.add_argument("--oui-build", metavar="OUI_CSV")
    a = ap.parse_args(argv)
    if a.oui_build:
        doc = build_oui(a.oui_build)
        say(f"  [OK]  {OUI_FILE}: {len(doc['vendors'])} vendors, {sum(len(v['oui'].split()) for v in doc['vendors'].values()):,} prefixes")
        return 0
    st = M.obj(M.read_json(os.path.join(M.me_dir(env), STATE), {}))
    if a.name or a.forget:
        np_ = os.path.join(M.me_dir(env), NAMES)
        nd = names_of(env)
        macs = list(M.obj(st.get("devices")))
        for kv in a.name:
            k, _, v = kv.partition("=")
            mac = norm_mac(k) or next((m for m in macs if dev_id(m) == k.strip().lower()), None)
            nm = M.clean(v.strip().strip('"'), 40)
            if not mac or not nm:
                say(f"  [FIX] {kv!r}: use an id from --devices (or the MAC) = a name")
                return 2
            nd["names"][mac] = nm
            say(f"  [OK]  {dev_id(mac)} is now {nm!r}")
        for k in a.forget:
            mac = norm_mac(k) or next((m for m in macs if dev_id(m) == k.strip().lower()), None)
            if mac and mac in M.obj(st.get("devices")):
                st["devices"].pop(mac, None)
                nd["names"].pop(mac, None)
                M.write_json(os.path.join(M.me_dir(env), STATE), st, compact=True)
                say(f"  [OK]  forgot {dev_id(mac)}")
        M.write_json(np_, nd)
        return 0
    if a.devices:
        doc = build(st, time.time(), names_of(env))
        for x in M.arr(M.obj(doc.get("devices")).get("list")):
            mac = next((m for m in M.obj(st.get("devices")) if dev_id(m) == x["id"]), "")
            say(f"  {x['id']}  {x['ip'] or '-':<15} {mac:<17}  {x['name'][:24]:<24} {x['vendor'][:18]:<18} {'online' if x['online'] else ''}{' NEW' if x['new'] else ''}")
        if not M.obj(doc.get("devices")).get("n"):
            say("  No devices yet: run python tools\\me_home.py once (the PC report does it every 15 minutes).")
        return 0
    doc, ev = maybe_run(env=env, sweep=not a.no_sweep, force_speed=a.speed, say=say)
    say(card_text(doc or {}))
    for x in ev:
        say(f"  [push] {x['title']}: {x['body']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
