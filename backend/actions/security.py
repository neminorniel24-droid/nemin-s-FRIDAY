"""
Security helpers for YOUR OWN machine and home network.

Everything here is on purpose limited: port scans only run against this computer or private
(home / office LAN) addresses, never against the internet. URL checks are heuristics, not a guarantee.
"""
import ipaddress
import re
import socket
import ssl
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

from . import Result, action
from .winshell import run_ps

PORTS = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns", 80: "http", 110: "pop3", 135: "rpc",
    139: "netbios", 143: "imap", 443: "https", 445: "smb", 993: "imaps", 1433: "mssql", 3000: "dev server",
    3306: "mysql", 3389: "remote desktop", 5000: "dev server", 5432: "postgres", 5900: "vnc", 6379: "redis",
    8000: "http alt", 8001: "nemiii backend", 8080: "http alt", 8443: "https alt", 9200: "elasticsearch",
    11434: "ollama", 27017: "mongodb",
}
EXPOSED_BAD = {23, 135, 139, 445, 1433, 3306, 3389, 5432, 5900, 6379, 9200, 27017}


# ------------------------------------------------------------------ port scan
def windows_host_ip() -> str | None:
    """From inside WSL2, the Windows machine is the default gateway."""
    try:
        out = subprocess.run(["ip", "route"], capture_output=True, text=True, timeout=2).stdout
        m = re.search(r"default via (\d+\.\d+\.\d+\.\d+)", out)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


def resolve_private_target(target: str) -> tuple[str | None, str]:
    """Returns (ip, note). ip is None when the target is not allowed."""
    t = (target or "").strip().lower()
    if t in ("", "localhost", "this pc", "wsl", "here", "127.0.0.1"):
        return "127.0.0.1", "this Linux side (WSL)"
    if t in ("windows", "my pc", "my computer", "host", "windows host"):
        ip = windows_host_ip()
        return (ip, "your Windows PC") if ip else (None, "I couldn't find the Windows host address.")
    try:
        ip = socket.gethostbyname(t)
    except Exception:
        return None, f"I couldn't resolve {target}."
    addr = ipaddress.ip_address(ip)
    if addr.is_loopback or addr.is_private or addr.is_link_local:
        return ip, ip
    return None, "I only scan this computer and private home-network addresses, never the internet."


def _probe(ip: str, port: int) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=0.4):
            return True
    except OSError:
        return False


def scan(ip: str) -> list[int]:
    with ThreadPoolExecutor(max_workers=32) as ex:
        results = list(ex.map(lambda p: (p, _probe(ip, p)), PORTS))
    return [p for p, up in results if up]


@action("scan_ports", "info",
        'Check which common network ports are open on THIS pc or a home-network device. '
        'args: {"target": "windows" | "localhost" | "192.168.1.5"} (private addresses only)')
def scan_ports(a: dict) -> Result:
    ip, note = resolve_private_target(str(a.get("target", "")))
    if not ip:
        return Result(False, note)
    open_ports = scan(ip)
    if not open_ports:
        return Result(True, f"I checked {len(PORTS)} common ports on {note}. None are open.")
    desc = ", ".join(f"{p} {PORTS[p]}" for p in open_ports)
    risky = [p for p in open_ports if p in EXPOSED_BAD]
    warn = (" Worth a look, these are usually not meant to be reachable: " +
            ", ".join(f"{p} {PORTS[p]}" for p in risky) + ".") if risky and ip != "127.0.0.1" else ""
    return Result(True, f"On {note}, open ports: {desc}.{warn}")


# ------------------------------------------------------------------- URL check
SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly", "cutt.ly", "rb.gy", "shorturl.at"}
BAD_TLDS = {"zip", "mov", "tk", "ml", "ga", "cf", "gq", "top", "xyz", "click", "loan", "work", "country", "kim", "rest"}
BRANDS = ["paypal", "google", "microsoft", "apple", "amazon", "netflix", "instagram", "facebook", "whatsapp",
          "sbi", "hdfc", "icici", "paytm", "phonepe", "github", "binance", "coinbase"]
