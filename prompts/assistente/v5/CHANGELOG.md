# assistente

## v5 (20/10/2026)

Corrige o laço de busca e o markdown. No v4, pergunta que misturava BIM e previsão do tempo fazia o
modelo buscar a cidade nos documentos (repetidas vezes, até `LIMITE_PASSOS`) em vez de usar
`listar_obras` e `consultar_mcp`; e ele escrevia `**` mesmo com a regra de não usar markdown. O v5
diz de onde vêm os dados cadastrais (listar_obras), o caminho da previsão do tempo (cidade da obra,
sem UF, em `consultar_mcp`), reforça "nunca ** nem #" e proíbe repetir a mesma busca. O resto é
igual ao v4.
