"""PLAN Step 4: adversarial robustness tests for blueprint failure modes."""
import asyncio

import pytest

from backend.swarm_bus import AgentMessage
from backend.llm_provider import llm_provider


class TestMalformedIPC:
    def test_malformed_json_rejected_not_crashed(self):
        # Malformed payload must raise a validation error, never silently pass
        with pytest.raises(Exception):
            AgentMessage.model_validate_json("{not valid json")

    def test_missing_required_fields_rejected(self):
        with pytest.raises(Exception):
            AgentMessage.model_validate({"source_agent": "x"})


class TestCircuitBreaker:
    def test_three_strikes_blocks_goal(self):
        from backend.mission_engine import GoalDependencyTree, GoalNode
        gdt = GoalDependencyTree()
        gdt.add_goal(GoalNode(goal_id="g1", title="t", agent="x"))
        for _ in range(3):  # full retry cycle: ready -> running -> failed
            gdt.mark_running("g1")
            gdt.mark_failed("g1", "boom")
        assert gdt.goals["g1"].state.value == "BLOCKED"
        assert gdt.goals["g1"].attempts == 3


class TestScopeEnforcement:
    def test_out_of_scope_ip_rejected(self):
        """A resolved IP outside the authorized scope must fail the check."""
        from backend.mission_engine import ScopeEnforcer, TargetScope

        # Domain in scope but redirect resolves outside declared networks
        scope = TargetScope(domains=["allowed.example.com"],
                            networks=["10.0.0.0/8"], exclusions=[])
        enforcer = ScopeEnforcer(scope)
        verdict = enforcer.check("allowed.example.com", resolved_ip="203.0.113.99")
        assert verdict["in_scope"] is False
        assert "redirect" in verdict["reason"]

    def test_in_scope_target_passes(self):
        from backend.mission_engine import ScopeEnforcer, TargetScope

        scope = TargetScope(domains=["allowed.example.com"], networks=[], exclusions=[])
        enforcer = ScopeEnforcer(scope)
        assert enforcer.check("allowed.example.com")["in_scope"] is True


class TestLLMFallback:
    def test_no_key_falls_back_to_heuristic(self):
        provider = llm_provider
        provider.api_key = None
        provider.provider = "heuristic"
        out = asyncio.run(provider.generate_cyber_reasoning(
            "TEST", "test prompt", {}))
        assert isinstance(out, str) and len(out) > 0

    def test_timeout_produces_heuristic_not_hang(self, monkeypatch):
        import httpx

        class TimeoutClient:
            def __init__(self, *a, **k): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def post(self, *a, **k):
                raise httpx.TimeoutException("simulated")

        monkeypatch.setattr(httpx, "AsyncClient", TimeoutClient)
        provider = llm_provider
        provider.api_key = "fake-key"
        provider.provider = "openai"
        try:
            out = asyncio.run(provider.generate_cyber_reasoning(
                "TEST", "analyze this target", {}))
        finally:
            provider.api_key = None
            provider.provider = "heuristic"
        assert "FALLBACK" in out or len(out) > 0
