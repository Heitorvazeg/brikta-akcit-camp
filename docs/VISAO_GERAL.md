# Brikta IA — Visão Geral

> Serviço que concentra **toda** a inteligência artificial do Brikta.
> Implementação e próximos passos: [`IMPLEMENTACAO.md`](IMPLEMENTACAO.md) (documento vivo).
> Desenho completo (ADRs, contratos, pipeline, avaliação, segurança): [`planos/plano-de-implementacao.md`](planos/plano-de-implementacao.md).

| | |
|---|---|
| **Pasta** | `ia/` no monorepo Brikta |
| **Branch** | `main` do monorepo (importado de `IA-Brikta`, branch `docs/diagramas-arquitetura`, em 06/10/2026) |
| **Documentação de produto** | `docs/`: Visão V4 (Seção 7), Design RDO por Voz, Custos de IA, regras de RDO por voz e do Assistente (`docs/02-dominios/05-rdo/`, `docs/02-dominios/07-assistente-de-obra.md`), Diagramas de Arquitetura |
| **Última revisão deste documento** | 27/09/2026 |

---

## 1. O que é o Brikta (contexto em 30 segundos)

Plataforma de gestão de obras cuja porta de entrada é o **RDO por voz**: "Mande um áudio. Receba o RDO pronto." O mestre de obras narra o dia (com ruído de betoneira, sotaque e gíria de canteiro) e recebe o relatório estruturado para revisar. Como voz e IA viraram obrigatórias no mercado, o diferencial é **qualidade em canteiro real**, **offline-first** e o **histórico por obra**, que vira contexto para o **Assistente de Obra**.

## 2. O que este repositório se propõe a ser

| Capacidade | O que é | Fase |
|---|---|---|
| **RDO por voz** | Pipeline **determinístico**: baixar áudio → normalizar → transcrever com glossário de obra → pós-processar → extrair `RdoProposto` (com evidência por item e `campos_incertos`) → validar → devolver ao backend | MVP |
| **Glossário de obra** | Vocabulário global e por empresa que melhora transcrição e extração, crescendo com as correções dos usuários | MVP → pós |
| **Qualidade medida** | Conjunto de avaliação com áudios reais; nenhuma troca de modelo/prompt sem medir | MVP |
| **Assistente de Obra** | **Agente** que responde perguntas sobre a obra usando ferramentas: dados da obra (via backend), busca nos RDOs e documentos (RAG), plantas, BIM (IFC), base técnica e serviços externos — sempre citando a fonte | Pós-MVP |
| **Servidor MCP `brikta-dados`** | As mesmas ferramentas expostas por MCP para outros consumidores | Pós-MVP |
| **Inteligência de Obra** | Previsões de atraso, produtividade, alertas | Futuro |

### 2.1 O que NÃO é

- **Não é fonte da verdade:** propõe; o backend decide e grava.
- **Não acessa o banco do backend** nem gera SQL a partir de texto; dado de negócio sempre via API do backend, com o JWT do usuário.
- **Não guarda mídia:** lê por URL pré-assinada temporária.
- **Não valida RDO** nem gerencia usuários.

## 3. Onde ele se encaixa

```
 Backend ──POST /v1/jobs/rdo-voz (token de serviço)──▶ API ─▶ fila (Postgres) ─▶ Worker
    ▲                                                                  │  GET áudio (URL assinada) ─▶ Storage
    │                                                                  │  STT / LLM ─────────────────▶ Provedores de IA
    └──────── POST /internal/ia/callback (HMAC) ◀──────────────────────┘

 App (pós-MVP) ──SSE + JWT──▶ API do Assistente ─▶ agente ─▶ registro de ferramentas
                                                     ├─▶ Backend /internal/assistente/* (JWT do usuário)
                                                     ├─▶ índice próprio (pgvector, filtro empresa/obra no SQL)
                                                     └─▶ serviços externos via MCP
```

| Pasta | Relação | Contrato |
|---|---|---|
| `backend/` | Dispara jobs, recebe callbacks, expõe rotas de leitura ao Assistente | `contracts/*.json` (gerados de `src/brikta_ia/domain/contratos.py`) |
| `Frontend-Mobile-Brikta` | Indireta no MVP (revisa o `RdoProposto` que o backend aplicou); direta no chat do Assistente | `contracts/rdo_proposto.v1.json`; Plano, Seção 6.4 |
| `docs/` | Regras de negócio da IA (RN50–RN60), custos, diagramas | — |

