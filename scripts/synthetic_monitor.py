from __future__ import annotations

import argparse
import json
import os
import sys
import time
from contextlib import suppress
from typing import Any

import requests


def _now_ms() -> int:
    return int(time.time() * 1000)


def perform_check(
    base_url: str, query: str, size: int, max_latency_ms: int
) -> tuple[bool, dict[str, Any]]:
    t0 = _now_ms()
    url = f"{base_url.rstrip('/')}/search"
    try:
        resp = requests.get(url, params={"q": query, "size": size}, timeout=10)
        latency_ms = _now_ms() - t0
        ok = resp.status_code == 200
        payload: dict[str, Any] = {
            "query": query,
            "status": resp.status_code,
            "latency_ms": latency_ms,
        }
        if not ok:
            payload["error"] = f"HTTP {resp.status_code}"
            return False, payload
        try:
            data = resp.json()
        except Exception:
            payload["error"] = "Non-JSON response"
            return False, payload
        total = int((data or {}).get("total") or 0)
        payload["total"] = total
        if total <= 0:
            payload["error"] = "Zero results"
            return False, payload
        if latency_ms > max_latency_ms:
            payload["error"] = f"Latency {latency_ms}ms exceeds {max_latency_ms}ms"
            return False, payload
        return True, payload
    except requests.RequestException as e:
        return False, {"query": query, "error": str(e), "latency_ms": _now_ms() - t0}


def post_webhook(webhook_url: str, event_type: str, payload: dict[str, Any]) -> None:
    headers = {"Content-Type": "application/json"}
    body = json.dumps({"type": event_type, "payload": payload})
    with suppress(Exception):
        requests.post(webhook_url, data=body, headers=headers, timeout=5)


def post_telemetry(base_url: str, event_type: str, payload: dict[str, Any]) -> None:
    url = f"{base_url.rstrip('/')}/ui/telemetry"
    body = {
        "session_id": "synthetic",
        "ui_version": "v1",
        "event_type": event_type,
        "payload": payload,
    }
    with suppress(Exception):
        requests.post(
            url, data=json.dumps(body), headers={"Content-Type": "application/json"}, timeout=5
        )


def run_once(
    base_url: str, queries: list[str], size: int, max_latency_ms: int, webhook_url: str | None
) -> int:
    failures: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for q in queries:
        ok, payload = perform_check(base_url, q, size, max_latency_ms)
        results.append({"ok": ok, **payload})
        if not ok:
            failures.append(payload)
    # Report failures via webhook, falling back to telemetry
    if failures:
        summary = {
            "base_url": base_url,
            "total_checks": len(results),
            "failures": failures,
            "ok_count": sum(1 for r in results if r.get("ok")),
            "ts": int(time.time()),
        }
        if webhook_url:
            post_webhook(webhook_url, "synthetic_monitor_failure", summary)
        else:
            post_telemetry(base_url, "synthetic_failure", summary)
    # Print concise output for logs/cron
    for r in results:
        status = "OK" if r.get("ok") else "FAIL"
        msg = f"[{status}] q='{r.get('query')}' total={r.get('total', '?')} latency_ms={r.get('latency_ms', '?')}"
        if not r.get("ok"):
            msg += f" reason={r.get('error', 'unknown')}"
        print(msg)
    return 0 if not failures else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Synthetic monitor for UI/API health")
    parser.add_argument(
        "--base-url", default=os.environ.get("MONITOR_BASE_URL", "http://localhost:8000")
    )
    parser.add_argument(
        "--queries",
        default=os.environ.get("MONITOR_QUERIES", "transformer,graph,neural"),
        help="Comma-separated list of queries",
    )
    parser.add_argument("--size", type=int, default=int(os.environ.get("MONITOR_SIZE", 5)))
    parser.add_argument(
        "--max-latency-ms",
        type=int,
        default=int(os.environ.get("MONITOR_MAX_LATENCY_MS", 2000)),
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.environ.get("MONITOR_INTERVAL", 0)),
        help="Seconds between runs; 0 runs once and exits",
    )
    parser.add_argument(
        "--webhook-url",
        default=os.environ.get("ALERT_WEBHOOK_URL", ""),
        help="Override alert webhook URL (defaults to ALERT_WEBHOOK_URL env)",
    )
    args = parser.parse_args()

    queries = [q.strip() for q in str(args.queries).split(",") if q.strip()]
    webhook_url = args.webhook_url.strip() or None

    if args.interval <= 0:
        return run_once(args.base_url, queries, args.size, args.max_latency_ms, webhook_url)

    # Daemon mode
    exit_code = 0
    try:
        while True:
            code = run_once(args.base_url, queries, args.size, args.max_latency_ms, webhook_url)
            exit_code = code if code != 0 else exit_code
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
