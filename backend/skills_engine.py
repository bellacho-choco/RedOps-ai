"""
====================================================================
PROJECT REDOPS-AI - SKILLS DISCOVERY & EXECUTION MATRIX
Dynamic Indexer and Execution Bridge for 316+ RedOps Security Skills
====================================================================
"""

import os
import re
from typing import Dict, List, Any, Optional

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    yaml = None
    _HAS_YAML = False


class SkillEntry:
    def __init__(self, name: str, category: str, file_path: str, description: str,
                 tags: List[str], mitre_attack: Optional[List[str]] = None,
                 has_frontmatter: bool = True):
        self.name = name
        self.category = category
        self.file_path = file_path
        self.description = description
        self.tags = tags
        self.mitre_attack = mitre_attack or []
        self.has_frontmatter = has_frontmatter

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "path": self.file_path,
            "description": self.description,
            "tags": self.tags,
            "mitre_attack": self.mitre_attack
        }


class RedOpsSkillEngine:
    """
    Indexes and maps all 316+ security skills in the workspace to the 6 Agent Heroes.
    """
    GROUPING_DIRS = {"standard", "plugins", "shared"}

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = workspace_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Keyed by unique relative path; name_index maps display name -> registry key
        self.skills: Dict[str, SkillEntry] = {}
        self.name_index: Dict[str, str] = {}
        self.mitre_index: Dict[str, List[str]] = {}
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

            for root, dirs, files in os.walk(base_dir):
                # Synthesized drafts stay out of the live index until a
                # human approves them (controlled self-improvement gate).
                dirs[:] = [d for d in dirs if d != "staging"]
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

            # Strip the leading root ('skills/...' or '.agents/skills/...'),
            # then unwrap grouping dirs (standard/plugins/shared) so the
            # category is the actual skill domain (e.g. 'verifier', 'ad').
            if parts[0] == ".agents":
                parts = parts[2:]
            else:
                parts = parts[1:]
            parts = [p for p in parts if p]
            if parts and parts[0] in self.GROUPING_DIRS and len(parts) > 2:
                category = parts[1]
            elif parts:
                category = parts[0]
            else:
                category = "general"

            # Default name from folder or frontmatter
            folder_name = os.path.basename(os.path.dirname(file_path))
            skill_name = folder_name if folder_name != "skills" else category

            description = "Security skill playbook"
            tags = [category]

            # Parse YAML frontmatter (PyYAML for nested structures,
            # regex fallback when PyYAML unavailable or frontmatter invalid)
            mitre_attack: List[str] = []
            has_frontmatter = False
            if content.startswith("---"):
                fm_match = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
                if fm_match:
                    has_frontmatter = True
                    fm_text = fm_match.group(1)
                    parsed = self._parse_yaml_frontmatter(fm_text)
                    if parsed:
                        skill_name = str(parsed.get("name") or skill_name).strip()
                        description = str(parsed.get("description") or description).strip()
                        parsed_tags = self._extract_nested_tags(parsed)
                        tags.extend(parsed_tags)
                        mitre_attack = self._extract_mitre(parsed)
                    else:
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
                tags=list(set(tags)),
                mitre_attack=mitre_attack,
                has_frontmatter=has_frontmatter
            )
            key = rel_path.replace("\\", "/").lower()
            self.skills[key] = entry
            for tid in mitre_attack:
                self.mitre_index.setdefault(tid, []).append(key)
            # First registration wins for name lookup; duplicates stay
            # reachable via their unique path key.
            self.name_index.setdefault(skill_name.lower(), key)

        except Exception as e:
            pass

    # ---- Frontmatter helpers (Step 12 hardening) ---------------------
    @staticmethod
    def _parse_yaml_frontmatter(fm_text: str) -> Optional[Dict[str, Any]]:
        if not _HAS_YAML:
            return None
        try:
            data = yaml.safe_load(fm_text)
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    @staticmethod
    def _extract_nested_tags(parsed: Dict[str, Any]) -> List[str]:
        """Flatten tags from top-level and nested metadata.tags (str or list)."""
        found: List[str] = []

        def _collect(value):
            if isinstance(value, str):
                found.extend(t.strip() for t in value.split(",") if t.strip())
            elif isinstance(value, (list, tuple)):
                for v in value:
                    _collect(v)

        _collect(parsed.get("tags"))
        metadata = parsed.get("metadata")
        if isinstance(metadata, dict):
            _collect(metadata.get("tags"))
        return found

    @staticmethod
    def _extract_mitre(parsed: Dict[str, Any]) -> List[str]:
        """MITRE ATT&CK technique IDs from mitre_attack (str or list)."""
        raw = parsed.get("mitre_attack") or parsed.get("mitre")
        if isinstance(raw, str):
            raw = [raw]
        if not isinstance(raw, list):
            return []
        return [str(t).strip().upper() for t in raw if str(t).strip()]

    def lookup_mitre(self, technique_id: str) -> List[Dict[str, Any]]:
        """Skills mapped to a MITRE ATT&CK technique (e.g. 'T1190')."""
        keys = self.mitre_index.get(technique_id.strip().upper(), [])
        return [self.skills[k].to_dict() for k in keys]

    def audit(self) -> Dict[str, Any]:
        """Production-grade index audit: per-agent counts, data gaps, dupes."""
        per_agent = {a: len(v) for a, v in self.agent_skill_mapping.items()}
        missing_tags = [e.file_path for e in self.skills.values() if len(e.tags) <= 1]
        missing_frontmatter = [e.file_path for e in self.skills.values()
                               if not e.has_frontmatter]
        name_counts: Dict[str, int] = {}
        for e in self.skills.values():
            name_counts[e.name.lower()] = name_counts.get(e.name.lower(), 0) + 1
        duplicates = sorted(n for n, c in name_counts.items() if c > 1)
        return {
            "total_skills": len(self.skills),
            "per_agent": per_agent,
            "mitre_techniques_indexed": len(self.mitre_index),
            "missing_tags": missing_tags,
            "missing_frontmatter": missing_frontmatter,
            "duplicate_names": duplicates,
            "yaml_parser": "pyyaml" if _HAS_YAML else "regex-fallback",
        }

    def load_bundle(self, bundle_path: str) -> Dict[str, Any]:
        """
        Declarative plugin-bundle loader (PLAN Step 11): a bundle is a
        directory containing a `bundle.json` manifest plus one or more
        SKILL.md playbooks. Registered into the live index without restart.
        """
        import json as _json
        manifest_path = os.path.join(bundle_path, "bundle.json")
        if not os.path.isdir(bundle_path):
            return {"status": "NOT_FOUND", "path": bundle_path}
        manifest: Dict[str, Any] = {"name": os.path.basename(bundle_path)}
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest.update(_json.load(f))
            except Exception:
                return {"status": "BAD_MANIFEST", "path": manifest_path}
        before = len(self.skills)
        for root, _, files in os.walk(bundle_path):
            for file in files:
                if file.lower() == "skill.md":
                    self._parse_and_register_skill(os.path.join(root, file))
        loaded = len(self.skills) - before
        self._assign_skills_to_agents()
        return {"status": "LOADED", "bundle": manifest.get("name"),
                "skills_loaded": loaded, "total_skills": len(self.skills)}

    def _assign_skills_to_agents(self):
        """
        Maps indexed skills to each hero's domain specialization.
        """
        for skill in self.skills.values():
            name = skill.name.lower()
            cat = skill.category.lower()

            # 1. OVERLORD-PRIME: Orchestration, RoE, CONOPS, Threat Profiles
            if cat in ["soundwave", "adversary", "orchestration", "benchmark"] or "opplan" in name:
                self.agent_skill_mapping["OVERLORD-PRIME"].append(skill.name)

            # 2. SPECTRE-RECON: Surface discovery, OSINT, Recon, Wireless, Cloud, IoT
            elif cat in ["recon", "osint", "wireless", "iot", "cloud", "scanner"]:
                self.agent_skill_mapping["SPECTRE-RECON"].append(skill.name)

            # 3. NEXUS-CYPHER: Graph topology, AD, lateral movement, identity
            elif cat in ["ad", "lateral-movement"] or "graph" in name or "mitre" in name:
                self.agent_skill_mapping["NEXUS-CYPHER"].append(skill.name)

            # 4. VORTEX-EXPLOIT: Web exploits, API, Contracts, MPC, Vulnresearch, Detector
            elif cat in ["exploit", "analyst", "contracts", "detector", "vulnresearch",
                         "exploiter", "web", "api", "ics", "mpc-cryptography-audit"]:
                self.agent_skill_mapping["VORTEX-EXPLOIT"].append(skill.name)

            # 5. CIPHER-MORPH: Evasion, Reversing, Malware triage, C2, Phisher, LLM-Redteam
            elif cat in ["reverser", "c2", "post-exploit", "phisher", "llm-redteam",
                         "mobile", "opsec", "stealth-infra", "defense-evasion",
                         "adversary-emulation"]:
                self.agent_skill_mapping["CIPHER-MORPH"].append(skill.name)

            # 6. CHRONO-DEBRIEF: DFIR, Reporting, Mitigation, Patching, Validation
            elif cat in ["dfir", "reporting", "patcher", "verifier", "finding-protocol",
                         "references"] or "report" in name or "cleanup" in name:
                self.agent_skill_mapping["CHRONO-DEBRIEF"].append(skill.name)

            else:
                # Default fallback assignment based on tags
                self.agent_skill_mapping["VORTEX-EXPLOIT"].append(skill.name)

    def search_skills(self, query: str, limit: int = 15) -> List[Dict[str, Any]]:
        q = query.lower()
        results = []
        for skill in self.skills.values():
            if q in skill.name.lower() or q in skill.description.lower() or any(q in t.lower() for t in skill.tags):
                results.append(skill.to_dict())
                if len(results) >= limit:
                    break
        return results

    def get_skills_for_agent(self, agent_name: str) -> List[str]:
        return self.agent_skill_mapping.get(agent_name.upper(), [])

    def read_skill_content(self, skill_name: str) -> Optional[str]:
        key = self.name_index.get(skill_name.lower())
        skill = self.skills.get(key) if key else None
        if not skill:
            # Try fuzzy search on names, then on path keys
            q = skill_name.lower()
            for name, k in self.name_index.items():
                if q in name:
                    skill = self.skills[k]
                    break
            else:
                for k, v in self.skills.items():
                    if q in k:
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
