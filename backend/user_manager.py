"""
====================================================================
PROJECT REDOPS-AI - USER MANAGEMENT SYSTEM
Complete user accounts, roles, permissions, and authentication
====================================================================
"""

import hashlib
import secrets
import time
import uuid
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import json
import os


class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    ANALYST = "analyst"
    VIEWER = "viewer"


class Permission(str, Enum):
    # Mission Permissions
    MISSION_CREATE = "mission_create"
    MISSION_READ = "mission_read"
    MISSION_UPDATE = "mission_update"
    MISSION_DELETE = "mission_delete"
    MISSION_EXECUTE = "mission_execute"
    
    # Agent Permissions
    AGENT_CONTROL = "agent_control"
    AGENT_CONFIGURE = "agent_configure"
    AGENT_VIEW = "agent_view"
    
    # Skills Permissions
    SKILLS_READ = "skills_read"
    SKILLS_WRITE = "skills_write"
    SKILLS_EXECUTE = "skills_execute"
    
    # System Permissions
    SYSTEM_CONFIG = "system_config"
    USER_MANAGE = "user_manage"
    REPORTS_VIEW = "reports_view"
    REPORTS_EXPORT = "reports_export"
    
    # Collaboration Permissions
    WORKSPACE_CREATE = "workspace_create"
    WORKSPACE_JOIN = "workspace_join"
    WORKSPACE_MANAGE = "workspace_manage"
    COMMENT_WRITE = "comment_write"
    COMMENT_READ = "comment_read"


# Role-Permission Mapping
ROLE_PERMISSIONS = {
    UserRole.ADMIN: {
        Permission.MISSION_CREATE, Permission.MISSION_READ, Permission.MISSION_UPDATE, 
        Permission.MISSION_DELETE, Permission.MISSION_EXECUTE,
        Permission.AGENT_CONTROL, Permission.AGENT_CONFIGURE, Permission.AGENT_VIEW,
        Permission.SKILLS_READ, Permission.SKILLS_WRITE, Permission.SKILLS_EXECUTE,
        Permission.SYSTEM_CONFIG, Permission.USER_MANAGE,
        Permission.REPORTS_VIEW, Permission.REPORTS_EXPORT,
        Permission.WORKSPACE_CREATE, Permission.WORKSPACE_JOIN, Permission.WORKSPACE_MANAGE,
        Permission.COMMENT_WRITE, Permission.COMMENT_READ
    },
    UserRole.OPERATOR: {
        Permission.MISSION_CREATE, Permission.MISSION_READ, Permission.MISSION_UPDATE,
        Permission.MISSION_EXECUTE,
        Permission.AGENT_CONTROL, Permission.AGENT_VIEW,
        Permission.SKILLS_READ, Permission.SKILLS_EXECUTE,
        Permission.REPORTS_VIEW, Permission.REPORTS_EXPORT,
        Permission.WORKSPACE_CREATE, Permission.WORKSPACE_JOIN,
        Permission.COMMENT_WRITE, Permission.COMMENT_READ
    },
    UserRole.ANALYST: {
        Permission.MISSION_READ,
        Permission.AGENT_VIEW,
        Permission.SKILLS_READ,
        Permission.REPORTS_VIEW,
        Permission.WORKSPACE_JOIN,
        Permission.COMMENT_READ
    },
    UserRole.VIEWER: {
        Permission.MISSION_READ,
        Permission.AGENT_VIEW,
        Permission.SKILLS_READ,
        Permission.REPORTS_VIEW,
        Permission.WORKSPACE_JOIN,
        Permission.COMMENT_READ
    }
}


@dataclass
class User:
    id: str
    username: str
    email: str
    password_hash: str
    role: UserRole
    full_name: str
    created_at: float
    last_login: Optional[float] = None
    is_active: bool = True
    permissions: Set[Permission] = field(default_factory=set)
    avatar_url: Optional[str] = None
    preferences: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        # Set permissions based on role
        self.permissions = ROLE_PERMISSIONS.get(self.role, set())
    
    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        data = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role.value,
            "full_name": self.full_name,
            "created_at": self.created_at,
            "last_login": self.last_login,
            "is_active": self.is_active,
            "permissions": [p.value for p in self.permissions],
            "avatar_url": self.avatar_url,
            "preferences": self.preferences
        }
        if include_sensitive:
            data["password_hash"] = self.password_hash
        return data


@dataclass
class Session:
    session_id: str
    user_id: str
    created_at: float
    expires_at: float
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_valid: bool = True
    
    def is_expired(self) -> bool:
        return time.time() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "is_valid": self.is_valid
        }


