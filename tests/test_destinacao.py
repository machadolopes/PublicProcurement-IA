import json
from pathlib import Path

from analysis.destinacao import classify, fold, load_rules, montar_corpus


def test_curso_de_reconhecimento_facial_e_capacitacao():
    rules = load_rules()
    texto = fold("Inscrição no curso de reconhecimento facial e ponto eletrônico")
    primaria, atingidas, _ = classify(texto, rules)
    assert primaria == "capacitacao"
    assert "reconhecimento_facial" in atingidas


def test_licenca_copilot():
    rules = load_rules()
    texto = fold("21 subscrições do Microsoft Copilot para Microsoft 365")
    primaria, _, _ = classify(texto, rules)
    assert primaria == "licenca_assistente"


def test_catraca_facial():
    rules = load_rules()
    texto = fold("Aquisição de catracas com reconhecimento facial para controle de acesso")
    primaria, _, _ = classify(texto, rules)
    assert primaria == "reconhecimento_facial"


def test_chatbot():
    rules = load_rules()
    texto = fold("Contratação de chatbot no WhatsApp para atendimento ao cidadão")
    primaria, _, _ = classify(texto, rules)
    assert primaria == "chatbot"


def test_minutaia():
    rules = load_rules()
    texto = fold("Licença de uso da ferramenta MinutaIA para peças jurídicas")
    primaria, _, _ = classify(texto, rules)
    assert primaria == "ferramenta_oficio"


def test_cafe_da_secretaria_e_residual():
    rules = load_rules()
    texto = fold(
        "Aquisição de café para a Secretaria de Inovação e Inteligência Artificial"
    )
    assert "inteligencia_artificial" in rules.phrases_in(texto)
    primaria, atingidas, padrao = classify(texto, rules)
    assert primaria == "residual"
    assert atingidas == []
    assert padrao is None


def test_claude_nao_casa_claudia():
    rules = load_rules()
    texto = fold("Serviços de limpeza no município de Cláudia")
    assert rules.phrases_in(texto) == []


def test_cursos_no_plural_e_capacitacao():
    rules = load_rules()
    texto = fold("Contratação de cursos em inteligência artificial para agentes")
    primaria, _, _ = classify(texto, rules)
    assert primaria == "capacitacao"


def test_ignora_documento_que_nao_e_contrato(tmp_path: Path):
    rules = load_rules()
    outro = {
        "numero_controle_pncp": "0001-1-000001/2025",
        "document_type": "edital",
        "description": "Curso de inteligência artificial",
        "data_publicacao_pncp": "2025-03-01",
        "uf": "SP",
        "orgao_cnpj": "11111111000191",
        "orgao_nome": "Município A",
    }
    contrato = {
        "numero_controle_pncp": "0002-2-000009/2025",
        "document_type": "contrato",
        "description": "Contrato de curso de inteligência artificial",
        "data_publicacao_pncp": "2025-06-01",
        "uf": "MG",
        "orgao_cnpj": "22222222000191",
        "orgao_nome": "Município B",
        "valor_global": 500,
    }
    path = tmp_path / "hits.jsonl"
    path.write_text(
        "\n".join(json.dumps(doc, ensure_ascii=False) for doc in (outro, contrato)) + "\n",
        encoding="utf-8",
    )
    rows, fluxo = montar_corpus(path, rules)
    assert fluxo["documentos_lidos"] == 2
    assert fluxo["contratos_lidos"] == 1
    assert fluxo["contratos_com_lexico_na_descricao"] == 1
    assert len(rows) == 1
    assert rows[0]["document_type"] == "contrato"


def test_deduplica_contrato_pelo_controle(tmp_path: Path):
    rules = load_rules()
    curto = {
        "numero_controle_pncp": "0001-2-000001/2025",
        "document_type": "contrato",
        "description": "Curso de inteligência artificial",
        "data_publicacao_pncp": "2025-03-01",
        "uf": "SP",
        "esfera_nome": "Municipal",
        "modalidade_licitacao_nome": "Pregão - Eletrônico",
        "orgao_nome": "Prefeitura",
        "valor_global": 1000,
    }
    longo = {
        "numero_controle_pncp": "0001-2-000001/2025",
        "document_type": "contrato",
        "description": "Curso de inteligência artificial para servidores, com carga horária ampliada",
        "data_publicacao_pncp": "2025-06-01",
        "uf": "SP",
        "esfera_nome": "Municipal",
        "modalidade_licitacao_nome": "Pregão - Eletrônico",
        "orgao_nome": "Prefeitura",
        "valor_global": 900,
    }
    fora = {
        "numero_controle_pncp": "0002-1-000002/2025",
        "document_type": "edital",
        "description": "Curso de inteligência artificial sem contrato",
        "data_publicacao_pncp": "2025-01-01",
    }
    path = tmp_path / "hits.jsonl"
    path.write_text(
        "\n".join(json.dumps(doc, ensure_ascii=False) for doc in (curto, longo, fora)) + "\n",
        encoding="utf-8",
    )
    rows, fluxo = montar_corpus(path, rules)
    assert fluxo["documentos_lidos"] == 3
    assert fluxo["contratos_lidos"] == 2
    assert fluxo["contratos_com_lexico_na_descricao"] == 2
    assert fluxo["contratos_apos_deduplicacao"] == 1
    assert len(rows) == 1
    assert rows[0]["classe_primaria"] == "capacitacao"
    assert rows[0]["n_caracteres"] == len(longo["description"])
