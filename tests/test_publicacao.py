import json
from pathlib import Path

import pytest
import yaml

from collect.config_loader import load_config
from collect.publicacao import collect_probe, collect_publicacao, count_duplicate_ids
from collect.store import RawStore, sha256_bytes
from tests.pages import contratacao, page


def _config(pause: float = 0) -> dict:
    raw = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))
    raw["http"]["pause_seconds"] = pause
    raw["http"]["max_retries"] = 1
    return raw


class FakeClient:
    def __init__(self, pages_by_key: dict) -> None:
        self.pages_by_key = pages_by_key
        self.calls: list[tuple] = []

    def fetch_publicacao(self, data_inicial, data_final, modalidade, pagina, tamanho_pagina=None):
        self.calls.append((data_inicial, data_final, modalidade, pagina, tamanho_pagina))
        return self.pages_by_key[(data_inicial, data_final, modalidade, pagina)]


def test_duas_paginas_e_para(tmp_path: Path):
    config = _config()
    key = ("20260801", "20260801", 8)
    client = FakeClient(
        {
            (*key, 1): (200, page(1, 2, [contratacao("a-1")])),
            (*key, 2): (200, page(2, 2, [contratacao("a-2")])),
        }
    )
    store = RawStore(tmp_path)
    totals = collect_publicacao(
        config, tmp_path, "2026-08-01", "2026-08-01", client, store, modalidades=[8]
    )
    assert totals["records"] == 2
    assert totals["pages"] == 2
    assert len(client.calls) == 2
    raw = (tmp_path / "data/raw/contratacoes/publicacao/m08/20260801_20260801/page-00001.json").read_bytes()
    assert sha256_bytes(raw) == json.loads((tmp_path / "data/raw/manifest.json").read_text(encoding="utf-8"))["files"][0]["sha256"]


def test_retoma_nao_duplica_jsonl(tmp_path: Path):
    config = _config()
    key = ("20260801", "20260801", 8)
    first = FakeClient({(*key, 1): (200, page(1, 2, [contratacao("a-1")]))})
    store = RawStore(tmp_path)
    with pytest.raises(KeyError):
        collect_publicacao(config, tmp_path, "2026-08-01", "2026-08-01", first, store, modalidades=[8])

    second = FakeClient(
        {
            (*key, 1): (200, page(1, 2, [contratacao("a-1")])),
            (*key, 2): (200, page(2, 2, [contratacao("a-2")])),
        }
    )
    collect_publicacao(config, tmp_path, "2026-08-01", "2026-08-01", second, store, modalidades=[8])
    assert [call[3] for call in second.calls] == [2]
    lines = (
        tmp_path / "data/raw/contratacoes/publicacao/m08/20260801_20260801/records.jsonl"
    ).read_text(encoding="utf-8").splitlines()
    assert lines == [
        json.dumps(contratacao("a-1"), ensure_ascii=False, separators=(",", ":")),
        json.dumps(contratacao("a-2"), ensure_ascii=False, separators=(",", ":")),
    ]


def test_janela_completa_nao_repete(tmp_path: Path):
    config = _config()
    key = ("20260801", "20260801", 8)
    body = page(1, 1, [contratacao("a-1")])
    client = FakeClient({(*key, 1): (200, body)})
    store = RawStore(tmp_path)
    collect_publicacao(config, tmp_path, "2026-08-01", "2026-08-01", client, store, modalidades=[8])
    again = FakeClient({(*key, 1): (200, body)})
    totals = collect_publicacao(config, tmp_path, "2026-08-01", "2026-08-01", again, store, modalidades=[8])
    assert again.calls == []
    assert totals["skipped_complete"] == 1


def test_sonda_e_uma_chamada_com_o_intervalo_do_manual(tmp_path: Path):
    config = _config()
    client = FakeClient(
        {
            ("20230801", "20230802", 8, 1): (
                200,
                page(1, 4, [contratacao("a-1")], total_registros=4),
            )
        }
    )
    store = RawStore(tmp_path)
    totals = collect_probe(config, tmp_path, client, store)
    assert totals["pages"] == 1
    assert client.calls == [("20230801", "20230802", 8, 1, 10)]
    again = FakeClient({})
    collect_probe(config, tmp_path, again, store)
    assert again.calls == []


def test_http_204_conta_como_janela_vazia(tmp_path: Path):
    config = _config()
    client = FakeClient({("20260801", "20260801", 6, 1): (204, b"")})
    store = RawStore(tmp_path)
    totals = collect_publicacao(
        config, tmp_path, "2026-08-01", "2026-08-01", client, store, modalidades=[6]
    )
    assert totals["empty_windows"] == 1
    assert totals["records"] == 0


def test_duplicados_sao_contados_sem_apagar(tmp_path: Path):
    path = tmp_path / "records.jsonl"
    line = json.dumps(contratacao("mesmo"))
    path.write_text(line + "\n" + line + "\n", encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    counts = count_duplicate_ids([path])
    assert counts == {"rows": 2, "unique_ids": 1, "duplicate_rows": 1, "missing_id": 0}
    assert path.read_text(encoding="utf-8") == before


def test_config_do_repositorio_tem_a_janela_fechada():
    config = load_config(Path("config.yaml"))
    assert config["window"] == {"start": "2021-01-01", "end": "2026-09-30"}
    assert config["pilot"] == {"start": "2026-08-01", "end": "2026-08-31"}
    assert config["modalidades"] == list(range(1, 14))
