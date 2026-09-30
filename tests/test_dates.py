from datetime import date

import pytest

from collect.dates import iter_chunks, parse_iso_date, to_api_date


def test_formato_da_api():
    assert to_api_date(date(2026, 9, 30)) == "20260930"


def test_rejeita_data_invertida():
    with pytest.raises(ValueError):
        list(iter_chunks(date(2026, 8, 2), date(2026, 8, 1), 1))


def test_um_dia_por_janela():
    chunks = list(iter_chunks(date(2026, 8, 1), date(2026, 8, 3), 1))
    assert chunks == [
        (date(2026, 8, 1), date(2026, 8, 1)),
        (date(2026, 8, 2), date(2026, 8, 2)),
        (date(2026, 8, 3), date(2026, 8, 3)),
    ]


def test_parse_iso():
    assert parse_iso_date("2021-01-01") == date(2021, 1, 1)
    with pytest.raises(ValueError):
        parse_iso_date("20210101")
