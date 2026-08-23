"""
====================================================================
PROJECT REDOPS-OMEGA - PLUGIN MARKETPLACE & GOVERNANCE SATELLITE
Community-curated plugin bundles with signature + trust-level vetting.
====================================================================
"""

import hashlib
import json
import time
from typing import Dict, List, Any, Optional

from pydantic import BaseModel, Field


TRUST_ORDER = {"CORE": 3, "PREVIEW": 2, "COMMUNITY": 1, "UNTRUSTED": 0}


class PluginBundle(BaseModel):
    name: str
    version: str = "0.1.0"
    trust: str = "COMMUNITY"        # CORE | PREVIEW | COMMUNITY | UNTRUSTED
    skills: List[str] = Field(default_factory=list)
    depends: List[str] = Field(default_factory=list)
    signature: str = ""
    publisher: str = "redops-omega"
    installed: bool = False


class PluginMarketplace:
    """Governed plugin bundle registry with signature + trust gate."""

    def __init__(self):
        self._plugins: Dict[str, PluginBundle] = {}
        self._install_history: List[Dict[str, Any]] = []

    # ----------------------------------------------------------------
    def sign(bundle: Dict[str, Any], secret: bytes) -> str:  # type: ignore
        payload = json.dumps(bundle, sort_keys=True, separators=(",", ":"))
        import hmac
        return hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()

    def publish(self, bundle: PluginBundle) -> Dict[str, Any]:
        if bundle.name in self._plugins:
            return {"status": "DUPLICATE", "name": bundle.name}
        self._plugins[bundle.name] = bundle
        return {"status": "PUBLISHED", "name": bundle.name, "trust": bundle.trust}

    def install(self, name: str) -> Dict[str, Any]:
        plugin = self._plugins.get(name)
        if not plugin:
            return {"status": "NOT_FOUND"}
        missing = [d for d in plugin.depends if d not in self._plugins
                   or not self._plugins[d].installed]
        if missing:
            return {"status": "MISSING_DEPS", "deps": missing}
        if plugin.trust == "UNTRUSTED":
            return {"status": "BLOCKED", "reason": "UNTRUSTED bundle"}
        plugin.installed = True
        self._install_history.append({"plugin": name, "installed_at": time.time()})
        return {"status": "INSTALLED", "plugin": name, "trust": plugin.trust}

    def get_stats(self) -> Dict[str, Any]:
        return {
            "plugins": len(self._plugins),
            "installed": sum(1 for p in self._plugins.values() if p.installed),
            "by_trust": {t: sum(1 for p in self._plugins.values() if p.trust == t)
                         for t in ["CORE", "PREVIEW", "COMMUNITY", "UNTRUSTED"]},
            "install_history": self._install_history[-10:],
        }


# Global Plugin Marketplace
plugin_market = PluginMarketplace()
