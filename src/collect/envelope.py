"""Envelope da listagem, secção 4.2 do manual de consultas."""

from __future__ import annotations

import json
from typing import Any

ENVELOPE_KEYS = (
    "data",
    "totalRegistros",
    "totalPaginas",
    "numeroPagina",
    "paginasRestantes",
    "empty",
)


class SchemaDivergence(RuntimeError):
    """A resposta 200 não tem o envelope que o manual descreve. A coleta para."""


def parse_envelope(body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SchemaDivergence(f"Corpo 200 não é JSON UTF-8: {exc}") from exc
    if not isinstance(payload, dict):
        raise SchemaDivergence("O corpo 200 não é um objeto JSON.")
    missing = [key for key in ENVELOPE_KEYS if key not in payload]
    if missing:
        raise SchemaDivergence(
            "Faltam chaves do envelope documentado na secção 4.2: " + ", ".join(missing)
        )
    if not isinstance(payload["data"], list):
        raise SchemaDivergence("O campo data não é uma lista.")
    return payload


def page_is_last(payload: dict[str, Any], pagina: int) -> bool:
    if payload["empty"] is True:
        return True
    if payload["paginasRestantes"] == 0:
        return True
    total = payload["totalPaginas"]
    if isinstance(total, int) and pagina >= total:
        return True
    return False
