# Brikta IA — Implementação (documento vivo)

> **Este documento é o lugar do status.** Cada atividade `IA-xx` tem aqui seu estado atual; a descrição completa, os critérios e o "porquê" estão em [`planos/plano-de-implementacao.md`](planos/plano-de-implementacao.md) (Seção 14 e as seções citadas).
> Visão do repositório: [`VISAO_GERAL.md`](VISAO_GERAL.md).

| | |
|---|---|
| **Última atualização** | 15/10/2026 — protótipo do Assistente (IA-66 e IA-64 parciais) |
| **Fase atual** | IA-F0 — Fundação · protótipo do Assistente adiantado (IA-F6) |
| **Próximos itens recomendados** | IA-01 (aceitar ADRs) · IA-03 (revisar contratos com o backend) · IA-04/05/07 (áudios e glossário com o Carlos) |

---

## 0. Como manter este documento

1. **No mesmo PR** que avança uma atividade: atualize o checkbox, a coluna "Situação" e, se a implementação divergiu do plano, anote aqui **o que foi feito** (e ajuste o plano se a decisão mudou).
2. Trabalho novo → novo `IA-xx` (próximo livre na fase) aqui **e** no plano (Seção 14), + histórico (Seção 6).
3. Decisão tomada → status do ADR em `docs/decisoes/README.md` e na Seção 4 abaixo.
4. Atualize a data e a "Fase atual".

**Legenda:** `[ ]` pendente · `[~]` parcial · `[x]` feito.

---

## 1. Estado atual do código (15/10/2026)

| Componente | Situação | Arquivos |
|---|---|---|
| Projeto (uv, Python 3.12), lint, tipos, testes | ✅ 26 testes passando; ruff e pyright limpos | `pyproject.toml`, `tests/` |
| API FastAPI + `/health` | ✅ | `main.py`, `api/health.py` |
| Autenticação por token de serviço (com rotação) | ✅ | `api/auth.py` |
| Configuração por ambiente | ✅ | `config.py`, `.env.sample` |
| Logs estruturados | ✅ | `observability/logging.py` |
| `RdoProposto` v1 | ✅ | `domain/rdo_schema.py` |
| Contratos v1 (job, resultado, RDO) + JSON Schemas + exemplos | ✅ rascunho — **aguardando revisão com o backend (IA-03)** | `domain/contratos.py`, `contracts/`, `tests/contract/exemplos/` |
| Estados do job e transições | ✅ | `domain/estados.py` |
| Códigos de erro | ✅ | `domain/erros.py` |
| Assinatura HMAC do callback (assinar/verificar) | ✅ | `integrations/assinatura.py` |
| Interfaces de STT, LLM, embeddings + fakes | ✅ | `providers/` |
| Registro de ferramentas do Assistente + guardrails (contexto injetado, obra visível, só leitura, timeout) | ✅ | `assistente/ferramentas/registro.py` |
| Dockerfile (ffmpeg) + compose (Postgres + pgvector) | ✅ imagem construída e `/health` testado localmente | `Dockerfile`, `infra/docker-compose.yml` (raiz do monorepo) |
| CI (GitHub Actions) | ✅ verde (lint, formatação, tipos, contratos, testes, build da imagem) | `.github/workflows/ci-ia.yml` (raiz do monorepo) |
| Assistente (protótipo): passe do backend, conversa em SSE, agente com laço próprio, ferramentas de exemplo, provedor compatível com OpenAI (Groq) | ✅ protótipo · 71 testes | `api/assistente.py`, `assistente/` (`passe.py`, `servico.py`, `conversas.py`, `contexto.py`, `fabrica.py`, `agente/`, `ferramentas/exemplo.py`, `ferramentas/execucao.py`), `providers/llm/openai_compativel.py`, `prompts/assistente/v2/`, `contracts/assistente_*.v1.json` |
| Pipeline, fila, banco, provedores reais do RDO, framework de agente, MCP | ❌ | pacotes com descrição do que entra |

