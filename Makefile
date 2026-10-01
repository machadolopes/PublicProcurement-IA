.PHONY: test probe pilot pilot-ia filter-existing candidatas search-ia pilot-itens publicacao artigo

# PYTHONHASHSEED tem de existir antes do interpretador arrancar (config.yaml, seeds.pythonhashseed).
export PYTHONHASHSEED := 42
export PYTHONPATH := src

PYTHON ?= python

test:
	$(PYTHON) -m pytest -q

probe:
	$(PYTHON) -m collect probe

# Legado: grava TODAS as compras. Preferir search-ia ou pilot-ia.
pilot:
	$(PYTHON) -m collect pilot

pilot-ia:
	$(PYTHON) -m collect pilot-ia

filter-existing:
	$(PYTHON) -m collect filter-existing

candidatas:
	$(PYTHON) -m collect candidatas

# Caminho preferido: busca textual do portal com queries de IA.
search-ia:
	$(PYTHON) -m collect search-ia

pilot-itens:
	$(PYTHON) -m collect pilot-itens

publicacao:
	$(PYTHON) -m collect publicacao

# Corpus de análise, classificação e figuras do artigo (outputs/artigo).
artigo:
	$(PYTHON) -m analysis.export_artigo
