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

## D012 — Piloto não executado nesta sessão

**Estado:** bloqueio registado em 2026-09-30.

**O que aconteceu.** O cliente correu a sonda (`python -m collect probe`: 2023-08-01 a 2023-08-02, modalidade 8, página 1, `tamanhoPagina` 10). O host aceita a ligação e corta-a sem resposta HTTP (`httpx.RemoteProtocolError: Server disconnected without sending a response`), depois das repetições configuradas. `www.gov.br` no mesmo ambiente responde. Não houve corpo para arquivar, portanto não há contagem de registos. O mês piloto não foi pedido.

**O que não se fez.** Não se inventou uma resposta, não se trocou a API de Consulta por outra fonte e não se avançou para a coleta completa.
