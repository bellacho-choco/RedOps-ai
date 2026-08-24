"""
====================================================================
PROJECT REDOPS-AI - SELF-IMPROVEMENT ENGINE
Autonomous code modification, learning, and capability development
====================================================================
"""

import ast
import inspect
import os
import time
import uuid
import json
import subprocess
import shutil
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import hashlib


class ImprovementType(str, Enum):
    CODE_OPTIMIZATION = "code_optimization"
    BUG_FIX = "bug_fix"
    CAPABILITY_ADDITION = "capability_addition"
    PERFORMANCE_ENHANCEMENT = "performance_enhancement"
    SECURITY_HARDENING = "security_hardening"
    LEARNING_UPDATE = "learning_update"


class ImprovementStatus(str, Enum):
    PROPOSED = "proposed"
    VALIDATED = "validated"
    IMPLEMENTED = "implemented"
    TESTED = "tested"
    DEPLOYED = "deployed"
    ROLLED_BACK = "rolled_back"


@dataclass
class CodeModification:
    id: str
    file_path: str
    original_code: str
    modified_code: str
    improvement_type: ImprovementType
    reason: str
    proposed_by: str
    proposed_at: float
    status: ImprovementStatus
    validation_result: Optional[Dict[str, Any]] = None
    test_result: Optional[Dict[str, Any]] = None
    rollback_code: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "file_path": self.file_path,
            "improvement_type": self.improvement_type.value,
            "reason": self.reason,
            "proposed_by": self.proposed_by,
            "proposed_at": self.proposed_at,
            "status": self.status.value,
            "validation_result": self.validation_result,
            "test_result": self.test_result
        }


@dataclass
class LearningPattern:
    id: str
    pattern_type: str
    pattern_data: Dict[str, Any]
    frequency: int
    success_rate: float
    last_observed: float
    applicability: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "pattern_type": self.pattern_type,
            "pattern_data": self.pattern_data,
            "frequency": self.frequency,
            "success_rate": self.success_rate,
            "last_observed": self.last_observed,
            "applicability": self.applicability
        }


