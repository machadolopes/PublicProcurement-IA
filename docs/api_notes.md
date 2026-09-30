# Notas da API do PNCP

Data da leitura: 2026-09-30. Nenhuma coleta foi executada.

Estas notas registram apenas endpoints, parâmetros e campos lidos em documentação oficial. Onde a documentação é ambígua, contraditória ou estava inacessível, isso está marcado. Nada aqui foi inferido a partir de clientes de terceiros.

## 1. Fontes

| Fonte | URL | O que foi obtido |
| --- | --- | --- |
| Manual das APIs de Consultas, versão 1.0 (PDF) | https://www.gov.br/pncp/pt-br/pncp/copy_of_manuais/ManualPNCPAPIConsultasVerso1.0.pdf/@@display-file/file | Texto integral. É a fonte da API de consulta em lote. |
| Manual de Integração, índice “latest”, rotulado v. 2.6 (atual) | https://pncp.gov.br/manual/pt-br/latest/ | Sumário. A versão 2.6 está datada de 31/08/2026 no histórico indexado. |
| Manual de Integração, página única | https://pncp.gov.br/manual/pt-br/latest/singlehtml/ | Corpo obtido identifica-se como **v. 2.5**, datada de 11/06/2026. As tabelas de itens, contratação unitária, resultados e contratos abaixo vêm deste corpo. |
| Histórico v. 2.6 | https://pncp.gov.br/manual/pt-br/latest/historico_de_versoes/index.html | A página devolveu HTTP 500 nesta sessão. O trecho indexado só mostra a legenda de destaque em verde e um exemplo de linha (`ano` em contrato/empenho). A lista funcional do que mudou de 2.5 para 2.6 **não foi lida**. |

Não obtido em 2026-09-30, apesar de tentativas com o cliente HTTP desta máquina:

- Swagger UI: `https://pncp.gov.br/api/consulta/swagger-ui/index.html` (HTTP 500 no leitor de páginas; `curl` recebeu *connection reset*).
- OpenAPI: `https://pncp.gov.br/api/consulta/v3/api-docs` e `https://pncp.gov.br/pncp-consulta/v3/api-docs` (*connection reset*).
- Swagger da API de integração: `https://pncp.gov.br/api/pncp/swagger-ui/index.html?configUrl=/pncp-api/v3/api-docs/swagger-config` (mesma falha de conexão).

Consequência: **não há snapshot do OpenAPI vivo**. Endpoints que aparecem só em páginas de terceiros (ver secção 6) não entram no desenho até o JSON oficial ser gravado.

O PDF de consultas não traz número de versão da API além do path `/v1/` e da própria “Versão 1.0” do manual.

## 2. Há duas APIs, com bases diferentes

O prompt aponta a API de Consulta. O próprio manual de consultas (secção 6.4.1) manda buscar itens, documentos e resultados no Manual de Integração, que usa outra base.

| API | Base documentada | Autenticação | Papel neste estudo |
| --- | --- | --- | --- |
| Consulta | `https://pncp.gov.br/api/consulta` | Não. O manual de consultas não pede credencial. Todos os exemplos são `GET`. | Varredura por período: contratações, atas e contratos. |
| Integração | `https://pncp.gov.br/api/pncp` em produção; `https://treina.pncp.gov.br/api/pncp` em treino. Nos exemplos, `${BASE_URL}`. | Inserção, retificação e exclusão exigem JWT (`POST /v1/usuarios/login`, cabeçalho `Authorization: Bearer …`, validade de 1 hora). Os `GET` de consulta unitária nos exemplos **não** enviam esse cabeçalho. O manual diz que o acesso ao portal de consultas é público e que a autenticação vale para manutenção. | Itens, resultado de item e contratos de uma contratação já identificada. |

Protocolo, nas duas: REST sobre HTTP 1.1, corpo JSON. O manual de integração acrescenta: cabeçalhos em ISO-8859-1; ficheiros enviados em UTF-8 quando aplicável. A API de consulta não declara charset.

Não foi verificado ao vivo se os `GET` de `/api/pncp/.../itens` respondem sem token. Isso fica para o piloto, com um único identificador público, antes de qualquer laço.

## 3. Endpoints confirmados que o desenho usa

