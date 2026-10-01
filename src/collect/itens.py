"""Coleta de itens por contratação (API de Integração)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from collect.envelope import SchemaDivergence
from collect.store import RawStore

LOG = logging.getLogger("collect")


def parse_itens_body(body: bytes) -> list[dict[str, Any]]:
    """A resposta observada é uma lista JSON; o manual descrevia um objeto com chave itens."""
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SchemaDivergence(f"Corpo de itens não é JSON UTF-8: {exc}") from exc
    if isinstance(payload, list):
        if payload and not isinstance(payload[0], dict):
            raise SchemaDivergence("Lista de itens com elemento que não é objeto.")
        return payload
    if isinstance(payload, dict):
        if "itens" in payload and isinstance(payload["itens"], list):
            return payload["itens"]
        if "data" in payload and isinstance(payload["data"], list):
            return payload["data"]
    raise SchemaDivergence(
        "Formato de itens inesperado: esperado lista ou objeto com chave itens/data."
    )


def iter_contratacoes_from_raw(root: Path, start_api: str, end_api: str):
    """Percorre records.jsonl das janelas cujo intervalo diário está dentro de [start_api, end_api]."""
    base = root / "data" / "raw" / "contratacoes" / "publicacao"
    if not base.is_dir():
        return
    for jsonl in sorted(base.glob("m*/????_????/records.jsonl")):
        window = jsonl.parent.name  # AAAAMMDD_AAAAMMDD
        if "_" not in window:
            continue
        w_start, w_end = window.split("_", 1)
        if w_end < start_api or w_start > end_api:
            continue
        with jsonl.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


def collect_itens_for_period(
    config: dict[str, Any],
    root: Path,
    start_iso: str,
    end_iso: str,
    client: Any,
    store: RawStore | None = None,
) -> dict[str, int]:
    from collect.dates import parse_iso_date, to_api_date

    store = store or RawStore(root)
    start_api = to_api_date(parse_iso_date(start_iso))
    end_api = to_api_date(parse_iso_date(end_iso))
    totals = {
        "contratacoes": 0,
        "pages": 0,
        "itens": 0,
        "sem_chave": 0,
        "erros": 0,
        "skipped_complete": 0,
    }

    for rec in iter_contratacoes_from_raw(root, start_api, end_api):
        cnpj = ((rec.get("orgaoEntidade") or {}).get("cnpj")) or ""
        ano = rec.get("anoCompra")
        sequencial = rec.get("sequencialCompra")
        controle = rec.get("numeroControlePNCP") or f"{cnpj}-{ano}-{sequencial}"
        if not cnpj or ano is None or sequencial is None:
            totals["sem_chave"] += 1
            LOG.warning("Contratação sem chave de itens: %s", controle)
            continue
        totals["contratacoes"] += 1
        result = _collect_itens_one(
            client=client,
            store=store,
            root=root,
            cnpj=str(cnpj),
            ano=int(ano),
            sequencial=int(sequencial),
            controle=str(controle),
        )
        totals["pages"] += result["pages"]
        totals["itens"] += result["itens"]
        totals["erros"] += result["erros"]
        totals["skipped_complete"] += result["skipped"]
    return totals


def _collect_itens_one(
    client: Any,
    store: RawStore,
    root: Path,
    cnpj: str,
    ano: int,
    sequencial: int,
    controle: str,
) -> dict[str, int]:
    directory = (
        root
        / "data"
        / "raw"
        / "itens"
        / f"cnpj_{cnpj}"
        / f"{ano}_{sequencial:06d}"
    )
    directory.mkdir(parents=True, exist_ok=True)
    checkpoint = store.read_checkpoint(directory) or {}
    if checkpoint.get("complete") is True:
        return {"pages": 0, "itens": 0, "erros": 0, "skipped": 1}

    pagina = 1
    pages = 0
    itens = 0
    jsonl_path = directory / "records.jsonl"
    if jsonl_path.exists():
        jsonl_path.unlink()

    while True:
        try:
            status, body = client.fetch_itens(cnpj, ano, sequencial, pagina=pagina)
        except Exception:
            LOG.exception("Erro ao pedir itens %s página %s", controle, pagina)
            store.write_checkpoint(
                directory,
                {
                    "cnpj": cnpj,
                    "ano": ano,
                    "sequencial": sequencial,
                    "numeroControlePNCP": controle,
                    "last_completed_page": pagina - 1,
                    "itens": itens,
                    "complete": False,
                    "error": True,
                },
            )
            return {"pages": pages, "itens": itens, "erros": 1, "skipped": 0}

        page_file = directory / f"page-{pagina:05d}.json"
        digest = store.write_page(page_file, body)
        relative = page_file.relative_to(root).as_posix()
        pages += 1

        if status == 204 or not body.strip():
            store.remember(relative, digest, len(body), 0, status)
            store.write_checkpoint(
                directory,
                {
                    "cnpj": cnpj,
                    "ano": ano,
                    "sequencial": sequencial,
                    "numeroControlePNCP": controle,
                    "last_completed_page": pagina,
                    "itens": itens,
                    "complete": True,
                },
            )
            return {"pages": pages, "itens": itens, "erros": 0, "skipped": 0}

        try:
            records = parse_itens_body(body)
        except SchemaDivergence:
            LOG.error("Formato de itens divergente em %s; corpo gravado.", relative)
            raise

        n = store.append_jsonl(jsonl_path, records)
        itens += n
        store.remember(relative, digest, len(body), n, status)

        # Sem envelope de paginação no corpo observado: se a página veio vazia ou
        # com menos itens que o tamanho pedido, paramos. tamanhoPagina=500.
        if len(records) == 0 or len(records) < 500:
            store.write_checkpoint(
                directory,
                {
                    "cnpj": cnpj,
                    "ano": ano,
                    "sequencial": sequencial,
                    "numeroControlePNCP": controle,
                    "last_completed_page": pagina,
                    "itens": itens,
                    "complete": True,
                },
            )
            LOG.info("Itens %s: %s itens em %s página(s)", controle, itens, pages)
            return {"pages": pages, "itens": itens, "erros": 0, "skipped": 0}
        pagina += 1