---

### 1.1 Assistente: onde cada evolução entra

O protótipo foi montado para que as próximas etapas troquem uma peça de cada vez. A fábrica (`assistente/fabrica.py`) é o único lugar que escolhe implementações.

| Evolução | O que muda | O que não muda |
|---|---|---|
| Framework de agente (IA-64a/65) | Nova implementação de `Agente` (`agente/base.py`) + valor em `ASSISTENTE_AGENTE` | Serviço, rotas, contrato, ferramentas, guardrails, citações |
| Ferramentas reais (BE-51) | `ferramentas/backend.py` com os mesmos nomes e entradas; `ASSISTENTE_FERRAMENTAS=backend` | Agente, prompt, contrato |
| Mais ferramentas (RAG, documentos, BIM) | Registrar no `RegistroFerramentas` | Agente e serviço (as citações saem do `ExecucaoFerramentas`) |
| Conversas no Postgres (IA-61) | Nova implementação de `RepositorioConversas` | Serviço e rotas |
| Laço maior (mais passos, multiagente) | `ASSISTENTE_MAX_PASSOS`; nova implementação de `Agente` | Limite de chamadas e citações seguem no `ExecucaoFerramentas` |
| Outro provedor de LLM | `LLM_ASSISTENTE_*` (compatível com OpenAI) ou novo adaptador em `providers/llm/` | Tudo fora de `providers/` |
| Contrato `.v2` | `domain/assistente.py` + tradução em `servico.py` | Agente (emite eventos neutros) |
| Servidor MCP (IA-6M) | Expõe o mesmo `RegistroFerramentas` | Guardrails e testes de isolamento |

## 2. Atividades por fase

Detalhes de cada item: Plano, Seção 14 (e a seção indicada).

### IA-F0 — Planejamento e fundação

| | ID | Atividade | Situação |
|---|---|---|---|
| [x] | IA-00 | Repositório com plano, README e CLAUDE.md | Feito em 27/09/2026 |
| [ ] | IA-01 | Aceitar/alterar ADR-01 a ADR-11 (`docs/decisoes/`) | Todos como "Proposta" |
| [x] | IA-02 | Esqueleto: uv, FastAPI, settings, structlog, ruff, pyright, pytest, Docker, compose, CI | CI verde no GitHub em 27/09/2026 (qualidade + build da imagem) |
| [~] | IA-03 | Contratos v1 revisados em conjunto com o backend | Modelos, schemas e exemplos prontos; **falta a revisão conjunta** |
| [ ] | IA-04 | Coleta dos 30 áudios com consentimento | Termo-modelo em `eval/CONSENTIMENTO.md` (revisar com jurídico) |
| [~] | IA-05 | Glossário seed (150–300 termos) | 26 termos iniciais em `glossario/seed.csv`; completar com o Carlos |
| [ ] | IA-06 | Contas e limites de gasto nos provedores | — |
| [ ] | IA-07 | Anotação dos áudios (referência + RDO esperado + termos) | — |

### IA-F1 — Transcrição (Plano, 5.2 e 7)

| | ID | Atividade | Situação |
|---|---|---|---|
| [~] | IA-10 | `SpeechToText` + fake | Interface e fake prontos |
| [ ] | IA-11 | Normalização de áudio (ffprobe/ffmpeg) | — |
| [ ] | IA-12 | Adaptador OpenAI (Whisper) | — |
| [ ] | IA-13 | Seleção de dicas do glossário | — |
| [ ] | IA-14 | Pós-processamento (correção fuzzy, números, unidades) | — |
| [ ] | IA-15 | Avaliação de STT + baseline | — |
| [ ] | IA-16 | Script `transcrever_arquivo.py` | — |

### IA-F2 — Extração estruturada (Plano, 5.3–5.6)