### 3.1 Contratações por data de publicação

Fonte: manual de consultas, secção 6.3.

`GET https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao`

Parâmetros:

| Parâmetro | Tipo | Obrigatório | Notas do manual |
| --- | --- | --- | --- |
| `dataInicial` | Data | Sim | Formato `AAAAMMDD`. |
| `dataFinal` | Data | Sim | Formato `AAAAMMDD`. O manual **não** declara intervalo máximo entre as duas datas. |
| `codigoModalidadeContratacao` | Inteiro | Sim | Um código por chamada. Não existe parâmetro “todas as modalidades”. |
| `pagina` | Inteiro | Sim | Os exemplos usam `pagina=1`. O manual não diz o que acontece com `0`. |
| `codigoModoDisputa` | Inteiro | Não | |
| `uf` | String | Não | UF da unidade administrativa. |
| `codigoMunicipioIbge` | String | Não | |
| `cnpj` | String | Não | Órgão proprietário da contratação. Nome do parâmetro aqui é `cnpj`, não `cnpjOrgao`. |
| `codigoUnidadeAdministrativa` | String | Não | |
| `idUsuario` | Inteiro | Não | Sistema que publicou. |
| `tamanhoPagina` | Inteiro | Não | “Por padrão cada página contém no máximo 50 registros”; pode ser ajustado “até o limite de 500”. |

O texto da secção diz “Dados a serem enviados no cabeçalho da requisição”, mas o `curl` oficial coloca os parâmetros na query string. O desenho segue o `curl`.

Não há parâmetro de busca por texto. Confirma a regra do prompt: o filtro de IA é local.

Envelope (secção 4.2, explícita para PCA e contratações):

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `data` | Vetor | Registros da página. |
| `totalRegistros` | Inteiro | |
| `totalPaginas` | Inteiro | |
| `numeroPagina` | Inteiro | |
| `paginasRestantes` | Inteiro | |
| `empty` | Booleano | `data` vazio. |

Códigos: 200 OK, 204 No Content, 400, 422, 500. O manual não documenta 429 nem quota. Qualquer pausa entre chamadas será escolha metodológica (ver `docs/decisions.md`), não regra publicada.

Campos de cada contratação que o estudo precisa, tal como nomeados na secção 6.3:

| Campo | Uso |
| --- | --- |
| `numeroControlePNCP` | Identificador único. Máscara documentada: `99999999999999-1-999999/9999` (CNPJ 14 + marcador `1` + sequencial 6 + ano 4). |
| `numeroCompra`, `anoCompra`, `sequencialCompra`, `processo` | Chaves de origem e para montar o path dos itens. |
| `modalidadeId`, `modalidadeNome` | Modalidade. |
| `modoDisputaId`, `modoDisputaNome` | |
| `situacaoCompraId`, `situacaoCompraNome` | Situação da contratação (domínio na secção 5.5: 1 Divulgada, 2 Revogada, 3 Anulada, 4 Suspensa). O tipo do nome está escrito “Inteiro” na tabela; o valor descrito é textual. Guardar o JSON bruto resolve a dúvida. |
| `objetoCompra` | Texto (5120). Objeto. É o texto principal da camada em lote. |
| `informacaoComplementar` | Texto (5120). |
| `srp` | Booleano. Sistema de registro de preços. |
| `amparoLegal.codigo`, `.nome`, `.descricao` | |
| `valorTotalEstimado` | Decimal, 4 casas. **Zero** se o orçamento for sigiloso e o item não tiver resultado. |
| `valorTotalHomologado` | Decimal, 4 casas. |
| `dataAberturaProposta`, `dataEncerramentoProposta` | Data e hora, horário de Brasília. |
| `dataPublicacaoPncp`, `dataInclusao`, `dataAtualizacao` | |
| `orgaoEntidade.cnpj`, `.razaosocial`, `.poderId`, `.esferaId` | `poderId`: L Legislativo, E Executivo, J Judiciário. `esferaId`: F Federal, E Estadual, M Municipal, **D Distrital**. |
| `unidadeOrgao.codigoUnidade`, `.nomeUnidade`, `.codigoIbge`, `.municipioNome`, `.ufSigla`, `.ufNome` | UF e município saem da unidade, não de um campo solto “UF do órgão”. |
| `orgaoSubRogado` / `unidadeSubRogada` | Mesma estrutura, quando houver. A numeração da tabela salta (27 órgão, 28.x campos, 29 unidade). |
| `usuarioNome` | Sistema de origem. |
| `linkSistemaOrigem` | URL do sistema de origem para propostas. **Não** é documentado como URL da ficha no PNCP. |
| `justificativaPresencial` | |

