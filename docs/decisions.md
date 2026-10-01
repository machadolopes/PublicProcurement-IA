# Decisões metodológicas

Cada entrada diz o que foi decidido, porquê, o que foi descartado e o que ainda depende de confirmação. Nada nesta lista autoriza coleta em massa.

## D001 — Fonte normativa da API

**Estado:** decidida em 2026-09-30.

**Decisão.** A API de consulta em lote segue o *Manual das APIs de Consultas* (PDF, versão 1.0). Itens, resultado de item e contrato-por-contratação seguem o *Manual de Integração* (corpo HTML lido como v. 2.5, de 11/06/2026; o índice “latest” já anuncia v. 2.6, de 31/08/2026). O OpenAPI vivo não entrou porque `pncp.gov.br` recusou a ligação nesta sessão.

**Porquê.** O prompt exige não inventar endpoints. O PDF é a única especificação integral da consulta em lote que foi lida por completo.

**Descartado.** Completar parâmetros em falta com tutoriais de terceiros ou com o índice do Swagger visto por motores de busca. Esses caminhos estão listados em `docs/api_notes.md`, secção 6, como não confirmados.

**Em aberto.** Gravar o OpenAPI oficial assim que o host responder, e reler os campos na v. 2.6. Se um nome divergir, o manual mais recente daquele endpoint ganha, e esta entrada é atualizada.

## D002 — Não chamar endpoints só conhecidos por fontes secundárias

**Estado:** decidida em 2026-09-30.

**Decisão.** `GET /v1/contratacoes/atualizacao` e os análogos de atas e contratos não são usados.

**Porquê.** Não estão no PDF de consultas. Sem o JSON OpenAPI, não há lista oficial de parâmetros obrigatórios.

**Descartado.** Usá-los para “apanhar retificações” na primeira coleta. Retificações posteriores a um snapshot são precisamente a razão de existir o modo `--from-snapshot`: o artigo reproduz o snapshot, não o portal no dia da leitura.

## D003 — PCA fora do corpus

**Estado:** decidida em 2026-09-30, reversível.

**Decisão.** Não coletar planos de contratações anuais (`/v1/pca/` e `/v1/pca/usuario`).

**Porquê.** As perguntas de investigação são sobre contratações realizadas (objeto, valor, modalidade, esfera). O PCA é plano. O prompt não o pede.

**Descartado.** Usar o PCA como proxy de intenção de compra de IA. Misturaria plano e execução e mudaria a unidade de análise.

## D004 — Coleta em duas etapas, condicionada ao piloto

**Estado:** proposta, à espera de confirmação. Sem código e sem coleta.

**Proposta.** (1) Cabeçalhos de todas as contratações via `/v1/contratacoes/publicacao`, todas as modalidades, sem filtro de IA na API. (2) Itens de todas as contratações só num mês-piloto. (3) Itens do restante do período apenas se o piloto mostrar que a descrição do item acrescenta menções a IA ausentes do objeto, na proporção que for medida. Contratos e atas do mês-piloto entram na mesma medição; a série completa deles só continua se acrescentarem objeto ou valor que o cabeçalho não tem.

**Porquê.** O manual não devolve itens na listagem. Um `GET` por contratação, noutra base, sobre 2021–2026 e 13 modalidades, é o cenário que o prompt manda declarar em vez de fingir que a API filtra.

**Viés se a etapa 2 ficar restrita às candidatas do objeto.** Compra descrita como “solução de TIC” ou “software”, com IA só no item, sai do corpus. Esse viés é o que o piloto tem de contar. Não será assumido como pequeno.

**Descartado por agora.** Baixar itens de todo o universo sem essa contagem. Também descartado: filtrar por `categoriaProcesso = Informática (TIC)`, porque esse campo está no contrato, não na listagem de contratações, e deixaria de fora IA contratada sob outra categoria.

## D005 — Janela temporal

**Estado:** decidida em 2026-09-30. Valores em `config.yaml`, não no relógio.

**Decisão.** Publicação no PNCP de **2021-01-01** a **2026-09-30**, inclusive. A data final é o dia em que a janela foi fechada, escrita por extenso, não “a data de hoje” calculada numa execução futura.

**Porquê.** A Lei nº 14.133 é de 1º de abril de 2021 e o manual de consultas declara-se sobre contratações dessa lei. 1 de janeiro de 2021 é o início do ano civil da lei. Janeiro a março de 2021 são anteriores à lei; se voltarem vazios, entram no manifest com `totalRegistros = 0`. A série da RQ3 precisa de 2021 e 2022, mesmo com subnotificação do portal. 2026 fica incompleto (acaba em 30 de setembro) e não se compara como ano cheio a 2025.

