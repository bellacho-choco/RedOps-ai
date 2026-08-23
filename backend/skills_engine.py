"""
====================================================================
PROJECT REDOPS-AI - SKILLS DISCOVERY & EXECUTION MATRIX
Dynamic Indexer and Execution Bridge for 316+ RedOps Security Skills
====================================================================
"""

import os
import re
from typing import Dict, List, Any, Optional


class SkillEntry:
    def __init__(self, name: str, category: str, file_path: str, description: str, tags: List[str]):
        self.name = name
        self.category = category
        self.file_path = file_path
        self.description = description
        self.tags = tags

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "path": self.file_path,
            "description": self.description,
            "tags": self.tags
        }


class RedOpsSkillEngine:
    """
    Indexes and maps all 316+ security skills in the workspace to the 6 Agent Heroes.
    """
    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = workspace_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.skills: Dict[str, SkillEntry] = {}
        self.agent_skill_mapping: Dict[str, List[str]] = {
            "OVERLORD-PRIME": [],
            "SPECTRE-RECON": [],
            "NEXUS-CYPHER": [],
            "VORTEX-EXPLOIT": [],
            "CIPHER-MORPH": [],
            "CHRONO-DEBRIEF": []
        }
        self.index_all_skills()

    def index_all_skills(self):
        """
        Recursively scans `skills/` and `.agents/skills/` to index all SKILL.md playbooks.
        """
        search_dirs = [
            os.path.join(self.workspace_root, "skills"),
            os.path.join(self.workspace_root, ".agents", "skills")
        ]

        for base_dir in search_dirs:
            if not os.path.exists(base_dir):
                continue

            for root, _, files in os.walk(base_dir):
                for file in files:
                    if file.lower() == "skill.md":
                        full_path = os.path.join(root, file)
                        self._parse_and_register_skill(full_path)

        self._assign_skills_to_agents()

    def _parse_and_register_skill(self, file_path: str):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            rel_path = os.path.relpath(file_path, self.workspace_root)
            parts = rel_path.replace("\\", "/").split("/")

            # Determine category and name
            category = parts[1] if len(parts) > 1 else "general"
            if category == "standard" and len(parts) > 2:
                category = parts[2]
            
            # Default name from folder or frontmatter
            folder_name = os.path.basename(os.path.dirname(file_path))
            skill_name = folder_name if folder_name != "skills" else category

            description = "Security skill playbook"
            tags = [category]

            # Parse YAML frontmatter if present
            if content.startswith("---"):
                fm_match = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
                if fm_match:
                    fm_text = fm_match.group(1)
                    name_match = re.search(r"name:\s*(.+)", fm_text)
                    if name_match:
                        skill_name = name_match.group(1).strip()
                    desc_match = re.search(r"description:\s*[\"']?(.*?)[\"']?$", fm_text, re.MULTILINE)
                    if desc_match:
                        description = desc_match.group(1).strip()
                    tags_match = re.search(r"tags:\s*(.+)", fm_text)
                    if tags_match:
                        tags.extend([t.strip() for t in tags_match.group(1).split(",")])

            entry = SkillEntry(
                name=skill_name,
                category=category,
                file_path=rel_path,
                description=description,
                tags=list(set(tags))
            )
            self.skills[skill_name.lower()] = entry

        except Exception as e:
            pass

    def _assign_skills_to_agents(self):
        """
        Maps indexed skills to each hero's domain specialization.
        """
        for name, skill in self.skills.items():
            cat = skill.category.lower()
            
            # 1. OVERLORD-PRIME: Orchestration, RoE, CONOPS, Threat Profiles
            if cat in ["soundwave", "decepticon", "orchestration"] or "opplan" in name:
                self.agent_skill_mapping["OVERLORD-PRIME"].append(skill.name)

            # 2. SPECTRE-RECON: Surface discovery, OSINT, Recon, Wireless, Cloud, IoT
            elif cat in ["recon", "osint", "wireless", "iot", "cloud", "scanner"]:
                self.agent_skill_mapping["SPECTRE-RECON"].append(skill.name)

            # 3. NEXUS-CYPHER: Graph topology, AD, lateral movement, identity
            elif cat in ["ad", "lateral-movement"] or "graph" in name or "mitre" in name:
                self.agent_skill_mapping["NEXUS-CYPHER"].append(skill.name)

            # 4. VORTEX-EXPLOIT: Web exploits, API, Contracts, MPC, Vulnresearch, Detector
            elif cat in ["exploit", "analyst", "contracts", "detector", "vulnresearch", "web", "api", "ics"]:
                self.agent_skill_mapping["VORTEX-EXPLOIT"].append(skill.name)

            # 5. CIPHER-MORPH: Evasion, Reversing, Malware triage, C2, Phisher, LLM-Redteam
            elif cat in ["reverser", "c2", "post-exploit", "phisher", "llm-redteam", "mobile"]:
                self.agent_skill_mapping["CIPHER-MORPH"].append(skill.name)

            # 6. CHRONO-DEBRIEF: DFIR, Reporting, Mitigation, Patching
            elif cat in ["dfir", "reporting", "patcher", "verifier"] or "report" in name or "cleanup" in name:
                self.agent_skill_mapping["CHRONO-DEBRIEF"].append(skill.name)

            else:
                # Default fallback assignment based on tags
                self.agent_skill_mapping["VORTEX-EXPLOIT"].append(skill.name)

    def search_skills(self, query: str, limit: int = 15) -> List[Dict[str, Any]]:
        q = query.lower()
        results = []
        for name, skill in self.skills.items():
            if q in name or q in skill.description.lower() or any(q in t.lower() for t in skill.tags):
                results.append(skill.to_dict())
                if len(results) >= limit:
                    break
        return results

    def get_skills_for_agent(self, agent_name: str) -> List[str]:
        return self.agent_skill_mapping.get(agent_name.upper(), [])

    def read_skill_content(self, skill_name: str) -> Optional[str]:
        skill = self.skills.get(skill_name.lower())
        if not skill:
            # Try fuzzy search
            for k, v in self.skills.items():
                if skill_name.lower() in k:
                    skill = v
                    break
        if not skill:
            return None

        full_path = os.path.join(self.workspace_root, skill.file_path)
        if os.path.exists(full_path):
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        return None

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_skills": len(self.skills),
            "agent_distribution": {
                agent: len(skill_list)
                for agent, skill_list in self.agent_skill_mapping.items()
            }
        }


# Global Skills Engine Instance
skills_engine = RedOpsSkillEngine()
