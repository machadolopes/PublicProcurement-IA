"""Ponto de entrada: python -m collect ..."""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import sys
from pathlib import Path

from collect import __version__
from collect.candidatas import collect_candidatas, filter_existing_publicacao
from collect.client import ConsultaClient
from collect.config_loader import load_config, repo_root_from
from collect.itens import collect_itens_for_period
from collect.publicacao import collect_probe, collect_publicacao
from collect.search_ia import collect_search_ia
from collect.store import RawStore, sha256_bytes, utc_now


def _configure_log(root: Path) -> None:
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "collect.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def _require_hashseed(config: dict) -> None:
    expected = str(config["seeds"]["pythonhashseed"])
    found = os.environ.get("PYTHONHASHSEED")
    if found != expected:
        raise SystemExit(
            f"PYTHONHASHSEED está {found!r} e config.yaml pede {expected!r}. "
            "No PowerShell: $env:PYTHONHASHSEED = "
            f"'{expected}'; python -m collect ..."
        )


def _write_run_manifest(root: Path, profile: str, config: dict, totals: dict) -> None:
    outputs = root / "outputs" / "json"
    outputs.mkdir(parents=True, exist_ok=True)
    config_bytes = (root / "config.yaml").read_bytes()
    payload = {
        "schema_version": 1,
        "finished_at": utc_now(),
        "profile": profile,
        "package_version": __version__,
        "python": sys.version,
        "platform": platform.platform(),
        "seeds": config["seeds"],
        "config_sha256": sha256_bytes(config_bytes),
        "totals": totals,
    }
    path = outputs / f"run_manifest_{profile}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run_publicacao(profile: str, start: str, end: str, modalidade: int | None) -> int:
    root = repo_root_from(Path.cwd())
    config = load_config(root / "config.yaml")
    _require_hashseed(config)
    _configure_log(root)
    modalidades = [modalidade] if modalidade is not None else None
    store = RawStore(root)
    try:
        with ConsultaClient(config) as client:
            if profile == "probe":
                totals = collect_probe(config, root, client, store)
            else:
                totals = collect_publicacao(
                    config,
                    root,
                    start,
                    end,
                    client,
                    store,
                    modalidades=modalidades,
                )
    except Exception:
        logging.getLogger("collect").exception("Coleta interrompida.")
        return 1
    _write_run_manifest(root, profile, config, totals)
    logging.getLogger("collect").info("Totais: %s", totals)
    return 0


def _run_candidatas(profile: str, start: str, end: str) -> int:
    root = repo_root_from(Path.cwd())
    config = load_config(root / "config.yaml")
    _require_hashseed(config)
    _configure_log(root)
    store = RawStore(root)
    try:
        with ConsultaClient(config) as client:
            totals = collect_candidatas(config, root, start, end, client, store)
    except Exception:
        logging.getLogger("collect").exception("Coleta de candidatas interrompida.")
        return 1
    _write_run_manifest(root, profile, config, totals)
    logging.getLogger("collect").info("Totais candidatas: %s", totals)
    return 0


def _run_itens(profile: str, start: str, end: str) -> int:
    root = repo_root_from(Path.cwd())
    config = load_config(root / "config.yaml")
    _require_hashseed(config)
    _configure_log(root)
    store = RawStore(root)
    try:
        with ConsultaClient(config) as client:
            totals = collect_itens_for_period(config, root, start, end, client, store)
    except Exception:
        logging.getLogger("collect").exception("Coleta de itens interrompida.")
        return 1
    _write_run_manifest(root, profile, config, totals)
    logging.getLogger("collect").info("Totais itens: %s", totals)
    return 0


def _run_filter_existing(start: str | None, end: str | None) -> int:
    root = repo_root_from(Path.cwd())
    config = load_config(root / "config.yaml")
    _require_hashseed(config)
    _configure_log(root)
    totals = filter_existing_publicacao(root, start=start, end=end)
    _write_run_manifest(root, "filter-existing", config, totals)
    logging.getLogger("collect").info("Filtro sobre bruto existente: %s", totals)
    return 0


def _run_search_ia(profile: str, start: str, end: str) -> int:
    root = repo_root_from(Path.cwd())
    config = load_config(root / "config.yaml")
    _require_hashseed(config)
    _configure_log(root)
    store = RawStore(root)
    try:
        with ConsultaClient(config) as client:
            totals = collect_search_ia(config, root, start, end, client, store)
    except Exception:
        logging.getLogger("collect").exception("Coleta search-ia interrompida.")
        return 1
    _write_run_manifest(root, profile, config, totals)
    logging.getLogger("collect").info("Totais search-ia: %s", totals)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Coleta de contratações no PNCP.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("probe", help="Uma página, com as datas do exemplo oficial.")
    sub.add_parser(
        "pilot",
        help="(legado) Cabeçalhos de TODAS as compras do mês piloto — preferir pilot-ia.",
    )
    sub.add_parser(
        "pilot-ia",
        help="Varre o mês piloto e GRAVA SÓ candidatas cujo objeto casa com termos de IA.",
    )
    sub.add_parser(
        "filter-existing",
        help="Aplica o dicionário de IA aos records.jsonl já descarregados (sem HTTP).",
    )
    sub.add_parser(
        "pilot-itens",
        help="Itens das contratações candidatas já coletadas no mês piloto.",
    )

    full = sub.add_parser("publicacao", help="(legado) Cabeçalhos sem filtro de IA.")
    full.add_argument("--start", default=None)
    full.add_argument("--end", default=None)
    full.add_argument("--modalidade", type=int, default=None)

    ia = sub.add_parser("candidatas", help="Varredura com filtro de IA num intervalo.")
    ia.add_argument("--start", default=None)
    ia.add_argument("--end", default=None)

    search = sub.add_parser(
        "search-ia",
        help="Busca textual do portal (/api/search/) com queries de IA; grava hits únicos.",
    )
    search.add_argument("--start", default=None, help="AAAA-MM-DD (default: window.start)")
    search.add_argument("--end", default=None, help="AAAA-MM-DD (default: window.end)")

    args = parser.parse_args(argv)
    root = repo_root_from(Path.cwd())
    config = load_config(root / "config.yaml")

    if args.command == "probe":
        return _run_publicacao(
            "probe",
            config["probe"]["start"],
            config["probe"]["end"],
            int(config["probe"]["modalidade"]),
        )
    if args.command == "pilot":
        return _run_publicacao("pilot", config["pilot"]["start"], config["pilot"]["end"], None)
    if args.command == "pilot-ia":
        return _run_candidatas("pilot-ia", config["pilot"]["start"], config["pilot"]["end"])
    if args.command == "candidatas":
        return _run_candidatas(
            "candidatas",
            args.start or config["window"]["start"],
            args.end or config["window"]["end"],
        )
    if args.command == "search-ia":
        return _run_search_ia(
            "search-ia",
            args.start or config["window"]["start"],
            args.end or config["window"]["end"],
        )
    if args.command == "filter-existing":
        return _run_filter_existing(config["pilot"]["start"], config["pilot"]["end"])
    if args.command == "pilot-itens":
        return _run_itens("pilot-itens", config["pilot"]["start"], config["pilot"]["end"])
    if args.command == "publicacao":
        return _run_publicacao(
            "publicacao",
            args.start or config["window"]["start"],
            args.end or config["window"]["end"],
            args.modalidade,
        )
    parser.error(f"Comando desconhecido: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
