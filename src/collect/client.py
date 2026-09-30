"""Cliente HTTP da API de Consulta.

Só envia parâmetros que o Manual das APIs de Consultas, secção 6.3, nomeia.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

RETRY_STATUS = {500, 502, 503, 504}


class ApiError(RuntimeError):
    """A API respondeu com um erro que não deve ser repetido às cegas."""

    def __init__(self, status: int, body: bytes, url: str) -> None:
        self.status = status
        self.body = body
        self.url = url
        preview = body[:500].decode("utf-8", errors="replace")
        super().__init__(f"HTTP {status} em {url}: {preview}")


def _should_retry(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException)):
        return True
    return isinstance(exc, ApiError) and exc.status in RETRY_STATUS


class ConsultaClient:
    def __init__(self, config: dict[str, Any], transport: httpx.BaseTransport | None = None) -> None:
        http = config["http"]
        self.base_url = config["api"]["consulta_base_url"].rstrip("/") + "/"
        self.publicacao_path = config["api"]["publicacao_path"]
        self.timeout = float(http["timeout_seconds"])
        self.pause_seconds = float(http["pause_seconds"])
        self.tamanho_pagina = int(http["tamanho_pagina_publicacao"])
        self._max_retries = int(http["max_retries"])
        self._backoff_initial = float(http["backoff_initial_seconds"])
        self._backoff_max = float(http["backoff_max_seconds"])
        self._client = httpx.Client(
            timeout=self.timeout,
            headers={
                "User-Agent": http["user_agent"],
                "Accept": http["accept"],
            },
            transport=transport,
            follow_redirects=False,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ConsultaClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def fetch_publicacao(
        self,
        data_inicial: str,
        data_final: str,
        modalidade: int,
        pagina: int,
        tamanho_pagina: int | None = None,
    ) -> tuple[int, bytes]:
        params = {
            "dataInicial": data_inicial,
            "dataFinal": data_final,
            "codigoModalidadeContratacao": modalidade,
            "pagina": pagina,
            "tamanhoPagina": self.tamanho_pagina if tamanho_pagina is None else tamanho_pagina,
        }
        url = urljoin(self.base_url, self.publicacao_path.lstrip("/"))
        return self._get(url, params)

    def _get(self, url: str, params: dict[str, Any]) -> tuple[int, bytes]:
        retrying = retry(
            retry=retry_if_exception(_should_retry),
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=self._backoff_initial, max=self._backoff_max),
            reraise=True,
        )
        return retrying(self._get_once)(url, params)

    def _get_once(self, url: str, params: dict[str, Any]) -> tuple[int, bytes]:
        try:
            response = self._client.get(url, params=params)
        except (httpx.TransportError, httpx.TimeoutException):
            raise
        body = response.content
        if response.status_code in (200, 204):
            return response.status_code, body
        raise ApiError(response.status_code, body, str(response.url))
