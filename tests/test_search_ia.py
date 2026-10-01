import json

import httpx

from collect.client import ConsultaClient
from collect.search_ia import collect_search_ia
from collect.store import RawStore


def _config(tmp_path) -> dict:
    return {
        "api": {
            "consulta_base_url": "https://pncp.gov.br/api/consulta",
            "integracao_base_url": "https://pncp.gov.br/api/pncp",
            "search_base_url": "https://pncp.gov.br/api/search/",
            "publicacao_path": "/v1/contratacoes/publicacao",
        },
        "http": {
            "timeout_seconds": 5,
            "pause_seconds": 0,
            "max_retries": 1,
            "backoff_initial_seconds": 0,
            "backoff_max_seconds": 0,
            "tamanho_pagina_publicacao": 50,
            "user_agent": "teste",
            "accept": "application/json",
        },
        "search": {
            "status": "todos",
            "ordenacao": "-data",
            "tam_pagina": 2,
            "queries_path": str(tmp_path / "queries.yaml"),
        },
    }


def test_fetch_search_parametros(tmp_path):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"items": [], "total": 0})

    with ConsultaClient(_config(tmp_path), transport=httpx.MockTransport(handler)) as client:
        status, body = client.fetch_search(
            "inteligencia artificial",
            1,
            tipos_documento="edital",
            data_inicio="2021-01-01",
            data_fim="2026-09-30",
        )
    assert status == 200
    assert "q=inteligencia" in seen["url"] or "q=inteligencia+artificial" in seen["url"]
    assert "tipos_documento=edital" in seen["url"]
    assert "pagina=1" in seen["url"]
    assert "data_inicio=2021-01-01" in seen["url"]
    assert "data_fim=2026-09-30" in seen["url"]
    assert "/api/search/" in seen["url"]
    assert json.loads(body)["total"] == 0


def test_collect_search_ia_dedupe(tmp_path):
    (tmp_path / "queries.yaml").write_text(
        """
schema_version: 1
document_types: [edital]
queries:
  - id: ia
    q: "inteligencia artificial"
  - id: ml
    q: "machine learning"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    shared = {
        "numero_controle_pncp": "11111111000111-1-000001/2026",
        "description": "Solucao de inteligencia artificial",
        "document_type": "edital",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        q = request.url.params.get("q", "")
        if "inteligencia" in q:
            return httpx.Response(200, json={"items": [shared], "total": 1})
        if "machine" in q:
            # Mesmo controlo — deve deduplicar
            return httpx.Response(200, json={"items": [shared], "total": 1})
        return httpx.Response(200, json={"items": [], "total": 0})

    root = tmp_path / "repo"
    root.mkdir()
    (root / "data" / "raw").mkdir(parents=True)
    config = _config(tmp_path)
    store = RawStore(root)
    with ConsultaClient(config, transport=httpx.MockTransport(handler)) as client:
        totals = collect_search_ia(config, root, "2021-01-01", "2026-09-30", client, store)

    hits = (root / "data" / "raw" / "candidatas_search" / "hits.jsonl").read_text(encoding="utf-8")
    lines = [line for line in hits.splitlines() if line.strip()]
    assert len(lines) == 1
    assert totals["hits_new"] == 1
    assert totals["hits_raw"] == 2
