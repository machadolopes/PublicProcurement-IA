import httpx

from collect.client import RETRY_STATUS, ApiError, ConsultaClient, _should_retry


def _config() -> dict:
    return {
        "api": {
            "consulta_base_url": "https://pncp.gov.br/api/consulta",
            "integracao_base_url": "https://pncp.gov.br/api/pncp",
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
    }


def test_parametros_sao_os_do_manual():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["accept"] = request.headers["Accept"]
        return httpx.Response(204)

    transport = httpx.MockTransport(handler)
    with ConsultaClient(_config(), transport=transport) as client:
        status, body = client.fetch_publicacao("20230801", "20230802", 8, 1, tamanho_pagina=10)
    assert status == 204
    assert body == b""
    assert "dataInicial=20230801" in seen["url"]
    assert "dataFinal=20230802" in seen["url"]
    assert "codigoModalidadeContratacao=8" in seen["url"]
    assert "pagina=1" in seen["url"]
    assert "tamanhoPagina=10" in seen["url"]
    assert seen["accept"] == "application/json"
    assert "/v1/contratacoes/publicacao" in seen["url"]


def test_user_agent_do_config_e_ascii():
    from pathlib import Path

    from collect.config_loader import load_config

    config = load_config(Path("config.yaml"))
    config["http"]["max_retries"] = 1
    with ConsultaClient(config, transport=httpx.MockTransport(lambda request: httpx.Response(204))) as client:
        client._client.headers["user-agent"].encode("ascii")


def test_429_repete():
    assert _should_retry(ApiError(429, b"limite", "http://exemplo")) is True
    assert 429 in RETRY_STATUS


def test_400_nao_repete():
    assert _should_retry(ApiError(400, b"erro", "http://exemplo")) is False
    assert _should_retry(ApiError(422, b"erro", "http://exemplo")) is False
    assert _should_retry(ApiError(500, b"erro", "http://exemplo")) is True
    assert 500 in RETRY_STATUS
