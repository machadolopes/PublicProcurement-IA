"""Filtro lexical de recall sobre o objeto da contratação."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class TermHit:
    term_id: str
    strength: str
    match: str


@dataclass
class FilterResult:
    matched: bool
    hits: list[TermHit] = field(default_factory=list)
    excluded_by: list[str] = field(default_factory=list)
    haystack: str = ""


def normalize_text(value: str) -> str:
    """NFKC + casefold + remoção de diacríticos (ç→c, ê→e) para padrões ASCII."""
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.casefold()


def load_terms(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"terms.yaml inválido: {path}")
    return data


class LexicalFilter:
    def __init__(self, terms: dict[str, Any]) -> None:
        self.fields = list(terms.get("search_fields") or ["objetoCompra"])
        self._strong = self._compile(terms.get("strong") or [], "strong")
        self._ambiguous = self._compile(terms.get("ambiguous") or [], "ambiguous")
        self._exclusions = [
            (item["id"], re.compile(item["pattern"], re.IGNORECASE | re.UNICODE))
            for item in (terms.get("exclusions") or [])
        ]

    @staticmethod
    def _compile(items: list[dict[str, Any]], strength: str) -> list[tuple[str, str, re.Pattern[str]]]:
        compiled = []
        for item in items:
            compiled.append(
                (
                    item["id"],
                    strength,
                    re.compile(item["pattern"], re.IGNORECASE | re.UNICODE),
                )
            )
        return compiled

    def field_texts(self, record: dict[str, Any]) -> list[str]:
        """Normaliza cada campo à parte — evita falso positivo na junção (ex.: '... I' + 'A ...')."""
        texts: list[str] = []
        for name in self.fields:
            value = record.get(name)
            if value:
                normalized = normalize_text(str(value))
                if normalized:
                    texts.append(normalized)
        return texts

    def haystack_from_record(self, record: dict[str, Any]) -> str:
        return " | ".join(self.field_texts(record))

    def apply(self, record: dict[str, Any]) -> FilterResult:
        texts = self.field_texts(record)
        haystack = " | ".join(texts)
        if not texts:
            return FilterResult(matched=False, haystack=haystack)

        excluded: list[str] = []
        for text in texts:
            for eid, pattern in self._exclusions:
                if pattern.search(text) and eid not in excluded:
                    excluded.append(eid)

        hits: list[TermHit] = []
        for text in texts:
            for term_id, strength, pattern in self._strong:
                for match in pattern.finditer(text):
                    span = match.group(0)
                    if self._blocked(term_id, span, text, excluded):
                        continue
                    hits.append(TermHit(term_id=term_id, strength=strength, match=span))

            for term_id, strength, pattern in self._ambiguous:
                if excluded:
                    continue
                for match in pattern.finditer(text):
                    span = match.group(0)
                    if self._context_rejects_ambiguous(term_id, match, text):
                        continue
                    hits.append(TermHit(term_id=term_id, strength=strength, match=span))

        # Deduplicar por term_id mantendo a primeira ocorrência.
        seen: set[str] = set()
        unique: list[TermHit] = []
        for hit in hits:
            if hit.term_id in seen:
                continue
            seen.add(hit.term_id)
            unique.append(hit)

        return FilterResult(
            matched=bool(unique),
            hits=unique,
            excluded_by=excluded,
            haystack=haystack,
        )

    def _blocked(self, term_id: str, span: str, haystack: str, excluded: list[str]) -> bool:
        if term_id == "inteligencia_artificial" and "inseminacao_artificial" in excluded:
            # "inseminação artificial" não deve acionar inteligência artificial.
            if "insemina" in haystack and "artificial" in span:
                return True
        if "inteligencia_policial" in excluded and term_id == "inteligencia_artificial":
            # Só bloqueia se "artificial" não estiver junto — a exclusão é outra expressão.
            return False
        return False

    def _context_rejects_ambiguous(self, term_id: str, match: re.Match[str], haystack: str) -> bool:
        start, end = match.span()
        window = haystack[max(0, start - 40) : min(len(haystack), end + 40)]
        if term_id in {"sigla_ia", "sigla_ai"}:
            if "insemina" in window:
                return True
            if "instituto" in window and "artificial" not in window:
                return True
            if "intelig" in window and "artificial" not in window:
                return True
            if "anexo" in window:
                return True
            if re.search(r"\bia\s+e\s+ib\b", window):
                return True
            # Exige vizinhança tecnológica — a sigla isolada é ruído demais.
            tech = (
                r"artificial|generativ|aprendizado|aprendizagem|machine|deep\s*learning|"
                r"llm|gpt|modelo|algoritm|software|sistema|solucao|tecnolog|dados|"
                r"monitoramento|camera|insight|processamento|nucleos?|inovador|"
                r"chatbot|copilot|openai|azure|cloud|analytics|predit"
            )
            wider = haystack[max(0, start - 80) : min(len(haystack), end + 80)]
            if not re.search(tech, wider):
                return True
        if term_id == "sigla_ai":
            if re.search(r"e\.?\s*t\.?\s*a\.?\s*i\b|eta\s*i\b", window):
                return True
        if term_id == "rpa":
            if re.search(r"drone|aeronave|remotamente\s+pilotad|vant\b|uas\b", window):
                return True
        if term_id == "claude" and "antropic" not in window and "llm" not in window and "modelo" not in window:
            # Nome próprio sem contexto de modelo — descartar na camada ambígua.
            return True
        if term_id == "gemini" and "google" not in window and "llm" not in window and "modelo" not in window:
            return True
        return False


def default_terms_path(root: Path) -> Path:
    return root / "src" / "filter" / "terms.yaml"