TWO_PART_TLDS = {"co.in", "co.uk", "com.au", "org.in", "gov.in", "ac.in", "com.br", "co.jp"}


def registrable(host: str) -> str:
    parts = host.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in TWO_PART_TLDS:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def url_findings(url: str) -> tuple[str, list[str]]:
    """Pure checks on the text of the address. Returns (host, list of warnings)."""
    u = urlparse(url if re.match(r"^[a-z]+://", url, re.I) else "https://" + url)
    host = (u.hostname or "").lower()
    warn: list[str] = []
    if u.scheme == "http":
        warn.append("it is not encrypted (http, not https)")
    if "@" in u.netloc:
        warn.append("it has an @ sign, a common trick to hide the real site")
    try:
        ipaddress.ip_address(host)
        warn.append("it uses a raw IP address instead of a name")
    except ValueError:
        pass
    if "xn--" in host:
        warn.append("the name uses look-alike international characters")
    reg = registrable(host)
    if reg in SHORTENERS:
        warn.append("it is a link shortener, so the real destination is hidden")
    if host.count(".") >= 4:
        warn.append("it has many subdomains")
    if len(host) > 60:
        warn.append("the address is unusually long")
    if host.rsplit(".", 1)[-1] in BAD_TLDS:
        warn.append(f"the ending .{host.rsplit('.', 1)[-1]} is often used for scams")
    for b in BRANDS:
        if b in host and not reg.startswith(b + "."):
            warn.append(f"it mentions {b} but is not the real {b} website")
            break
    if re.search(r"(login|signin|verify|secure|update|wallet|account).*", host) and reg not in SHORTENERS and warn:
        warn.append("the name pushes you to log in or verify")
    return host, warn


def _cert_note(host: str) -> str | None:
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=4) as raw, ctx.wrap_socket(raw, server_hostname=host) as s:
            cert = s.getpeercert()
        end = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        days = (end - datetime.now(timezone.utc)).days
        return None if days > 7 else f"its security certificate expires in {max(days, 0)} days"
    except ssl.SSLCertVerificationError:
        return "its security certificate is not valid"
    except Exception:
        return None


@action("check_url", "info", 'Check whether a link looks safe (heuristics, not a guarantee). args: {"url": "..."}')
def check_url(a: dict) -> Result:
    url = str(a.get("url", "")).strip()
    if not url:
        return Result(False, "Which link should I check?")
    host, warn = url_findings(url)
    if not host:
        return Result(False, "That doesn't look like a web address.")
    notes = list(warn)
    final = None
    try:
        ips = {i[4][0] for i in socket.getaddrinfo(host, None)}
    except Exception:
        return Result(True, f"{host} does not resolve on the internet, so the link is probably dead or fake.")
    if any(ipaddress.ip_address(ip).is_private or ipaddress.ip_address(ip).is_loopback for ip in ips):
        notes.append("it points to a private address on your own network")
    else:
        cert = _cert_note(host) if url.lower().startswith("https") or "://" not in url else None
        if cert:
            notes.append(cert)
        try:
            cur = url if "://" in url else "https://" + url
            for _ in range(5):
                r = requests.head(cur, allow_redirects=False, timeout=5, headers={"User-Agent": "Nemiii"})
                loc = r.headers.get("Location")
                if r.status_code in (301, 302, 303, 307, 308) and loc:
                    cur = requests.compat.urljoin(cur, loc)
                else:
                    break
            final = urlparse(cur).hostname
        except Exception:
            pass
        if final and registrable(final) != registrable(host):
            notes.append(f"it redirects to a different site, {final}")
    if not notes:
        return Result(True, f"{host} looks normal. I found no warning signs, but no check is perfect.")
    level = "be careful" if len(notes) == 1 else "this looks suspicious"
    return Result(True, f"{host}: {level}. " + "; ".join(notes) + ". I only check the address, not the page itself.")


