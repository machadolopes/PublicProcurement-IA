"""Páginas sintéticas com o envelope da secção 4.2. Não são respostas do PNCP."""

from __future__ import annotations

import json


def page(numero: int, total_paginas: int, registros: list[dict], total_registros: int | None = None) -> bytes:
    restantes = total_paginas - numero
    payload = {
        "data": registros,
        "totalRegistros": total_registros if total_registros is not None else len(registros) * total_paginas,
        "totalPaginas": total_paginas,
        "numeroPagina": numero,
        "paginasRestantes": restantes,
        "empty": len(registros) == 0,
    }
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def contratacao(controle: str, objeto: str = "objeto sintético") -> dict:
    return {"numeroControlePNCP": controle, "objetoCompra": objeto}