**Descartado.** Começar em 2023, no fim da transição da lei antiga, sem mostrar 2021–2022. Começar só em 1º de abril de 2021, o que esconderia os três meses vazios em vez de os contar. Deixar a data final solta, porque uma nova execução alargaria o corpus e quebraria a reprodução.

## D006 — Zero em valor sigiloso não é valor observado

**Estado:** decidida em 2026-09-30, para quando houver análise.

**Decisão.** `valorTotalEstimado`, `valorUnitarioEstimado` e `valorTotal` do item iguais a zero com orçamento sigiloso (ou sem resultado, nos termos do manual) são valor em falta, não zero reais. A mediana, o IQR e os testes de valor usam essa distinção.

**Porquê.** O manual diz que a API devolve 0 nesse caso. Tratar 0 como preço colapsaria a cauda inferior.

## D007 — CPF de fornecedor pessoa física

**Estado:** decidida em 2026-09-30.

**Decisão.** `niFornecedor` com `tipoPessoa = PF` não entra em `outputs/` nem em tabelas do artigo. Se um snapshot bruto precisar do campo para não alterar o JSON da API, o ficheiro bruto fica de fora do pacote público e o derivado guarda só um indicador de pessoa física, sem o número.

**Porquê.** O prompt proíbe dados pessoais na divulgação. O contrato e o resultado do item trazem CPF quando o fornecedor é pessoa física.

## D008 — Tipo de órgão não será inventado a partir da razão social

**Estado:** decidida em 2026-09-30.

**Decisão.** Esfera (`esferaId`, incluindo Distrital) e poder (`poderId`) vêm do payload. “Tipo de órgão” não tem campo na contratação. Não será derivado do nome do órgão nesta fase.

**Porquê.** Uma tipologia (autarquia, fundação, empresa pública, município) feita por palavras na razão social é uma classificação nossa, com erro, e o prompt pede para não fazer suposições silenciosas. Se for necessária à RQ2, será uma tabela versionada em `data/human/`, não uma regra embutida.

## D009 — Pausas entre pedidos

**Estado:** valor inicial em `config.yaml` (`http.pause_seconds: 1.0`). Não é limite oficial.

**Decisão.** Um segundo entre pedidos bem-sucedidos, com nova tentativa só em falha de rede e em HTTP 500, 502, 503 e 504. HTTP 400 e 422 não são repetidos. O manual não publica rate limit; este número é cautela nossa e muda se o piloto mostrar cortes ou se a coleta for desnecessariamente lenta.

## D010 — O bruto é o corpo HTTP, não o JSONL

**Estado:** decidida em 2026-09-30.

**Decisão.** Cada resposta é gravada byte a byte. O SHA-256 do manifest é desses ficheiros. O JSONL é uma cópia estrutural, uma contratação por linha, para leitura posterior. Não substitui o corpo original.

**Porquê.** Voltar a serializar o JSON muda espaços e pode mudar a ordem das chaves. O prompt pede o bruto sem transformação.

## D011 — Janelas de um dia e mês do piloto

**Estado:** decidida em 2026-09-30.

**Decisão.** A coleta parte o período em janelas de um dia (`collect.chunk_days: 1`), uma modalidade de cada vez. O piloto de volume é agosto de 2026 (2026-08-01 a 2026-08-31), o último mês civil completo dentro da janela fechada. A primeira sonda, antes do mês, repete o exemplo do manual: 2023-08-01 a 2023-08-02, modalidade 8, página 1, `tamanhoPagina` 10.

**Porquê.** O manual não diz qual é o intervalo máximo de datas. Um dia é o recorte que cabe num checkpoint e que não assume um teto que a documentação não dá. Agosto de 2026 evita usar setembro, que acaba no dia em que a janela foi fechada.

**Descartado.** Pedir 2021–2026 numa só chamada. Tratar 365 dias como limite da API: esse número aparece em clientes de terceiros, não no manual.

## D012 — Sonda e disponibilidade da API

**Estado:** atualizada em 2026-09-30 (tarde).

**O que aconteceu.** De manhã, a sonda falhou com `RemoteProtocolError`. À tarde, a mesma sonda (`2023-08-01`–`2023-08-02`, modalidade 8, página 1, `tamanhoPagina` 10) devolveu HTTP 200: 10 registos na página, `totalRegistros` 1334, envelope idêntico ao manual. O corpo ficou em `data/raw/contratacoes/publicacao/m08/20230801_20230802/`.

