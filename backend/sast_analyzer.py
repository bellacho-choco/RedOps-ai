"""
====================================================================
PROJECT REDOPS-AI - SAST & SECRET ENTROPY AUDITOR
Detects Hardcoded Secrets, High-Entropy Credentials, and Risky AST Sinks
====================================================================
"""

import re
import os
import math
from typing import List, Dict, Any, Optional
from cython_core.fast_entropy import calculate_shannon_entropy


class SASTSecretAuditor:
    """
    Static code and buffer analyzer for credentials, API tokens, and code security flaws.
    """
    SECRET_PATTERNS = [
        ("AWS_ACCESS_KEY", r"(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}", "CRITICAL"),
        ("JWT_BEARER_TOKEN", r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}", "HIGH"),
        ("GENERIC_PRIVATE_KEY", r"-----BEGIN (?:RSA|EC|OPENSSH|PGP) PRIVATE KEY-----", "CRITICAL"),
        ("GITHUB_PAT", r"ghp_[a-zA-Z0-9]{36}", "CRITICAL"),
        ("SLACK_WEBHOOK", r"https://hooks\.slack\.com/services/T[a-zA-Z0-9_]+/B[a-zA-Z0-9_]+/[a-zA-Z0-9_]+", "HIGH"),
        ("GENERIC_API_KEY", r"(?:api_key|apikey|secret_key|auth_token)\s*[:=]\s*['\"][a-zA-Z0-9_\-]{16,64}['\"]", "HIGH"),
        ("UNSAFE_EVAL_EXEC", r"(?:eval|exec)\s*\([^)]+\)", "MEDIUM"),
        ("SQL_CONCATENATION", r"(?:SELECT|INSERT|UPDATE|DELETE).*\+.*(?:request|req|params|input)", "HIGH")
    ]

    @staticmethod
    def analyze_buffer(content: str, source_name: str = "Buffer") -> List[Dict[str, Any]]:
        """
        Scans a string buffer for secrets, high-entropy tokens, and risky patterns.
        """
        findings: List[Dict[str, Any]] = []

        # 1. Regex Pattern Search
        for pattern_name, regex, severity in SASTSecretAuditor.SECRET_PATTERNS:
            matches = re.finditer(regex, content, re.IGNORECASE)
            for m in matches:
                matched_text = m.group(0)
                # Redact matched text for safe display
                redacted = matched_text[:6] + "..." + matched_text[-4:] if len(matched_text) > 10 else "***"
                findings.append({
                    "type": pattern_name,
                    "severity": severity,
                    "source": source_name,
                    "position": m.start(),
                    "sample": redacted,
                    "entropy": calculate_shannon_entropy(matched_text.encode('utf-8'))
                })

        # 2. High-Entropy String Extraction
        words = re.findall(r'[a-zA-Z0-9_\-+/=]{20,}', content)
        for word in words:
            ent = calculate_shannon_entropy(word.encode('utf-8'))
            if ent > 4.5 and not any(f["position"] == content.find(word) for f in findings):
                findings.append({
                    "type": "HIGH_ENTROPY_TOKEN",
                    "severity": "LOW",
                    "source": source_name,
                    "position": content.find(word),
                    "sample": word[:4] + "..." + word[-4:],
                    "entropy": ent
                })

        return findings

    @staticmethod
    def analyze_file(file_path: str) -> Dict[str, Any]:
        """
        Scans a local file for security findings.
        """
        if not os.path.exists(file_path):
            return {"error": f"File not found: {file_path}", "findings": []}

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            findings = SASTSecretAuditor.analyze_buffer(content, source_name=os.path.basename(file_path))
            return {
                "file": file_path,
                "size_bytes": len(content),
                "total_findings": len(findings),
                "findings": findings
            }
        except Exception as e:
            return {"file": file_path, "error": str(e), "findings": []}

    @staticmethod
    def analyze_directory(dir_path: str, max_files: int = 50) -> Dict[str, Any]:
        """
        Scans a project directory recursively for secrets and insecure coding patterns.
        """
        results = []
        total_scanned = 0

        for root, _, files in os.walk(dir_path):
            if any(ignore in root for ignore in [".git", "__pycache__", "node_modules", ".venv", "env"]):
                continue

            for f in files:
                if f.endswith(('.py', '.js', '.ts', '.env', '.json', '.yaml', '.yml', '.go', '.sh', '.conf')):
                    fp = os.path.join(root, f)
                    res = SASTSecretAuditor.analyze_file(fp)
                    if res.get("total_findings", 0) > 0:
                        results.append(res)
                    total_scanned += 1
                    if total_scanned >= max_files:
                        break
            if total_scanned >= max_files:
                break

        return {
            "directory": dir_path,
            "files_scanned": total_scanned,
            "vulnerable_files_count": len(results),
            "findings_by_file": results
        }


sast_auditor = SASTSecretAuditor()
