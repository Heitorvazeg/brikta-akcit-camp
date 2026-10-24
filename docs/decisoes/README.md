# Decisões de arquitetura (ADRs)

O texto completo de cada decisão está em `docs/planos/plano-de-implementacao.md`, Seção 3. Esta pasta registra **status, data e mudanças**. Quando uma decisão mudar, crie um arquivo `ADR-XX-<titulo>.md` com contexto, decisão e consequências, e atualize a tabela.

| ADR | Decisão | Status | Data |
|---|---|---|---|
| ADR-01 | Python 3.12 + FastAPI + Pydantic v2 | Proposta | 27/09/2026 |
| ADR-02 | Fila de jobs no PostgreSQL (Procrastinate ou tabela própria) | Proposta | 27/09/2026 |
| ADR-03 | Banco próprio `brikta_ia` com pgvector | Proposta | 27/09/2026 |
| ADR-04 | Pipeline sem estado de negócio: contexto vem no job | Proposta | 27/09/2026 |
| ADR-05 | Backend ↔ IA: job HTTP (202) + callback HMAC com outbox | Proposta | 27/09/2026 |
| ADR-06 | Assistente: app → IA direto com o **passe emitido pelo backend** ([revisão](ADR-06-passe-do-assistente.md)); dados via backend | Revisada (passe aceito no protótipo) | 15/10/2026 |
| ADR-07 | Agentes só no Assistente (framework escolhido na IA-64a); ferramentas independentes de framework | Proposta (revisada) | 27/09/2026 |
| ADR-08 | Prompts versionados como código | Proposta | 27/09/2026 |
| ADR-09 | Observabilidade: structlog + Sentry + OpenTelemetry + Langfuse | Proposta | 27/09/2026 |
| ADR-10 | Avaliação como porta de qualidade | Proposta | 27/09/2026 |
| ADR-11 | MCP como interface de ferramentas e serviços externos; sem acesso direto ao banco | Proposta | 27/09/2026 |

IA-01: revisar em time e mudar para **Aceita** (ou registrar a alteração).