O que a secção 6.3 **não** devolve, e o prompt pedia:

- Descrição de itens, quantidade, valor unitário, código de catálogo. Itens são outro serviço (secção 3.2).
- Fornecedor. Está no contrato (secção 3.4) e no resultado do item (secção 3.3), não neste payload.
- Tipo de órgão / natureza jurídica **do órgão contratante**. A natureza jurídica documentada no retorno de resultado é a do fornecedor. Não há campo “tipo de órgão” na contratação. Tratar isso como variável da RQ2 exigiria uma classificação externa; isso ainda não foi decidido.
- Link canónico da contratação no portal PNCP. Não está neste payload.

### 3.2 Itens de uma contratação

Fonte: manual de integração, corpo lido como v. 2.5, secção 10.13. O manual de consultas (6.4.1) aponta para o mesmo serviço.

`GET ${BASE_URL}/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/itens`

`${BASE_URL}` de produção, secção 5.3: `https://pncp.gov.br/api/pncp`.

Entrada (path e query):

| Campo | Tipo | Notas |
| --- | --- | --- |
| `cnpj` | Texto (14) | Path. Órgão proprietário. |
| `ano` | Inteiro | Path. Ano da contratação. |
| `sequencial` | Inteiro | Path. `sequencialCompra`, não o número no sistema de origem. |
| `pagina` | Inteiro | Query. O manual **não** diz se é obrigatório nem o máximo. |
| `tamanhoPagina` | Inteiro | Query. O manual **não** declara o limite. Não usar 500 por analogia com a outra API até o piloto medir a resposta. |

O `curl` oficial não envia `Authorization`.

Retorno: lista `itens`. Campos que o estudo usa:

| Campo | Notas |
| --- | --- |
| `numeroItem` | Inteiro, único e crescente na contratação. |
| `descricao` | Texto (2048). Entra no texto de análise, **separado** de `objetoCompra` no bruto. |
| `informacaoComplementar` | Texto complementar do item. |
| `ncmNbsCodigo`, `ncmNbsDescricao` | NCM/NBS. A descrição pode repetir linguagem de catálogo, não necessariamente o objeto comprado. |
| `quantidade` | Decimal, até 4 casas. |
| `unidadeMedida` | Texto (30). |
| `valorUnitarioEstimado`, `valorTotal` | Decimal. Zero se `orcamentoSigiloso` for verdadeiro e o item não tiver resultado. |
| `materialOuServico`, `materialOuServicoNome` | `M` ou `S`. |
| `situacaoCompraItemId`, `situacaoCompraItemNome` | Domínio 5.6 do manual de consultas: 1 Em andamento, 2 Homologado, 3 Anulado/Revogado/Cancelado, 4 Deserto, 5 Fracassado. |
| `temResultado` | Booleano. |
| `orcamentoSigiloso` | Booleano. |
| `catalogoCodigoItem` | Código no catálogo de referência. |
| `catalogo` | Objeto (`id`, `nome`, `descricao`, datas, `statusAtivo`, `url`). |
| `categoriaItemCatalogo` | Objeto (`id`, `nome`, `descricao`, …). É categoria de catálogo, não “tipo de órgão”. |
| `criterioJulgamentoId`, `criterioJulgamentoNome` | |
| `dataInclusao`, `dataAtualizacao` | |

Códigos: 200, 400, 422, 500. Este `GET` **não** lista 204 na secção 10.13.5.

Consulta de um item só, se precisar: `GET .../itens/{numeroItem}` (secção 10.14). Não é necessária para a varredura.

### 3.3 Resultados do item (fornecedor e valor homologado do item)

Fonte: secção 10.17 do mesmo corpo.

`GET ${BASE_URL}/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/itens/{numeroItem}/resultados`

