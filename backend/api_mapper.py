"""API Mapper — real endpoint discovery.

Discovers the attack surface of a web target from real sources:
  - robots.txt / sitemap.xml
  - OpenAPI/Swagger JSON at well-known locations
  - GraphQL introspection query
  - Same-host link extraction from the HTML entry page and JS bundles

Everything is a real HTTP fetch through RequestForge; no hardcoded endpoint
lists. Produces Endpoint objects with parameter hints for the fuzz engine.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from backend.request_forge import request_forge

OPENAPI_PATHS = ["/openapi.json", "/swagger.json", "/api-docs", "/v1/openapi.json",
                 "/api/openapi.json", "/docs/openapi.json"]
GRAPHQL_PATHS = ["/graphql", "/api/graphql", "/v1/graphql"]
JS_RE = re.compile(r'<script[^>]+src=["\']([^"\']+\.js[^"\']*)["\']', re.I)
LINK_RE = re.compile(r'(?:href|action)=["\']([^"\']+)["\']', re.I)
ENDPOINT_RE = re.compile(r'["\'](/[a-zA-Z0-9_\-/{}:.?=&]{2,120})["\']')
PARAM_RE = re.compile(r'[?&]([a-zA-Z0-9_\-]{1,32})=')

INTROSPECTION = {"query": "{__schema{queryType{name fields{name args{name type{name kind ofType{name kind}}}}}}}"}


@dataclass
class Endpoint:
    url: str
    method: str = "GET"
    params: List[str] = field(default_factory=list)
    source: str = "crawl"


class ApiMapper:
    def __init__(self):
        self.maps: Dict[str, List[Endpoint]] = {}

    async def map_target(self, base_url: str, identity: str = "unauth",
                         max_endpoints: int = 100) -> List[Endpoint]:
        found: Dict[str, Endpoint] = {}

        def add(url: str, method: str = "GET", params: Optional[List[str]] = None,
                source: str = "crawl"):
            if len(found) >= max_endpoints:
                return
            key = f"{method}:{url}"
            if key not in found:
                found[key] = Endpoint(url=url, method=method,
                                      params=params or [], source=source)

        # robots.txt + sitemap
        for path in ("/robots.txt", "/sitemap.xml"):
            rec = await request_forge.send(urljoin(base_url, path), identity=identity)
            if rec.status == 200:
                for m in re.findall(r'(?:Disallow|Allow):\s*(\S+)|<loc>([^<]+)</loc>', rec.body):
                    u = m[0] or m[1]
                    if u:
                        full = u if u.startswith("http") else urljoin(base_url, u)
                        if self._same_host(base_url, full):
                            add(full, source=path)

        # OpenAPI
        for path in OPENAPI_PATHS:
            rec = await request_forge.send(urljoin(base_url, path), identity=identity)
            if rec.status == 200 and ("paths" in rec.body[:2000] or "openapi" in rec.body[:500].lower()):
                try:
                    spec = json.loads(rec.body)
                    for p, ops in (spec.get("paths") or {}).items():
                        for method, op in (ops.items() if isinstance(ops, dict) else []):
                            params = [pr.get("name") for pr in (op.get("parameters") or [])
                                      if isinstance(pr, dict) and pr.get("name")]
                            add(urljoin(base_url, p), method.upper(), params, source="openapi")
                    break
                except ValueError:
                    continue

        # GraphQL introspection
        for path in GRAPHQL_PATHS:
            url = urljoin(base_url, path)
            rec = await request_forge.send(url, method="POST", json_body=INTROSPECTION,
                                           identity=identity)
            if rec.status == 200 and "__schema" in rec.body:
                try:
                    schema = json.loads(rec.body)["data"]["__schema"]
                    qt = schema.get("queryType") or {}
                    for fld in qt.get("fields") or []:
                        args = [a["name"] for a in (fld.get("args") or []) if a.get("name")]
                        add(url, "POST", [f"graphql:{fld['name']}({','.join(args)})"],
                            source="graphql")
                except (ValueError, TypeError, KeyError):
                    pass

        # HTML entry page: same-host links + JS bundles
        entry = await request_forge.send(base_url, identity=identity)
        if entry.status < 400:
            for href in LINK_RE.findall(entry.body):
                full = urljoin(base_url, href)
                if self._same_host(base_url, full):
                    add(full, params=PARAM_RE.findall(full), source="html")
            js_files = [urljoin(base_url, s) for s in JS_RE.findall(entry.body)][:10]
            for js in js_files:
                rec = await request_forge.send(js, identity=identity)
                if rec.status == 200:
                    for ep in ENDPOINT_RE.findall(rec.body):
                        if any(ep.startswith(p) for p in ("/api", "/v1", "/v2", "/graphql", "/user", "/account")):
                            add(urljoin(base_url, ep), source="js")

        endpoints = list(found.values())
        self.maps[base_url] = endpoints
        return endpoints

    @staticmethod
    def _same_host(base: str, url: str) -> bool:
        b, u = urlparse(base).hostname or "", urlparse(url).hostname or ""
        return u == b or u.endswith("." + b)


api_mapper = ApiMapper()
