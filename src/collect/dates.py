"""Datas da coleta. O formato da API é AAAAMMDD, inclusive nas duas pontas."""

from __future__ import annotations

from datetime import date, datetime, timedelta


def parse_iso_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"Data inválida {value!r}; use AAAA-MM-DD.") from exc


def to_api_date(value: date) -> str:
    return value.strftime("%Y%m%d")


def iter_chunks(start: date, end: date, chunk_days: int):
    """Janelas inclusivas. chunk_days=1 devolve um par por dia."""
    if chunk_days < 1:
        raise ValueError("chunk_days tem de ser pelo menos 1.")
    if end < start:
        raise ValueError(f"Fim {end} anterior ao início {start}.")
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=chunk_days - 1), end)
        yield cursor, chunk_end
        cursor = chunk_end + timedelta(days=1)
