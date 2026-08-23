"""Session & Identity Engine — real auth state for authenticated testing.

Maintains named identity contexts (e.g. 'unauth', 'user_a', 'user_b') with
real cookies, bearer tokens and API keys. Identities are what make IDOR and
privilege-escalation detection possible: the same request issued under two
contexts and diffed by the ResponseAnalyzer.

Identity material comes from env/secret config at runtime — NEVER from the
repo. Format:
  REDOPS_IDENTITY_<NAME>_APIKEY=...
  REDOPS_IDENTITY_<NAME>_BEARER=...
  REDOPS_IDENTITY_<NAME>_COOKIES=k=v; k2=v2
  REDOPS_IDENTITY_<NAME>_HEADERS={"X-Api-Key": "..."}
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class IdentityContext:
    name: str
    headers: Dict[str, str] = field(default_factory=dict)
    cookies: Dict[str, str] = field(default_factory=dict)
    bearer: Optional[str] = None
    api_key: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def build_headers(self) -> Dict[str, str]:
        h = dict(self.headers)
        if self.bearer:
            h["Authorization"] = f"Bearer {self.bearer}"
        if self.api_key and "X-Api-Key" not in h and "x-api-key" not in {k.lower(): v for k, v in h.items()}:
            h["X-Api-Key"] = self.api_key
        return h


class SessionEngine:
    """Registry of identity contexts + per-target cookie jars."""

    def __init__(self):
        self.identities: Dict[str, IdentityContext] = {}
        self._jars: Dict[str, Dict[str, str]] = {}  # target_host -> cookies
        self._load_env_identities()
        if "unauth" not in self.identities:
            self.register("unauth", IdentityContext(name="unauth"))

    # ---------------- identities ----------------
    def register(self, name: str, ctx: IdentityContext) -> IdentityContext:
        self.identities[name.lower()] = ctx
        return ctx

    def create(self, name: str, headers: Optional[Dict[str, str]] = None,
               bearer: Optional[str] = None, api_key: Optional[str] = None,
               cookies: Optional[Dict[str, str]] = None) -> IdentityContext:
        return self.register(name, IdentityContext(
            name=name.lower(), headers=headers or {}, cookies=cookies or {},
            bearer=bearer, api_key=api_key))

    def get(self, name: str) -> Optional[IdentityContext]:
        return self.identities.get(name.lower())

    def list_identities(self) -> List[Dict[str, str]]:
        return [{
            "name": c.name,
            "authenticated": bool(c.bearer or c.api_key or c.cookies or c.headers),
        } for c in self.identities.values()]

    def _load_env_identities(self) -> None:
        prefix = "REDOPS_IDENTITY_"
        names = {k[len(prefix):].rsplit("_", 1)[0]
                 for k in os.environ if k.startswith(prefix)}
        for n in names:
            headers = {}
            raw_headers = os.environ.get(f"{prefix}{n}_HEADERS")
            if raw_headers:
                import json
                try:
                    headers = json.loads(raw_headers)
                except ValueError:
                    headers = {}
            cookies = {}
            raw_cookies = os.environ.get(f"{prefix}{n}_COOKIES", "")
            for pair in raw_cookies.split(";"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    cookies[k.strip()] = v.strip()
            self.create(n.lower(),
                        headers=headers,
                        bearer=os.environ.get(f"{prefix}{n}_BEARER"),
                        api_key=os.environ.get(f"{prefix}{n}_APIKEY"),
                        cookies=cookies)

    # ---------------- cookie jars ----------------
    def update_jar(self, host: str, set_cookies: Dict[str, str]) -> None:
        jar = self._jars.setdefault(host, {})
        jar.update(set_cookies)

    def jar_for(self, host: str) -> Dict[str, str]:
        return dict(self._jars.get(host, {}))


session_engine = SessionEngine()