class SelfImprovementEngine:
    """Autonomous self-improvement engine with code modification capabilities"""
    
    def __init__(self, data_path: Optional[str] = None):
        self.data_path = data_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".redops_memory", "self_improvement.json"
        )
        
        # Code modifications
        self.modifications: Dict[str, CodeModification] = {}
        
        # Learning patterns
        self.learning_patterns: Dict[str, LearningPattern] = {}
        
        # Improvement tracking
        self.improvement_history: List[Dict[str, Any]] = []
        self.successful_improvements: int = 0
        self.failed_improvements: int = 0
        
        # Safe mode (prevent destructive changes)
        self.safe_mode = True
        self.requires_approval = True
        
        self._load_data()
    
    def _load_data(self):
        """Load self-improvement data from persistent storage"""
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, 'r') as f:
                    data = json.load(f)
                    self.improvement_history = data.get("improvement_history", [])
                    self.successful_improvements = data.get("successful_improvements", 0)
                    self.failed_improvements = data.get("failed_improvements", 0)
                    
                    for mod_data in data.get("modifications", []):
                        mod = CodeModification(**mod_data)
                        mod.improvement_type = ImprovementType(mod_data.get("improvement_type", "code_optimization"))
                        mod.status = ImprovementStatus(mod_data.get("status", "proposed"))
                        self.modifications[mod.id] = mod
                    
                    for pattern_data in data.get("learning_patterns", []):
                        pattern = LearningPattern(**pattern_data)
                        self.learning_patterns[pattern.id] = pattern
            except Exception as e:
                print(f"Error loading self-improvement data: {e}")
    
    def _save_data(self):
        """Save self-improvement data to persistent storage"""
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
        data = {
            "improvement_history": self.improvement_history,
            "successful_improvements": self.successful_improvements,
            "failed_improvements": self.failed_improvements,
            "modifications": [mod.to_dict() for mod in self.modifications.values()],
            "learning_patterns": [pattern.to_dict() for pattern in self.learning_patterns.values()]
        }
        with open(self.data_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def analyze_code_for_improvement(self, file_path: str) -> List[Dict[str, Any]]:
        """Analyze code for potential improvements"""
        if not os.path.exists(file_path):
            return []
        
        improvements = []
        
        try:
            with open(file_path, 'r') as f:
                code = f.read()
            
            # Parse code
            tree = ast.parse(code)
            
            # Analyze for common improvement patterns
            for node in ast.walk(tree):
                # Check for performance issues
                if isinstance(node, ast.For):
                    improvements.append({
                        "type": "performance",
                        "suggestion": "Consider using list comprehensions or built-in functions",
                        "line": node.lineno,
                        "confidence": 0.7
                    })
                
                # Check for security issues
                if isinstance(node, ast.Call):
                    if hasattr(node.func, 'id') and node.func.id in ['eval', 'exec']:
                        improvements.append({
                            "type": "security",
                            "suggestion": "Avoid using eval/exec for security reasons",
                            "line": node.lineno,
                            "confidence": 0.9
                        })
                
                # Check for code duplication
                if isinstance(node, ast.FunctionDef):
                    if len(node.body) > 50:
                        improvements.append({
                            "type": "refactoring",
                            "suggestion": "Consider breaking down large function",
                            "line": node.lineno,
                            "confidence": 0.6
                        })
        
        except Exception as e:
            print(f"Error analyzing code: {e}")
        
        return improvements
    
    def propose_code_modification(self, file_path: str, original_code: str, 
                                 modified_code: str, improvement_type: ImprovementType,
                                 reason: str, proposed_by: str = "self_improvement_engine") -> CodeModification:
        """Propose a code modification"""
        modification = CodeModification(
            id=str(uuid.uuid4()),
            file_path=file_path,
            original_code=original_code,
            modified_code=modified_code,
            improvement_type=improvement_type,
            reason=reason,
            proposed_by=proposed_by,
            proposed_at=time.time(),
            status=ImprovementStatus.PROPOSED,
            rollback_code=original_code
        )
        
        self.modifications[modification.id] = modification
        self._save_data()
        
        return modification
    
    def validate_modification(self, modification_id: str) -> Dict[str, Any]:
        """Validate a proposed code modification"""
        modification = self.modifications.get(modification_id)
        if not modification:
            return {"valid": False, "reason": "Modification not found"}
        
        validation_result = {
            "syntax_valid": False,
            "imports_valid": False,
            "logic_sound": False,
            "security_safe": False,
            "overall_valid": False
        }
        
        try:
            # Check syntax
            ast.parse(modification.modified_code)
            validation_result["syntax_valid"] = True
            
            # Check imports
            tree = ast.parse(modification.modified_code)
            imports_valid = True
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        try:
                            __import__(alias.name)
                        except ImportError:
                            imports_valid = False
            validation_result["imports_valid"] = imports_valid
            
            # Check for security issues
            if "eval(" not in modification.modified_code and "exec(" not in modification.modified_code:
                validation_result["security_safe"] = True
            
            # Overall validation
            validation_result["overall_valid"] = all([
                validation_result["syntax_valid"],
                validation_result["imports_valid"],
                validation_result["security_safe"]
            ])
            
            modification.status = ImprovementStatus.VALIDATED if validation_result["overall_valid"] else ImprovementStatus.PROPOSED
            modification.validation_result = validation_result
            
            self._save_data()
            
        except Exception as e:
            validation_result["error"] = str(e)
        
        return validation_result
    
    def implement_modification(self, modification_id: str, force: bool = False) -> bool:
        """Implement a validated code modification"""
        modification = self.modifications.get(modification_id)
        if not modification:
            return False
        
        if modification.status != ImprovementStatus.VALIDATED and not force:
            return False
        
        if self.requires_approval and not force:
            return False
        
        try:
            # Create backup
            backup_path = modification.file_path + ".backup"
            if os.path.exists(modification.file_path):
                shutil.copy2(modification.file_path, backup_path)
            
            # Write modified code
            with open(modification.file_path, 'w') as f:
                f.write(modification.modified_code)
            
            modification.status = ImprovementStatus.IMPLEMENTED
            self.successful_improvements += 1
            
            self.improvement_history.append({
                "id": modification.id,
                "type": modification.improvement_type.value,
                "file": modification.file_path,
                "timestamp": time.time(),
                "success": True
            })
            
            self._save_data()
            return True
            
        except Exception as e:
            print(f"Error implementing modification: {e}")
            self.failed_improvements += 1
            return False
    
    def rollback_modification(self, modification_id: str) -> bool:
        """Rollback a code modification"""
        modification = self.modifications.get(modification_id)
        if not modification:
            return False
        
        try:
            # Restore from backup
            backup_path = modification.file_path + ".backup"
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, modification.file_path)
                os.remove(backup_path)
            
            modification.status = ImprovementStatus.ROLLED_BACK
            self._save_data()
            return True
            
        except Exception as e:
            print(f"Error rolling back modification: {e}")
            return False
    
    def learn_from_pattern(self, pattern_type: str, pattern_data: Dict[str, Any], 
                          success: bool, context: Dict[str, Any]):
        """Learn from patterns to improve future decisions"""
        pattern_id = hashlib.md5(f"{pattern_type}{str(pattern_data)}".encode()).hexdigest()
        
        if pattern_id not in self.learning_patterns:
            self.learning_patterns[pattern_id] = LearningPattern(
                id=pattern_id,
                pattern_type=pattern_type,
                pattern_data=pattern_data,
                frequency=1,
                success_rate=1.0 if success else 0.0,
                last_observed=time.time(),
                applicability=[context.get("agent", "general")]
            )
        else:
            pattern = self.learning_patterns[pattern_id]
            pattern.frequency += 1
            pattern.success_rate = (pattern.success_rate * 0.9) + (1.0 if success else 0.0) * 0.1
            pattern.last_observed = time.time
            if context.get("agent") not in pattern.applicability:
                pattern.applicability.append(context.get("agent"))
        
        self._save_data()
    
    def generate_improvement_suggestion(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate improvement suggestions based on learned patterns"""
        applicable_patterns = [
            pattern for pattern in self.learning_patterns.values()
            if context.get("agent", "general") in pattern.applicability
            and pattern.success_rate > 0.7
        ]
        
        if not applicable_patterns:
            return None
        
        # Select best pattern
        best_pattern = max(applicable_patterns, key=lambda p: p.success_rate * p.frequency)
        
        return {
            "pattern_id": best_pattern.id,
            "suggestion": f"Apply learned pattern: {best_pattern.pattern_type}",
            "confidence": best_pattern.success_rate,
            "pattern_data": best_pattern.pattern_data
        }
    
    def autonomous_improvement_cycle(self) -> Dict[str, Any]:
        """Run autonomous improvement cycle"""
        results = {
            "analyzed_files": 0,
            "proposed_improvements": 0,
            "implemented_improvements": 0,
            "learned_patterns": len(self.learning_patterns)
        }
        
        # Analyze backend files for improvements
        backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
        if os.path.exists(backend_dir):
            for filename in os.listdir(backend_dir):
                if filename.endswith(".py"):
                    file_path = os.path.join(backend_dir, filename)
                    improvements = self.analyze_code_for_improvement(file_path)
                    results["analyzed_files"] += 1
                    results["proposed_improvements"] += len(improvements)
        
        # Implement valid improvements if safe mode is off
        if not self.safe_mode or not self.requires_approval:
            for mod_id, mod in self.modifications.items():
                if mod.status == ImprovementStatus.VALIDATED:
                    if self.implement_modification(mod_id, force=True):
                        results["implemented_improvements"] += 1
        
        return results
    
    def get_improvement_stats(self) -> Dict[str, Any]:
        """Get self-improvement statistics"""
        return {
            "total_modifications": len(self.modifications),
            "successful_improvements": self.successful_improvements,
            "failed_improvements": self.failed_improvements,
            "learning_patterns": len(self.learning_patterns),
            "improvement_history_size": len(self.improvement_history),
            "safe_mode": self.safe_mode,
            "requires_approval": self.requires_approval,
            "success_rate": (self.successful_improvements / (self.successful_improvements + self.failed_improvements)) 
                          if (self.successful_improvements + self.failed_improvements) > 0 else 0.0
        }
    
    def enable_autonomous_mode(self, enable: bool = True):
        """Enable or disable autonomous improvement mode"""
        self.requires_approval = not enable
        self.safe_mode = not enable
        self._save_data()


# Global Self-Improvement Engine
self_improvement_engine = SelfImprovementEngine()