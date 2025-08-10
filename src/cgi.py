# Minimal stub of deprecated stdlib cgi for compatibility with packages on Python 3.13+
from __future__ import annotations

from html import escape as _html_escape


def escape(s: str, quote: bool = False) -> str:  # pragma: no cover - shim
    return _html_escape(s, quote=quote)


def parse_header(value: str) -> tuple[str, dict[str, str]]:  # pragma: no cover - shim
    if not isinstance(value, str):
        value = str(value)
    parts = [p.strip() for p in value.split(";") if p.strip()]
    if not parts:
        return "", {}
    main = parts[0]
    params: dict[str, str] = {}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            v = v.strip().strip('"')
            params[k.strip()] = v
        else:
            params[p] = ""
    return main, params
