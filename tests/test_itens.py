import json

import pytest

from collect.envelope import SchemaDivergence
from collect.itens import parse_itens_body


def test_itens_como_lista():
    body = json.dumps([{"numeroItem": 1, "descricao": "x"}]).encode()
    assert parse_itens_body(body)[0]["descricao"] == "x"


def test_itens_como_objeto_com_chave():
    body = json.dumps({"itens": [{"numeroItem": 2, "descricao": "y"}]}).encode()
    assert parse_itens_body(body)[0]["numeroItem"] == 2


def test_itens_formato_invalido():
    with pytest.raises(SchemaDivergence):
        parse_itens_body(b'{"foo": 1}')
