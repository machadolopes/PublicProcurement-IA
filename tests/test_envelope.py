import json

import pytest

from collect.envelope import SchemaDivergence, page_is_last, parse_envelope
from tests.pages import contratacao, page


def test_envelope_documentado():
    payload = parse_envelope(page(1, 1, [contratacao("00000000000000-1-000001/2023")]))
    assert payload["numeroPagina"] == 1
    assert page_is_last(payload, 1) is True


def test_falta_de_chave_interrompe():
    body = json.dumps({"data": [], "empty": True}).encode()
    with pytest.raises(SchemaDivergence, match="totalRegistros"):
        parse_envelope(body)


def test_pagina_intermedia_nao_e_a_ultima():
    payload = parse_envelope(page(1, 3, [contratacao("00000000000000-1-000001/2023")]))
    assert page_is_last(payload, 1) is False
    assert page_is_last(parse_envelope(page(3, 3, [contratacao("x")])), 3) is True
