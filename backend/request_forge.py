"""Request Forge — real HTTP probing engine (async httpx).

Every request is a real network call with an injected identity context.
Responses are captured as ResponseRecord objects for the differential
analyzer. This module does NOT enforce authorization — it is only ever
invoked through the governed Tool Gateway.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from backend.session_engine import session_engine

DEFAULT_TIMEOUT = 15.0
MAX_BODY_CAPTURE = 64_000


@dataclass
class ResponseRecord:
    url: str
    method: str
    status: int
    elapsed_ms: float
    body: str
    headers: Dict[str, str]
    identity: str
    request_params: Dict[str, Any] = field(default_factory=dict)

    @property
    def length(self) -> int:
        return len(self.body)

    @property
    def digest(self) -> str:
        return hashlib.sha256(
            f"{self.status}|{self.length}|{self.body[:4096]}".encode()).hexdigest()[:16]


class RequestForge:
    def __init__(self):
        self.request_log: List[Dict[str, Any]] = []

    async def send(self, url: str, method: str = "GET",
                   identity: str = "unauth",
                   params: Optional[Dict[str, Any]] = None,
                   data: Optional[Any] = None,
                   json_body: Optional[Any] = None,
                   headers: Optional[Dict[str, str]] = None,
                   timeout: float = DEFAULT_TIMEOUT,
                   follow_redirects: bool = False) -> ResponseRecord:
        ctx = session_engine.get(identity) or session_engine.get("unauth")
        merged_headers = ctx.build_headers() if ctx else {}
        merged_headers.update(headers or {})
        host = httpx.URL(url).host
        cookies = dict(ctx.cookies) if ctx else {}
        cookies.update(session_engine.jar_for(host))

        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                    timeout=timeout, follow_redirects=follow_redirects,
                    verify=True, cookies=cookies) as client:
                resp = await client.request(
                    method.upper(), url, params=params, data=data,
                    json=json_body, headers=merged_headers)
            elapsed = round((time.perf_counter() - t0) * 1000, 2)
            body = resp.text[:MAX_BODY_CAPTURE]
            set_cookies = {k: v for k, v in resp.cookies.items()}
            if set_cookies:
                session_engine.update_jar(host, set_cookies)
            status = resp.status_code
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            resp_url = str(resp.url)
        except Exception as e:
            elapsed = round((time.perf_counter() - t0) * 1000, 2)
            body = f"ERROR: {str(e)}"
            status = 0
            resp_headers = {}
            resp_url = url

        record = ResponseRecord(
            url=resp_url, method=method.upper(), status=status,
            elapsed_ms=elapsed, body=body,
            headers=resp_headers,
            identity=ctx.name if ctx else "unauth",
            request_params={"params": params, "json": json_body, "data": data})
        self.request_log.append({
            "ts": time.time(), "url": url, "method": method.upper(),
            "identity": record.identity, "status": status,
            "elapsed_ms": elapsed})
        return record


request_forge = RequestForge()
