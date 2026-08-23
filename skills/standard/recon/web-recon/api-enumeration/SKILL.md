---
name: web-api-enumeration
description: "REST API discovery, GraphQL detection, parameter fuzzing."
allowed-tools: Bash Read Write
metadata:
  subdomain: reconnaissance
  when_to_use: "API enumeration, swagger, openapi, GraphQL, introspection, parameter fuzzing, REST endpoints"
  tags: api-enum, graphql, swagger, parameter-discovery
  mitre_attack: T1595.003
---

# Web API Enumeration & Parameter Discovery

Surface REST/GraphQL endpoints, parse OpenAPI/Swagger schemas automatically, and uncover hidden parameters.

---

## 1. Automated REST API & Schema Extraction

### A. OpenAPI / Swagger Auto-Extractor
When Swagger or OpenAPI endpoint is found, parse all paths, HTTP methods, and parameters in 1 second:

```bash
python3 - <<'PY'
import urllib.request, json

doc_urls = [
    "https://<TARGET>/swagger.json",
    "https://<TARGET>/v2/api-docs",
    "https://<TARGET>/v3/api-docs",
    "https://<TARGET>/openapi.json",
    "https://<TARGET>/api/swagger.json"
]

routes = []
for url in doc_urls:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                paths = data.get("paths", {})
                print(f"[FOUND SCHEMA] {url} -> {len(paths)} endpoints")
                for path, methods in paths.items():
                    for method, details in methods.items():
                        routes.append({"path": path, "method": method.upper(), "summary": details.get("summary", "")})
                break
    except Exception:
        continue

if routes:
    with open("/workspace/api_routes.json", "w") as f:
        json.dump(routes, f, indent=2)
    print(f"[SAVED] /workspace/api_routes.json ({len(routes)} routes)")
PY
```

### B. High-Speed REST API Path Fuzzing
```bash
# JSON output fuzzing for clean parsing
ffuf -u "https://<TARGET>/api/FUZZ" -w /usr/share/wordlists/api-endpoints.txt \
     -o /workspace/api_endpoints.json -of json -mc 200,201,401,403,405 -silent

python3 -c "import json; d=json.load(open('/workspace/api_endpoints.json')); print([(r['input'], r['status']) for r in d.get('results', [])])"
```

---

## 2. GraphQL Schema Introspection & Mutation Analysis

```bash
# 1. Probe for GraphQL endpoints
for path in graphql graphiql api/graphql v1/graphql playground query; do
    code=$(curl -sk -o /dev/null -w "%{http_code}" -X POST "https://<TARGET>/$path" \
           -H "Content-Type: application/json" -d '{"query":"query{__typename}"}')
    [ "$code" = "200" ] && echo "[GRAPHQL FOUND] -> https://<TARGET>/$path"
done

# 2. Extract full Schema & Mutations if introspection is enabled
python3 - <<'PY'
from curl_cffi import requests as r
import json

target = "https://<TARGET>/graphql"
query = """
{
  __schema {
    types {
      name
      fields {
        name
        args { name type { name kind } }
      }
    }
  }
}
"""
try:
    resp = r.post(target, json={"query": query}, impersonate="chrome", timeout=10)
    if resp.status_code == 200 and "data" in resp.json():
        schema = resp.json()
        open("/workspace/graphql_schema.json", "w").write(json.dumps(schema, indent=2))
        types = [t["name"] for t in schema["data"]["__schema"]["types"] if not t["name"].startswith("__")]
        print(f"[INTROSPECTION SUCCESS] Saved to /workspace/graphql_schema.json | Custom Types: {types[:15]}")
    else:
        print("[INTROSPECTION DISABLED] Schema introspection blocked or disabled.")
except Exception as e:
    print(f"GraphQL query error: {e}")
PY
```

---

## 3. Parameter Discovery & Secret Token Extraction

```bash
# Hidden parameter discovery on live endpoints
ffuf -u "https://<TARGET>/api/user?FUZZ=1" -w /usr/share/wordlists/params.txt \
     -mc 200 -fs <baseline_size> -o /workspace/params.json -of json -silent

# JWT Header & Signature Analysis (None Algorithm / Expired check)
python3 - <<'PY'
import json, base64

def decode_jwt(token):
    parts = token.split('.')
    if len(parts) >= 2:
        def b64_decode(data):
            return base64.urlsafe_b64decode(data + '=' * (-len(data) % 4)).decode('utf-8', errors='ignore')
        header = json.loads(b64_decode(parts[0]))
        payload = json.loads(b64_decode(parts[1]))
        print(f"JWT Header: {header}")
        print(f"JWT Payload: {payload}")

# Example: decode_jwt("<TOKEN>")
PY
```