Sem `Authorization` no `curl`. Sem paginação documentada.

Lista `listaResultados`. Campos relevantes: `quantidadeHomologada`, `valorUnitarioHomologado`, `percentualDesconto`, `tipoPessoa` (`PJ`, `PF`, `PE`), `niFornecedor`, `nomeRazaoSocialFornecedor`, `porteFornecedorId`, `porteFornecedorNome`, `dataResultado`, `situacaoCompraItemResultadoId`.

`niFornecedor` é CNPJ, **CPF** ou identificador estrangeiro. CPF é dado pessoal. O bruto pode guardá-lo no snapshot de investigação; a exportação pública do artigo não pode incluí-lo. Ver decisões.

Este endpoint é por item. Multiplica o número de chamadas. Não entra na coleta em massa até o piloto de um mês medir volume e ganho de texto. O texto do fornecedor não descreve o uso da IA; o ganho analítico aqui é valor homologado e fornecedor agregado.

### 3.4 Contratos e empenhos por data de publicação

Fonte: manual de consultas, secção 6.6.

`GET https://pncp.gov.br/api/consulta/v1/contratos`

| Parâmetro | Obrigatório | Notas |
| --- | --- | --- |
| `dataInicial`, `dataFinal` | Sim | `AAAAMMDD`. Publicação do contrato, não da contratação. |
| `pagina` | Sim | |
| `cnpjOrgao` | Não | Aqui o nome é `cnpjOrgao`. |
| `codigoUnidadeAdministrativa` | Não | |
| `usuarioId` | Não | Na contratação o parâmetro chama-se `idUsuario`. |
| `tamanhoPagina` | Não | Padrão no máximo 500; ajustável até 500. |

Ligação com a contratação: `numeroControlePNCPCompra`. Identificador do contrato: `numeroControlePNCP` (máscara `99999999999999-2-999999/9999`, marcador `2`).

Texto adicional: `objetoContrato` (5120) e `informacaoComplementar` (5120). Pode repetir o objeto da contratação ou acrescentar detalhe. Isso será medido no piloto, não assumido.

Valor: `valorInicial`, `valorParcela`, `valorGlobal`, `valorAcumulado`. Fornecedor: `tipoPessoa`, `niFornecedor`, `nomeRazaoSocialFornecedor` (e campos de subcontratado). Mesma ressalva de CPF.

Órgão: `orgaoEntidade.cnpj`, `.razaoSocial`, `.poderId`, `.esferaId`; unidade com `codigoIbge`, `municipioNome`, `ufSigla`, `ufNome`.

`categoriaProcesso` (domínio 5.11, inclui código 3 Informática/TIC) existe no contrato, **não** na listagem de contratações da secção 6.3. Não serve de filtro prévio do universo de contratações.

Códigos: 200, 204, 400, 422, 500.

Contratos de uma contratação já conhecida, se o piloto mostrar que vale a pena: `GET ${BASE_URL}/v1/orgaos/{cnpj}/contratos/contratacao/{anoContratacao}/{sequencialContratacao}` (manual de integração, secção 12.10). Também sem `Authorization` no exemplo.

### 3.5 Atas de registro de preço por vigência

Fonte: manual de consultas, secção 6.5.

`GET https://pncp.gov.br/api/consulta/v1/atas`

| Parâmetro | Obrigatório | Notas |
| --- | --- | --- |
| `dataInicial`, `dataFinal` | Sim | `AAAAMMDD`. O texto diz que devolve atas **cuja vigência coincida** com o período, não atas publicadas no período. |
| `pagina` | Sim | |
| `idUsuario` | Não | |
| CNPJ do órgão | Não | A tabela extraída do PDF nomeia `cnpj`. O segundo `curl` do mesmo manual usa `cnpjOrgao`. **Contradição interna.** O piloto deve testar os dois nomes num único dia e gravar qual devolve 200. Até lá, nenhum dos dois é tratado como certo. |
| `codigoUnidadeAdministrativa` | Não | |
| `tamanhoPagina` | Não | Padrão no máximo 500; até 500. |

Ligação: `numeroControlePNCPCompra`. Identificador da ata: `numeroControlePNCPAta`. Texto: `objetoContratacao` (pode ser o objeto da contratação, não um texto novo). Não há descrição de itens da ata neste payload.

