"""Coleta por palavra-chave via GET /api/search/ (índice do portal)."""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

import yaml

from collect.store import RawStore, utc_now

LOG = logging.getLogger("collect")


def default_queries_path(root: Path) -> Path:
    return root / "src" / "filter" / "search_queries.yaml"


def load_search_queries(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict) or not data.get("queries"):
        raise ValueError(f"search_queries.yaml inválido: {path}")
    return data


def collect_search_ia(
    config: dict[str, Any],
    root: Path,
    start: str,
    end: str,
    client: Any,
    store: RawStore | None = None,
) -> dict[str, int]:
    """Percorre queries × tipos de documento; grava hits deduplicados.

    Datas do config/window em ISO (AAAA-MM-DD) — formato exigido por /api/search/.
    """
    store = store or RawStore(root)
    search_cfg = config.get("search") or {}
    queries_rel = search_cfg.get("queries_path") or "src/filter/search_queries.yaml"
    queries_path = root / queries_rel if not Path(queries_rel).is_absolute() else Path(queries_rel)
    if not queries_path.is_file():
        queries_path = default_queries_path(root)

    bundle = load_search_queries(queries_path)
    queries = list(bundle["queries"])
    doc_types = list(bundle.get("document_types") or ["edital"])

    out_dir = root / "data" / "raw" / "candidatas_search"
    out_dir.mkdir(parents=True, exist_ok=True)
    hits_path = out_dir / "hits.jsonl"
    stats_path = out_dir / "search_stats.jsonl"
    index_path = out_dir / "seen_controle.json"

    seen = _load_seen(index_path)
    totals = {
        "pages": 0,
        "hits_raw": 0,
        "hits_new": 0,
        "queries_done": 0,
        "skipped_complete": 0,
        "empty_queries": 0,
    }

    for query in queries:
        qid = str(query["id"])
        qtext = str(query["q"])
        for doc_type in doc_types:
            result = _scan_query(
                client=client,
                store=store,
                out_dir=out_dir,
                hits_path=hits_path,
                stats_path=stats_path,
                index_path=index_path,
                seen=seen,
                query_id=qid,
                q=qtext,
                doc_type=doc_type,
                data_inicio=start,
                data_fim=end,
            )
            totals["pages"] += result["pages"]
            totals["hits_raw"] += result["hits_raw"]
            totals["hits_new"] += result["hits_new"]
            totals["skipped_complete"] += result["skipped"]
            totals["empty_queries"] += result["empty"]
            if not result["skipped"]:
                totals["queries_done"] += 1

    _write_manifest(out_dir, hits_path, totals, start, end, queries_path)
    return totals


