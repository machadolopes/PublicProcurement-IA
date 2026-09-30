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