| | ID | Atividade | Situação |
|---|---|---|---|
| [~] | IA-20 | `RdoProposto` v1 + versão reduzida para o modelo | Schema completo pronto; falta gerar o schema reduzido (sem `CAMPOS_PREENCHIDOS_POR_CODIGO`) |
| [~] | IA-21 | `LLMEstruturado` + adaptador real + fake | Interface e fake prontos |
| [ ] | IA-22 | Prompt `rdo_extracao/v1` | — |
| [ ] | IA-23 | Montagem de contexto | — |
| [ ] | IA-24 | Validação + casamento com catálogo + retentativa | — |
| [ ] | IA-25 | `campos_incertos` finais + verificação de evidência | — |
| [ ] | IA-26 | Script `extrair_de_texto.py` | — |
| [ ] | IA-27 | Avaliação da extração + baseline | — |

### IA-F3 — Serviço e integração (Plano, 3, 6 e 12)

| | ID | Atividade | Situação |
|---|---|---|---|
| [ ] | IA-30 | Banco + Alembic | Compose com pgvector pronto |
| [ ] | IA-31 | Fila + processo worker | — |
| [~] | IA-32 | `POST /v1/jobs/rdo-voz` e `GET /v1/jobs/{id}` | Autenticação de serviço pronta; rotas não |
| [~] | IA-33 | Orquestrador (estados, timeouts, retentativas) | `transicao_valida` pronta |
| [~] | IA-34 | Outbox de callbacks com HMAC | Assinatura pronta; outbox não |
| [ ] | IA-35 | Custo e latência por etapa | — |
| [ ] | IA-36 | Testes de integração e contrato | Testes de contrato dos schemas prontos |
| [ ] | IA-37 | Ponta a ponta com o backend local | Depende de BE-40..43 |
| [ ] | IA-38 | Deploy em staging | Depende de INFRA-14 |

### IA-F4 — Endurecimento e produção

| | ID | Atividade | Situação |
|---|---|---|---|
| [ ] | IA-40 | Provedores secundários + A/B | — |
| [ ] | IA-41 | Observabilidade (Sentry, OTel, Langfuse, alertas) | — |
| [ ] | IA-42 | Circuit breaker, limites e orçamento por empresa | — |
| [ ] | IA-43 | Runbooks | — |
| [ ] | IA-44 | Teste de carga | — |
| [ ] | IA-45 | Revisão de segurança e LGPD | — |
| [ ] | IA-46 | Produção | — |

### IA-F5 — Aprendizado contínuo

| | ID | Atividade | Situação |
|---|---|---|---|
| [ ] | IA-50 | Receber diffs da revisão | Depende de BE-45 |
| [ ] | IA-51 | Candidatos a glossário + aprovação | — |
| [ ] | IA-52 | Glossário por empresa aplicado | — |
| [ ] | IA-53 | Conjunto de avaliação crescendo com o piloto | — |
| [ ] | IA-54 | Painel de taxa de correção | — |

### IA-F6 — Assistente, camada A (Plano, 9)

| | ID | Atividade | Situação |
|---|---|---|---|
| [ ] | IA-60 | Perguntas reais + obra sintética + conjunto de avaliação | — |
| [ ] | IA-61 | Tabelas de índice, conversas, mensagens | — |
| [ ] | IA-62 | Indexação de RDOs + expurgo | Depende de BE-50 |
| [ ] | IA-63 | Escolha de embeddings | — |
| [~] | IA-64 | Ferramentas com filtros forçados | Registro e guardrails prontos; `ExecucaoFerramentas` (contexto, limite de 6 chamadas, citações só do que foi consultado). `listar_obras` e `consultar_rdos` **de exemplo** (fixtures do app). Reais dependem de BE-51 |
| [ ] | IA-64a | Comparação LangGraph × PydanticAI (× ADK) | — |
| [ ] | IA-65 | Agente no framework escolhido | — |
| [~] | IA-66 | API de conversa (SSE) + passe do backend | **Protótipo (15/10/2026):** `POST /v1/assistente/conversas` e `/mensagens` em SSE, passe conferido localmente (`IA_TICKET_SECRET`; `SUPABASE_JWT_SECRET` removido), idempotência por `cliente_mensagem_id`, uma pergunta por vez, dono da conversa. **Falta:** persistência (IA-61), listar/histórico, cota (IA-68) |
| [ ] | IA-67 | Avaliação + testes de isolamento (bloqueantes) | — |
| [ ] | IA-68 | Limites por plano, custo, cache | — |
| [ ] | IA-69 | Beta com design partners | — |
| [ ] | IA-6M | Servidor MCP `brikta-dados` | — |

