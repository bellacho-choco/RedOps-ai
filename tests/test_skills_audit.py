"""PLAN Step 12: skills audit — PyYAML parser, nested tags, MITRE index."""
from backend.skills_engine import RedOpsSkillEngine, skills_engine


def _write_skill(d, name, frontmatter):
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(frontmatter + "\n# Body\n")


class TestYamlFrontmatter:
    def test_nested_tags_and_mitre_extracted(self, tmp_path):
        root = tmp_path / "ws"
        skills_dir = root / "skills" / "standard" / "exploit" / "demo"
        _write_skill(skills_dir, "demo", """---
name: demo-skill
description: test skill
metadata:
  tags:
    - web
    - sql
mitre_attack:
  - t1190
  - T1059
---""")
        eng = RedOpsSkillEngine(workspace_root=str(root))
        entry = list(eng.skills.values())[0]
        assert entry.name == "demo-skill"
        assert "web" in entry.tags and "sql" in entry.tags
        assert entry.mitre_attack == ["T1190", "T1059"]
        assert "T1190" in eng.mitre_index

    def test_mitre_lookup(self, tmp_path):
        root = tmp_path / "ws"
        _write_skill(root / "skills" / "standard" / "x" / "a", "a",
                     "---\nname: a\nmitre_attack: T1190\n---")
        eng = RedOpsSkillEngine(workspace_root=str(root))
        assert len(eng.lookup_mitre("t1190")) == 1

    def test_invalid_yaml_falls_back_to_regex(self, tmp_path):
        root = tmp_path / "ws"
        _write_skill(root / "skills" / "standard" / "x" / "b", "b",
                     "---\nname: broken\n  bad: [unclosed\n---")
        eng = RedOpsSkillEngine(workspace_root=str(root))
        entry = list(eng.skills.values())[0]
        assert entry.name == "broken"  # regex fallback picked the name

    def test_no_frontmatter_flagged(self, tmp_path):
        root = tmp_path / "ws"
        d = root / "skills" / "standard" / "x" / "c"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("# no frontmatter\n")
        eng = RedOpsSkillEngine(workspace_root=str(root))
        entry = list(eng.skills.values())[0]
        assert entry.has_frontmatter is False
        assert entry.file_path in eng.audit()["missing_frontmatter"]


class TestLiveIndexAudit:
    def test_full_index_valid(self):
        report = skills_engine.audit()
        assert report["total_skills"] >= 300
        assert report["yaml_parser"] in ("pyyaml", "regex-fallback")
        assert set(report["per_agent"].keys()) == {
            "OVERLORD-PRIME", "SPECTRE-RECON", "NEXUS-CYPHER",
            "VORTEX-EXPLOIT", "CIPHER-MORPH", "CHRONO-DEBRIEF"}

    def test_every_skill_has_name_and_category(self):
        for entry in skills_engine.skills.values():
            assert entry.name and entry.category
