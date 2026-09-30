"""Coleta de contratações por data de publicação, com retoma por página."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from collect.dates import iter_chunks, parse_iso_date, to_api_date
from collect.envelope import SchemaDivergence, page_is_last, parse_envelope
from collect.store import RawStore

LOG = logging.getLogger("collect")


def collect_publicacao(
    config: dict[str, Any],
    root: Path,
    start: str,
    end: str,
    client: Any,
    store: RawStore | None = None,
    modalidades: list[int] | None = None,
    tamanho_pagina: int | None = None,
) -> dict[str, int]:
    store = store or RawStore(root)
    modalidades = modalidades if modalidades is not None else list(config["modalidades"])
    chunk_days = int(config["collect"]["chunk_days"])
    pause = float(config["http"]["pause_seconds"])
    totals = {"pages": 0, "records": 0, "empty_windows": 0, "skipped_complete": 0}

    for modalidade in modalidades:
        for chunk_start, chunk_end in iter_chunks(
            parse_iso_date(start), parse_iso_date(end), chunk_days
        ):
            data_inicial = to_api_date(chunk_start)
            data_final = to_api_date(chunk_end)
            result = _collect_window(
                client=client,
                store=store,
                root=root,
                modalidade=modalidade,
                data_inicial=data_inicial,
                data_final=data_final,
                pause=pause,
                tamanho_pagina=tamanho_pagina,
            )
            totals["pages"] += result["pages"]
            totals["records"] += result["records"]
            totals["empty_windows"] += result["empty"]
            totals["skipped_complete"] += result["skipped"]
    return totals


def collect_probe(config: dict[str, Any], root: Path, client: Any, store: RawStore | None = None) -> dict[str, int]:
    """Uma página, com as datas e a modalidade do exemplo do manual. Sem partir o intervalo."""
    store = store or RawStore(root)
    probe = config["probe"]
    data_inicial = to_api_date(parse_iso_date(probe["start"]))
    data_final = to_api_date(parse_iso_date(probe["end"]))
    result = _collect_window(
        client=client,
        store=store,
        root=root,
        modalidade=int(probe["modalidade"]),
        data_inicial=data_inicial,
        data_final=data_final,
        pause=0,
        tamanho_pagina=int(probe["tamanho_pagina"]),
        max_pages=1,
    )
    return {
        "pages": result["pages"],
        "records": result["records"],
        "empty_windows": result["empty"],
        "skipped_complete": result["skipped"],
    }


def _collect_window(
    client: Any,
    store: RawStore,
    root: Path,
    modalidade: int,
    data_inicial: str,
    data_final: str,
    pause: float,
    tamanho_pagina: int | None,
    max_pages: int | None = None,
) -> dict[str, int]:
    directory = store.page_dir(modalidade, data_inicial, data_final)
    checkpoint = store.read_checkpoint(directory) or {}
    if checkpoint.get("complete") is True:
        LOG.info("Janela já completa m%s %s–%s", modalidade, data_inicial, data_final)
        return {"pages": 0, "records": 0, "empty": 0, "skipped": 1}

    pagina, already_complete = _rebuild_from_pages(
        store, directory, modalidade, data_inicial, data_final
    )
    if already_complete or (max_pages is not None and pagina > max_pages):
        LOG.info("Nada a pedir em m%s %s–%s (próxima página %s).", modalidade, data_inicial, data_final, pagina)
        return {"pages": 0, "records": 0, "empty": 0, "skipped": 1}

    records_in_window = _count_jsonl(directory / "records.jsonl")
    pages_fetched = 0
    new_records = 0

    while max_pages is None or pages_fetched < max_pages:
        if pages_fetched > 0 and pause:
            time.sleep(pause)
        status, body = client.fetch_publicacao(
            data_inicial,
            data_final,
            modalidade,
            pagina,
            tamanho_pagina=tamanho_pagina,
        )
        page_file = store.page_path(modalidade, data_inicial, data_final, pagina)
        digest = store.write_page(page_file, body)
        relative = page_file.relative_to(root).as_posix()
        pages_fetched += 1

        if status == 204:
            store.remember(relative, digest, len(body), 0, status)
            _mark_complete(store, directory, modalidade, data_inicial, data_final, pagina, records_in_window)
            return {"pages": pages_fetched, "records": 0, "empty": 1, "skipped": 0}

        payload = parse_envelope(body)
        if payload["numeroPagina"] != pagina:
            raise SchemaDivergence(
                f"Pedimos pagina={pagina} e a resposta trouxe numeroPagina={payload['numeroPagina']}."
            )
        _guard_pagination(payload)

        n_records = store.append_jsonl(directory / "records.jsonl", payload["data"])
        records_in_window += n_records
        new_records += n_records
        store.remember(relative, digest, len(body), n_records, status)
        last = page_is_last(payload, pagina)
        store.write_checkpoint(
            directory,
            {
                "modalidade": modalidade,
                "data_inicial": data_inicial,
                "data_final": data_final,
                "last_completed_page": pagina,
                "records": records_in_window,
                "total_paginas": payload["totalPaginas"],
                "total_registros": payload["totalRegistros"],
                "complete": last,
            },
        )
        LOG.info(
            "m%s %s–%s página %s: %s registos (total anunciado %s)",
            modalidade,
            data_inicial,
            data_final,
            pagina,
            n_records,
            payload["totalRegistros"],
        )
        if last or (max_pages is not None and pages_fetched >= max_pages):
            empty = 1 if records_in_window == 0 else 0
            return {"pages": pages_fetched, "records": new_records, "empty": empty, "skipped": 0}
        pagina += 1

    return {"pages": pages_fetched, "records": new_records, "empty": 0, "skipped": 0}


def _guard_pagination(payload: dict[str, Any]) -> None:
    restantes = payload["paginasRestantes"]
    total = payload["totalPaginas"]
    empty = payload["empty"]
    if empty is True:
        return
    if not isinstance(restantes, int) or not isinstance(total, int):
        raise SchemaDivergence(
            "paginasRestantes e totalPaginas têm de ser inteiros quando empty não é true. "
            f"Recebido: paginasRestantes={restantes!r}, totalPaginas={total!r}."
        )


def _rebuild_from_pages(
    store: RawStore,
    directory: Path,
    modalidade: int,
    data_inicial: str,
    data_final: str,
) -> tuple[int, bool]:
    """Reconstrói o JSONL a partir dos corpos já gravados.

    Devolve a próxima página a pedir e se a janela já está completa.
    """
    pages = sorted(directory.glob("page-*.json"))
    jsonl_path = directory / "records.jsonl"
    if jsonl_path.exists():
        jsonl_path.unlink()
    next_page = 1
    records = 0
    complete = False
    for path in pages:
        pagina = int(path.stem.split("-")[1])
        if pagina != next_page:
            break
        body = path.read_bytes()
        if not body.strip():
            next_page += 1
            complete = True
            continue
        payload = parse_envelope(body)
        records += store.append_jsonl(jsonl_path, payload["data"])
        complete = page_is_last(payload, pagina)
        next_page += 1
    if next_page > 1:
        store.write_checkpoint(
            directory,
            {
                "modalidade": modalidade,
                "data_inicial": data_inicial,
                "data_final": data_final,
                "last_completed_page": next_page - 1,
                "records": records,
                "complete": complete,
            },
        )
    return next_page, complete


def _count_jsonl(path: Path) -> int:
    if not path.is_file():
        return 0
    with path.open(encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _mark_complete(
    store: RawStore,
    directory: Path,
    modalidade: int,
    data_inicial: str,
    data_final: str,
    pagina: int,
    records: int,
) -> None:
    previous = store.read_checkpoint(directory) or {}
    previous.update(
        {
            "modalidade": modalidade,
            "data_inicial": data_inicial,
            "data_final": data_final,
            "last_completed_page": pagina,
            "records": records,
            "complete": True,
        }
    )
    store.write_checkpoint(directory, previous)


def count_duplicate_ids(jsonl_paths: list[Path], id_field: str = "numeroControlePNCP") -> dict[str, int]:
    """Conta identificadores repetidos. Não apaga linhas do bruto."""
    seen: set[str] = set()
    duplicates = 0
    missing = 0
    rows = 0
    for path in jsonl_paths:
        if not path.is_file():
            continue
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                rows += 1
                record = json.loads(line)
                identifier = record.get(id_field)
                if not identifier:
                    missing += 1
                    continue
                if identifier in seen:
                    duplicates += 1
                else:
                    seen.add(identifier)
    return {"rows": rows, "unique_ids": len(seen), "duplicate_rows": duplicates, "missing_id": missing}