## 4. Tecnologias

| Camada | Tecnologia | Estado |
|---|---|---|
| Linguagem / pacotes | Python 3.12 · `uv` | ✅ |
| API | FastAPI · Uvicorn · Pydantic v2 · pydantic-settings | ✅ esqueleto |
| Logs | structlog (JSON, sem dado pessoal) | ✅ |
| Qualidade | ruff · pyright (estrito em `domain/` e `integrations/`) · pytest | ✅ |
| Contratos | JSON Schema gerado dos modelos Pydantic | ✅ v1 (em revisão) |
| Áudio | ffmpeg / ffprobe (na imagem Docker) | ✅ na imagem, sem uso ainda |
| Fila | Procrastinate ou tabela própria sobre Postgres (ADR-02) | ❌ |
| Banco | PostgreSQL + pgvector · SQLAlchemy 2 async · Alembic | ❌ (compose pronto) |
| Provedores | STT (OpenAI Whisper, Deepgram, Google), LLM (Anthropic, Google Gemini, OpenAI) atrás de `Protocol` | 🟡 interfaces + fakes |
| Agente | LangGraph × PydanticAI (× Google ADK) — escolha na IA-64a | ❌ |
| MCP | SDK oficial de MCP em Python | ❌ |
| BIM / documentos | IfcOpenShell · PyMuPDF | ❌ |
| Observabilidade | Sentry · OpenTelemetry · Langfuse | ❌ |

## 5. Arquitetura interna

```
src/brikta_ia/
  api/            rotas HTTP; auth.py (token de serviço, com rotação)
  domain/         rdo_schema.py (RdoProposto v1) · contratos.py · estados.py · erros.py   ← sem I/O
  pipeline/       rdo_voz/: baixar, normalizar, transcrever, pos_processar, extrair, validar, orquestrador
  glossario/      dicas de STT, dicionário de correção, casamento com o catálogo
  assistente/     ferramentas/ (RegistroFerramentas + ContextoExecucao) · agente/ (adaptador do framework)
  servidor_mcp/   servidor MCP sobre o mesmo registro
  providers/      stt/ · llm/ · embeddings/   ← único lugar que importa SDKs de modelo
  integrations/   assinatura HMAC · cliente do backend · storage · outbox de callbacks
  fila/ db/ observability/
contracts/        JSON Schemas versionados  ·  prompts/  versionados  ·  glossario/seed.csv
eval/             manifest do conjunto de avaliação (áudios em bucket privado)
```

Princípios (Plano, Seção 2.3): a IA propõe e a pessoa confirma · medir antes de otimizar · provedor é detalhe · números vêm de código · tudo rastreável · falha da IA não bloqueia · isolamento por empresa em código, nunca no prompt.

## 6. Conceitos-chave

| Conceito | Significado |
|---|---|
| `RdoProposto` | Saída da extração: itens com `ref_id` (atualiza existente) ou novos, evidência literal, `campos_incertos` |
| Erro silencioso | Campo errado **não** marcado como incerto — a métrica de confiança mais importante |
| `editado_manual` | Item que o usuário alterou; a IA não sobrescreve (RN52) |
| `ContextoExecucao` | Empresa, usuário, perfil, obras visíveis e JWT, montados do token; o agente nunca escolhe esses valores |
| Conjunto de avaliação | Áudios reais anotados; divisão `dev`/`teste` |

## 7. Como rodar

```bash
uv sync
cp .env.sample .env
uv run uvicorn brikta_ia.main:app --reload       # http://localhost:8000/health
uv run pytest && uv run ruff check . && uv run pyright
npm --prefix .. run docker:banco                      # Postgres do monorepo (banco brikta_ia com pgvector)
```

## 8. Regras para quem desenvolve aqui

Estão em [`../CLAUDE.md`](../CLAUDE.md). As principais: só `providers/` chama SDKs de modelo; testes sem rede (fakes); nunca logar transcrição; contrato mudou → regenerar `contracts/` e avisar o backend; prompt mudou → nova versão + avaliação; ferramentas do Assistente só no registro e só leitura.
