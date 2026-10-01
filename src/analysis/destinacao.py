"""Corpus de destinação e classificação por regras.

Só contratos. A descrição tem de conter o léxico de inclusão.
A primeira classe que casa em ``destinacao_rules.yaml`` é a classe primária.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import yaml

RULES_PATH = Path(__file__).with_name("destinacao_rules.yaml")
CLASSIFIER_VERSION = "destinacao-2"


def fold(text: str | None) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return stripped.lower()


@dataclass(frozen=True)
class Rule:
    id: str
    rotulo: str
    priority: int
    definicao: str
    compiled: tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class Ruleset:
    schema_version: int
    inclusao: tuple[tuple[str, re.Pattern[str]], ...]
    classes: tuple[Rule, ...]
    sha256: str

    def phrases_in(self, folded: str) -> list[str]:
        return [pid for pid, pattern in self.inclusao if pattern.search(folded)]

    def classes_in(self, folded: str) -> list[str]:
        return [rule.id for rule in self.classes if any(p.search(folded) for p in rule.compiled)]


def load_rules(path: Path | None = None) -> Ruleset:
    path = path or RULES_PATH
    raw_bytes = path.read_bytes()
    data = yaml.safe_load(raw_bytes)
    inclusao = tuple(
        (item["id"], re.compile(item["pattern"])) for item in data["inclusao"]
    )
    classes = []
    for item in data["classes"]:
        classes.append(
            Rule(
                id=item["id"],
                rotulo=item["rotulo"],
                priority=int(item["priority"]),
                definicao=" ".join(str(item.get("definicao", "")).split()),
                compiled=tuple(re.compile(p) for p in item.get("patterns") or []),
            )
        )
    classes.sort(key=lambda rule: rule.priority)
    return Ruleset(
        schema_version=int(data["schema_version"]),
        inclusao=inclusao,
        classes=tuple(classes),
        sha256=hashlib.sha256(raw_bytes).hexdigest(),
    )


def classify(folded: str, rules: Ruleset) -> tuple[str, list[str], str | None]:
    atingidas: list[str] = []
    padrao: str | None = None
    for rule in rules.classes:
        for pattern in rule.compiled:
            if pattern.search(folded):
                atingidas.append(rule.id)
                if padrao is None:
                    padrao = pattern.pattern
                break
    if not atingidas:
        return "residual", [], None
    return atingidas[0], atingidas, padrao


def _positive(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value <= 0:
        return None
    return float(value)


def _compra_de_contrato(doc: dict) -> str | None:
    numero = doc.get("numero_contratacao")
    if isinstance(numero, str) and numero.strip():
        return numero.strip()
    return None


def _ano(doc: dict) -> str:
    raw = doc.get("data_publicacao_pncp")
    if isinstance(raw, str) and len(raw) >= 4 and raw[:4].isdigit():
        return raw[:4]
    return ""


def _modalidade(doc: dict) -> str:
    nome = doc.get("modalidade_licitacao_nome")
    if isinstance(nome, str) and nome.strip():
        return nome.strip()
    return "Não informada"


def montar_corpus(hits_path: Path, rules: Ruleset) -> tuple[list[dict], dict]:
    """Devolve contratos deduplicados e as contagens de cada etapa.

    Documentos que não são contrato são ignorados (não entram no corpus).
    """
    por_controle: dict[str, dict] = {}
    lidos = 0
    contratos_lidos = 0
    com_frase = 0
    for line in hits_path.open(encoding="utf-8"):
        if not line.strip():
            continue
        lidos += 1
        doc = json.loads(line)
        if doc.get("document_type") != "contrato":
            continue
        contratos_lidos += 1
        desc = doc.get("description") if isinstance(doc.get("description"), str) else ""
        folded = fold(desc)
        frases = rules.phrases_in(folded)
        if not frases:
            continue
        com_frase += 1
        controle = str(doc.get("numero_controle_pncp") or "")
        if not controle:
            continue
        row = {
            "chave": f"C:{controle}",
            "numero_controle_pncp": controle,
            "document_type": "contrato",
            "ano": _ano(doc),
            "uf": doc.get("uf") or "",
            "esfera_nome": doc.get("esfera_nome") or "",
            "modalidade": _modalidade(doc),
            "orgao_nome": doc.get("orgao_nome") or "",
            "municipio_nome": doc.get("municipio_nome") or "",
            "description": desc,
            "folded": folded,
            "frases": frases,
            "valor": _positive(doc.get("valor_global")),
            "n_caracteres": len(desc),
            "numero_contratacao": _compra_de_contrato(doc) or "",
        }
        atual = por_controle.get(controle)
        if atual is None or row["n_caracteres"] > atual["n_caracteres"]:
            por_controle[controle] = row

    registros = list(por_controle.values())
    for row in registros:
        primaria, atingidas, padrao = classify(row["folded"], rules)
        row["classe_primaria"] = primaria
        row["classes_atingidas"] = atingidas
        row["padrao_primario"] = padrao
        row.pop("folded")
    registros.sort(key=lambda row: (row["ano"], row["uf"], row["numero_controle_pncp"]))
    fluxo = {
        "documentos_lidos": lidos,
        "contratos_lidos": contratos_lidos,
        "contratos_com_lexico_na_descricao": com_frase,
        "contratos_apos_deduplicacao": len(registros),
    }
    return registros, fluxo