**Divergências face ao PDF de consultas, observadas no JSON real:**

- Instrumento convocatório: `tipoInstrumentoConvocatorioCodigo` / `tipoInstrumentoConvocatorioNome` (o PDF falava em `…Id`).
- Campos a mais: `emendaParlamentar`, `fontesOrcamentarias`, `linkProcessoEletronico`, `dataAtualizacaoGlobal`.
- `poderId` = `N` num registo municipal (além de L/E/J do manual).
- `valorTotalHomologado` pode ser `null`, não só número ou zero.

**Itens.** `GET https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/itens` respondeu 200 **sem** token. O corpo é uma **lista** JSON, não um objeto com chave `itens`. Nomes observados: `situacaoCompraItem` (não `…Id`), `tipoBeneficio` (não `…Id`), e o campo extra `imagem`.

## D013 — Modalidades 1–19 a partir da lista viva

**Estado:** decidida em 2026-09-30.

**Decisão.** A coleta usa os códigos **1 a 19** ativos em `GET /api/pncp/v1/modalidades?statusAtivo=true` (snapshot `data/raw/_modalidades_ativas.json`). O manual de consultas só listava 1–13. Os códigos 14–19 são: Inaplicabilidade da Licitação; Chamada pública; Concorrência eletrónica/presencial internacional; Pregão eletrónico/presencial internacional.

**Porquê.** Omitir 14–19 deixaria fora contratações publicadas sob essas modalidades. A lista viva está na API de integração, não na de consulta (`/api/consulta/v1/modalidades` devolve 404).

**Descartado.** Ficar só nos 13 do PDF. Inventar nomes para códigos sem confirmar na lista viva.

## D014 — HTTP 429 e ritmo entre janelas

**Estado:** decidida em 2026-09-30, após o início do piloto.

**O que aconteceu.** Com `pause_seconds: 1.0` só entre páginas da **mesma** janela, a coleta fez ~10 pedidos em 4 segundos e recebeu HTTP 429 com HTML “Limite de requisições excedido”. O manual de consultas não documenta 429 nem quota.

**Decisão.** (1) Tratar 429 como retentável, com espera de 30 s × 2^(tentativa−1) se não houver `Retry-After`. (2) Aplicar a pausa entre **todos** os pedidos no cliente (`PncpClient._pace`). (3) `pause_seconds` em `config.yaml` (valor corrente 2.5). Continua a ser decisão nossa, não limite oficial publicado.

**Descartado.** Ignorar 429. Inventar um “limite oficial” numérico no README.

## D015 — Só persistir candidatas de IA (filtro lexical na escrita)

**Estado:** decidida em 2026-09-30, após correção do utilizador.

**Contexto.** O piloto `collect pilot` gravava **todas** as contratações publicadas (dezenas de milhares só em agosto/2026 na modalidade 6). O utilizador pediu gravar apenas compras cujo objeto coincida com palavras-chave de IA.

**Limite da API.** `/v1/contratacoes/publicacao` **não** tem parâmetro de busca textual. Continua a ser necessário **pedir** todas as páginas do intervalo. O que muda é o que fica em disco.

**Decisão.** Modo `pilot-ia` / `candidatas`: varre a API, aplica `src/filter/terms.yaml` a `objetoCompra` + `informacaoComplementar`, e grava só as candidatas em `data/raw/candidatas/`. Mantém contagens `scanned` / `matched` por janela em `scan_stats.jsonl` para o fluxograma PRISMA. Itens só se pedem depois, e só para candidatas.

**Regras das siglas (2026-09-30, endurecidas após FPs).** `IA`/`AI` só contam como palavra completa (`\bia\b` / `\bai\b`) ou pontuadas sem espaço (`I.A.`, `A.I.`). Exigem vizinhança tecnológica (software, sistema, monitoramento, generativa, etc.). Rejeitam-se anexos do tipo “Anexo I, IA e IB”, junções entre campos (`… I` + `A …`), `E.T.A. I`, e RPA no sentido de drone/aeronave.

**Sobre o bruto de agosto/2026 já descarregado.** Não se apaga automaticamente. O comando `filter-existing` reaplica o dicionário a esse JSONL e produz `candidatas_from_existing.jsonl` sem novos pedidos HTTP. Novas coletas usam só `pilot-ia` / `candidatas`.

**Descartado.** Inventar um endpoint de “busca por IA”. Continuar a arquivar o JSONL de todas as compras. Filtrar só na API (impossível). Aceitar `i. a` / `a. i` com espaço (falsos positivos em finais de frase).

