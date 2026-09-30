# Compras públicas de IA no PNCP

Pipeline para mapear, a partir do Portal Nacional de Contratações Públicas, para que a administração pública brasileira contrata inteligência artificial. A janela de publicação está fechada em `config.yaml`: **2021-01-01** a **2026-09-30**.

O corpus ainda não existe. Em 2026-09-30 o host `pncp.gov.br` não completou a ligação a partir deste ambiente. O cliente está pronto para a sonda e para o mês piloto; não inventa respostas.

Cópia de trabalho: `C:\Users\marce\Documents\PublicProcurement-IA` (fora do Google Drive, para o `.venv` funcionar neste Windows).

## Requisitos

Python 3.12. O comando `python` desta máquina é o 3.14 da Anaconda, e o `PyYAML==6.0.2` não tem wheel para 3.14: a instalação tenta compilar e falha. O ambiente abaixo usa o Python 3.12.13.

## Correr

Na raiz do repositório, em PowerShell:

```powershell
& "$env:USERPROFILE\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\python.exe" -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
$env:PYTHONHASHSEED = "42"
$env:PYTHONPATH = "src"
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m collect probe
```

`probe` pede uma página, com o exemplo do manual: 1 a 2 de agosto de 2023, modalidade 8 (dispensa), `tamanhoPagina` 10.

`pilot` pede os cabeçalhos de agosto de 2026, as 13 modalidades, um dia de cada vez. Só faz sentido depois de a sonda devolver JSON.

Com GNU Make, os mesmos passos são `make test`, `make probe` e `make pilot`. `PYTHONHASHSEED` sai do Makefile, alinhado com `config.yaml`.

## O que fica em disco

Cada resposta HTTP é gravada em `data/raw/contratacoes/publicacao/`, sem reescrita. O SHA-256 desses ficheiros está em `data/raw/manifest.json`. O JSONL ao lado é uma cópia para leitura; se a coleta for interrompida, ele é reconstruído a partir dos corpos já gravados.

## Documentação da API

`docs/api_notes.md` regista os endpoints lidos no manual. `docs/decisions.md` regista as escolhas. `docs/methods_log.md` é o texto corrido das etapas.
