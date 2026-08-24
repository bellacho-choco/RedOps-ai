"""
====================================================================
PROJECT REDOPS-AI - TEAM COLLABORATION SYSTEM
Multi-user workspaces, real-time collaboration, and team features
====================================================================
"""

import time
import uuid
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import json
import os
from datetime import datetime


class WorkspaceRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class CommentType(str, Enum):
    GENERAL = "general"
    TASK = "task"
    BUG = "bug"
    QUESTION = "question"
    ANNOUNCEMENT = "announcement"


@dataclass
class WorkspaceMember:
    user_id: str
    role: WorkspaceRole
    joined_at: float
    permissions: Set[str] = field(default_factory=set)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "role": self.role.value,
            "joined_at": self.joined_at,
            "permissions": list(self.permissions)
        }


@dataclass
class Comment:
    id: str
    user_id: str
    content: str
    comment_type: CommentType
    created_at: float
    updated_at: float
    parent_id: Optional[str] = None
    mentions: List[str] = field(default_factory=list)
    reactions: Dict[str, List[str]] = field(default_factory=dict)  # emoji -> user_ids
    task_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "content": self.content,
            "comment_type": self.comment_type.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "parent_id": self.parent_id,
            "mentions": self.mentions,
            "reactions": self.reactions,
            "task_id": self.task_id
        }


@dataclass
class Task:
    id: str
    title: str
    description: str
    status: str  # TODO, IN_PROGRESS, REVIEW, DONE
    priority: str  # LOW, MEDIUM, HIGH, CRITICAL
    created_by: str
    created_at: float
    assigned_to: Optional[str] = None
    due_date: Optional[float] = None
    tags: List[str] = field(default_factory=list)
    related_mission: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "assigned_to": self.assigned_to,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "due_date": self.due_date,
            "tags": self.tags,
            "related_mission": self.related_mission
        }


@dataclass
class Workspace:
    id: str
    name: str
    description: str
    created_by: str
    created_at: float
    members: Dict[str, WorkspaceMember] = field(default_factory=dict)
    tasks: Dict[str, Task] = field(default_factory=dict)
    comments: Dict[str, Comment] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "members": {k: v.to_dict() for k, v in self.members.items()},
            "tasks": {k: v.to_dict() for k, v in self.tasks.items()},
            "comments": {k: v.to_dict() for k, v in self.comments.items()},
            "settings": self.settings,
            "is_active": self.is_active
        }


