from __future__ import annotations

from .utils import http_get_json


def fetch_openalex_neighbors(seed_doi: str) -> list[str]:
    """Return a list of DOIs that cite the seed OR are referenced by the seed (up to ~50).

    Strategy for reliability against API changes:
      1) Resolve the seed work via /works/doi:{seed} to get 'cited_by_api_url' and 'referenced_works'.
      2) Use 'cited_by_api_url' (if present) to fetch citations (first page, 25 items).
      3) For references, dereference each Work ID to extract DOI (up to 25).
    """
    base = "https://api.openalex.org/works"
    dois: set[str] = set()

    # Resolve seed work to get helpers
    # Try doi:DOI first, then fallback to the canonical DOI URL form, then a search-based resolution
    try:
        seed = http_get_json(
            f"{base}/doi:{seed_doi}",
            timeout_seconds=30,
            source_name="openalex",
            min_interval_seconds=0.5,
        )
    except Exception:
        try:
            seed = http_get_json(
                f"{base}/https://doi.org/{seed_doi}",
                timeout_seconds=30,
                source_name="openalex",
                min_interval_seconds=0.5,
            )
        except Exception:
            # Final fallback: generic search by DOI string to resolve the Work
            search_res = http_get_json(
                base,
                params={"search": seed_doi, "per_page": "1"},
                timeout_seconds=30,
                source_name="openalex",
                min_interval_seconds=0.5,
            )
            first = (search_res.get("results") or [])[:1]
            if not first:
                return []
            wid = first[0].get("id")
            if not isinstance(wid, str) or not wid:
                return []
            seed = http_get_json(
                wid,
                timeout_seconds=30,
                source_name="openalex",
                min_interval_seconds=0.5,
            )

    # 1) Who cites the seed: use the provided API URL when available
    cited_by_url = seed.get("cited_by_api_url")
    if isinstance(cited_by_url, str) and cited_by_url:
        try:
            cited = http_get_json(
                cited_by_url,
                params={"per_page": "25"},
                timeout_seconds=30,
                source_name="openalex",
                min_interval_seconds=0.5,
            )
            for it in cited.get("results", [])[:25]:
                doi_val = it.get("doi")
                if isinstance(doi_val, str) and doi_val:
                    dois.add(doi_val)
        except Exception:  # noqa: BLE001
            pass
    else:
        # If not provided, try {work_id}/cited-by endpoint
        wid = seed.get("id")
        if isinstance(wid, str) and wid:
            try:
                cited = http_get_json(
                    f"{wid}/cited-by",
                    params={"per_page": "25"},
                    timeout_seconds=30,
                    source_name="openalex",
                    min_interval_seconds=0.5,
                )
                for it in cited.get("results", [])[:25]:
                    doi_val = it.get("doi")
                    if isinstance(doi_val, str) and doi_val:
                        dois.add(doi_val)
            except Exception:  # noqa: BLE001
                pass

    # 2) References of the seed: dereference work IDs to DOIs (best-effort)
    refs = seed.get("referenced_works", []) or []
    for wid in refs[:25]:
        try:
            w = http_get_json(
                wid, timeout_seconds=30, source_name="openalex", min_interval_seconds=0.2
            )
            doi_val = w.get("doi")
            if isinstance(doi_val, str) and doi_val:
                dois.add(doi_val)
        except Exception:  # noqa: BLE001
            continue

    return list(dois)
