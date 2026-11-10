"""Read-only website/backend HTTP release probe.

Only GET requests. Emits field-limited JSON evidence, never response bodies,
provider secrets, prompts, or visitor information.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

EXPECTED_HEADERS = (
    "content-security-policy",
    "strict-transport-security",
    "x-content-type-options",
    "referrer-policy",
)


def normalize_origin(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Origin must be an absolute HTTP(S) URL.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Origin must not include credentials, query or fragment.")
    if parsed.path not in {"", "/"}:
        raise ValueError("Origin must contain only scheme, host and optional port.")
    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Remote probes require HTTPS.")
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def classify_health(path: str, status: int, payload: object) -> tuple[bool, dict[str, str]]:
    """Check public health contracts without preserving raw response bodies."""
    if not isinstance(payload, dict):
        return False, {}
    if path.endswith("/live"):
        result = {"status": str(payload.get("status", "unknown"))}
        return status == 200 and payload.get("status") == "alive", result
    if path.endswith("/ready"):
        fields = ("status", "vector_db", "llm_config", "contact_email")
        allowed = {key: str(payload.get(key, "missing")) for key in fields}
        passed = (
            status == 200
            and payload.get("status") == "ready"
            and payload.get("vector_db") == "ready"
            and payload.get("llm_config") == "configured"
        )
        return passed, allowed
    return False, {}


def probe_url(origin: str, path: str, *, timeout: float, health: bool = False) -> dict:
    check = {"path": path, "result": "BLOCKED", "http_status": None}
    request = urllib.request.Request(
        f"{origin}{path}",
        headers={"Accept": "application/json" if health else "text/html", "User-Agent": "site-release-readonly-probe/1"},
        method="GET",
    )
    try:
        try:
            response = urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            status = int(response.status)
            check["http_status"] = status
            if health:
                # Health endpoints are bounded to 16 KiB and only whitelisted
                # schema values are retained in the result.
                raw = response.read(16385)
                payload = json.loads(raw) if len(raw) <= 16384 else None
                passed, fields = classify_health(path, status, payload)
                check["fields"] = fields
            else:
                content_type = response.headers.get("content-type", "").lower()
                passed = status == 200 and "text/html" in content_type
                check["security_headers_present"] = {
                    name: bool(response.headers.get(name)) for name in EXPECTED_HEADERS
                }
            check["result"] = "PASS" if passed else "FAIL"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        # Never serialize error text, which can contain proxy addresses.
        check["failure_type"] = type(exc).__name__
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        check["result"] = "FAIL"
        check["failure_type"] = "invalid_health_json"
    return check


def build_report(site: str, backend: str | None, timeout: float) -> dict:
    groups: dict[str, dict] = {}
    groups["frontend"] = {
        "base": site,
        "checks": [
            probe_url(site, "/", timeout=timeout),
            probe_url(site, "/chat", timeout=timeout),
            probe_url(site, "/api/health/live", timeout=timeout, health=True),
            probe_url(site, "/api/health/ready", timeout=timeout, health=True),
        ],
    }
    if backend:
        if backend == site:
            raise ValueError("Direct backend origin must differ from frontend origin.")
        groups["direct_backend"] = {
            "base": backend,
            "checks": [
                probe_url(backend, "/api/health/live", timeout=timeout, health=True),
                probe_url(backend, "/api/health/ready", timeout=timeout, health=True),
            ],
        }
    statuses = [c["result"] for g in groups.values() for c in g["checks"]]
    return {
        "schema_version": 1,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": "read_only_get",
        "overall": "FAIL" if "FAIL" in statuses else ("BLOCKED" if "BLOCKED" in statuses else "PASS"),
        "direct_backend_checked": backend is not None,
        "groups": groups,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-base", default="https://alextym.com")
    parser.add_argument("--backend-base")
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--output", type=Path, default=Path(".tmp/release-evidence/site-http.json"))
    args = parser.parse_args(argv)
    try:
        if not 1 <= args.timeout <= 120:
            raise ValueError("--timeout must be between 1 and 120 seconds")
        site = normalize_origin(args.site_base)
        backend = normalize_origin(args.backend_base) if args.backend_base else None
        report = build_report(site, backend, args.timeout)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Release HTTP probe: {report['overall']} (evidence: {args.output})")
        if backend is None:
            print("Direct Render backend remains UNVERIFIED (pass --backend-base after confirmation).")
        return 0 if report["overall"] == "PASS" else 1
    except (ValueError, OSError) as exc:
        print(f"Release probe could not run: {type(exc).__name__}.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