class TeamCollaborationSystem:
    """Complete team collaboration system with workspaces and real-time features"""
    
    def __init__(self, data_path: Optional[str] = None):
        self.data_path = data_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".redops_memory", "workspaces.json"
        )
        self.workspaces: Dict[str, Workspace] = {}
        self._load_data()
    
    def _load_data(self):
        """Load workspaces from persistent storage"""
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, 'r') as f:
                    data = json.load(f)
                    for ws_data in data.get("workspaces", []):
                        workspace = Workspace(**ws_data)
                        self.workspaces[workspace.id] = workspace
            except Exception as e:
                print(f"Error loading workspace data: {e}")
    
    def _save_data(self):
        """Save workspaces to persistent storage"""
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
        data = {
            "workspaces": [ws.to_dict() for ws in self.workspaces.values()]
        }
        with open(self.data_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def create_workspace(self, name: str, description: str, created_by: str) -> Workspace:
        """Create a new team workspace"""
        workspace = Workspace(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            created_by=created_by,
            created_at=time.time()
        )
        
        # Add creator as owner
        workspace.members[created_by] = WorkspaceMember(
            user_id=created_by,
            role=WorkspaceRole.OWNER,
            joined_at=time.time(),
            permissions={"workspace_manage", "member_manage", "task_create", "task_delete"}
        )
        
        self.workspaces[workspace.id] = workspace
        self._save_data()
        return workspace
    
    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """Get workspace by ID"""
        return self.workspaces.get(workspace_id)
    
    def list_workspaces(self, user_id: str) -> List[Dict[str, Any]]:
        """List workspaces accessible to user"""
        accessible = []
        for ws in self.workspaces.values():
            if user_id in ws.members or ws.is_active:
                accessible.append(ws.to_dict())
        return accessible
    
    def add_member(self, workspace_id: str, user_id: str, role: WorkspaceRole = WorkspaceRole.MEMBER) -> bool:
        """Add member to workspace"""
        workspace = self.workspaces.get(workspace_id)
        if not workspace:
            return False
        
        if user_id in workspace.members:
            return False
        
        permissions = {"task_create", "comment_write"} if role != WorkspaceRole.VIEWER else set()
        
        workspace.members[user_id] = WorkspaceMember(
            user_id=user_id,
            role=role,
            joined_at=time.time(),
            permissions=permissions
        )
        
        self._save_data()
        return True
    
    def remove_member(self, workspace_id: str, user_id: str) -> bool:
        """Remove member from workspace"""
        workspace = self.workspaces.get(workspace_id)
        if not workspace:
            return False
        
        if user_id not in workspace.members:
            return False
        
        # Cannot remove owner
        if workspace.members[user_id].role == WorkspaceRole.OWNER:
            return False
        
        del workspace.members[user_id]
        self._save_data()
        return True
    
    def create_task(self, workspace_id: str, title: str, description: str, 
                   created_by: str, priority: str = "MEDIUM", assigned_to: Optional[str] = None) -> Task:
        """Create a task in workspace"""
        workspace = self.workspaces.get(workspace_id)
        if not workspace:
            raise ValueError("Workspace not found")
        
        if created_by not in workspace.members:
            raise ValueError("User not a member of workspace")
        
        task = Task(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            status="TODO",
            priority=priority,
            assigned_to=assigned_to,
            created_by=created_by,
            created_at=time.time()
        )
        
        workspace.tasks[task.id] = task
        self._save_data()
        return task
    
    def update_task(self, workspace_id: str, task_id: str, **updates) -> Optional[Task]:
        """Update task"""
        workspace = self.workspaces.get(workspace_id)
        if not workspace:
            return None
        
        task = workspace.tasks.get(task_id)
        if not task:
            return None
        
        for key, value in updates.items():
            if hasattr(task, key):
                setattr(task, key, value)
        
        self._save_data()
        return task
    
    def add_comment(self, workspace_id: str, user_id: str, content: str, 
                  comment_type: CommentType = CommentType.GENERAL, 
                  parent_id: Optional[str] = None, task_id: Optional[str] = None) -> Comment:
        """Add comment to workspace"""
        workspace = self.workspaces.get(workspace_id)
        if not workspace:
            raise ValueError("Workspace not found")
        
        if user_id not in workspace.members:
            raise ValueError("User not a member of workspace")
        
        # Extract mentions from content
        mentions = []
        for member_id in workspace.members.keys():
            if f"@{member_id}" in content:
                mentions.append(member_id)
        
        comment = Comment(
            id=str(uuid.uuid4()),
            user_id=user_id,
            content=content,
            comment_type=comment_type,
            created_at=time.time(),
            updated_at=time.time(),
            parent_id=parent_id,
            mentions=mentions,
            task_id=task_id
        )
        
        workspace.comments[comment.id] = comment
        self._save_data()
        return comment
    
    def get_comments(self, workspace_id: str, task_id: Optional[str] = None) -> List[Comment]:
        """Get comments from workspace"""
        workspace = self.workspaces.get(workspace_id)
        if not workspace:
            return []
        
        if task_id:
            return [c for c in workspace.comments.values() if c.task_id == task_id]
        
        return list(workspace.comments.values())
    
    def get_activity_feed(self, workspace_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get activity feed for workspace"""
        workspace = self.workspaces.get(workspace_id)
        if not workspace:
            return []
        
        activities = []
        
        # Task activities
        for task in workspace.tasks.values():
            activities.append({
                "type": "task_created",
                "timestamp": task.created_at,
                "user_id": task.created_by,
                "task_id": task.id,
                "title": task.title,
                "priority": task.priority
            })
        
        # Comment activities
        for comment in workspace.comments.values():
            activities.append({
                "type": "comment_added",
                "timestamp": comment.created_at,
                "user_id": comment.user_id,
                "comment_id": comment.id,
                "comment_type": comment.comment_type.value,
                "content": comment.content[:100]
            })
        
        # Member activities
        for member in workspace.members.values():
            activities.append({
                "type": "member_joined",
                "timestamp": member.joined_at,
                "user_id": member.user_id,
                "role": member.role.value
            })
        
        # Sort by timestamp and limit
        activities.sort(key=lambda x: x["timestamp"], reverse=True)
        return activities[:limit]


# Global Team Collaboration System
team_collaboration = TeamCollaborationSystem()