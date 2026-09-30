.PHONY: test probe pilot publicacao

# PYTHONHASHSEED tem de existir antes do interpretador arrancar (config.yaml, seeds.pythonhashseed).
export PYTHONHASHSEED := 42
export PYTHONPATH := src

PYTHON ?= python

test:
	$(PYTHON) -m pytest -q

probe:
	$(PYTHON) -m collect probe

pilot:
	$(PYTHON) -m collect pilot

publicacao:
	$(PYTHON) -m collect publicacao
