# Registo de métodos

Texto corrido do que já foi feito. Serve de base à secção de Métodos; ainda não descreve resultados empíricos.

## 2026-09-30 — Leitura da API, sem coleta

A unidade de análise prevista é a contratação publicada no Portal Nacional de Contratações Públicas ao abrigo da Lei nº 14.133/2021. A fonte de listagem é a API de Consulta (`https://pncp.gov.br/api/consulta`), documentada no Manual das APIs de Consultas, versão 1.0. Essa API não oferece busca por texto: o recorte de inteligência artificial terá de ser feito no corpus local, a partir do objeto da contratação (`objetoCompra`, até 5120 caracteres) e, quando forem obtidos, das descrições dos itens.

Os itens não acompanham a listagem. O manual de consultas remete para o Manual de Integração, cuja base de produção é `https://pncp.gov.br/api/pncp`. O serviço é `GET /v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/itens`. Os exemplos oficiais desse `GET` não usam token; inserção e retificação usam. A disponibilidade sem autenticação ainda não foi testada, porque nesta data o host `pncp.gov.br` não completou a ligação a partir do ambiente de trabalho (Swagger e OpenAPI inacessíveis; o PDF em gov.br e o HTML do manual de integração foram lidos).

A varredura por data de publicação exige `dataInicial`, `dataFinal` (formato `AAAAMMDD`), `codigoModalidadeContratacao` e `pagina`. Há 13 modalidades no manual de consultas; a lista viva será conferida no piloto, porque o manual de integração permite consultar modalidades ativas. A página de contratações traz no máximo 50 registos por omissão e aceita até 500. O manual não fixa o intervalo máximo de datas nem um limite de pedidos por tempo.

Esfera e poder vêm no próprio registo (`esferaId`: F, E, M e D distrital; `poderId`: L, E, J). Não há campo de tipo de órgão. Valor estimado igual a zero pode significar orçamento sigiloso, não preço nulo. Fornecedor pode ser pessoa física; o número de identificação correspondente não será publicado.

Ainda não há corpus. A coleta em massa não começou.

## 2026-09-30 — Janela fechada e cliente de coleta, sem respostas da API

A janela de publicação ficou fechada de 1 de janeiro de 2021 a 30 de setembro de 2026. Esses valores estão em `config.yaml`. Uma execução posterior não substitui a data final pela data do relógio.

O cliente pede `GET /v1/contratacoes/publicacao` com os quatro parâmetros obrigatórios do manual, guarda o corpo HTTP sem o reescrever e só então extrai o envelope documentado (`data`, `totalRegistros`, `totalPaginas`, `numeroPagina`, `paginasRestantes`, `empty`). Se uma resposta 200 não trouxer essas chaves, a coleta para. Isso é de propósito: o primeiro JSON real tem de confirmar o manual antes de se percorrer o mês.

A sonda foi executada em 2026-09-30 e não devolveu corpo. O erro, depois das repetições, foi `RemoteProtocolError: Server disconnected without sending a response`. Os testes locais, com páginas sintéticas, passaram (paginação, retoma sem duplicar o JSONL, hash do corpo, parâmetros do pedido). Agosto de 2026 continua por coletar quando o host passar a responder.

A cópia de trabalho passou de `G:\O meu disco\Main\Cursos\ISCTE\PhDPA\MyPapers\PublicProcurement-IA` (Google Drive) para `C:\Users\marce\Documents\PublicProcurement-IA`. No Drive, a criação de `.venv` falhava com acesso negado. Nesta pasta o ambiente local criou-se e os 17 testes voltaram a passar.

## 2026-09-30 (tarde) — Sonda bem-sucedida e início do piloto

A sonda (`2023-08-01`–`2023-08-02`, modalidade 8) devolveu HTTP 200: 10 registos na página, 1334 anunciados no intervalo. O envelope bate com a secção 4.2. O JSON real diverge do PDF em nomes (`tipoInstrumentoConvocatorioCodigo` em vez de `…Id`), campos a mais (`emendaParlamentar`, `fontesOrcamentarias`, `linkProcessoEletronico`, `dataAtualizacaoGlobal`) e um `poderId` = `N` não listado no manual. Itens responderam sem token em `/api/pncp/.../itens` como lista JSON.

