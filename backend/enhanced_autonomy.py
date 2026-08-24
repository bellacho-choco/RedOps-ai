"""
====================================================================
PROJECT REDOPS-AI - ENHANCED AGENT AUTONOMY SYSTEM
Advanced agent task handling, autonomous decision making, and coordination
====================================================================
"""

import asyncio
import time
import uuid
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import os


class TaskPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentState(str, Enum):
    IDLE = "idle"
    ACTIVE = "active"
    BUSY = "busy"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"


@dataclass
class AgentTask:
    id: str
    title: str
    description: str
    priority: TaskPriority
    status: TaskStatus
    assigned_to: str
    created_by: str
    created_at: float
    deadline: Optional[float] = None
    skills_required: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    progress: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value,
            "status": self.status.value,
            "assigned_to": self.assigned_to,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "deadline": self.deadline,
            "skills_required": self.skills_required,
            "dependencies": self.dependencies,
            "result": self.result,
            "error_message": self.error_message,
            "progress": self.progress,
            "metadata": self.metadata
        }


@dataclass
class AgentProfile:
    agent_id: str
    codename: str
    role: str
    specialization: str
    capabilities: Set[str]
    skills: List[str]
    state: AgentState
    current_task_id: Optional[str] = None
    performance_score: float = 1.0
    tasks_completed: int = 0
    tasks_failed: int = 0
    last_active: float = field(default_factory=time.time)
    workload_capacity: int = 5
    preferences: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "codename": self.codename,
            "role": self.role,
            "specialization": self.specialization,
            "capabilities": list(self.capabilities),
            "skills": self.skills,
            "state": self.state.value,
            "current_task_id": self.current_task_id,
            "performance_score": self.performance_score,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "last_active": self.last_active,
            "workload_capacity": self.workload_capacity,
            "preferences": self.preferences
        }


