"""
====================================================================
PROJECT REDOPS-AI - REAL NETWORK SCANNER & WEB SECURITY AUDITOR
High-Performance Asynchronous Socket Prober, Banner Grabber & TLS Auditor
====================================================================
"""

import asyncio
import socket
import ssl
import time
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse
import httpx
import dns.resolver


class AsyncSocketScanner:
    """
    High-performance asynchronous TCP port scanner and service banner grabber.
    """
    COMMON_PORTS = [
        21, 22, 23, 25, 53, 80, 110, 143, 389, 443, 445,
        1433, 1521, 3000, 3306, 3389, 5000, 5432, 6379,
        8000, 8080, 8443, 9000, 9090, 27017
    ]

    SERVICE_MAP = {
        21: "FTP", 22: "SSH", 23: "TELNET", 25: "SMTP", 53: "DNS",
        80: "HTTP", 110: "POP3", 143: "IMAP", 389: "LDAP", 443: "HTTPS",
        445: "SMB", 1433: "MSSQL", 1521: "ORACLE", 3000: "NODE_WEB",
        3306: "MYSQL", 3389: "RDP", 5000: "FLASK/DOCKER", 5432: "POSTGRESQL",
        6379: "REDIS", 8000: "HTTP_ALT", 8080: "HTTP_PROXY", 8443: "HTTPS_ALT",
        9000: "FASTAPI/METRICS", 9090: "GO_DAEMON", 27017: "MONGODB"
    }

    async def probe_port(self, host: str, port: int, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """
        Probes a single TCP port using raw non-blocking async sockets.
        """
        start_time = time.perf_counter()
        try:
            conn = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(conn, timeout=timeout)
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

            banner = ""
            try:
                # Send a probe line to induce a service banner
                if port in [80, 8080, 8000, 3000, 5000]:
                    writer.write(b"HEAD / HTTP/1.0\r\nHost: " + host.encode() + b"\r\n\r\n")
                    await writer.drain()
                elif port in [21, 22, 25, 110]:
                    pass # Service sends banner automatically on connect

                banner_data = await asyncio.wait_for(reader.read(512), timeout=0.6)
                banner = banner_data.decode("utf-8", errors="ignore").strip()
            except Exception:
                banner = ""

            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

            service_name = self.SERVICE_MAP.get(port, "UNKNOWN")
            return {
                "port": port,
                "protocol": "TCP",
                "state": "OPEN",
                "service": service_name,
                "latency_ms": latency_ms,
                "banner": banner[:120] if banner else f"Standard {service_name} endpoint"
            }
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            return None

    # Cymru-style TTL cache (BEAT #5): repeated target hits collapse into
    # cached_data, collateral probe traffic is amortized to zero.
    CACHE_TTL_S = 30.0

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    async def scan_target(self, target: str, ports: Optional[List[int]] = None, concurrency: int = 50) -> Dict[str, Any]:
        """
        Scans all specified ports on a target host concurrently.
        """
        ports_to_scan = ports or self.COMMON_PORTS
        cache_key = f"{target}|{sorted(ports_to_scan)}"
        hit = self._cache.get(cache_key)
        if hit and time.time() - hit["cached_at"] < self.CACHE_TTL_S:
            return {**hit, "cached": True,
                    "cache_age_s": round(time.time() - hit["cached_at"], 2)}

        # Resolve hostname to IP
        try:
            resolved_ip = socket.gethostbyname(target)
        except Exception:
            resolved_ip = target

        semaphore = asyncio.Semaphore(concurrency)

        async def _bounded_probe(p: int):
            async with semaphore:
                return await self.probe_port(resolved_ip, p)

        start_time = time.perf_counter()
        tasks = [_bounded_probe(p) for p in ports_to_scan]
        results = await asyncio.gather(*tasks)
        scan_duration_s = round(time.perf_counter() - start_time, 3)

        open_ports = [r for r in results if r is not None]

        report = {
            "target": target,
            "ip": resolved_ip,
            "total_probed": len(ports_to_scan),
            "open_ports_count": len(open_ports),
            "open_ports": open_ports,
            "scan_duration_s": scan_duration_s,
            "cached": False,
        }
        self._cache[cache_key] = {**report, "cached_at": time.time()}
        return report

    async def batch_recon(self, targets: List[str], max_concurrent: int = 8) -> Dict[str, Any]:
        """Fan-out one recon stream per host (BEAT #5 batch-layer)."""
        sem = asyncio.Semaphore(max_concurrent)

        async def _one(t: str):
            async with sem:
                return await self.scan_target(t)

        started = time.perf_counter()
        scans = await asyncio.gather(*[_one(t) for t in targets])
        return {
            "batch_count": len(scans),
            "elapsed_s": round(time.perf_counter() - started, 3),
            "scans": scans,
        }


class WebSecurityAuditor:
    """
    Audits live web endpoints for security headers, SSL/TLS posture, and technology stack.
    """
    SECURITY_HEADERS = [
        "Content-Security-Policy",
        "Strict-Transport-Security",
        "X-Frame-Options",
        "X-Content-Type-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Cross-Origin-Opener-Policy",
        "Cross-Origin-Embedder-Policy"
    ]

    async def audit_url(self, target_url: str) -> Dict[str, Any]:
        """
        Performs live HTTP inspection and security posture auditing.
        """
        if not target_url.startswith("http://") and not target_url.startswith("https://"):
            target_url = "https://" + target_url

        parsed = urlparse(target_url)
        hostname = parsed.hostname or "localhost"
        is_https = parsed.scheme == "https"

        report: Dict[str, Any] = {
            "url": target_url,
            "hostname": hostname,
            "scheme": parsed.scheme,
            "status_code": 0,
            "headers_present": {},
            "missing_security_headers": [],
            "technology_stack": {},
            "ssl_certificate": {},
            "security_risks": []
        }

        # 1. Fetch live HTTP Response
        async with httpx.AsyncClient(verify=False, timeout=10.0, follow_redirects=True) as client:
            try:
                resp = await client.get(target_url)
                report["status_code"] = resp.status_code

                # Check security headers
                for header in self.SECURITY_HEADERS:
                    val = resp.headers.get(header)
                    if val:
                        report["headers_present"][header] = val
                    else:
                        report["missing_security_headers"].append(header)

                # Identify Tech Stack
                server_hdr = resp.headers.get("server")
                powered_by = resp.headers.get("x-powered-by")
                report["technology_stack"] = {
                    "server": server_hdr or "Undisclosed",
                    "x_powered_by": powered_by or "None",
                    "content_type": resp.headers.get("content-type", "unknown")
                }

                # Evaluate Risk Findings
                if "Content-Security-Policy" in report["missing_security_headers"]:
                    report["security_risks"].append({
                        "id": "SEC-HDR-01",
                        "title": "Missing Content-Security-Policy (CSP)",
                        "severity": "MEDIUM",
                        "description": "Increases susceptibility to Cross-Site Scripting (XSS) and code injection."
                    })

                if is_https and "Strict-Transport-Security" in report["missing_security_headers"]:
                    report["security_risks"].append({
                        "id": "SEC-HDR-02",
                        "title": "Missing Strict-Transport-Security (HSTS)",
                        "severity": "MEDIUM",
                        "description": "Vulnerable to SSL stripping and man-in-the-middle downgrade attacks."
                    })

                if "X-Frame-Options" in report["missing_security_headers"]:
                    report["security_risks"].append({
                        "id": "SEC-HDR-03",
                        "title": "Missing X-Frame-Options (Clickjacking Risk)",
                        "severity": "LOW",
                        "description": "Allows page to be framed inside malicious third-party iframes."
                    })

                cors_hdr = resp.headers.get("access-control-allow-origin")
                if cors_hdr == "*":
                    report["security_risks"].append({
                        "id": "SEC-CORS-01",
                        "title": "Permissive Wildcard CORS Policy (Access-Control-Allow-Origin: *)",
                        "severity": "HIGH",
                        "description": "Any external origin can make authenticated or cross-domain XMLHttpRequests."
                    })

            except Exception as e:
                report["connection_error"] = str(e)

        # 2. Inspect SSL/TLS Certificate if HTTPS
        if is_https:
            try:
                ssl_ctx = ssl.create_default_context()
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE

                port = parsed.port or 443
                with socket.create_connection((hostname, port), timeout=5.0) as sock:
                    with ssl_ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                        cert = ssock.getpeercert(binary_form=False)
                        cipher = ssock.cipher()
                        report["ssl_certificate"] = {
                            "tls_version": ssock.version(),
                            "cipher_suite": cipher[0] if cipher else "Unknown",
                            "bits": cipher[2] if cipher else 0,
                            "subject": dict(x[0] for x in cert.get("subject", [])) if cert else "Unknown",
                            "issuer": dict(x[0] for x in cert.get("issuer", [])) if cert else "Unknown",
                            "expires": cert.get("notAfter", "Unknown") if cert else "Unknown"
                        }
            except Exception as e:
                report["ssl_certificate"] = {"error": f"TLS handshake failed: {str(e)}"}

        return report


class DNSSecurityAuditor:
    """
    Audits DNS records for zone hygiene, SPF, and DMARC enforcement.
    """
    @staticmethod
    def audit_domain(domain: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "domain": domain,
            "a_records": [],
            "mx_records": [],
            "txt_records": [],
            "spf_status": "MISSING",
            "dmarc_status": "MISSING"
        }

        try:
            answers = dns.resolver.resolve(domain, 'A')
            result["a_records"] = [str(r) for r in answers]
        except Exception:
            pass

        try:
            answers = dns.resolver.resolve(domain, 'MX')
            result["mx_records"] = [str(r.exchange).rstrip('.') for r in answers]
        except Exception:
            pass

        try:
            answers = dns.resolver.resolve(domain, 'TXT')
            txts = [str(r).strip('"') for r in answers]
            result["txt_records"] = txts
            for t in txts:
                if "v=spf1" in t:
                    result["spf_status"] = "CONFIGURED: " + t[:40]
        except Exception:
            pass

        try:
            dmarc_answers = dns.resolver.resolve(f"_dmarc.{domain}", 'TXT')
            for r in dmarc_answers:
                if "v=DMARC1" in str(r):
                    result["dmarc_status"] = "CONFIGURED: " + str(r).strip('"')[:40]
        except Exception:
            pass

        return result


# Singleton Instances
socket_scanner = AsyncSocketScanner()
web_auditor = WebSecurityAuditor()
dns_auditor = DNSSecurityAuditor()
