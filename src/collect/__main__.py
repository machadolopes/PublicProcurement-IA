"""Ponto de entrada: python -m collect probe | pilot | publicacao."""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import sys
from pathlib import Path

from collect import __version__
from collect.client import ConsultaClient
from collect.config_loader import load_config, repo_root_from
from collect.publicacao import collect_probe, collect_publicacao
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


def _run(profile: str, start: str, end: str, modalidade: int | None) -> int:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Coleta de contratações no PNCP.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("probe", help="Uma página, com as datas do exemplo oficial.")
    sub.add_parser("pilot", help="Cabeçalhos do mês piloto, todas as modalidades.")

    full = sub.add_parser("publicacao", help="Cabeçalhos num intervalo do config ou indicado.")
    full.add_argument("--start", default=None)
    full.add_argument("--end", default=None)
    full.add_argument("--modalidade", type=int, default=None)

    args = parser.parse_args(argv)
    root = repo_root_from(Path.cwd())
    config = load_config(root / "config.yaml")

    if args.command == "probe":
        return _run(
            "probe",
            config["probe"]["start"],
            config["probe"]["end"],
            int(config["probe"]["modalidade"]),
        )
    if args.command == "pilot":
        return _run("pilot", config["pilot"]["start"], config["pilot"]["end"], None)
    return _run(
        "publicacao",
        args.start or config["window"]["start"],
        args.end or config["window"]["end"],
        args.modalidade,
    )


if __name__ == "__main__":
    raise SystemExit(main())