Códigos: 200, 204, 400, 422, 500.

A secção 4.2 descreve o envelope `data` / `totalRegistros` / `totalPaginas` para PCA e contratações. Para atas e contratos o manual começa a lista de campos pelo agrupador (`Atas`) ou por `numeroControlePNCP`, sem repetir o envelope. O piloto confirma se o envelope é o mesmo antes de generalizar o parser.

## 4. Domínio de modalidade (obrigatório na varredura)

Manual de consultas, secção 5.2. Uma chamada de publicação por código:

| Código | Nome |
| --- | --- |
| 1 | Leilão - Eletrônico |
| 2 | Diálogo Competitivo |
| 3 | Concurso |
| 4 | Concorrência - Eletrônica |
| 5 | Concorrência - Presencial |
| 6 | Pregão - Eletrônico |
| 7 | Pregão - Presencial |
| 8 | Dispensa de Licitação |
| 9 | Inexigibilidade |
| 10 | Manifestação de Interesse |
| 11 | Pré-qualificação |
| 12 | Credenciamento |
| 13 | Leilão - Presencial |

O manual de integração expõe `GET /v1/modalidades` e `GET /v1/modalidades?statusAtivo=true`. A lista ativa pode ter crescido depois do PDF. O piloto deve gravar a lista viva e comparar com estes 13 códigos. Códigos novos entram na coleta; códigos desta tabela que a API rejeitar são registados, não silenciosamente omitidos.

Esfera e poder usados na RQ2 estão no payload (`esferaId`, `poderId`), com o quarto valor **D** (Distrital), que o prompt não nomeava.

## 5. Fora do desenho inicial

| Serviço | Porquê fica de fora |
| --- | --- |
| `GET /v1/contratacoes/proposta` (consultas, 6.4) | Só propostas em aberto. Não reconstrói o histórico 2021–hoje. A tabela marca `codigoModalidadeContratacao` como obrigatório; o parágrafo diz que a modalidade é opcional. Não precisamos deste endpoint para as RQ. |
| `GET /v1/pca/` e `GET /v1/pca/usuario` | Plano de contratações anual: intenção, não contratação realizada. O prompt não pede PCA. |
| Documentos (`.../arquivos`) | PDF de edital/TR. Fora da API de metadados. Baixar anexos mudaria o corpus e os termos de volume. Não está no desenho. |
| Histórico, imagens de item, fontes orçamentárias, empenhos aninhados | Sem texto de objeto além do que já vem na contratação, no item ou no contrato. |

## 6. Mencionado fora do manual de consultas e ainda não confirmado

Páginas de terceiros e um índice de Swagger descrevem, na base `/api/consulta`, caminhos que **não** estão no PDF versão 1.0, entre eles `GET /v1/contratacoes/atualizacao`, `GET /v1/atas/atualizacao`, `GET /v1/contratos/atualizacao`. O OpenAPI que os confirmaria não foi descarregado (secção 1). **Não serão chamados** até existir um `docs/openapi-consulta.json` gravado a partir do URL oficial, com hash no manifest.

Também não se assume que `GET /api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/itens` exista. O path de itens documentado está em `/api/pncp`.

## 7. Paginação, erros e limites que o manual não fixa

- Contratações por publicação: página padrão até 50, `tamanhoPagina` até 500.
- Propostas, atas, contratos e PCA: página padrão até 500, teto 500.
- Itens: `pagina` e `tamanhoPagina` existem; teto não documentado.
- Intervalo máximo `dataInicial`–`dataFinal`: não documentado. O piloto começa com janelas curtas (um dia, depois um mês) e só alarga se a API devolver o recorte completo (`totalRegistros` coerente com a soma das páginas).
- Rate limit: não documentado. Não inventar um número “oficial”.
- Retentativas: o manual não define. 400 e 422 são erro de pedido (não repetir às cegas). 500 e falha de rede podem ser repetidos. 204 e `empty: true` são sucesso sem registos, não erro.
- `valorTotalEstimado` e valores de item sigiloso voltam 0. Zero não é “compra de valor nulo”; é valor oculto ou ausente. A análise tem de separar essas situações com `orcamentoSigiloso` / `temResultado`, senão a mediana fica enviesada para baixo.
- `objetoCompra` trunca em 5120 caracteres e `descricao` do item em 2048. Objetos longos podem perder a menção a IA. Quantificar no piloto a fração de textos no limite.

