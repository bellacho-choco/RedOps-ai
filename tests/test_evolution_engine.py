"""Evolution engine: continuous self-improvement loop harness."""
from backend.evolution_engine import EvolutionEngine


class TestEvolutionEngine:
    def test_cycle_produces_decision_with_axes(self):
        eng = EvolutionEngine()
        d = eng.run()
        assert d.decision in ("ADVANCE", "HOLD", "REGRESS")
        assert d.weak_axis in ("attack", "safety", "defense", "lessons")
        assert d.gscore_before >= 0 and d.gscore_after >= 0

    def test_report_tracks_loops(self):
        eng = EvolutionEngine()
        eng.run()
        eng.run()
        rep = eng.report()
        assert rep["loops"] == 2
        assert rep["latest"]["decision"]["decision"] in ("ADVANCE", "HOLD", "REGRESS")
        assert len(rep["gs_history"]) == 2

    def test_like_axis_defense_records_lessons(self, monkeypatch):
        class FakeVaccine:
            def get_report(self):
                return {"recent": [
                    {"verdict": "BLIND_SPOT", "finding": {
                        "type": "sqli", "sample": "' OR 1=1", "source": "x"}}]}
            def run_cycle(self, finding):
                class R:  # noqa
                    verdict = "IMMUNIZED"
                return R()

        eng = EvolutionEngine()
        monkeypatch.setattr("backend.evolution_engine.vaccine_engine", FakeVaccine())
        d = eng.run()
        # Weak axis may be defense → pulls from blind spot queue
        assert d.cycles_ran <= 3
        assert d.decision in ("ADVANCE", "HOLD", "REGRESS")