class UserManager:
    """Complete user management system with authentication and authorization"""
    
    def __init__(self, data_path: Optional[str] = None):
        self.data_path = data_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".redops_memory", "users.json"
        )
        self.users: Dict[str, User] = {}
        self.sessions: Dict[str, Session] = {}
        self._load_data()
    
    def _load_data(self):
        """Load users from persistent storage"""
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, 'r') as f:
                    data = json.load(f)
                    for user_data in data.get("users", []):
                        user = User(**user_data)
                        user.permissions = {Permission(p) for p in user_data.get("permissions", [])}
                        self.users[user.id] = user
            except Exception as e:
                print(f"Error loading user data: {e}")
        
        # Create default admin user if no users exist
        if not self.users:
            self.create_default_admin()
    
    def _save_data(self):
        """Save users to persistent storage"""
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
        data = {
            "users": [user.to_dict(include_sensitive=True) for user in self.users.values()]
        }
        with open(self.data_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def create_default_admin(self):
        """Create default admin user"""
        admin = User(
            id=str(uuid.uuid4()),
            username="admin",
            email="admin@redops.local",
            password_hash=self._hash_password("admin123"),  # Default password
            role=UserRole.ADMIN,
            full_name="System Administrator",
            created_at=time.time()
        )
        self.users[admin.id] = admin
        self._save_data()
        print("Default admin user created (username: admin, password: admin123)")
    
    def _hash_password(self, password: str) -> str:
        """Hash password using SHA-256 with salt"""
        salt = secrets.token_hex(16)
        return f"{salt}${hashlib.sha256(f"{salt}{password}".encode()).hexdigest()}"
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        salt, hash_value = password_hash.split('$')
        computed_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return secrets.compare_digest(computed_hash, hash_value)
    
    def create_user(self, username: str, email: str, password: str, 
                    full_name: str, role: UserRole = UserRole.ANALYST) -> User:
        """Create a new user"""
        if self.get_user_by_username(username):
            raise ValueError(f"Username '{username}' already exists")
        
        if self.get_user_by_email(email):
            raise ValueError(f"Email '{email}' already exists")
        
        user = User(
            id=str(uuid.uuid4()),
            username=username,
            email=email,
            password_hash=self._hash_password(password),
            role=role,
            full_name=full_name,
            created_at=time.time()
        )
        
        self.users[user.id] = user
        self._save_data()
        return user
    
    def authenticate(self, username: str, password: str) -> Optional[Session]:
        """Authenticate user and create session"""
        user = self.get_user_by_username(username)
        if not user:
            return None
        
        if not self._verify_password(password, user.password_hash):
            return None
        
        if not user.is_active:
            return None
        
        # Create session
        session = Session(
            session_id=str(uuid.uuid4()),
            user_id=user.id,
            created_at=time.time(),
            expires_at=time.time() + (24 * 60 * 60)  # 24 hour session
        )
        
        self.sessions[session.session_id] = session
        user.last_login = time.time()
        self._save_data()
        
        return session
    
    def validate_session(self, session_id: str) -> Optional[User]:
        """Validate session and return user"""
        session = self.sessions.get(session_id)
        if not session or not session.is_valid or session.is_expired():
            return None
        
        user = self.users.get(session.user_id)
        if not user or not user.is_active:
            return None
        
        return user
    
    def logout(self, session_id: str):
        """Logout user by invalidating session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        return self.users.get(user_id)
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        for user in self.users.values():
            if user.username == username:
                return user
        return None
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        for user in self.users.values():
            if user.email == email:
                return user
        return None
    
    def list_users(self) -> List[Dict[str, Any]]:
        """List all users (for admin)"""
        return [user.to_dict() for user in self.users.values()]
    
    def update_user(self, user_id: str, **updates) -> Optional[User]:
        """Update user information"""
        user = self.users.get(user_id)
        if not user:
            return None
        
        for key, value in updates.items():
            if key == "password":
                user.password_hash = self._hash_password(value)
            elif key == "role":
                user.role = UserRole(value)
                user.permissions = ROLE_PERMISSIONS.get(user.role, set())
            elif hasattr(user, key):
                setattr(user, key, value)
        
        self._save_data()
        return user
    
    def delete_user(self, user_id: str) -> bool:
        """Delete user"""
        if user_id in self.users:
            del self.users[user_id]
            # Invalidate all sessions for this user
            self.sessions = {sid: sess for sid, sess in self.sessions.items() 
                           if sess.user_id != user_id}
            self._save_data()
            return True
        return False
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        current_time = time.time()
        expired = [sid for sid, sess in self.sessions.items() 
                   if sess.is_expired() or not sess.is_valid]
        for sid in expired:
            del self.sessions[sid]
        return len(expired)


# Global User Manager
user_manager = UserManager()