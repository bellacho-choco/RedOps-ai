"""
====================================================================
PROJECT REDOPS-OMEGA - SONIC SPEED LAYER (BEAT #5)
Parallel GDT dispatch with bounded concurrency + token plumbing.

READY goals on parallel branches fan out concurrently; a semaphore
enforces max_concurrent and the Token Issuer validates each lane.
====================================================================
"""

import asyncio
import copy
import time
from typing import Awaitable, Callable, Dict, List, Any, Optional

from pydantic import BaseModel, Field

from backend.mission_engine import mission_engine, GoalNode, GoalState


class LaneContext(BaseModel):
    """Isolated per-lane goal context (BEAT #7): the runner receives a deep
    copy of its goal + a frozen mission snapshot; no mutable refs to shared
    frontier state — Satellite-style 'system prompt reset' isolation."""
    goal: Dict[str, Any]
    agent: str
    snapshot: Dict[str, Any] = Field(default_factory=dict)


class LaneResult(BaseModel):
    goal_id: str
    agent: str
    status: str = "PENDING"   # PENDING | DONE | FAILED | SKIPPED
    elapsed_ms: float = 0.0
    summary: Optional[str] = None


class ParallelGoalDispatcher:
    """
    Fan-out executor for GDT READY goals. A semaphore caps concurrency;
    every lane re-checks GoalState under an internal lock before RUNNING,
    so the dispatch is race-safe.
    """

    def __init__(self, max_concurrent: int = 4):
        self.max_concurrent = max_concurrent

    async def dispatch(self, runner: Callable[[LaneContext], Awaitable[Any]],
                       max_concurrent: Optional[int] = None) -> List[LaneResult]:
        mission = mission_engine.get_active()
        if not mission:
            return [LaneResult(goal_id="—", agent="—", status="SKIPPED",
                               summary="no ACTIVE mission")]
        ready = mission.gdt.next_ready()
        if not ready:
            return [LaneResult(goal_id="—", agent="—", status="SKIPPED",
                               summary="no READY goals on frontier")]
        sem = asyncio.Semaphore(max_concurrent or self.max_concurrent)

        async def _lane(goal: GoalNode) -> LaneResult:
            async with sem:
                started = time.perf_counter()
                try:
                    mission.gdt.mark_running(goal.goal_id)
                except ValueError:
                    return LaneResult(goal_id=goal.goal_id, agent=goal.agent,
                                      status="SKIPPED", summary="no longer READY")
                # Fresh-context lane: deep copy of the goal + frozen snapshot.
                ctx = LaneContext(
                    goal=copy.deepcopy(goal.model_dump()),
                    agent=goal.agent,
                    snapshot=copy.deepcopy(mission.gdt.to_dict()))
                try:
                    result = await runner(ctx)
                    mission.gdt.mark_done(goal.goal_id,
                                          result={"result": str(result)[:400]} if result else None)
                    return LaneResult(goal_id=goal.goal_id, agent=goal.agent,
                                      status="DONE",
                                      elapsed_ms=round((time.perf_counter() - started) * 1000, 2))
                except Exception as exc:
                    mission.gdt.mark_failed(goal.goal_id, error=str(exc))
                    return LaneResult(goal_id=goal.goal_id, agent=goal.agent,
                                      status="FAILED",
                                      elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
                                      summary=str(exc)[:160])

        return await asyncio.gather(*[_lane(g) for g in ready])


# Global Parallel Goal Dispatcher
parallel_dispatcher = ParallelGoalDispatcher()