A lista viva de modalidades ativas tem códigos **1–19** (snapshot em `data/raw/_modalidades_ativas.json`). O PDF só tinha 1–13; a coleta passou a incluir 14–19.

O piloto de cabeçalhos de agosto de 2026 arrancou e, após ~10 pedidos rápidos, a API devolveu HTTP 429 (“Limite de requisições excedido”). A pausa passou a aplicar-se a todos os pedidos no cliente; 429 passou a ser retentável; `pause_seconds` = 1.5. A coleta retomou a partir do checkpoint.

## 2026-09-30 (noite) — Filtro lexical: só candidatas de IA em disco

A API de publicação continua sem busca por texto: é preciso pedir todas as páginas do intervalo. Por pedido do estudo, deixou de se gravar o JSONL de todas as compras. O modo `pilot-ia` / `candidatas` aplica `src/filter/terms.yaml` a `objetoCompra` e `informacaoComplementar` e persiste apenas matches, com contagens `scanned`/`matched` por janela (`scan_stats.jsonl`).

O piloto completo de agosto/2026 já estava parcialmente em disco (~39 231 cabeçalhos). `filter-existing` reaplicou o dicionário sem novos HTTP: **83 candidatas** após endurecer as siglas `IA`/`AI` (antes ~105, com FPs do tipo “anexo I, IA e IB”, “lei. A …”, “referência. Informamos”, `E.T.A. I`). Termos dominantes no recorte de agosto: inteligência artificial (37), reconhecimento facial (32), sigla IA com contexto tecnológico (12).

Padrões ambíguos de sigla exigem agora vizinhança tecnológica; RPA no sentido de drone/aeronave é excluído. 26 testes unitários passam.

A coleta da janela 2021-01-01→2026-09-30 com persistência só de candidatas arranca a seguir (`python -m collect candidatas`).

## 2026-09-30 (noite) — Mudanca para /api/search/ (D016)

A varredura completa via API de Consultas foi interrompida: estimativa de varios dias so para percorrer dia x modalidade. O portal expoe busca textual em `GET /api/search/` (a mesma do site), com `q`, `tipos_documento`, `status`, `data_inicio`, `data_fim`, paginacao. Sonda: `inteligencia artificial` + edital na janela do estudo devolveu `total` ~8539.

Implementado `python -m collect search-ia`: le `src/filter/search_queries.yaml` (dezenas de frases PT/EN, sem siglas isoladas), pede edital e contrato, deduplica por `numero_controle_pncp`, grava em `data/raw/candidatas_search/`.

## 2026-10-01 — Corpus do artigo e classificação de destinação

A busca `search-ia` ficou em 33.480 documentos únicos. O corpus do artigo não é esse ficheiro: exige a frase na descrição e uma compra, um texto (D018). As regras estão em `src/analysis/destinacao_rules.yaml`. O comando `python -m analysis.export_artigo` grava `outputs/artigo/`: `metodologia.json` (regras, hash, semente 42), `resultados.json` (descritivo e classes), `classificacao.jsonl` (uma compra por linha), `briefing_claude.md` e cinco PNG a 300 dpi em `figuras/`, com legendas em `figuras/legendas.json`. Dez testes em `tests/test_destinacao.py` fixam a prioridade (curso de reconhecimento facial é capacitação), o plural `cursos`, a não fusão de adesão de outro órgão e o facto de “Claude” não casar com “Cláudia”.

## 2026-10-01 — Corpus so de contratos

Por pedido do estudo, o corpus de analise deixa de incluir convocacoes indexadas como outro tipo de documento. `montar_corpus` filtra `document_type == contrato`, deduplica por `numero_controle_pncp` e classifica (`destinacao-2`). Resultado: **4.570** contratos (antes 8.626 compras misturando tipos). Figuras e briefing regenerados sem mencao a editais; `search_queries.yaml` passa a pedir so `contrato`.
