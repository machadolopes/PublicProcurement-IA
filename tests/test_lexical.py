from pathlib import Path

from filter.lexical import LexicalFilter, load_terms


def _filter() -> LexicalFilter:
    return LexicalFilter(load_terms(Path("src/filter/terms.yaml")))


def test_match_inteligencia_artificial():
    objeto = "Contrata\u00e7\u00e3o de solu\u00e7\u00e3o de intelig\u00eancia artificial"
    result = _filter().apply({"objetoCompra": objeto})
    assert result.matched
    assert any(h.term_id == "inteligencia_artificial" for h in result.hits)


def test_exclui_inseminacao_artificial():
    objeto = "Aquisi\u00e7\u00e3o de material para insemina\u00e7\u00e3o artificial bovina"
    result = _filter().apply({"objetoCompra": objeto})
    assert result.matched is False


def test_exclui_inteligencia_policial_sem_artificial():
    objeto = "Servi\u00e7os de intelig\u00eancia policial e monitoramento"
    result = _filter().apply({"objetoCompra": objeto})
    assert result.matched is False


def test_chatbot():
    objeto = "Implanta\u00e7\u00e3o de chatbot para atendimento ao cidad\u00e3o"
    result = _filter().apply({"objetoCompra": objeto})
    assert result.matched
    assert any(h.term_id == "chatbot" for h in result.hits)


def test_rpa_ambigua_sem_exclusao_ainda_casa():
    objeto = "Contrata\u00e7\u00e3o de RPA para automa\u00e7\u00e3o de processos"
    result = _filter().apply({"objetoCompra": objeto})
    assert result.matched
    assert any(h.term_id == "rpa" for h in result.hits)


def test_anexo_ia_ib_nao_e_ia():
    objeto = (
        "Contratacao de empresa de engenharia conforme especificacoes "
        "constantes no termo de referencia anexo i, ia e ib e demais anexos"
    )
    result = _filter().apply({"objetoCompra": objeto})
    assert result.matched is False


def test_eta_i_nao_e_ai():
    result = _filter().apply(
        {
            "objetoCompra": "Bombas para a E.T.A. I do municipio",
            "informacaoComplementar": "A capacidade da E.T.A. I nao e suficiente",
        }
    )
    assert result.matched is False


def test_cruzamento_campos_i_mais_a_nao_e_ia():
    result = _filter().apply(
        {
            "objetoCompra": "Materiais cadastrados no DRS- I",
            "informacaoComplementar": "A aquisicao se faz necessaria para reposicao de estoque",
        }
    )
    assert result.matched is False


def test_frase_lei_ponto_a_nao_e_ia():
    result = _filter().apply(
        {
            "objetoCompra": "Alienacao de bens",
            "informacaoComplementar": "Previstas em lei. A alienacao compreende toda transferencia",
        }
    )
    assert result.matched is False


def test_referencia_ponto_informamos_nao_e_ai():
    result = _filter().apply(
        {
            "informacaoComplementar": (
                "conforme termo de referencia. Informamos que o codigo cadastrado no sistema"
            )
        }
    )
    assert result.matched is False


def test_rpa_drone_nao_e_automacao():
    result = _filter().apply(
        {"objetoCompra": "Aquisicao de kit Aeronave Remotamente Pilotada - RPA (drone)"}
    )
    assert result.matched is False


def test_ia_entre_parenteses_bate():
    result = _filter().apply(
        {"objetoCompra": "cameras de monitoramento (com IA), com sala de videomonitoramento"}
    )
    assert result.matched
    assert any(h.term_id == "sigla_ia" for h in result.hits)
