# License Policy v0.2 (Phase-2)

This project respects source licensing and applies conservative defaults.

- Normalization: license strings are normalized to tokens like `cc-by`, `cc-by-sa`, `cc0`, `public-domain`.
- PDF Storage Rules:
  - Allowed: any license starting with `cc-`, `cc0`, or `public-domain`.
  - Disallowed (metadata-only): anything else or unknown licenses.
- API No-Serve Rule:
  - `/paper/{id}` returns `pdf_path` only when the license permits PDF storage.
  - For restricted/unknown licenses, `pdf_path` is `null`.

Implementation notes:
- Normalization and permission logic live in `ingestion.utils`.
- Enforcement is applied in ingestion (download step) and in API response shaping.

Future work:
- Expand the allowlist/denylist with specific source terms.
- Add per-source overrides where needed.


