"""
====================================================================
PROJECT REDOPS-OMEGA - STRATEGY MEMORY (THREE-TIER)
Ephemeral session context, campaign key-value state & long-term
lesson extraction with regression gates. Blueprint Section 5.
====================================================================
"""

import re
import time
import uuid
from collections import Counter, deque
from typing import Dict, List, Any, Optional

from pydantic import BaseModel, Field


class Lesson(BaseModel):
    lesson_id: str = Field(default_factory=lambda: f"lesson-{uuid.uuid4().hex[:8]}")
    pattern: str                   # what was attempted (normalized signature)
    outcome: str                   # SUCCESS | FAILURE
    context_tags: List[str] = Field(default_factory=list)
    occurrences: int = 1
    regression_tested: bool = False   # sandbox gate before promotion
    created_at: float = Field(default_factory=time.time)
    last_seen: float = Field(default_factory=time.time)


class CampaignRecord(BaseModel):
    key: str
    value: Any
    updated_at: float = Field(default_factory=time.time)


def _normalize_signature(text: str) -> str:
    """Strip volatile bits (IPs, ports, timestamps) so similar attempts cluster."""
    sig = re.sub(r"\b\d{1,3}(\.\d{1,3}){3}\b", "<IP>", text)
    sig = re.sub(r":\d{2,5}\b", ":<PORT>", sig)
    sig = re.sub(r"\b\d{10,}\b", "<TS>", sig)
    return sig.strip().lower()[:200]


class StrategyMemory:
    """
    Tier 1 (session): bounded deque of recent events.
    Tier 2 (campaign): key-value mission state.
    Tier 3 (long-term): lesson store. A lesson is only *promoted* to the
    approved playbook after a sandbox regression flag — the agent learns
    strategy, it never rewrites its own control plane.
    """
    def __init__(self, session_capacity: int = 500):
        self.session_context: deque = deque(maxlen=session_capacity)
        self.campaign_state: Dict[str, CampaignRecord] = {}
        self.lessons: Dict[str, Lesson] = {}          # keyed by normalized signature

    # Tier 1 ------------------------------------------------------------
    def push_session_event(self, agent: str, event: str, meta: Optional[Dict] = None):
        self.session_context.append({
            "ts": time.time(), "agent": agent, "event": event, "meta": meta or {},
        })

    def recent_events(self, limit: int = 25) -> List[Dict[str, Any]]:
        return list(self.session_context)[-limit:]

    # Tier 2 ------------------------------------------------------------
    def set_campaign(self, key: str, value: Any):
        self.campaign_state[key] = CampaignRecord(key=key, value=value)

    def get_campaign(self, key: str, default: Any = None) -> Any:
        rec = self.campaign_state.get(key)
        return rec.value if rec else default

    # Tier 3 ------------------------------------------------------------
    def record_outcome(self, attempt: str, outcome: str,
                       tags: Optional[List[str]] = None,
                       regression_tested: bool = False) -> Lesson:
        sig = _normalize_signature(attempt)
        lesson = self.lessons.get(sig)
        if lesson:
            lesson.occurrences += 1
            lesson.last_seen = time.time()
            lesson.outcome = outcome
            lesson.regression_tested = lesson.regression_tested or regression_tested
            if tags:
                lesson.context_tags = sorted(set(lesson.context_tags) | set(tags))
            return lesson
        lesson = Lesson(
            pattern=sig, outcome=outcome.upper(),
            context_tags=tags or [], regression_tested=regression_tested,
        )
        self.lessons[sig] = lesson
        return lesson

    def recall(self, attempt: str) -> Optional[Lesson]:
        """Exact-signature recall of a prior attempt's outcome."""
        return self.lessons.get(_normalize_signature(attempt))

    def search_lessons(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        q = query.lower()
        hits = [l for l in self.lessons.values()
                if q in l.pattern or any(q in t.lower() for t in l.context_tags)]
        hits.sort(key=lambda l: (l.regression_tested, l.occurrences), reverse=True)
        return [l.model_dump() for l in hits[:limit]]

    def approved_strategies(self) -> List[Dict[str, Any]]:
        """Only regression-tested successes may guide future operations."""
        return [l.model_dump() for l in self.lessons.values()
                if l.outcome == "SUCCESS" and l.regression_tested]

    def get_stats(self) -> Dict[str, Any]:
        outcomes = Counter(l.outcome for l in self.lessons.values())
        return {
            "session_events": len(self.session_context),
            "campaign_keys": len(self.campaign_state),
            "lessons_total": len(self.lessons),
            "lessons_by_outcome": dict(outcomes),
            "approved_strategies": len(self.approved_strategies()),
        }


# Global Strategy Memory
strategy_memory = StrategyMemory()