### IA-F7 / IA-F8 / IA-F9

| | ID | Atividade | Situação |
|---|---|---|---|
| [ ] | IA-70 | Ingestão de documentos (PDF, plantas, planilhas) | — |
| [ ] | IA-71 | Ferramentas de documentos | `buscar_documentos` e `ler_pagina` existem **simuladas** (`exemplo/documentos.json`); falta a ingestão real |
| [ ] | IA-72 | Avaliação com documentos reais | — |
| [ ] | IA-73 | Ingestão IFC + `consultar_modelo_bim` | Ferramenta **simulada** (`exemplo/bim.json`); falta a ingestão IFC |
| [ ] | IA-74 | Clientes MCP para serviços externos | `consultar_mcp` **simulado** (clima e índices, `exemplo/mcp.json`); falta o cliente MCP real |
| [ ] | IA-80 | Parecer jurídico da camada C | — |
| [ ] | IA-81 | Base técnica de uso permitido | — |
| [ ] | IA-82 | Classificador de risco + políticas | — |
| [ ] | IA-83 | Avaliação técnica com engenheiro | — |
| [ ] | IA-F9 | Inteligência de Obra | Backlog |

---

## 3. Dependências com outros repositórios (resumo)

| Precisamos de | Item | Para |
|---|---|---|
| Backend | BE-40..43 (cliente, disparo, callback, merge) | IA-37 |
| Backend | BE-44 (status para o app), BE-45 (diff da revisão) | MVP, IA-50 |
| Backend | BE-108 ✅ (passe do Assistente) | IA-66 |
| Backend | BE-50, BE-51, BE-52 | Assistente |
| Mobile | MOB-44, MOB-45 (status e revisão), MOB-80 (chat) | MVP, Assistente |
| Infra | INFRA-14 (banco `brikta_ia`, deploy, segredos) | IA-38 |

Tabela completa: Plano, Seção 15.

## 4. Decisões

| ID | Decisão | Situação |
|---|---|---|
| ADR-01..11 | Ver `docs/decisoes/README.md` | Propostas |
| DP-2 | Procrastinate × tabela própria | Pendente (IA-31) |
| DP-3/DP-4 | Provedores padrão de STT e LLM | Pendente (com dados: IA-27/IA-40) |
| DP-10 | Framework de agentes | Pendente (IA-64a) |
| DP-11 | Expor MCP a clientes externos | Pendente (pós-beta) |

## 5. Divergências em relação ao plano

Registre aqui quando a implementação seguir um caminho diferente do plano (e por quê).