**Nota.** O prompt original pedia coletar o bruto completo e filtrar localmente. Esta decisão reduz o armazenamento por pedido explícito do estudo; a reprodutibilidade do artigo fica ancorada no dicionário versionado + contagens de varredura + snapshot das candidatas.

## D016 — Busca textual do portal (`/api/search/`) como fonte primária de candidatas

**Estado:** decidida em 2026-09-30, após o utilizador rejeitar a varredura completa da API de Consultas (tempo estimado de dias a semanas).

**Contexto.** A API de Consultas (`/api/consulta/.../publicacao`) não filtra por objeto. A interface web do PNCP usa outro endpoint: `GET https://pncp.gov.br/api/search/?q=...`, com `tipos_documento`, `status`, `data_inicio`, `data_fim`, `pagina`, `tam_pagina`. Resposta observada: `{ "items": [...], "total": N }` (sonda 2026-09-30; “inteligencia artificial” + edital + janela do estudo → `total` ≈ 8500).

**Decisão.** Modo `search-ia`: percorre `src/filter/search_queries.yaml` (frases, não regex) × tipos `edital` e `contrato`, na janela `config.window`, e grava hits únicos em `data/raw/candidatas_search/hits.jsonl` (chave `numero_controle_pncp`). Checkpoints por query. Não usa siglas isoladas (`IA`, `AI`, `RPA`) como `q`.

**Limitações a declarar no artigo.** Este endpoint não está no Manual das APIs de Consultas. O índice pode ter ranking, atraso ou cobertura diferente da listagem por publicação. O `total` anunciado não é um universo enumerável da mesma forma que `totalRegistros` da API de Consultas. A API mostrou timeouts ocasionais; o cliente retenta 429/5xx/transporte.

**Descartado para a série completa.** Continuar a varredura dia×modalidade de `/contratacoes/publicacao` só para achar texto de IA.

**Relação com D015.** O filtro lexical local continua útil para validar/refinar hits e para o dump de agosto já em disco. A descoberta em massa passa a ser `search-ia`.

## D017 — Frases guarda-chuva fora da busca; nomes de modelos dentro

**Estado:** decidida em 2026-09-30, a pedido do estudo, depois de inspecionar os objetos de `ciência de dados`.

**O que aconteceu.** Em 2.396 editais de `ciência de dados`, só 171 traziam a frase no título ou na descrição. O índice casa palavras soltas, inclusive “Ciência” no nome do órgão (Institutos Federais, centros de ciências). `mineração de dados` anunciou 13.701 editais no mesmo padrão. A grafia acentuada de `inteligência artificial` repetiu o total da forma sem acento e acrescentou 4 documentos.

**Decisão.** Saem de `search_queries.yaml`: `inteligência artificial` (acento), `visao computacional`, `ciência de dados`, `data science`, `mineração de dados`, `análise preditiva`, `modelagem preditiva`, `análise de sentimentos`. Entram, ao lado de ChatGPT/OpenAI/Copilot: Claude, Anthropic, Gemini, Grok, xAI, Llama, Mistral, DeepSeek. A sigla isolada `IA` continua de fora. Hits já gravados só por `ciencia_dados`, `data_science` ou `mineracao_dados` saem de `hits.jsonl`; o índice `seen_controle.json` é reconstruído a partir do que fica.

## D018 — Corpus de análise e classificação de destinação

**Estado:** atualizada em 2026-10-01.

**Corpus.** Parte de `data/raw/candidatas_search/hits.jsonl`. Entram **apenas contratos** (`document_type = contrato`) cuja `description` casa com o léxico de inclusão em `src/analysis/destinacao_rules.yaml` (texto dobrado, sem acento). Um registo por `numero_controle_pncp` (descrição mais longa se houver duplicata). Classificador `destinacao-2`.

**Descartado no corpus do artigo.** Documentos que não são contrato (incluindo convocações indexadas como outro tipo). A busca pode ainda os ter recolhido; a análise não os usa.

**Classificação.** Oito classes mais residual. A primeira regra que casa na descrição é a classe primária. As outras ficam em `classes_atingidas`. Não é modelo de tópicos. Um curso sobre reconhecimento facial fica em Capacitação, porque o objeto comprado é o curso. Uma passagem sobre o residual, depois da primeira contagem, acrescentou plurais e sinónimos da mesma classe (`cursos`, `formação`, `GPU`, `câmeras de vigilância`, `licito.guru`, tributos). O hash SHA-256 das regras está em `outputs/artigo/metodologia.json`.

**O que não entra no artigo como soma.** Valores monetários reportam-se por mediana e quartis. Há extremos incompatíveis com uma compra isolada.

