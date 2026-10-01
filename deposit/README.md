# Pacote de depósito Zenodo — PublicProcurement-IA v0.1.0

## Conteúdo

| Caminho | Descrição |
| --- | --- |
| `data/raw/candidatas_search/hits.jsonl` | Hits únicos da busca textual PNCP (`/api/search/`), um JSON por linha |
| `data/raw/candidatas_search/manifest.json` | Manifest da coleta search-ia |
| `data/raw/candidatas_search/search_stats.jsonl` | Contagens por query |
| `data/raw/candidatas_search/seen_controle.json` | Índice de `numero_controle_pncp` vistos |
| `outputs/artigo/` | Corpus classificado (só contratos), `resultados.json`, figuras PNG, briefing |

## Unidade de análise do artigo

Contratos (`document_type=contrato`) com léxico de inclusão na descrição, janela **2021-01-01 → 2026-09-30**. Código e regras: repositório GitHub [machadolopes/PublicProcurement-IA](https://github.com/machadolopes/PublicProcurement-IA).

## Reprodução

```bash
python -m analysis.export_artigo
```

Requer `hits.jsonl` em `data/raw/candidatas_search/`.

## Licença e proveniência

Metadados e software: ver `LICENSE` / `CITATION.cff` no repositório. Textos de objeto são publicados pelo PNCP (governo brasileiro); este pacote redistribui o extrato usado no estudo.