| Data | Item | O que mudou |
|---|---|---|
| 27/09/2026 | Estrutura | Subpacotes chamados `fila/` e `servidor_mcp/` (e não `queue/` e `mcp/`) para não colidir com a biblioteca padrão e com o SDK de MCP |
| 15/10/2026 | ADR-06 | App → IA com o **passe** emitido pelo backend, e não com o JWT do login ([revisão](decisoes/ADR-06-passe-do-assistente.md)) |
| 15/10/2026 | ADR-07 / IA-65 | **Laço de agente próprio e temporário** (`agente/laco_proprio.py`) antes da IA-64a, para o protótipo. Fica atrás da interface `Agente`: o framework escolhido entra como outra implementação (`ASSISTENTE_AGENTE`), sem mexer em serviço, rotas, ferramentas nem contrato. Não promover a produção sem a IA-64a |
| 15/10/2026 | IA-61 | Conversas **em memória** (`ConversasEmMemoria`), atrás de `RepositorioConversas`. Exige um processo só da API (o `Dockerfile` sobe `--workers 1`); reiniciar apaga as conversas |
| 15/10/2026 | IA-64 | Ferramentas **de exemplo** sobre uma cópia das fixtures do app (`scripts/copiar_fixtures_app.py`), com os mesmos IDs (a fonte abre o RDO certo). "Hoje" fixo da demonstração em `ASSISTENTE_DATA_REFERENCIA`. Só dados de exemplo vão ao provedor gratuito |
| 20/10/2026 | IA-64 | Os dados de exemplo passam a vir do **seed da demonstração do backend** (`scripts/gerar_dados_do_seed.py`, substitui `copiar_fixtures_app.py`): as 4 obras e os 20 RDOs por obra do staging, com `rdo_local_id` como id (a citação abre o RDO no app). Fotado em 20/10/2026; regerar ao semear de novo em outro dia. Solução definitiva: rotas internas do backend (BE-51) |
| 15/10/2026 | Provedor | Groq (plano gratuito) pelo adaptador compatível com OpenAI, só para o protótipo. A escolha definitiva segue por avaliação (7.2) |
| 15/10/2026 | Prompt | `assistente/v1` e `v2` sem relatório de avaliação (ADR-10): o conjunto do Assistente (IA-60) não existe. Avaliar antes do beta. A v2 recebe os períodos calculados em código (a v1 errava "semana passada" e dias da semana no teste com o Groq) |

## 6. Histórico deste documento

| Data | Alteração |
|---|---|
| 27/09/2026 | Versão inicial após a criação da estrutura base. |
| 27/09/2026 | IA-02 concluída: CI verde no GitHub (o ruff passou a ignorar `docs/` e `*.md`). |
| 15/10/2026 | Protótipo do Assistente (IA-64 e IA-66 parciais); ADR-06 revisado (passe); desvios na Seção 5. |
| 20/10/2026 | Assistente com ferramentas simuladas de documentos, BIM e MCP (fluxo real, dados de exemplo), citação tipada (`DOCUMENTO`, `BIM`, `EXTERNO`) e prompt `assistente/v3`. Liga/desliga por `ASSISTENTE_FERRAMENTAS_EXTRAS`. |
| 20/10/2026 | Prompt `assistente/v4`: respostas completas e específicas (datas, números, obra e documento), em vez do limite de 4 frases do v3. Só texto do prompt; sem mudança de contrato. |
| 20/10/2026 | `POST /v1/assistente/conversas` aceita `contexto_inicial` (até 4000 caracteres): o texto que o app já mostra (ex.: o Resumo IA) entra no prompt como dado, entre marcadores, e não vira mensagem do histórico. Base da "conversar sobre o resumo" no app real. |
| 20/10/2026 | Assistente: 429 do provedor (limite de tokens por minuto da Groq, 8000) espera e tenta de novo (3 tentativas) e, se persistir, avisa "muitas perguntas ao mesmo tempo"; schemas das ferramentas sem `title` (menos tokens por passo); status próprio para documentos, BIM e MCP; prompt `assistente/v6` (25% menor; clima via `consultar_mcp`, sem `**`, sem repetir a mesma busca). `listar_obras` virou ferramenta interna (só o servidor chama, `Ferramenta.interna`) e a lista de obras do contexto traz cidade, unidade, etapa, progresso e responsável: menos um passo por pergunta (BIM + clima: 4 passos e ~9500 tokens para 3 e ~6500; balanço da semana: ~6000 para ~3900). |
