"""Cliente HTTP: API de Consulta (listagens) e API de Integração (itens)."""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urljoin

import httpx
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

RETRY_STATUS = {429, 500, 502, 503, 504}
LOG = logging.getLogger("collect")


class ApiError(RuntimeError):
    """A API respondeu com um erro que não deve ser repetido às cegas."""

    def __init__(self, status: int, body: bytes, url: str, retry_after: float | None = None) -> None:
        self.status = status
        self.body = body
        self.url = url
        self.retry_after = retry_after
        preview = body[:500].decode("utf-8", errors="replace")
        super().__init__(f"HTTP {status} em {url}: {preview}")


def _should_retry(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException)):
        return True
    return isinstance(exc, ApiError) and exc.status in RETRY_STATUS


def _wait_for_retry(retry_state: RetryCallState) -> float:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if isinstance(exc, ApiError) and exc.status == 429:
        if exc.retry_after is not None:
            return max(exc.retry_after, 5.0)
        # O HTML do PNCP só diz "aguarde alguns instantes"; não publica o número.
        return 30.0 * (2 ** max(retry_state.attempt_number - 1, 0))
    return wait_exponential(multiplier=1, max=60)(retry_state)


class PncpClient:
    def __init__(self, config: dict[str, Any], transport: httpx.BaseTransport | None = None) -> None:
        http = config["http"]
        self.consulta_base = config["api"]["consulta_base_url"].rstrip("/") + "/"
        self.integracao_base = config["api"]["integracao_base_url"].rstrip("/") + "/"
        search_base = config["api"].get("search_base_url") or "https://pncp.gov.br/api/search/"
        self.search_base = search_base if search_base.endswith("/") else search_base + "/"
        self.publicacao_path = config["api"]["publicacao_path"]
        self.timeout = float(http["timeout_seconds"])
        self.pause_seconds = float(http["pause_seconds"])
        self.tamanho_pagina = int(http["tamanho_pagina_publicacao"])
        search_cfg = config.get("search") or {}
        self.search_tam_pagina = int(search_cfg.get("tam_pagina") or 50)
        self.search_status = str(search_cfg.get("status") or "todos")
        self.search_ordenacao = str(search_cfg.get("ordenacao") or "-data")
        self._max_retries = int(http["max_retries"])
        self._backoff_initial = float(http["backoff_initial_seconds"])
        self._backoff_max = float(http["backoff_max_seconds"])
        self._last_request_at = 0.0
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

    def __enter__(self) -> PncpClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _pace(self) -> None:
        if self.pause_seconds <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        if self._last_request_at and elapsed < self.pause_seconds:
            time.sleep(self.pause_seconds - elapsed)

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
        url = urljoin(self.consulta_base, self.publicacao_path.lstrip("/"))
        return self._get(url, params)

    def fetch_itens(
        self,
        cnpj: str,
        ano: int,
        sequencial: int,
        pagina: int = 1,
        tamanho_pagina: int = 500,
    ) -> tuple[int, bytes]:
        path = f"v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/itens"
        url = urljoin(self.integracao_base, path)
        return self._get(url, {"pagina": pagina, "tamanhoPagina": tamanho_pagina})

    def fetch_search(
        self,
        q: str,
        pagina: int,
        *,
        tipos_documento: str = "edital",
        data_inicio: str | None = None,
        data_fim: str | None = None,
        tam_pagina: int | None = None,
        status: str | None = None,
        ordenacao: str | None = None,
    ) -> tuple[int, bytes]:
        """Busca textual do portal (GET /api/search/). Datas em AAAA-MM-DD."""
        params: dict[str, Any] = {
            "q": q,
            "tipos_documento": tipos_documento,
            "pagina": pagina,
            "tam_pagina": self.search_tam_pagina if tam_pagina is None else tam_pagina,
            "status": self.search_status if status is None else status,
            "ordenacao": self.search_ordenacao if ordenacao is None else ordenacao,
        }
        if data_inicio:
            params["data_inicio"] = data_inicio
        if data_fim:
            params["data_fim"] = data_fim
        return self._get(self.search_base, params)

    def _get(self, url: str, params: dict[str, Any]) -> tuple[int, bytes]:
        retrying = retry(
            retry=retry_if_exception(_should_retry),
            stop=stop_after_attempt(self._max_retries),
            wait=_wait_for_retry,
            reraise=True,
            before_sleep=lambda state: LOG.warning(
                "Nova tentativa %s após %s",
                state.attempt_number + 1,
                state.outcome.exception() if state.outcome else "?",
            ),
        )
        return retrying(self._get_once)(url, params)

    def _get_once(self, url: str, params: dict[str, Any]) -> tuple[int, bytes]:
        self._pace()
        try:
            response = self._client.get(url, params=params)
        except (httpx.TransportError, httpx.TimeoutException):
            self._last_request_at = time.monotonic()
            raise
        self._last_request_at = time.monotonic()
        body = response.content
        if response.status_code in (200, 204):
            return response.status_code, body
        retry_after = None
        if response.status_code == 429:
            header = response.headers.get("Retry-After")
            if header:
                try:
                    retry_after = float(header)
                except ValueError:
                    retry_after = None
            LOG.warning("HTTP 429; Retry-After=%s", header)
        raise ApiError(response.status_code, body, str(response.url), retry_after=retry_after)


ConsultaClient = PncpClient
