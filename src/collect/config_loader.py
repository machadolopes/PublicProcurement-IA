"""Leitura de config.yaml. Os valores não são repetidos no código."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REQUIRED = (
    "window",
    "pilot",
    "probe",
    "api",
    "modalidades",
    "http",
    "collect",
    "seeds",
)


class ConfigError(ValueError):
    """config.yaml incompleto ou incoerente com o que o coletor sabe ler."""


def load_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"Não encontrei {path}. Execute a partir da raiz do repositório.")
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ConfigError("config.yaml não é um mapeamento.")
    missing = [key for key in REQUIRED if key not in data]
    if missing:
        raise ConfigError(f"Faltam chaves em config.yaml: {', '.join(missing)}")
    modalidades = data["modalidades"]
    if not isinstance(modalidades, list) or not modalidades:
        raise ConfigError("modalidades tem de ser uma lista não vazia.")
    if modalidades != sorted(modalidades) or any(not isinstance(m, int) or m < 1 for m in modalidades):
        raise ConfigError("modalidades tem de ser inteiros positivos em ordem crescente.")
    # Congelada em config.yaml a partir da lista viva (D013). Não editar sem atualizar decisions.md.
    if int(data["collect"]["chunk_days"]) < 1:
        raise ConfigError("collect.chunk_days tem de ser pelo menos 1.")
    return data


def repo_root_from(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "config.yaml").is_file():
            return candidate
    raise ConfigError("Não encontrei config.yaml a partir do diretório de trabalho.")
