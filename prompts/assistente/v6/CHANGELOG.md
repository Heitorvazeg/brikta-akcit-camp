# assistente

## v6 (20/10/2026)

Mesmo comportamento do v5 (respostas completas e específicas, clima por `consultar_mcp`, sem
markdown, sem repetir busca) em cerca de 25% menos texto, agrupado em Como responder, Dados e
Cuidados. Cada passo do agente reenvia o prompt inteiro e o provedor limita tokens por minuto
(Groq: 8000), então prompt menor deixa caber mais perguntas. `listar_obras` deixa de ser ferramenta
do modelo (fica só no servidor, que a chama para montar o contexto): a lista de obras do contexto
passa a trazer cidade, unidade, etapa, progresso e responsável, o que tira um passo das perguntas
de clima e de andamento.