def _load_seen(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    items = data.get("controles") if isinstance(data, dict) else None
    if isinstance(items, list):
        return {str(x) for x in items}
    return set()


def _save_seen(path: Path, seen: set[str]) -> None:
    path.write_text(
        json.dumps(
            {"schema_version": 1, "updated_at": utc_now(), "controles": sorted(seen)},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _checkpoint_dir(out_dir: Path, query_id: str, doc_type: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in query_id)
    directory = out_dir / "checkpoints" / doc_type / safe
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _scan_query(
    client: Any,
    store: RawStore,
    out_dir: Path,
    hits_path: Path,
    stats_path: Path,
    index_path: Path,
    seen: set[str],
    query_id: str,
    q: str,
    doc_type: str,
    data_inicio: str,
    data_fim: str,
) -> dict[str, int]:
    directory = _checkpoint_dir(out_dir, query_id, doc_type)
    checkpoint = store.read_checkpoint(directory) or {}
    if checkpoint.get("complete") is True:
        return {"pages": 0, "hits_raw": 0, "hits_new": 0, "empty": 0, "skipped": 1}

    pagina = int(checkpoint.get("last_completed_page", 0)) + 1
    hits_raw = int(checkpoint.get("hits_raw", 0))
    hits_new = int(checkpoint.get("hits_new", 0))
    total_announced = checkpoint.get("total")
    pages = 0
    tam = int(getattr(client, "search_tam_pagina", 50) or 50)

    while True:
        status, body = client.fetch_search(
            q,
            pagina,
            tipos_documento=doc_type,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        pages += 1

        if status == 204 or not body.strip():
            _finish_query(
                store,
                directory,
                stats_path,
                query_id,
                q,
                doc_type,
                data_inicio,
                data_fim,
                pagina,
                hits_raw,
                hits_new,
                total=0,
                empty=True,
            )
            return {
                "pages": pages,
                "hits_raw": hits_raw,
                "hits_new": hits_new,
                "empty": 1,
                "skipped": 0,
            }

        payload = json.loads(body.decode("utf-8"))
        items = payload.get("items") or []
        total_announced = int(payload.get("total") or 0)

        raw_path = directory / f"page-{pagina:05d}.json"
        digest = store.write_page(raw_path, body)
        store.remember(
            raw_path.relative_to(store.raw_root).as_posix(),
            digest,
            len(body),
            len(items),
            status,
        )

        page_new = 0
        for item in items:
            hits_raw += 1
            controle = item.get("numero_controle_pncp") or item.get("id")
            if not controle:
                continue
            controle = str(controle)
            if controle in seen:
                continue
            seen.add(controle)
            hits_new += 1
            page_new += 1
            enriched = {
                **item,
                "_search": {
                    "query_id": query_id,
                    "q": q,
                    "tipos_documento": doc_type,
                    "data_inicio": data_inicio,
                    "data_fim": data_fim,
                    "pagina": pagina,
                    "source": "api/search",
                },
            }
            with hits_path.open("a", encoding="utf-8", newline="\n") as out:
                out.write(json.dumps(enriched, ensure_ascii=False, separators=(",", ":")))
                out.write("\n")

        _save_seen(index_path, seen)
        store.write_checkpoint(
            directory,
            {
                "query_id": query_id,
                "q": q,
                "tipos_documento": doc_type,
                "data_inicio": data_inicio,
                "data_fim": data_fim,
                "last_completed_page": pagina,
                "hits_raw": hits_raw,
                "hits_new": hits_new,
                "total": total_announced,
                "complete": False,
            },
        )
        LOG.info(
            "search q=%r tipo=%s p%s: items=%s new=%s (acum raw=%s new=%s total=%s)",
            q,
            doc_type,
            pagina,
            len(items),
            page_new,
            hits_raw,
            hits_new,
            total_announced,
        )

        total_pages = max(1, math.ceil(total_announced / tam)) if total_announced else pagina
        if not items or pagina >= total_pages:
            _finish_query(
                store,
                directory,
                stats_path,
                query_id,
                q,
                doc_type,
                data_inicio,
                data_fim,
                pagina,
                hits_raw,
                hits_new,
                total=total_announced,
                empty=(total_announced == 0),
            )
            return {
                "pages": pages,
                "hits_raw": hits_raw,
                "hits_new": hits_new,
                "empty": 1 if total_announced == 0 else 0,
                "skipped": 0,
            }
        pagina += 1


def _finish_query(
    store: RawStore,
    directory: Path,
    stats_path: Path,
    query_id: str,
    q: str,
    doc_type: str,
    data_inicio: str,
    data_fim: str,
    pagina: int,
    hits_raw: int,
    hits_new: int,
    *,
    total: int,
    empty: bool,
) -> None:
    store.write_checkpoint(
        directory,
        {
            "query_id": query_id,
            "q": q,
            "tipos_documento": doc_type,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
            "last_completed_page": pagina,
            "hits_raw": hits_raw,
            "hits_new": hits_new,
            "total": total,
            "complete": True,
            "empty": empty,
            "finished_at": utc_now(),
        },
    )
    with stats_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(
                {
                    "query_id": query_id,
                    "q": q,
                    "tipos_documento": doc_type,
                    "data_inicio": data_inicio,
                    "data_fim": data_fim,
                    "pages": pagina,
                    "hits_raw": hits_raw,
                    "hits_new": hits_new,
                    "total": total,
                    "empty": empty,
                    "finished_at": utc_now(),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        handle.write("\n")


def _write_manifest(
    out_dir: Path,
    hits_path: Path,
    totals: dict[str, int],
    start: str,
    end: str,
    queries_path: Path,
) -> None:
    n_lines = 0
    if hits_path.is_file():
        with hits_path.open(encoding="utf-8") as handle:
            n_lines = sum(1 for line in handle if line.strip())
    payload = {
        "schema_version": 1,
        "finished_at": utc_now(),
        "source": "api/search",
        "window": {"start": start, "end": end},
        "queries_file": queries_path.as_posix(),
        "hits_path": hits_path.as_posix(),
        "unique_hits_in_jsonl": n_lines,
        "totals": totals,
        "notes": (
            "Índice do portal (mesma busca do site). Não é a API de Consultas do manual. "
            "Deduplicação por numero_controle_pncp entre queries."
        ),
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
