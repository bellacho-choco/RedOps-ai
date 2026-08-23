"""
====================================================================
PROJECT REDOPS-AI - CUSTOM LLM PROVIDER & CYBER REASONING ENGINE
Multi-Provider LLM Bridge (Gemini, OpenAI, Claude, Custom Endpoint)
Strictly Excludes Ollama. Includes Offline Heuristic Fallback.
====================================================================
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
import httpx

logger = logging.getLogger("redops.llm")


class CustomLLMProvider:
    """
    Customizable LLM reasoning engine supporting:
    - 'gemini' (Google Gemini API via official endpoint)
    - 'openai' (OpenAI GPT-4o / GPT-4o-mini)
    - 'claude' (Anthropic Claude 3.5 Sonnet / Haiku via REST)
    - 'custom' (Any OpenAI-compatible base URL e.g. OpenRouter, vLLM, DeepSeek, LiteLLM)
    - 'heuristic' (Deterministic offline cyber reasoning fallback)

    Strictly excludes Ollama.
    """
    def __init__(self):
        self.provider: str = os.getenv("LLM_PROVIDER", "gemini").lower()
        self.api_key: str = (
            os.getenv("GEMINI_API_KEY") or
            os.getenv("GOOGLE_API_KEY") or
            os.getenv("OPENAI_API_KEY") or
            os.getenv("ANTHROPIC_API_KEY") or
            os.getenv("CUSTOM_LLM_API_KEY") or
            ""
        )
        self.base_url: str = os.getenv("CUSTOM_LLM_BASE_URL", "https://api.openai.com/v1")
        self.model: str = os.getenv("LLM_MODEL", "")

        # Default model selection based on provider
        if not self.model:
            if self.provider == "gemini":
                self.model = "gemini-2.0-flash"
            elif self.provider == "openai":
                self.model = "gpt-4o-mini"
            elif self.provider == "claude":
                self.model = "claude-3-5-haiku-20241022"
            else:
                self.model = "gpt-4o-mini"

        # Explicit safety check: reject Ollama if requested
        if "ollama" in self.provider or "ollama" in self.base_url.lower():
            logger.warning("[LLM] Ollama provider is blocked. Reverting to heuristic fallback.")
            self.provider = "heuristic"

    def configure(self, provider: str, api_key: str, model: Optional[str] = None, base_url: Optional[str] = None):
        """
        Dynamically reconfigures the LLM provider.
        """
        provider_clean = provider.strip().lower()
        if "ollama" in provider_clean:
            raise ValueError("Ollama provider is disabled by policy.")

        self.provider = provider_clean
        self.api_key = api_key.strip()
        if base_url:
            if "ollama" in base_url.lower():
                raise ValueError("Ollama base URL is disabled by policy.")
            self.base_url = base_url.strip()

        if model:
            self.model = model.strip()
        else:
            if self.provider == "gemini":
                self.model = "gemini-2.0-flash"
            elif self.provider == "openai":
                self.model = "gpt-4o-mini"
            elif self.provider == "claude":
                self.model = "claude-3-5-haiku-20241022"
            else:
                self.model = "default-model"

    def get_status(self) -> Dict[str, Any]:
        has_key = bool(self.api_key and len(self.api_key) > 5)
        return {
            "provider": self.provider,
            "model": self.model,
            "has_api_key": has_key,
            "base_url": self.base_url if self.provider == "custom" else "Default API Gateway",
            "active_mode": "LIVE_API" if has_key else "OFFLINE_HEURISTIC_REASONING"
        }

    async def generate_cyber_reasoning(
        self,
        agent_role: str,
        task: str,
        scan_context: Dict[str, Any],
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Generates tactical cyber reasoning and playbook alignment from target scan context.
        """
        # If no valid API key is present or provider is heuristic, use deterministic heuristic engine
        if not self.api_key or self.provider == "heuristic":
            return self._heuristic_reasoning(agent_role, task, scan_context)

        try:
            if self.provider == "gemini":
                return await self._call_gemini(agent_role, task, scan_context, system_prompt)
            elif self.provider == "openai" or self.provider == "custom":
                return await self._call_openai_compatible(agent_role, task, scan_context, system_prompt)
            elif self.provider == "claude":
                return await self._call_claude(agent_role, task, scan_context, system_prompt)
            else:
                return self._heuristic_reasoning(agent_role, task, scan_context)
        except Exception as e:
            logger.error(f"[LLM ERROR] Failed to query {self.provider}: {e}")
            return (
                f"[REASONING ENGINE FALLBACK] (Provider '{self.provider}' encountered error: {str(e)[:80]})\n"
                + self._heuristic_reasoning(agent_role, task, scan_context)
            )

    async def _call_gemini(self, agent_role: str, task: str, scan_context: Dict[str, Any], system_prompt: Optional[str]) -> str:
        """
        Calls Google Gemini REST API.
        """
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}

        sys_instruction = system_prompt or (
            f"You are {agent_role} in the RedOps-AI security platform. "
            "Analyze the target findings, identify architectural attack paths, missing defensive controls, "
            "and suggest precise remediation steps in professional, actionable bullet points."
        )

        user_content = f"TASK: {task}\n\nLIVE SCAN CONTEXT:\n{json.dumps(scan_context, indent=2)}"

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": f"{sys_instruction}\n\n{user_content}"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1000
            }
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return text
            else:
                raise RuntimeError(f"Gemini API returned HTTP {resp.status_code}: {resp.text[:120]}")

    async def _call_openai_compatible(self, agent_role: str, task: str, scan_context: Dict[str, Any], system_prompt: Optional[str]) -> str:
        """
        Calls OpenAI or any custom OpenAI-compatible endpoint (OpenRouter, DeepSeek, LiteLLM, vLLM).
        """
        base = self.base_url.rstrip("/")
        url = f"{base}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        sys_msg = system_prompt or (
            f"You are {agent_role} in the RedOps-AI cybersecurity swarm. "
            "Provide rigorous, concise, technical security analysis and defensive remediation recommendations."
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": f"TASK: {task}\n\nSCAN FINDINGS:\n{json.dumps(scan_context, indent=2)}"}
            ],
            "temperature": 0.2,
            "max_tokens": 1000
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            else:
                raise RuntimeError(f"OpenAI-compatible API returned HTTP {resp.status_code}: {resp.text[:120]}")

    async def _call_claude(self, agent_role: str, task: str, scan_context: Dict[str, Any], system_prompt: Optional[str]) -> str:
        """
        Calls Anthropic Claude REST API.
        """
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }

        sys_msg = system_prompt or (
            f"You are {agent_role} in the RedOps-AI security platform. "
            "Analyze security posture, identify potential vulnerabilities, and deliver prioritized remediation plans."
        )

        payload = {
            "model": self.model,
            "max_tokens": 1000,
            "system": sys_msg,
            "messages": [
                {"role": "user", "content": f"TASK: {task}\n\nFINDINGS:\n{json.dumps(scan_context, indent=2)}"}
            ]
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data["content"][0]["text"]
            else:
                raise RuntimeError(f"Claude API returned HTTP {resp.status_code}: {resp.text[:120]}")

    def _heuristic_reasoning(self, agent_role: str, task: str, scan_context: Dict[str, Any]) -> str:
        """
        Deterministic, offline security reasoning engine when no API keys are active.
        """
        target = scan_context.get("target", "Target Host")
        open_ports = scan_context.get("open_ports", [])
        web_findings = scan_context.get("web_audit", {})
        missing_headers = web_findings.get("missing_security_headers", [])
        tech_stack = web_findings.get("technology_stack", {})

        reasons: List[str] = [
            f"🎯 [ANALYSIS FOR {target}] Role: {agent_role}",
            f"• Attack Surface: {len(open_ports)} exposed TCP/UDP services detected.",
        ]

        if open_ports:
            ports_summary = ", ".join([f"{p.get('port')}/{p.get('service', 'unknown')}" for p in open_ports[:5]])
            reasons.append(f"• Active Services: {ports_summary}")
            for p in open_ports:
                port_num = p.get("port")
                if port_num in [21, 23]:
                    reasons.append(f"  ⚠️ HIGH RISK: Insecure cleartext protocol port {port_num} detected. Immediate migration to SSH/SFTP required.")
                elif port_num in [3389, 445]:
                    reasons.append(f"  ⚠️ EXPOSURE: Lateral movement vector port {port_num} open. Ensure strict Network Access Control (NAC) and MFA.")
                elif port_num in [6379, 27017, 9200]:
                    reasons.append(f"  ⚠️ DATABASE EXPOSURE: Internal database port {port_num} exposed to perimeter.")

        if missing_headers:
            reasons.append(f"• Web Security Posture: {len(missing_headers)} essential hardening headers missing ({', '.join(missing_headers[:4])}).")
            if "Content-Security-Policy" in missing_headers:
                reasons.append("  - Mitigation: Enforce strict CSP to neutralize Cross-Site Scripting (XSS) and unauthorized script injection.")
            if "Strict-Transport-Security" in missing_headers:
                reasons.append("  - Mitigation: Deploy HSTS (max-age=31536000; includeSubDomains; preload) to prevent SSL stripping.")
            if "X-Frame-Options" in missing_headers:
                reasons.append("  - Mitigation: Set X-Frame-Options: DENY to prevent Clickjacking attacks.")

        if tech_stack:
            server = tech_stack.get("server") or "Generic"
            reasons.append(f"• Fingerprinted Stack: Server={server}, Framework={tech_stack.get('x_powered_by', 'Undisclosed')}")

        reasons.append("• MITRE ATT&CK Mapping: T1595.002 (Vulnerability Scanning), T1190 (Exploit Public-Facing Application), T1046 (Network Service Discovery).")
        reasons.append("• Recommended Next Action: Implement defense-in-depth perimeter filtering and generate debrief mitigation report.")

        return "\n".join(reasons)


# Singleton Instance
llm_provider = CustomLLMProvider()