CNPJ alfanumérico: o histórico da v. 2.5 (11/06/2026) diz que a Receita passa a atribuir CNPJ alfanumérico a **novas** inscrições a partir de julho de 2026, e que os números já existentes não mudam. O path continua descrito como texto de 14 caracteres. O cliente não pode assumir que `cnpj` é só dígito. A máscara numérica `99999999999999-1-999999/9999` do PDF de consultas é anterior a essa nota.

## 8. Divergências em relação ao prompt

1. Itens não vêm na listagem. Cada contratação exige um `GET` adicional em **outra base** (`/api/pncp`, não `/api/consulta`).
2. Não há busca textual. Isso coincide com o prompt.
3. `codigoModalidadeContratacao` é obrigatório. A coleta itera os códigos da secção 5.2 (e os que a lista viva acrescentar).
4. Datas são `AAAAMMDD`, não ISO-8601.
5. Esfera tem código `D` (Distrital), além de F/E/M.
6. Não há campo de tipo de órgão na contratação.
7. Fornecedor e valor por item estão em endpoints por registo, com CPF possível em `niFornecedor`.
8. O manual não publica rate limit nem janela máxima de datas. Qualquer número desses no `config.yaml` será decisão nossa, testada no piloto, não um limite oficial.
9. O Swagger pedido no prompt esteve indisponível nesta sessão. O manual PDF e o manual de integração HTML são a fonte até o OpenAPI ser arquivado.
10. Coletar itens (e contratos) para **todas** as contratações desde 2021 é um produto cartesiano: 13 modalidades × páginas × um `GET` de itens por contratação × páginas de itens. O prompt autoriza uma estratégia em duas etapas quando o volume for inviável. A proposta está na secção 9 e **não foi executada**.

## 9. Proposta de coleta (aguardando confirmação antes do piloto)

Não coletar o universo inteiro de itens na primeira passagem.

1. **Cabeçalhos.** `GET /v1/contratacoes/publicacao` para todas as modalidades, em janelas curtas, de 2021-01-01 até a data da coleta (a Lei nº 14.133 é de 1º de abril de 2021; meses anteriores podem voltar vazios e devem ser contados, não saltados sem registo). Gravar JSONL bruto, sem transformar.
2. **Piloto de um mês** (mês a fixar no `config.yaml` depois desta revisão). Além dos cabeçalhos, buscar itens de **todas** as contratações desse mês, mais atas e contratos do mesmo recorte. Medir: contratações, itens por contratação, textos de item que contêm termos de IA quando `objetoCompra` não contém, tempo e erros HTTP.
3. **Viés se os itens ficarem só para candidatas.** IA citada apenas na descrição do item, com objeto genérico (“solução de TIC”, “software”), sai do corpus. O piloto quantifica essa perda. Se ela for material, a segunda etapa não pode restringir-se às candidatas lexicais do objeto. Se for rara, restringir é defensável e tem de ser escrito como limitação, com o número do piloto.
4. Contratos e atas entram na coleta completa só se o piloto mostrar texto ou valor que a contratação não traz. Caso contrário ficam como fonte de ligação e de fornecedor para o subconjunto incluído, com a limitação declarada.

Checkpoint previsto, ainda sem código: ficheiro por modalidade e por janela de datas, com a última página confirmada, para retomar sem repetir páginas já gravadas. Duplicatas pelo `numeroControlePNCP` são contadas, não fundidas no bruto; a deduplicação é etapa posterior.

## 10. O que falta antes de escrever o cliente

- Confirmação desta leitura, em especial da proposta da secção 9 e do mês do piloto.
- Uma chamada real (piloto mínimo: um dia, uma modalidade) para arquivar o JSON de resposta e o OpenAPI, e para decidir `cnpj` versus `cnpjOrgao` nas atas.
- Releitura das secções 10.13, 6.3 e 6.6 na v. 2.6 quando a página deixar de responder 500, para ver se algum nome de campo mudou depois de 11/06/2026.
