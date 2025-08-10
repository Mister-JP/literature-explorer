from __future__ import annotations

from ingestion.utils import PerSourceRateLimiter, license_permits_pdf_storage, normalize_license


def test_license_normalization_and_policy():
    assert normalize_license("CC BY 4.0") == "cc-by"
    assert normalize_license("Public Domain") == "public-domain"
    assert license_permits_pdf_storage("cc-by") is True
    assert license_permits_pdf_storage("cc0") is True
    assert license_permits_pdf_storage("public-domain") is True
    assert license_permits_pdf_storage(None) is False
    assert license_permits_pdf_storage("all-rights-reserved") is False


def test_per_source_rate_limiter_basic():
    rl = PerSourceRateLimiter()
    start = __import__("time").monotonic()
    rl.throttle("openalex", 0.2)
    rl.throttle("openalex", 0.2)
    elapsed = __import__("time").monotonic() - start
    # Two calls should incur ~0.2s total at minimum; allow slack on CI
    assert elapsed >= 0.18
