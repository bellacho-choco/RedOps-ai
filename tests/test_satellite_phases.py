"""
REDOPS-OMEGA satellite-phase tests: plugin marketplace, GSI scoring,
deployment wizard, scrub naming.
"""

from backend.plugin_market import PluginMarketplace, PluginBundle
from backend.gsi_engine import GSIEngine
from backend.gsi_engine import _grade
from backend.deployment_wizard import DeploymentWizard


def test_plugin_publish_install_and_dup_block():
    mp = PluginMarketplace()
    assert mp.publish(PluginBundle(name="vault", trust="CORE"))["status"] == "PUBLISHED"
    assert mp.publish(PluginBundle(name="vault", trust="CORE"))["status"] == "DUPLICATE"
    assert mp.install("vault")["status"] == "INSTALLED"


def test_plugin_missing_deps_blocked_untrusted():
    mp = PluginMarketplace()
    mp.publish(PluginBundle(name="anthro", depends=["skill_a"]))
    assert mp.install("anthro")["status"] == "MISSING_DEPS"
    mp.publish(PluginBundle(name="evil", trust="UNTRUSTED"))
    assert mp.install("evil")["status"] == "BLOCKED"


def test_gsi_grade_bounds():
    assert _grade(90) == "A"
    assert _grade(70) == "B"
    assert _grade(40) == "D"


def test_gsi_score_model_dump_keys():
    engine = GSIEngine()
    score = engine.score().model_dump()
    assert {"grade", "score", "attack_accuracy",
            "safety_compliance", "lessons_depth"} <= set(score)


def test_wizard_verdict_and_schema():
    wiz = DeploymentWizard()
    report = wiz.run_preflight()
    assert report.verdict in ("GO", "HOLD", "NOT_READY")
