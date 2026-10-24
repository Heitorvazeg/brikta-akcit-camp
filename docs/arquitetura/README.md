# Arquitetura da IA — diagramas

Visão por dentro do serviço de IA. O contexto entre repositórios (C4 níveis 1 e 2) fica em
`docs/03-arquitetura/`; o desenho e os critérios, em `docs/planos/plano-de-implementacao.md`.

| Diagrama | O que mostra |
|---|---|
| [IA_C4_3_Componentes](IA_C4_3_Componentes.png) | API FastAPI, fila de jobs no Postgres, pipeline de RDO por voz (determinístico, ADR-07), providers atrás de `Protocol`, Assistente (agente, `RegistroFerramentas`, `ContextoExecucao`, MCP, verificação de citações) e índice próprio. ✓ marca o que já existe no código. |
| [IA_Fluxo_Assistente](IA_Fluxo_Assistente.png) | Uma pergunta ao Assistente do começo ao fim: passe emitido pelo backend e conferido localmente, ferramentas validadas pelo registro, dados vindos do backend/SQL, verificação das citações e resposta por SSE. **Desenho-alvo:** o protótipo (IA-66) já faz a entrada com o passe e o laço do agente; os dados ainda são de exemplo (BE-51). |
| [IA_C4_3_Assistente_Simplificado](IA_C4_3_Assistente_Simplificado.png) | Só o Assistente, em seis peças: borda (passe), agente, registro de ferramentas, ferramentas, verificação de citações e política de risco, com o backend, o banco e o provedor de LLM. Para a visão rápida; o completo é o `IA_C4_3_Componentes`. |
| [IA_C4_3_Assistente_Completo](IA_C4_3_Assistente_Completo.png) | Versão do `IA_C4_3_Componentes` só com o Assistente, mas com todas as peças e cada ferramenta aberta: `listar_obras`, `consultar_rdos`, `buscar_documentos`/`ler_pagina`, `consultar_modelo_bim` e `consultar_mcp` (amarelo = dados de exemplo), o serviço de conversa, o prompt `assistente/v4`, o registro de ferramentas como porteiro e o que ainda é planejado (dados reais, verificação de citações, política de risco). Setas verdes 1–12. |
| [IA_Fluxo_Agentes](IA_Fluxo_Agentes.png) | Fluxograma dos dois fluxos que usam o mesmo agente e o mesmo registro de ferramentas: a pergunta do usuário ao Assistente (passe, SSE) e o Resumo IA (cron do backend, `POST /v1/jobs/resumo`, callback HMAC), com o laço do agente no meio (até 4 passos, ferramentas somente leitura, citações RDO, DOCUMENTO, BIM e EXTERNO). |

## Como ler

- **De cima para baixo:** quem usa → entrada → peças internas → bancos e serviços externos.
- **Setas grossas numeradas** são o caminho principal; siga os números. O que ele conta está na
  legenda de rodapé de cada imagem.
- **Cores** (paleta do app, `constants/brikta-theme.ts` do mobile): verde-escuro = pessoa;
  caixa verde-clara = peça central; azul-escura = segurança; branca = componente; cinza tracejada = previsto; amarela = mock;
  laranja tracejada = proposta não aprovada; cinza-escura = serviço externo; seta azul tracejada =
  assíncrono; seta roxa "REST:" = demais endpoints. Cada diagrama tem a própria legenda.
- Os diagramas de sequência agrupam os participantes por repositório (caixas de fundo).

- **IA:** verde 1–11 = uma pergunta ao Assistente; azul-petróleo V1–V8 = RDO por voz; ícone de
  check = já existe no código. A proposta em laranja (acesso a dados em degraus; busca nos textos do
  RDO sem pgvector) só vale depois de registrada no plano/ADR — hoje a ADR-11 proíbe texto → SQL.
- **Segurança do Assistente** (azul): autenticação → limites/cota → API na entrada; política de risco
  técnico (RN59), registro de ferramentas como porteiro e verificação de citações. Por que POST + SSE
  e não WebSocket: ADR-06 no `PLANO_DE_IMPLEMENTACAO.md`.

## Re-renderizar

```bash
# PlantUML >= 1.2023 (biblioteca C4 embutida) + Java
java -jar plantuml.jar -tpng docs/arquitetura/*.puml   # rodar de dentro da pasta do componente
```
Edite o `.puml` e re-renderize o `.png` no mesmo commit — a imagem é o que a maioria lê.
O estilo fica em `docs/03-arquitetura/_estilos/` na raiz do monorepo (`c4.iuml`, `sequencia.iuml`), compartilhado por todos os componentes; o app mobile, em repositório próprio, mantém uma cópia.
O layout é o `smetana` embutido (sem Graphviz); ele quebra com `Lay_*`, então a ordem vem da direção das setas (`Rel_U` para setas que voltam para cima).
Evite `→`, `≤`, `⇄`, `✓` no texto: a fonte não tem esses glifos (use `<&check>` para o check).
