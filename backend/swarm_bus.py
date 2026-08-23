"""
====================================================================
PROJECT REDOPS-AI - SUB-MILLISECOND ASYNC SWARM BUS (IPC)
Ultra-Low Latency Inter-Agent Event Routing & Telemetry Stream
====================================================================
"""

import asyncio
import time
from typing import Dict, List, Any, Callable, Optional
from collections import deque
from pydantic import BaseModel, Field


class AgentMessage(BaseModel):
    message_id: str
    source_agent: str
    target_agent: str
    event_type: str
    content: str
    meta: Dict[str, Any] = Field(default_factory=dict)
    timestamp_ns: int = Field(default_factory=time.time_ns)
    latency_ms: float = 0.0


class SwarmMessageBus:
    """
    Sub-millisecond Asynchronous Event Bus.
    Provides instant publish/subscribe, direct agent-to-agent IPC,
    and live telemetry tracking.
    """
    def __init__(self, max_history: int = 500):
        self.subscribers: Dict[str, List[asyncio.Queue]] = {}
        self.history: deque = deque(maxlen=max_history)
        self.total_messages: int = 0
        self.total_latency_ns: int = 0
        self._lock = asyncio.Lock()

    def subscribe(self, agent_name: str) -> asyncio.Queue:
        """
        Subscribes an agent to the event bus.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        if agent_name not in self.subscribers:
            self.subscribers[agent_name] = []
        self.subscribers[agent_name].append(queue)
        return queue

    async def publish(self, msg: AgentMessage) -> float:
        """
        Publishes a message to target agent(s) or broadcast with sub-millisecond dispatch.
        Returns the computed latency in milliseconds.
        """
        now_ns = time.time_ns()
        latency_ns = max(0, now_ns - msg.timestamp_ns)
        latency_ms = round(latency_ns / 1_000_000.0, 4)
        msg.latency_ms = latency_ms

        async with self._lock:
            self.history.append(msg)
            self.total_messages += 1
            self.total_latency_ns += latency_ns

        # Dispatch to specific target or broadcast to all
        targets = []
        if msg.target_agent == "BROADCAST" or msg.target_agent == "*":
            for q_list in self.subscribers.values():
                targets.extend(q_list)
        else:
            if msg.target_agent in self.subscribers:
                targets.extend(self.subscribers[msg.target_agent])
            # Always ensure global monitors receive the feed
            if "MONITOR" in self.subscribers:
                targets.extend(self.subscribers["MONITOR"])

        for q in targets:
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

        return latency_ms

    def get_telemetry(self) -> Dict[str, Any]:
        """
        Returns real-time performance telemetry.
        """
        avg_latency_ms = round((self.total_latency_ns / max(1, self.total_messages)) / 1_000_000.0, 4)
        return {
            "total_messages": self.total_messages,
            "subscribers_count": len(self.subscribers),
            "average_latency_ms": avg_latency_ms,
            "target_latency": "< 0.2ms",
            "recent_messages_count": len(self.history)
        }


# Global Swarm Bus
swarm_bus = SwarmMessageBus()
