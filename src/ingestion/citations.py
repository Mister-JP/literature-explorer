from __future__ import annotations

from .utils import http_get_json


def fetch_openalex_neighbors(seed_doi: str) -> list[str]:
    """Return a list of DOIs that cite the seed OR are referenced by the seed.

    Uses OpenAlex links:
      - Works citing the seed: /works?filter=cites:doi:{seed}
      - References of the seed: /works/doi:{seed}
    """
    base = "https://api.openalex.org/works"
    dois: set[str] = set()

    # 1) Who cites the seed
    data = http_get_json(
        base,
        params={"filter": f"cites:doi:{seed_doi}", "per_page": "25"},
        timeout_seconds=30,
        source_name="openalex",
        min_interval_seconds=0.5,
    )
    for it in data.get("results", [])[:25]:
        if it.get("doi"):
            dois.add(it["doi"])  # type: ignore[index]

    # 2) References of the seed
    data2 = http_get_json(
        f"{base}/doi:{seed_doi}",
        timeout_seconds=30,
        source_name="openalex",
        min_interval_seconds=0.5,
    )
    refs = data2.get("referenced_works", [])
    for wid in refs[:25]:
        try:
            w = http_get_json(
                wid, timeout_seconds=30, source_name="openalex", min_interval_seconds=0.2
            )
            if w.get("doi"):
                dois.add(w["doi"])  # type: ignore[index]
        except Exception:  # noqa: BLE001
            continue

    return list(dois)
