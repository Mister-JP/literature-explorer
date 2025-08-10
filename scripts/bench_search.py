from __future__ import annotations

import os
import statistics
import time
from typing import Any

from opensearchpy import OpenSearch


def main() -> None:
    host = os.environ.get("SEARCH_HOST", "http://localhost:9200")
    index = os.environ.get("SEARCH_INDEX", "papers")
    client = OpenSearch(hosts=[host])

    query: dict[str, Any] = {
        "bool": {
            "must": {"multi_match": {"query": "transformer", "fields": ["title^2", "abstract"]}},
            "filter": [],
        }
    }
    sort = [{"fetched_at": {"order": "desc"}}]

    times: list[float] = []
    n = int(os.environ.get("BENCH_N", "50"))
    size = int(os.environ.get("BENCH_SIZE", "20"))
    for _ in range(n):
        t0 = time.perf_counter()
        client.search(index=index, body={"query": query, "size": size, "sort": sort})
        times.append((time.perf_counter() - t0) * 1000)

    p95 = statistics.quantiles(times, n=100)[94]
    print(f"n={n} size={size} mean_ms={statistics.mean(times):.1f} p95_ms={p95:.1f}")


if __name__ == "__main__":
    main()