class EnhancedAgentAutonomy:
    """Advanced agent autonomy system with intelligent task distribution"""
    
    def __init__(self, data_path: Optional[str] = None):
        self.data_path = data_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".redops_memory", "agent_autonomy.json"
        )
        self.agents: Dict[str, AgentProfile] = {}
        self.tasks: Dict[str, AgentTask] = {}
        self.task_queue: List[str] = []  # Task IDs ordered by priority
        self._load_data()
        self._initialize_agents()
    
    def _load_data(self):
        """Load autonomy data from persistent storage"""
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, 'r') as f:
                    data = json.load(f)
                    for agent_data in data.get("agents", []):
                        agent = AgentProfile(**agent_data)
                        agent.capabilities = set(agent_data.get("capabilities", []))
                        agent.state = AgentState(agent_data.get("state", "idle"))
                        self.agents[agent.agent_id] = agent
                    
                    for task_data in data.get("tasks", []):
                        task = AgentTask(**task_data)
                        task.priority = TaskPriority(task_data.get("priority", "medium"))
                        task.status = TaskStatus(task_data.get("status", "pending"))
                        self.tasks[task.id] = task
            except Exception as e:
                print(f"Error loading autonomy data: {e}")
    
    def _save_data(self):
        """Save autonomy data to persistent storage"""
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
        data = {
            "agents": [agent.to_dict() for agent in self.agents.values()],
            "tasks": [task.to_dict() for task in self.tasks.values()]
        }
        with open(self.data_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _initialize_agents(self):
        """Initialize default agent profiles"""
        if not self.agents:
            default_agents = [
                {
                    "agent_id": "agent-overlord",
                    "codename": "OVERLORD-PRIME",
                    "role": "Supreme Mission Commander",
                    "specialization": "MITRE Kill-Chain Pathfinding & LLM Swarm Orchestration",
                    "capabilities": {"orchestration", "mission_planning", "coordination", "strategy"},
                    "skills": ["kill-chain-analysis", "threat-modeling", "mission-decomposition"],
                    "state": AgentState.IDLE,
                    "workload_capacity": 10
                },
                {
                    "agent_id": "agent-spectre",
                    "codename": "SPECTRE-RECON",
                    "role": "Surface Hunter",
                    "specialization": "Surface Discovery, OSINT, Wireless, Cloud Recon",
                    "capabilities": {"reconnaissance", "osint", "scanning", "discovery"},
                    "skills": ["port-scanning", "dns-enumeration", "cloud-discovery", "wireless-auditing"],
                    "state": AgentState.IDLE,
                    "workload_capacity": 8
                },
                {
                    "agent_id": "agent-nexus",
                    "codename": "NEXUS-CYPHER",
                    "role": "Graph Engine",
                    "specialization": "Graph Topology, AD Lateral Movement, Identity",
                    "capabilities": {"graph_analysis", "topology_mapping", "lateral_movement", "identity"},
                    "skills": ["attack-graph", "bloodhound", "lateral-movement", "ad-analysis"],
                    "state": AgentState.IDLE,
                    "workload_capacity": 6
                },
                {
                    "agent_id": "agent-vortex",
                    "codename": "VORTEX-EXPLOIT",
                    "role": "Vuln Synthesizer",
                    "specialization": "Web Exploits, API Vulnerabilities, MPC Audit",
                    "capabilities": {"exploitation", "vulnerability_analysis", "web_security", "api_security"},
                    "skills": ["sql-injection", "xss", "csrf", "api-abuse", "mpc-audit"],
                    "state": AgentState.IDLE,
                    "workload_capacity": 7
                },
                {
                    "agent_id": "agent-cipher",
                    "codename": "CIPHER-MORPH",
                    "role": "Evasion Core",
                    "specialization": "Evasion, Reversing, Malware Triage, C2",
                    "capabilities": {"evasion", "reversing", "malware_analysis", "c2"},
                    "skills": ["obfuscation", "anti-debug", "malware-triage", "c2-simulation"],
                    "state": AgentState.IDLE,
                    "workload_capacity": 5
                },
                {
                    "agent_id": "agent-chrono",
                    "codename": "CHRONO-DEBRIEF",
                    "role": "Defense Architect",
                    "specialization": "DFIR, Reporting, Mitigation, Validation",
                    "capabilities": {"defense", "forensics", "reporting", "validation"},
                    "skills": ["incident-response", "forensic-analysis", "report-generation", "validation"],
                    "state": AgentState.IDLE,
                    "workload_capacity": 8
                }
            ]
            
            for agent_data in default_agents:
                agent = AgentProfile(**agent_data)
                self.agents[agent.agent_id] = agent
            
            self._save_data()
    
    def register_agent(self, agent_id: str, codename: str, role: str, 
                      specialization: str, capabilities: Set[str], skills: List[str]) -> AgentProfile:
        """Register a new agent"""
        agent = AgentProfile(
            agent_id=agent_id,
            codename=codename,
            role=role,
            specialization=specialization,
            capabilities=capabilities,
            skills=skills,
            state=AgentState.IDLE
        )
        self.agents[agent_id] = agent
        self._save_data()
        return agent
    
    def get_agent(self, agent_id: str) -> Optional[AgentProfile]:
        """Get agent by ID"""
        return self.agents.get(agent_id)
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """List all agents"""
        return [agent.to_dict() for agent in self.agents.values()]
    
    def update_agent_state(self, agent_id: str, state: AgentState, current_task_id: Optional[str] = None):
        """Update agent state"""
        agent = self.agents.get(agent_id)
        if agent:
            agent.state = state
            agent.current_task_id = current_task_id
            agent.last_active = time.time()
            self._save_data()
    
    def create_task(self, title: str, description: str, priority: TaskPriority = TaskPriority.MEDIUM,
                   skills_required: List[str] = None, dependencies: List[str] = None,
                   created_by: str = "system", deadline: Optional[float] = None) -> AgentTask:
        """Create a new task"""
        task = AgentTask(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            priority=priority,
            status=TaskStatus.PENDING,
            assigned_to="",  # Will be assigned by scheduler
            created_by=created_by,
            created_at=time.time(),
            deadline=deadline,
            skills_required=skills_required or [],
            dependencies=dependencies or []
        )
        self.tasks[task.id] = task
        self._add_to_queue(task.id)
        self._save_data()
        return task
    
    def _add_to_queue(self, task_id: str):
        """Add task to priority queue"""
        task = self.tasks.get(task_id)
        if not task:
            return
        
        # Insert based on priority
        priority_order = {TaskPriority.CRITICAL: 0, TaskPriority.HIGH: 1, 
                         TaskPriority.MEDIUM: 2, TaskPriority.LOW: 3}
        task_priority = priority_order.get(task.priority, 2)
        
        inserted = False
        for i, queued_id in enumerate(self.task_queue):
            queued_task = self.tasks.get(queued_id)
            if queued_task:
                queued_priority = priority_order.get(queued_task.priority, 2)
                if task_priority < queued_priority:
                    self.task_queue.insert(i, task_id)
                    inserted = True
                    break
        
        if not inserted:
            self.task_queue.append(task_id)
    
    def assign_task(self, task_id: str, agent_id: str) -> bool:
        """Assign task to specific agent"""
        task = self.tasks.get(task_id)
        agent = self.agents.get(agent_id)
        
        if not task or not agent:
            return False
        
        if task.status != TaskStatus.PENDING:
            return False
        
        # Check dependencies
        for dep_id in task.dependencies:
            dep_task = self.tasks.get(dep_id)
            if dep_task and dep_task.status != TaskStatus.COMPLETED:
                task.status = TaskStatus.BLOCKED
                self._save_data()
                return False
        
        task.assigned_to = agent_id
        task.status = TaskStatus.ASSIGNED
        agent.current_task_id = task_id
        agent.state = AgentState.BUSY
        
        self._save_data()
        return True
    
    def auto_assign_task(self, task_id: str) -> Optional[str]:
        """Automatically assign task to best available agent"""
        task = self.tasks.get(task_id)
        if not task or task.status != TaskStatus.PENDING:
            return None
        
        # Check dependencies
        for dep_id in task.dependencies:
            dep_task = self.tasks.get(dep_id)
            if dep_task and dep_task.status != TaskStatus.COMPLETED:
                task.status = TaskStatus.BLOCKED
                self._save_data()
                return None
        
        # Find best agent
        best_agent = None
        best_score = -1
        
        for agent in self.agents.values():
            if agent.state != AgentState.IDLE:
                continue
            
            # Calculate match score
            score = 0
            
            # Skills match
            skills_match = len(set(task.skills_required) & set(agent.skills))
            score += skills_match * 10
            
            # Capabilities match
            caps_match = len(set(task.skills_required) & agent.capabilities)
            score += caps_match * 5
            
            # Performance score
            score += agent.performance_score * 2
            
            if score > best_score:
                best_score = score
                best_agent = agent
        
        if best_agent:
            if self.assign_task(task_id, best_agent.agent_id):
                return best_agent.agent_id
        
        return None
    
    def update_task_progress(self, task_id: str, progress: float, result: Optional[Dict[str, Any]] = None):
        """Update task progress"""
        task = self.tasks.get(task_id)
        if task:
            task.progress = progress
            if result:
                task.result = result
            self._save_data()
    
    def complete_task(self, task_id: str, result: Dict[str, Any] = None) -> bool:
        """Mark task as completed"""
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        task.status = TaskStatus.COMPLETED
        task.progress = 100.0
        task.result = result or {}
        
        # Update agent stats
        agent = self.agents.get(task.assigned_to)
        if agent:
            agent.tasks_completed += 1
            agent.performance_score = min(1.0, agent.performance_score + 0.01)
            agent.current_task_id = None
            agent.state = AgentState.IDLE
        
        # Unblock dependent tasks
        for other_task in self.tasks.values():
            if task_id in other_task.dependencies and other_task.status == TaskStatus.BLOCKED:
                other_task.status = TaskStatus.PENDING
        
        self._save_data()
        return True
    
    def fail_task(self, task_id: str, error_message: str) -> bool:
        """Mark task as failed"""
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        task.status = TaskStatus.FAILED
        task.error_message = error_message
        
        # Update agent stats
        agent = self.agents.get(task.assigned_to)
        if agent:
            agent.tasks_failed += 1
            agent.performance_score = max(0.1, agent.performance_score - 0.05)
            agent.current_task_id = None
            agent.state = AgentState.IDLE
        
        self._save_data()
        return True
    
    def get_agent_tasks(self, agent_id: str) -> List[AgentTask]:
        """Get all tasks assigned to agent"""
        return [task for task in self.tasks.values() if task.assigned_to == agent_id]
    
    def get_task_queue(self) -> List[AgentTask]:
        """Get current task queue"""
        return [self.tasks.get(task_id) for task_id in self.task_queue if task_id in self.tasks]
    
    def get_agent_performance(self, agent_id: str) -> Dict[str, Any]:
        """Get agent performance metrics"""
        agent = self.agents.get(agent_id)
        if not agent:
            return {}
        
        total_tasks = agent.tasks_completed + agent.tasks_failed
        success_rate = (agent.tasks_completed / total_tasks * 100) if total_tasks > 0 else 0
        
        return {
            "agent_id": agent.agent_id,
            "codename": agent.codename,
            "performance_score": agent.performance_score,
            "tasks_completed": agent.tasks_completed,
            "tasks_failed": agent.tasks_failed,
            "success_rate": success_rate,
            "current_task": agent.current_task_id,
            "state": agent.state.value
        }


# Global Enhanced Agent Autonomy System
enhanced_autonomy = EnhancedAgentAutonomy()