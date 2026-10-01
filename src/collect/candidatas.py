"""Varredura da API com persistência só de candidatas lexicais de IA."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from collect.dates import iter_chunks, parse_iso_date, to_api_date
from collect.envelope import SchemaDivergence, page_is_last, parse_envelope
from collect.store import RawStore, sha256_bytes, utc_now
from filter.lexical import LexicalFilter, default_terms_path, load_terms

LOG = logging.getLogger("collect")


def collect_candidatas(
    config: dict[str, Any],
    root: Path,
    start: str,
    end: str,
    client: Any,
    store: RawStore | None = None,
    modalidades: list[int] | None = None,
) -> dict[str, int]:
    """Percorre todas as publicações, mas só grava registos que passam no filtro de IA.

    A API não filtra por texto: os pedidos HTTP cobrem o universo. Em disco ficam
    apenas as candidatas e contagens por janela (não o JSONL de todas as compras).
    """
    store = store or RawStore(root)
    modalidades = modalidades if modalidades is not None else list(config["modalidades"])
    chunk_days = int(config["collect"]["chunk_days"])
    filt = LexicalFilter(load_terms(default_terms_path(root)))
    out_dir = root / "data" / "raw" / "candidatas"
    out_dir.mkdir(parents=True, exist_ok=True)
    candidates_path = out_dir / "candidatas.jsonl"
    stats_path = out_dir / "scan_stats.jsonl"

    totals = {
        "pages": 0,
        "scanned": 0,
        "matched": 0,
        "empty_windows": 0,
        "skipped_complete": 0,
    }

    for modalidade in modalidades:
        for chunk_start, chunk_end in iter_chunks(
            parse_iso_date(start), parse_iso_date(end), chunk_days
        ):
            data_inicial = to_api_date(chunk_start)
            data_final = to_api_date(chunk_end)
            result = _scan_window(
                client=client,
                store=store,
                root=root,
                modalidade=modalidade,
                data_inicial=data_inicial,
                data_final=data_final,
                filt=filt,
                candidates_path=candidates_path,
                stats_path=stats_path,
            )
            totals["pages"] += result["pages"]
            totals["scanned"] += result["scanned"]
            totals["matched"] += result["matched"]
            totals["empty_windows"] += result["empty"]
            totals["skipped_complete"] += result["skipped"]

    _write_candidates_manifest(out_dir, candidates_path, totals)
    return totals


def filter_existing_publicacao(
    root: Path,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, int]:
    """Aplica o dicionário aos records.jsonl já descarregados (sem novos pedidos HTTP)."""
    filt = LexicalFilter(load_terms(default_terms_path(root)))
    out_dir = root / "data" / "raw" / "candidatas"
    out_dir.mkdir(parents=True, exist_ok=True)
    candidates_path = out_dir / "candidatas_from_existing.jsonl"
    if candidates_path.exists():
        candidates_path.unlink()

    start_api = to_api_date(parse_iso_date(start)) if start else None
    end_api = to_api_date(parse_iso_date(end)) if end else None

    scanned = 0
    matched = 0
    base = root / "data" / "raw" / "contratacoes" / "publicacao"
    for jsonl in sorted(base.glob("m*/????????_????????/records.jsonl")):
        window = jsonl.parent.name
        if "_" not in window:
            continue
        w_start, w_end = window.split("_", 1)
        if start_api and w_end < start_api:
            continue
        if end_api and w_start > end_api:
            continue
        with jsonl.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                rec = json.loads(line)
                scanned += 1
                result = filt.apply(rec)
                if not result.matched:
                    continue
                matched += 1
                enriched = {
                    **rec,
                    "_filtro": {
                        "matched": True,
                        "terms": [
                            {"id": h.term_id, "strength": h.strength, "match": h.match}
                            for h in result.hits
                        ],
                        "excluded_by": result.excluded_by,
                        "source_file": jsonl.relative_to(root).as_posix(),
                    },
                }
                with candidates_path.open("a", encoding="utf-8", newline="\n") as out:
                    out.write(json.dumps(enriched, ensure_ascii=False, separators=(",", ":")))
                    out.write("\n")

    totals = {"scanned": scanned, "matched": matched, "pages": 0, "empty_windows": 0, "skipped_complete": 0}
    _write_candidates_manifest(out_dir, candidates_path, totals, name="manifest_from_existing.json")
    return totals


def _scan_window(
    client: Any,
    store: RawStore,
    root: Path,
    modalidade: int,
    data_inicial: str,
    data_final: str,
    filt: LexicalFilter,
    candidates_path: Path,
    stats_path: Path,
) -> dict[str, int]:
    directory = (
        root
        / "data"
        / "raw"
        / "candidatas"
        / "checkpoints"
        / f"m{modalidade:02d}"
        / f"{data_inicial}_{data_final}"
    )
    directory.mkdir(parents=True, exist_ok=True)
    checkpoint = store.read_checkpoint(directory) or {}
    if checkpoint.get("complete") is True:
        return {
            "pages": 0,
            "scanned": 0,
            "matched": 0,
            "empty": 0,
            "skipped": 1,
        }

    pagina = int(checkpoint.get("last_completed_page", 0)) + 1
    scanned = int(checkpoint.get("scanned", 0))
    matched = int(checkpoint.get("matched", 0))
    pages = 0

    while True:
        status, body = client.fetch_publicacao(data_inicial, data_final, modalidade, pagina)
        pages += 1

        if status == 204 or not body.strip():
            _finish_window(
                store,
                directory,
                stats_path,
                modalidade,
                data_inicial,
                data_final,
                pagina,
                scanned,
                matched,
                empty=True,
            )
            return {"pages": pages, "scanned": scanned, "matched": matched, "empty": 1, "skipped": 0}

        payload = parse_envelope(body)
        if payload["numeroPagina"] != pagina:
            raise SchemaDivergence(
                f"Pedimos pagina={pagina} e a resposta trouxe numeroPagina={payload['numeroPagina']}."
            )

        page_matches = 0
        for rec in payload["data"]:
            scanned += 1
            result = filt.apply(rec)
            if not result.matched:
                continue
            matched += 1
            page_matches += 1
            enriched = {
                **rec,
                "_filtro": {
                    "matched": True,
                    "terms": [
                        {"id": h.term_id, "strength": h.strength, "match": h.match}
                        for h in result.hits
                    ],
                    "excluded_by": result.excluded_by,
                    "modalidade_query": modalidade,
                    "data_inicial": data_inicial,
                    "data_final": data_final,
                    "pagina": pagina,
                },
            }
            with candidates_path.open("a", encoding="utf-8", newline="\n") as out:
                out.write(json.dumps(enriched, ensure_ascii=False, separators=(",", ":")))
                out.write("\n")

        store.write_checkpoint(
            directory,
            {
                "modalidade": modalidade,
                "data_inicial": data_inicial,
                "data_final": data_final,
                "last_completed_page": pagina,
                "scanned": scanned,
                "matched": matched,
                "complete": False,
            },
        )
        LOG.info(
            "m%s %s–%s p%s: scanned+=%s matched_page=%s (acum scanned=%s matched=%s)",
            modalidade,
            data_inicial,
            data_final,
            pagina,
            len(payload["data"]),
            page_matches,
            scanned,
            matched,
        )

        if page_is_last(payload, pagina):
            empty = scanned == 0
            _finish_window(
                store,
                directory,
                stats_path,
                modalidade,
                data_inicial,
                data_final,
                pagina,
                scanned,
                matched,
                empty=empty,
            )
            return {
                "pages": pages,
                "scanned": scanned,
                "matched": matched,
                "empty": 1 if empty else 0,
                "skipped": 0,
            }
        pagina += 1


def _finish_window(
    store: RawStore,
    directory: Path,
    stats_path: Path,
    modalidade: int,
    data_inicial: str,
    data_final: str,
    pagina: int,
    scanned: int,
    matched: int,
    empty: bool,
) -> None:
    store.write_checkpoint(
        directory,
        {
            "modalidade": modalidade,
            "data_inicial": data_inicial,
            "data_final": data_final,
            "last_completed_page": pagina,
            "scanned": scanned,
            "matched": matched,
            "complete": True,
            "empty": empty,
        },
    )
    with stats_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(
                {
                    "modalidade": modalidade,
                    "data_inicial": data_inicial,
                    "data_final": data_final,
                    "pages_done": pagina,
                    "scanned": scanned,
                    "matched": matched,
                    "empty": empty,
                    "finished_at": utc_now(),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        handle.write("\n")


def _write_candidates_manifest(
    out_dir: Path,
    candidates_path: Path,
    totals: dict[str, int],
    name: str = "manifest.json",
) -> None:
    digest = sha256_bytes(candidates_path.read_bytes()) if candidates_path.is_file() else None
    payload = {
        "schema_version": 1,
        "updated_at": utc_now(),
        "candidates_file": candidates_path.name,
        "sha256": digest,
        "bytes": candidates_path.stat().st_size if candidates_path.is_file() else 0,
        "totals": totals,
        "note": (
            "Só candidatas lexicais. O universo foi varrido via API mas não foi "
            "persistido contrato a contrato; ver scan_stats.jsonl / totals.scanned."
        ),
    }
    (out_dir / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