# --------------------------------------------------------------------- the LAN
def parse_arp(text: str) -> list[tuple[str, str]]:
    out = []
    for m in re.finditer(r"^\s*(\d+\.\d+\.\d+\.\d+)\s+([0-9a-f]{2}(?:-[0-9a-f]{2}){5})\s+\w+", text, re.I | re.M):
        ip, mac = m[1], m[2].lower()
        addr = ipaddress.ip_address(ip)
        if not addr.is_private or addr.is_multicast or ip.endswith(".255") or mac == "ff-ff-ff-ff-ff-ff" or mac.startswith("01-00-5e"):
            continue
        out.append((ip, mac))
    return out


@action("lan_devices", "info", "List devices recently seen on your home network (from the PC's ARP table). args: {}")
def lan_devices(a: dict) -> Result:
    ok, out = run_ps("arp -a")
    if not ok:
        return Result(False, out)
    devices = parse_arp(out)
    if not devices:
        return Result(True, "I see no other devices on the network right now.")
    shown = "; ".join(f"{ip} ({mac})" for ip, mac in devices[:12])
    return Result(True, f"{len(devices)} devices seen recently: {shown}. Unknown ones are worth checking in your router.")


# ----------------------------------------------------------------- CVE news
CISA = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
_CVE_CACHE: dict = {"at": 0.0, "items": []}


def kev_items() -> list[dict]:
    if time.time() - _CVE_CACHE["at"] < 3600 and _CVE_CACHE["items"]:
        return _CVE_CACHE["items"]
    r = requests.get(CISA, timeout=12, headers={"User-Agent": "Nemiii"})
    r.raise_for_status()
    items = sorted(r.json().get("vulnerabilities", []), key=lambda v: v.get("dateAdded", ""), reverse=True)
    _CVE_CACHE.update(at=time.time(), items=items)
    return items


@action("cve_news", "info",
        'Newest actively exploited vulnerabilities (CISA list). args: {"vendor": "optional, e.g. microsoft"}')
def cve_news(a: dict) -> Result:
    vendor = str(a.get("vendor", "")).lower().strip()
    items = kev_items()
    if vendor:
        items = [v for v in items if vendor in v.get("vendorProject", "").lower() or vendor in v.get("product", "").lower()]
    if not items:
        return Result(True, "Nothing new for that.")
    lines = [f"{v['cveID']} in {v['vendorProject']} {v['product']}: {v['vulnerabilityName']} (added {v['dateAdded']})"
             for v in items[:5]]
    return Result(True, "Actively exploited vulnerabilities:\n" + "\n".join(lines))


# ----------------------------------------------------------------- honeypot
@action("honeypot_status", "info", "State of your honeypot Docker container and its recent traffic. args: {}")
def honeypot_status(a: dict) -> Result:
    import config
    try:
        ps = subprocess.run(["docker", "ps", "-a", "--format", "{{.Names}}|{{.Status}}"],
                            capture_output=True, text=True, timeout=10)
    except FileNotFoundError:
        return Result(False, "Docker isn't available in WSL.")
    except subprocess.TimeoutExpired:
        return Result(False, "Docker took too long to answer.")
    rows = [ln.split("|", 1) for ln in ps.stdout.splitlines() if "|" in ln]
    want = config.HONEYPOT_CONTAINER.lower()
    match = [r for r in rows if want and want in r[0].lower()]
    if not match:
        return Result(False, f"I found no container with {want} in its name. Set HONEYPOT_CONTAINER in backend/.env.")
    name, status = match[0]
    msg = f"{name} is {status}."
    if status.lower().startswith("up"):
        logs = subprocess.run(["docker", "logs", "--tail", "300", name], capture_output=True, text=True, timeout=15)
        lines = (logs.stdout + logs.stderr).splitlines()
        hits = [ln for ln in lines if re.search(r"\b(GET|POST|PUT|DELETE)\b", ln)]
        msg += f" {len(hits)} web requests in its last 300 log lines."
        if hits:
            msg += " Latest: " + hits[-1][:140]
    return Result(True, msg)
