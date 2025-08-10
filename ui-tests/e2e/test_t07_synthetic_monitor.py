from __future__ import annotations

import os
import subprocess


def test_t07_synthetic_monitor_once() -> None:
    base_url = os.environ.get("BASE_URL", "http://localhost:8000")
    # Run once against a seeded positive query
    cmd = [
        "python",
        "scripts/synthetic_monitor.py",
        "--base-url",
        base_url,
        "--queries",
        "transformer",
        "--size",
        "3",
        "--max-latency-ms",
        "5000",
        "--interval",
        "0",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, f"monitor failed: rc={proc.returncode} out={out}"
    assert "[OK]" in out, out


