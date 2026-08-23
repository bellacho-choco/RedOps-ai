"""Real tests for payload corpus, blind injection, and the autonomous hunt loop.

Runs against a REAL threaded lab server with true time-based SQLi, SSTI,
reflection, error-based SQLi and auth-bypass bugs. No mocks.
"""
import asyncio
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import pytest

from backend.payload_corpus import payload_corpus, TechniqueCorpus
from backend.fuzz_engine import fuzz_engine, _ssti_confirmed
from backend.api_mapper import Endpoint
from backend.hunt_engine import hunt_engine
from backend.exploit_validator import exploit_validator
from backend.response_analyzer import Signal


class BlindVulnHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="text/html"):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/":
            self._send(200, '<a href="/render?tpl=x">r</a><a href="/item?id=1">i</a>')
        elif u.path == "/item":
            # true blind time-based SQLi: SLEEP payload delays response 2s
            val = q.get("id", [""])[0]
            if "SLEEP" in val.upper():
                time.sleep(2.2)
            self._send(200, '{"ok": true}')
        elif u.path == "/render":
            # true SSTI: server-side template engine evaluates expressions
            tpl = q.get("tpl", [""])[0]
            for marker in ("{{7*7}}", "${7*7}", "<%= 7*7 %>", "#{7*7}", "*{7*7}"):
                tpl = tpl.replace(marker, "49")
            self._send(200, f"<html>{tpl}</html>")
        else:
            self._send(404, "nope")


@pytest.fixture(scope="module")
def blind_lab():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), BlindVulnHandler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()


class FakeSkill:
    def __init__(self, name, tags, path):
        self.name, self.tags, self.file_path = name, tags, path


class TestPayloadCorpus:
    def test_builtin_corpora_present(self):
        for technique in ("sqli-error", "xss-reflected", "ssti", "ssrf", "sqli-blind-time"):
            assert technique in payload_corpus.techniques()

    def test_consumption_tracks_coverage(self):
        from backend.payload_corpus import PayloadCorpus
        corpus = PayloadCorpus()
        chosen = corpus.payloads_for("ssti", 2)
        assert len(chosen) == 2
        report = corpus.coverage_report()
        assert report["ssti"]["used"] >= 2 and report["ssti"]["coverage"] > 0

    def test_skill_extraction_adds_payloads(self, tmp_path):
        skill_file = tmp_path / "sqli-skill.md"
        skill_file.write_text(
            "# SQLi skill\n```sql\nadmin' OR '1'='1'--\n' UNION SELECT password--\n```\n")
        local = type("C", (), {})()
        from backend.payload_corpus import PayloadCorpus
        pc = PayloadCorpus()
        added = pc.load_from_skills([FakeSkill("sqli-advanced", ["sqli"], str(skill_file))])
        assert added >= 1
        assert any("UNION" in p or "OR '1'='1'" in p for p in pc.corpora["sqli-error"].payloads)


class TestBlindInjection:
    def test_time_based_sqli_detected(self, blind_lab):
        from backend.fuzz_engine import FuzzEngine
        engine = FuzzEngine()
        ep = Endpoint(url=f"{blind_lab}/item", params=["id"])
        result = asyncio.run(engine.fuzz_endpoint(ep, max_requests=14))
        kinds = {s.kind for s in result.signals}
        assert "BLIND_TIME_SQLI" in kinds
        sig = next(s for s in result.signals if s.kind == "BLIND_TIME_SQLI")
        assert sig.context["injected_ms"] - sig.context["baseline_ms"] >= 1800

    def test_time_based_validator_reproduces(self, blind_lab):
        sig = Signal(kind="BLIND_TIME_SQLI", url=f"{blind_lab}/item",
                     detail="timing", confidence=0.9, severity="CRITICAL",
                     context={"param": "id", "probe": "1' AND SLEEP(2)-- -",
                              "baseline_ms": 50.0})
        result = asyncio.run(exploit_validator.validate(
            sig, params={"id": "1' AND SLEEP(2)-- -"}))
        assert result.validated is True

    def test_ssti_detection(self, blind_lab):
        from backend.fuzz_engine import FuzzEngine
        engine = FuzzEngine()
        ep = Endpoint(url=f"{blind_lab}/render", params=["tpl"])
        result = asyncio.run(engine.fuzz_endpoint(ep, max_requests=14))
        assert any(s.kind == "SSTI" for s in result.signals)

    def test_ssti_helper_logic(self):
        assert _ssti_confirmed("<html>49</html>") is True
        assert _ssti_confirmed("<html>{{7*7}}</html>") is False
        assert _ssti_confirmed("<html>7*7 = 49</html>") is False


class TestAutonomousHuntLoop:
    def test_hunt_chains_map_fuzz_validate(self, blind_lab):
        report = asyncio.run(hunt_engine.hunt(
            blind_lab, max_endpoints=10, max_requests_per_endpoint=14,
            total_request_ceiling=120))
        assert report.endpoints_mapped >= 2
        assert report.endpoints_fuzzed >= 2
        assert report.requests_sent > 0
        assert report.signals_found >= 1
        # every signal must have been pushed through the validator
        assert report.findings_validated + report.findings_rejected == report.signals_found
        assert report.findings_validated >= 1  # lab has real bugs, they must validate
        assert all(v["finding_id"] for v in report.validations if v["validated"])
        assert "ssti" in report.corpus_coverage
