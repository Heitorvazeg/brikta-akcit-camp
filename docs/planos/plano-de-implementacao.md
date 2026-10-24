# Brikta IA — Plano de Implementação do Serviço de Orquestração de IA

> Serviço responsável por toda a inteligência artificial do Brikta: o **RDO por voz** (áudio → RDO estruturado) e o **Assistente de Obra** (perguntas em linguagem natural sobre a obra).
>
> Fica em `ia/docs/planos/plano-de-implementacao.md` no monorepo Brikta (cópia única; a antiga cópia do repositório `Docs` foi unificada aqui). Este é o documento de referência para planejar, construir e operar o serviço.

| | |
|---|---|
| **Versão** | 1.1 — setembro de 2026 (1.1: agentes no Assistente — ADR-07 revisado — e MCP — ADR-11) |
| **Estado do serviço** | Não iniciado |
| **Documentos de produto** | `docs/`: Visão V4, MVP v2.0, Requisitos v2.0, Regras de Negócio v2.0, Definição da API v2.0, Design RDO por Voz, Design de Storage, Custos de IA/Infra, Backlog de Desenvolvimento |
| **Vizinhos** | `backend/` (NestJS, fonte da verdade dos dados) · `frontend/` (web do gestor) · `Frontend-Mobile-Brikta` (React Native/Expo, repositório próprio) |

---

## Sumário

0. [Como usar este documento](#0-como-usar-este-documento)
1. [Contexto em uma página](#1-contexto-em-uma-página)
2. [Escopo, responsabilidades e princípios](#2-escopo-responsabilidades-e-princípios)
3. [Decisões de arquitetura (ADRs)](#3-decisões-de-arquitetura-adrs)
4. [Arquitetura](#4-arquitetura)
5. [Pipeline do RDO por voz](#5-pipeline-do-rdo-por-voz)
6. [Contratos de integração](#6-contratos-de-integração)
7. [Estratégia de modelos, provedores e glossário](#7-estratégia-de-modelos-provedores-e-glossário)
8. [Qualidade: conjunto de avaliação e métricas](#8-qualidade-conjunto-de-avaliação-e-métricas)
9. [Assistente de Obra](#9-assistente-de-obra)
10. [Segurança, privacidade e LGPD](#10-segurança-privacidade-e-lgpd)
11. [Observabilidade, custos e operação](#11-observabilidade-custos-e-operação)
12. [Infraestrutura e deploy](#12-infraestrutura-e-deploy)
13. [Estrutura do repositório e padrões de engenharia](#13-estrutura-do-repositório-e-padrões-de-engenharia)
14. [Plano de implementação por fases](#14-plano-de-implementação-por-fases)
15. [Dependências com o backend e o mobile](#15-dependências-com-o-backend-e-o-mobile)
16. [Riscos](#16-riscos)
17. [Decisões pendentes](#17-decisões-pendentes)
18. [Glossário](#18-glossário)

---

## 0. Como usar este documento

- **Seções 1–3:** o porquê. Leia antes de escrever código.
- **Seções 4–13:** o como. Arquitetura, contratos, qualidade, segurança e operação. Consulte durante o desenvolvimento.
- **Seção 14:** o quê e em que ordem. Cada atividade tem ID (`IA-xx`), dependências, tamanho e critério de pronto, para virar issue diretamente.
- **Seção 15:** o que precisa acontecer nos outros repositórios. IDs `BE-xx` e `MOB-xx` referem-se a `docs/04-planejamento/backlog.md`.
- Tamanhos: `P` ≤ 1 dia · `M` 2–4 dias · `G` 1–2 semanas.
- **Mantenha vivo:** decisão tomada → atualize a Seção 3 ou 17 no mesmo PR que a implementa.

---

## 1. Contexto em uma página

**Produto.** O Brikta é um app de gestão de obras cuja porta de entrada é o **RDO (Relatório Diário de Obra) por voz**. O mestre de obras ou empreiteiro grava um áudio narrando o dia ("hoje tinha três pedreiros e um servente, subimos a alvenaria do segundo pavimento, faltou cimento de tarde, choveu depois das três…") e recebe o RDO preenchido para revisar e validar.

**Persona.** Empreiteiro de execução e mestre de obras em Goiás (piloto): mãos ocupadas, sol, luvas, **sinal ruim**, vocabulário de canteiro ("baldrame", "chapisco", "contrapiso", "SINAPI", "massa", "laje", "escora"), sotaque regional e **ruído** (betoneira, serra, vento).

**Proposta.** "Mande um áudio. Receba o RDO pronto." Meta de tempo de registro < 3 min, contra > 15 min hoje.

**Diferencial esperado da IA.** Voz e IA já são obrigatórios no mercado (ObraVox e Obraguru já fazem RDO por voz). O que diferencia é: (1) **qualidade em canteiro real**, medida com áudio real; (2) **offline-first**, com a IA trabalhando depois da sincronização; (3) **histórico estruturado por obra**, que vira contexto do **Assistente de Obra**, o fosso de longo prazo.

**O que já existe fora deste repositório:**
- **Backend NestJS** com obras, RDO, sync offline idempotente, catálogos da empresa (funções, equipamentos, materiais), multi-tenant por `empresa_id` e autenticação própria do backend (JWT com `empresa_id` e `role`; até out/2026 era o Supabase ∈ `GESTOR`/`FISCAL`/`OPERADOR`). Tabelas `rdo_gravacoes` e `ia_processamentos` já existem, sem uso.
- **App mobile Expo** com login e telas; o botão "Registrar por voz" ainda mostra "Em breve".
- **Nada de IA implementado.**

**Custo esperado (documento de custos):** US$ 0,005–0,014 por RDO (STT + LLM), ou menos de R$ 2 por cliente/mês. **IA não é o problema de margem**; qualidade e confiabilidade são.

---

## 2. Escopo, responsabilidades e princípios

### 2.1 O serviço faz

| Capacidade | Fase |
|---|---|
| Baixar e normalizar áudio de campo | MVP |
| Transcrever (STT) com glossário de termos de obra | MVP |
| Corrigir termos recorrentes (dicionário) e normalizar números e unidades | MVP |
| Extrair o RDO estruturado a partir da transcrição e do contexto da obra, com `campos_incertos` e trecho de evidência por item | MVP |
| Entregar o resultado ao backend (callback assinado) | MVP |
| Medir qualidade (conjunto de avaliação), custo e latência | MVP |
| Manter glossário global e por empresa | MVP (global) / Pós (por empresa) |
| Assistente de Obra: indexação, ferramentas, conversa com citações | Pós-MVP |
| Ingestão de documentos da obra (plantas, orçamento, cronograma) | Pós-MVP |
| Inteligência de obra (previsões, alertas) | Futuro |

### 2.2 O serviço NÃO faz

- **Não é fonte da verdade** de RDO, obra, usuário ou mídia. Isso é do backend. O serviço de IA **propõe**; o backend **decide e grava**.
- **Não escreve no banco do backend** e não lê as tabelas dele diretamente.
- **Não gerencia usuários** nem senhas. No Assistente, valida o JWT emitido pelo backend e delega a autorização de dados ao backend.
- **Não guarda mídia definitiva.** Lê do storage por URL temporária e não copia o arquivo para outro lugar.
- **Não valida nem assina RDO** (regra RN50).

### 2.3 Princípios

1. **A IA propõe, a pessoa confirma.** Todo resultado vira rascunho revisável. Na dúvida, marcar como incerto em vez de chutar.
2. **Medir antes de otimizar.** Nenhuma troca de modelo, prompt ou provedor sem rodar o conjunto de avaliação e comparar com a versão anterior.
3. **Provedor é detalhe.** STT, LLM e embeddings ficam atrás de interfaces próprias. Trocar de provedor é configuração, não reescrita.
4. **Números vêm de código, não do modelo.** Somas, médias e contagens (no Assistente e na validação do RDO) são calculadas por código determinístico; o LLM só interpreta e redige.
5. **Toda saída é rastreável.** Cada resultado guarda provedor, modelo, versão do prompt, versão do schema, tokens, custo e latência.
6. **Falha da IA não bloqueia o usuário.** O RDO manual sempre funciona.
7. **Simples primeiro.** Sem broker extra, sem Kubernetes. Framework de agentes **só no Assistente** (ADR-07); o RDO por voz é um pipeline determinístico. Adicionar complexidade só com dado que justifique.
8. **Isolamento por empresa é inegociável.** Todo dado indexado carrega `empresa_id`, e todo acesso filtra por ele em código, nunca por instrução ao modelo.

---

## 3. Decisões de arquitetura (ADRs)

Status: **Proposta** até o time confirmar na IA-F0 (IA-01). Ao confirmar, mude para **Aceita**, com data.

### ADR-01 — Linguagem e framework: Python 3.12 + FastAPI + Pydantic v2
- **Contexto:** o backend é TypeScript. Um serviço em Python introduz uma segunda linguagem num time pequeno.
- **Decisão:** Python, pelo ecossistema de IA e áudio: SDKs oficiais de todos os provedores, ffmpeg, rapidfuzz, PyMuPDF, pgvector, ferramentas de avaliação, e Pydantic gerando JSON Schema para structured output. O documento de custos já previa um "serviço Python de IA".
- **Consequências:** contratos entre serviços via **JSON Schema versionado** (`contracts/`), gerado pelo Pydantic e validado também no backend. Ferramentas: `uv` (dependências), `ruff` (lint/format), `pyright` (tipos), `pytest`.
- **Alternativa descartada:** NestJS/TypeScript (mesma stack do backend). Ecossistema de áudio e avaliação mais fraco; o ganho de "uma linguagem só" não compensa.

### ADR-02 — Processamento assíncrono: fila no PostgreSQL
- **Decisão:** jobs em fila sobre Postgres, com a biblioteca **Procrastinate** (async, retries, agendamento, sem broker) ou uma tabela própria com `SELECT … FOR UPDATE SKIP LOCKED`. Um processo `worker` separado do processo `api`, a partir da mesma imagem.
- **Por quê:** zero infraestrutura nova (sem Redis/RabbitMQ), transações junto dos dados do job, volume do piloto baixíssimo (dezenas a centenas de jobs por dia).
- **Reavaliar quando:** mais de ~50 jobs/s sustentados ou necessidade de fan-out complexo.

### ADR-03 — Banco próprio com pgvector
- **Decisão:** um banco `brikta_ia` (pode ficar no mesmo cluster Postgres gerenciado do backend no início) com a extensão **pgvector**. Migrations com **Alembic** e SQLAlchemy 2.
- **Por quê:** separação de responsabilidades (o serviço de IA pode ser apagado e recriado sem tocar no dado de negócio) e busca vetorial sem um banco vetorial dedicado.

### ADR-04 — Pipeline sem estado de negócio: o contexto vem no job
- **Decisão:** o backend envia no pedido do job **tudo** o que a extração precisa: URL temporária do áudio, dados da obra, catálogo da empresa, resumo dos últimos RDOs, estado atual do RDO em rascunho e glossário da empresa.
- **Por quê:** o serviço de IA não precisa acessar o backend durante o pipeline, fica testável com fixtures e reprocessável.

### ADR-05 — Comunicação backend ↔ IA: job HTTP + callback assinado
- **Decisão:** o backend chama `POST /v1/jobs/rdo-voz` (resposta `202` com `job_id`). Ao terminar, o serviço de IA chama `POST {BACKEND}/api/v1/internal/ia/callback` com assinatura **HMAC-SHA256**. Entrega garantida por **outbox** com retentativas. O backend pode consultar `GET /v1/jobs/{id}` para reconciliar.
- **Alternativa descartada:** o backend fazer polling constante (desperdício) ou uma fila compartilhada entre serviços (acoplamento e infra extra).

### ADR-06 — Assistente: app → IA direto, com o passe emitido pelo backend *(revisado em 15/10/2026)*
- **Decisão:** o app chama o serviço de IA diretamente (streaming SSE) com um **passe do Assistente** emitido pelo backend (`POST /api/v1/assistente/sessao`: JWT HS256 com chave própria `IA_TICKET_SECRET`, `aud=brikta-ia`, 30 min, com usuário, empresa, perfil e obras visíveis). A IA confere o passe localmente; empresa, perfil e obras vêm dele, resolvidos pelo backend num único lugar. Para buscar dados, a IA chama rotas **somente leitura** do backend (`/internal/assistente/*`, BE-51); a credencial dessas chamadas se decide com a BE-51. Detalhes e consequências: [`decisoes/ADR-06-passe-do-assistente.md`](../decisoes/ADR-06-passe-do-assistente.md).
- **Por quê:** streaming de baixa latência, sem duplicar regras de autorização no serviço de IA.
- **Exceção:** a busca semântica no índice do próprio serviço de IA filtra por `empresa_id` e por `obra_id` ∈ obras visíveis, ambos do passe.
- **Transporte (reavaliado em out/2026):** a conversa é bidirecional, mas cada **turno** não é. Cada pergunta é um `POST` comum (com JWT, validação, cota, idempotência e retentativa como qualquer HTTP) cuja resposta vem em SSE. É o mesmo padrão das APIs de LLM. **Cancelar** = o app fecha a conexão; o servidor percebe e interrompe o agente. Pergunta de esclarecimento do agente = uma resposta normal; o usuário responde com outro `POST`. **WebSocket** só entra se surgir algo que o servidor precise mandar fora de um turno, ou conversa por voz em tempo real; não há caso assim no plano.

### ADR-07 — Agentes: sim no Assistente, não no RDO por voz; ferramentas independentes de framework *(revisado em 27/09/2026)*
- **Contexto:** o Assistente vai cruzar várias fontes (dados estruturados da obra, RAG sobre RDOs e documentos, plantas e BIM, base técnica e serviços externos), com roteamento entre fontes, várias etapas, memória de conversa e, mais adiante, agentes especializados. Um laço próprio de tool-calling fica caro de manter nesse cenário.
- **Decisão:**
  1. **RDO por voz continua sendo um pipeline determinístico**, sem agente: a sequência é sempre a mesma, e um agente só traria custo, latência e imprevisibilidade.
  2. **O Assistente é um agente orquestrado por framework.** Candidatos: **LangGraph** (ecossistema LangChain) e **PydanticAI**; **Google ADK** entra como terceiro candidato se o Gemini virar o modelo padrão. A escolha sai de uma comparação curta (IA-64a) com critérios fixos: streaming para SSE, checkpoint de conversa em Postgres, suporte a MCP, tool-calling com Claude/Gemini/OpenAI, facilidade de testar com modelo falso, integração com Langfuse e peso da dependência.
  3. **Ferramentas, filtros de empresa/obra, verificação de citações e limites de custo e de passos são código nosso** (`assistente/ferramentas/`), num **registro independente de framework**. O framework e o servidor MCP (ADR-11) recebem essas ferramentas por adaptadores finos.
  4. **Ingestão de documentos e BIM sem loaders de framework:** PyMuPDF e IfcOpenShell direto, para não acoplar o núcleo de dados ao framework.
  5. **Topologia inicial:** um agente único com boas ferramentas. Evoluir para supervisor + especialistas (dados da obra, documentos/BIM, técnico) **só quando a avaliação (8.5) mostrar ganho**.
- **Por quê:** o framework acelera a orquestração (grafo de estados, checkpoint, confirmação humana, multiagente) sem prender segurança e regra de negócio a ele. Trocar de framework = reescrever só o adaptador.

### ADR-11 — MCP como interface de ferramentas e de serviços externos *(novo em 27/09/2026)*
- **Decisão:**
  1. **Servidor MCP próprio `brikta-dados`**, neste repositório (SDK oficial de MCP em Python), expondo as ferramentas do registro: dados da obra, busca nos RDOs e documentos, BIM. Cada chamada exige o JWT do usuário, que é **repassado ao backend**; os filtros de empresa e obra são aplicados em código. Transporte HTTP com autenticação.
  2. **Ordem de adoção:** o agente do Assistente usa o registro **em processo** no início; o servidor MCP entra quando houver um segundo consumidor, por exemplo clientes Corporativos plugando os dados da obra no próprio assistente (Claude, ChatGPT), o que pode virar produto.
  3. **Serviços externos** (clima, Google Drive do cliente com as plantas, ERPs) são consumidos como **clientes MCP** quando houver servidor confiável; se não houver, como ferramenta HTTP própria no registro.
  4. **Proibido:** dar ao agente acesso direto ao banco (texto → SQL) ou usar um servidor MCP genérico de Postgres. Dado de negócio **sempre via backend**, com a autorização aplicada num lugar só.
  5. **Servidores MCP de terceiros:** lista de permitidos, somente leitura por padrão, timeout e custo por chamada, e saídas tratadas como **dados não confiáveis** (proteção contra injeção de prompt).
- **Por quê:** padrão aberto, suportado pelos principais modelos e frameworks. Permite reaproveitar as mesmas ferramentas entre o nosso agente, clientes externos e futuros canais.

### ADR-08 — Prompts versionados como código
- **Decisão:** prompts em arquivos no repositório (`prompts/<tarefa>/<versão>/`), com ID de versão gravado em cada resultado. Mudou o prompt → nova versão → avaliação → PR.

### ADR-09 — Observabilidade: logs estruturados + Sentry + Langfuse
- **Decisão:** `structlog` (JSON), Sentry para erros, OpenTelemetry para traces entre API → worker → provedores, e **Langfuse** para traces de LLM (prompts, respostas, tokens, custo), com mascaramento e retenção curta (Seção 10).

### ADR-10 — Avaliação como porta de qualidade
- **Decisão:** o conjunto de avaliação (Seção 8) roda sob demanda e antes de toda mudança de prompt, modelo ou provedor. Um subconjunto com respostas gravadas roda no CI a cada PR. Regressão acima do limite bloqueia o merge.

---

## 4. Arquitetura

### 4.1 Visão de componentes

```
                    ┌──────────────────────────── Serviço de IA (`ia/`) ───────────────────────────┐
                    │                                                                                    │
 Backend NestJS ───▶│  API (FastAPI)                         Worker                                      │
  POST /v1/jobs/…   │   ├─ /v1/jobs/rdo-voz  ──enfileira──▶   ├─ Pipeline RDO por voz                    │
  (token serviço)   │   ├─ /v1/jobs/{id}                      │    baixar → normalizar → STT →            │
                    │   ├─ /v1/index/*   (Pós)                │    pós-processar → extrair → validar      │
 App mobile ───────▶│   ├─ /v1/assistente/* (SSE, JWT)        ├─ Indexação (Pós)                          │
  (JWT do backend)  │   └─ /health                            └─ Entrega de callbacks (outbox)            │
                    │                                                                                    │
                    │  Adaptadores: STT · LLM · Embeddings · Storage · BackendClient                     │
                    │  Banco brikta_ia (Postgres + pgvector): jobs, execuções, transcrições,              │
                    │    glossário, outbox, consumo, documentos/chunks, conversas, avaliações            │
                    └───────────────┬──────────────────────────────┬─────────────────────────────────────┘
                                    │ GET URL pré-assinada          │ HTTPS
                                    ▼                               ▼
                           Storage S3-compatível         Provedores: STT (Whisper/Deepgram/Gemini),
                           (áudios, fotos, documentos)   LLM (Claude/Gemini/GPT), Embeddings
```

### 4.2 Sequência — RDO por voz

```
App            Backend                         IA API        IA Worker                    Provedores
 │ grava áudio offline                            │              │                            │
 │ … rede volta …                                 │              │                            │
 │─POST /uploads/request-url──▶│                  │              │                            │
 │◀─URL pré-assinada───────────│                  │              │                            │
 │─PUT áudio ──────────────────────────────▶ Storage             │                            │
 │─POST /uploads/confirm──────▶│                  │              │                            │
 │                             │ registra gravação, monta contexto                            │
 │                             │─POST /v1/jobs/rdo-voz──▶│       │                            │
 │                             │◀──202 {job_id}──────────│─fila─▶│                            │
 │◀─200 (status: processando)──│                  │              │─GET áudio (URL temp.)─▶ Storage
 │                             │                  │              │─transcrever───────────────▶│
 │                             │                  │              │─extrair (structured)──────▶│
 │                             │                  │              │ valida, calcula incertos    │
 │                             │◀────POST /internal/ia/callback (HMAC)──────│                  │
 │                             │ aplica merge (RN52), grava RASCUNHO         │                  │
 │─GET /rdos/:id/processamento▶│                  │              │                            │
 │◀─PRONTO + RDO proposto──────│                  │              │                            │
 │ revisão (campos incertos destacados) → PATCH/sync → validação                              │
```

### 4.3 Sequência — Assistente de Obra (Pós-MVP)

```
App ─POST /v1/assistente/conversas/{id}/mensagens (JWT, SSE)─▶ IA API
IA: valida JWT → empresa_id, role → obras visíveis (GET backend c/ JWT) → agente (framework, ADR-07):
    modelo decide ferramenta → registro de ferramentas (código nosso; ADR-11 também expõe via MCP):
        dados da obra → backend /internal/assistente/* (JWT do usuário)
        RAG → índice próprio (filtro empresa_id + obra_id no SQL)
        documentos/BIM → tabelas e páginas extraídas
        externos → clientes MCP permitidos
    → modelo redige resposta com citações → verificação de citações → eventos SSE: status, token, citação, fim
```

---

## 5. Pipeline do RDO por voz

### 5.1 Estados do job

`RECEBIDO → BAIXANDO → NORMALIZANDO → TRANSCREVENDO → EXTRAINDO → VALIDANDO → ENTREGANDO → CONCLUIDO`
Qualquer etapa pode ir para `FALHOU` com `erro_codigo`. Um `CONCLUIDO_PARCIAL` indica transcrição feita, mas extração falha: o usuário recebe a transcrição e preenche manualmente.

### 5.2 Etapas

| # | Etapa | Entrada → saída | Regras | Timeout | Retentativas |
|---|---|---|---|---|---|
| 1 | **Baixar** | URL pré-assinada → arquivo temporário | Só hosts do storage permitidos (anti-SSRF); tamanho ≤ 25 MB; checksum confere com o informado | 60 s | 3, backoff |
| 2 | **Normalizar** | M4A/AAC → WAV/FLAC mono 16 kHz (ou mantém o formato se o provedor aceitar) | `ffprobe`: duração ≤ 10 min, não vazio; detecta áudio quase mudo (`AUDIO_SEM_FALA`); opcional: remover silêncio longo | 60 s | 0 |
| 3 | **Transcrever** | Áudio → texto + segmentos com tempo e confiança (quando o provedor fornece) | Idioma `pt`; *prompt*/vocabulário com os termos de glossário mais relevantes (7.3); fatia áudio longo se o provedor exigir | 120 s | 3 (erros transitórios); troca de provedor após 3 falhas (7.4) |
| 4 | **Pós-processar** | Texto bruto → texto normalizado + mapa de correções | Dicionário de correção fuzzy ("sina pi" → "SINAPI"); números por extenso → dígitos ("três sacos" → "3 sacos"); unidades ("metro cúbico" → "m³"). **Guardar o texto bruto e o normalizado** | 5 s | 0 |
| 5 | **Extrair** | Texto + contexto → `RdoProposto` (schema 5.3) | Structured output/tool use obrigatório; temperatura 0; contexto do job (obra, catálogo, RDO atual, últimos dias) | 60 s | 1 retentativa com o erro de validação devolvido ao modelo |
| 6 | **Validar** | `RdoProposto` → `RdoProposto` validado + `campos_incertos` finais | Validação Pydantic; regras de sanidade (quantidade > 0 e plausível; % entre 0 e 100; clima no enum); casar nomes com o catálogo (7.5); cada item precisa de trecho de evidência que exista na transcrição, senão vira incerto | 5 s | 0 |
| 7 | **Entregar** | Resultado → callback ao backend | Via outbox; HMAC; idempotente por `job_id` | 10 s por tentativa | Backoff até 24 h |

### 5.3 Schema de saída `RdoProposto` v1

Definido em Pydantic (`src/brikta_ia/domain/rdo_schema.py`) e exportado para `contracts/rdo_proposto.v1.json`. Alinhado ao `SyncRdoDto` do backend e às colunas planejadas (Dicionário v2.0, Seção 7).

```python
class Clima(BaseModel):
    manha: Literal["SOL", "NUBLADO", "CHUVA", "CHUVA_FORTE"] | None
    tarde: Literal["SOL", "NUBLADO", "CHUVA", "CHUVA_FORTE"] | None
    impactou_atividades: bool | None

class Evidencia(BaseModel):
    trecho: str            # substring literal da transcrição normalizada
    inicio_seg: float | None
    fim_seg: float | None

class ItemBase(BaseModel):
    ref_id: str | None     # id de um item JÁ EXISTENTE no RDO atual que este item atualiza; None = item novo
    evidencia: Evidencia

class Equipe(ItemBase):
    funcao: str                          # nome normalizado ao catálogo quando possível
    funcao_catalogo_id: str | None
    quantidade: int
    horas_trabalhadas: float | None

class Atividade(ItemBase):
    descricao: str
    local_obra: str | None               # "2º pavimento", "bloco B"
    status: Literal["INICIADA", "EM_ANDAMENTO", "CONCLUIDA"] | None
    progresso_percentual: int | None
    id_local: str                        # gerado pela IA (ex.: "ia-<job>-1") para vincular fotos

class Material(ItemBase):
    descricao: str
    material_catalogo_id: str | None
    quantidade: float | None
    unidade: str | None
    evento: Literal["RECEBIDO", "UTILIZADO", "EM_FALTA"]

class Equipamento(ItemBase):
    nome: str
    equipamento_catalogo_id: str | None
    status: Literal["EM_USO", "DISPONIVEL", "COM_DEFEITO"] | None
    horimetro_inicial: float | None
    horimetro_final: float | None

class Ocorrencia(ItemBase):
    tipo: Literal["ATRASO_MATERIAL", "CLIMA", "ACIDENTE", "PROBLEMA_EXECUCAO",
                  "FALTA_MAO_DE_OBRA", "EQUIPAMENTO", "OUTRO"]
    descricao: str
    gravidade: Literal["BAIXA", "MEDIA", "ALTA"]
    impacto_cronograma: bool

class CampoIncerto(BaseModel):
    caminho: str           # ex.: "equipes[1].quantidade", "clima.tarde"
    motivo: Literal["BAIXA_CONFIANCA_STT", "AMBIGUO", "NAO_CASOU_CATALOGO",
                    "VALOR_IMPLAUSIVEL", "SEM_EVIDENCIA", "MODELO_INCERTO"]
    sugestoes: list[str] = []

class RdoProposto(BaseModel):
    versao_schema: Literal["rdo_proposto.v1"]
    clima: Clima
    equipes: list[Equipe]
    atividades: list[Atividade]
    materiais: list[Material]
    equipamentos: list[Equipamento]
    ocorrencias: list[Ocorrencia]
    observacoes_gerais: str | None
    proximas_atividades: str | None
    narrativa: str                       # texto corrido do dia → rdos.texto_gerado_ia
    campos_incertos: list[CampoIncerto]
```

> **Para o modelo:** o schema enviado ao LLM é uma versão **sem** os campos calculados por código (`*_catalogo_id`, `id_local`, `inicio_seg`/`fim_seg`), para reduzir erro e custo. O código preenche esses campos na etapa 6.

### 5.4 Vários áudios no mesmo RDO e merge

- O job traz `rdo_atual`: os itens que já existem no rascunho, cada um com `id`, `origem` (`MANUAL`/`IA`) e `editado_manual`.
- O modelo recebe o `rdo_atual` como contexto e **só adiciona ou atualiza** itens (`ref_id`). **A IA nunca remove itens**; remover é decisão humana.
- O backend aplica: item com `editado_manual = true` **não é sobrescrito** (RN52). A sugestão da IA para ele volta como `campos_incertos` com `sugestoes`, para o app oferecer "usar sugestão da IA?".
- Frases como "a parede que começamos ontem" são resolvidas com os **últimos RDOs** no contexto (5.5).

### 5.5 Contexto enviado ao modelo (montagem)

| Bloco | Conteúdo | Limite |
|---|---|---|
| Instruções do sistema | Papel, regras (não inventar, evidência obrigatória, marcar incerto), formato | Fixo, versionado |
| Glossário | Termos de obra com definição curta e variações faladas | ~150 termos mais relevantes |
| Exemplos (few-shot) | 3–5 pares transcrição → `RdoProposto`, com casos difíceis (números falados, correção no meio da fala, "ontem") | Fixo, versionado |
| Obra | Nome, etapa atual, local | Curto |
| Catálogo da empresa | Funções, equipamentos, materiais ativos (nomes) | Até ~300 itens; filtrar por semelhança se passar disso |
| Últimos RDOs | Resumo dos últimos 3 dias: atividades em andamento, equipes típicas | ~1.500 tokens |
| RDO atual | Itens existentes com `id`, `origem`, `editado_manual` | Completo |
| Transcrição | Texto normalizado, com marcações de trechos de baixa confiança | Completo |

Estimativa: ~2.000–4.000 tokens de entrada e ~500–900 de saída. Use **cache de prompt** nas partes fixas (instruções, glossário, exemplos) quando o provedor oferecer.

### 5.6 Como os `campos_incertos` são produzidos

Um campo é incerto se **qualquer** uma das fontes indicar:
1. **STT:** o trecho de evidência cai num segmento com confiança abaixo do limiar do provedor (calibrar no conjunto de avaliação).
2. **Modelo:** ele marcou `MODELO_INCERTO` ou `AMBIGUO` (instruído a fazê-lo).
3. **Código:** nome não casou com o catálogo (`NAO_CASOU_CATALOGO`), valor fora de faixa plausível (`VALOR_IMPLAUSIVEL`) ou evidência não encontrada literalmente na transcrição (`SEM_EVIDENCIA`).

**Meta de calibração (Seção 8):** poucos "erros silenciosos", isto é, campos errados que **não** foram marcados como incertos. Errar marcando é aceitável; errar sem marcar quebra a confiança do usuário.

### 5.7 Códigos de erro

| Código | Significado | O que o app mostra |
|---|---|---|
| `AUDIO_INVALIDO` | Formato ilegível, corrompido ou checksum diferente | "Não conseguimos ler o áudio. Grave de novo." |
| `AUDIO_LONGO` | Mais de 10 min | "Áudio muito longo. Divida em partes." |
| `AUDIO_SEM_FALA` | Silêncio ou ruído sem fala detectável | "Não ouvimos fala no áudio. Fale mais perto do celular." |
| `STT_INDISPONIVEL` | Todos os provedores de STT falharam | "A IA está indisponível. Preencha manualmente ou tente mais tarde." |
| `EXTRACAO_FALHOU` | Extração inválida após retentativa | Resultado parcial: transcrição + preenchimento manual |
| `LIMITE_EXCEDIDO` | Cota diária da empresa atingida | "Limite diário de áudios atingido." |
| `ERRO_INTERNO` | Outro | Mensagem genérica |

---

## 6. Contratos de integração

Todos os contratos ficam em `contracts/*.json` (JSON Schema gerado pelo Pydantic, versionado). O backend valida os payloads contra esses schemas em testes. **Mudança incompatível = nova versão** (`.v2`) convivendo com a anterior até o backend migrar.

### 6.1 Backend → IA: criar job

`POST /v1/jobs/rdo-voz`
Headers: `Authorization: Bearer <IA_SERVICE_TOKEN>` · `Idempotency-Key: <gravacao_id>:<versao_pipeline>`

```json
{
  "versao_contrato": "rdo_voz_job.v1",
  "empresa_id": "uuid",
  "obra_id": "uuid",
  "rdo_id": "uuid | null",
  "rdo_local_id": "uuid",
  "gravacao_id": "uuid",
  "data_referencia": "2026-09-26",
  "audio": {
    "url": "https://storage…/assinada",
    "expira_em": "2026-09-26T21:15:00Z",
    "content_type": "audio/mp4",
    "tamanho_bytes": 1048576,
    "checksum_sha256": "…",
    "duracao_seg": 94,
    "capturado_em": "2026-09-26T17:42:00-03:00"
  },
  "contexto": {
    "obra": { "nome": "Residencial Aurora", "localizacao": "Goiânia-GO", "status": "EXECUCAO" },
    "catalogo": {
      "funcoes": [ { "id": "…", "nome": "Pedreiro" } ],
      "equipamentos": [ { "id": "…", "nome": "Betoneira 400L" } ],
      "materiais": [ { "id": "…", "descricao": "Cimento CP-II", "unidade_padrao": "sc" } ]
    },
    "ultimos_rdos": [ { "data_referencia": "2026-09-25", "resumo": "…", "atividades_em_andamento": ["Alvenaria 2º pav."] } ],
    "rdo_atual": { "equipes": [ { "id": "…", "funcao": "Pedreiro", "quantidade": 3, "origem": "MANUAL", "editado_manual": true } ], "…": "…" },
    "glossario_empresa": [ { "termo": "massa grossa", "significado": "reboco" } ]
  },
  "opcoes": { "idioma": "pt-BR" }
}
```

Respostas: `202 { "job_id": "uuid", "status": "RECEBIDO" }` · `200` com o mesmo `job_id` se a `Idempotency-Key` já existir · `400` payload inválido · `401` token inválido · `429` limite da empresa.

### 6.2 Backend → IA: consultar job

`GET /v1/jobs/{job_id}` → `{ "job_id", "status", "etapa", "erro_codigo", "criado_em", "atualizado_em" }`. Usado pelo backend para reconciliar jobs parados; o app não chama o serviço de IA para isso.

### 6.3 IA → backend: callback de resultado

`POST {BACKEND_URL}/api/v1/internal/ia/callback`
Headers: `X-Brikta-Timestamp: <unix>` · `X-Brikta-Signature: sha256=<HMAC(IA_CALLBACK_SECRET, timestamp + "." + corpo)>`

```json
{
  "versao_contrato": "rdo_voz_resultado.v1",
  "job_id": "uuid",
  "gravacao_id": "uuid",
  "empresa_id": "uuid",
  "rdo_local_id": "uuid",
  "status": "CONCLUIDO | CONCLUIDO_PARCIAL | FALHOU",
  "erro_codigo": null,
  "transcricao": { "bruta": "…", "normalizada": "…", "correcoes": [ { "de": "sina pi", "para": "SINAPI" } ] },
  "rdo_proposto": { "versao_schema": "rdo_proposto.v1", "…": "…" },
  "metadados": {
    "versao_pipeline": "2026.10.1",
    "stt": { "provedor": "openai", "modelo": "…", "duracao_audio_seg": 94 },
    "llm": { "provedor": "anthropic", "modelo": "…", "versao_prompt": "rdo_extracao/v3", "tokens_entrada": 3120, "tokens_saida": 640 },
    "custo_usd": 0.0112,
    "latencia_ms": { "total": 38400, "stt": 21000, "extracao": 14200 }
  }
}
```

Regras:
- O backend rejeita assinatura inválida ou timestamp com mais de 5 min de diferença (`401`).
- O backend responde `200` também para `job_id` repetido (idempotente).
- Resposta diferente de 2xx → o serviço de IA tenta de novo com backoff (1 min, 5 min, 30 min, 2 h, 6 h, 24 h). Depois disso, alerta.

### 6.4 Rotas do Assistente

Contrato publicado: `contracts/assistente_conversa.v1.json` (corpos HTTP e erro) e `contracts/assistente_eventos.v1.json` (eventos SSE). Na VPS, o Caddy publica só `/ia/v1/assistente/*` e corta o `/ia`.

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| POST | `/v1/assistente/conversas` | Passe | Cria conversa `{ obra_id? }` (foco; precisa estar no passe) → `{ conversa_id }`. **Protótipo** |
| GET | `/v1/assistente/conversas` | Passe | Lista conversas do usuário (IA-61) |
| GET | `/v1/assistente/conversas/{id}` | Passe | Histórico (IA-61) |
| POST | `/v1/assistente/conversas/{id}/mensagens` | Passe | `{ cliente_mensagem_id, texto }`; resposta em **SSE**. Mesmo `cliente_mensagem_id` = mesma resposta. **Protótipo** |
| POST | `/v1/index/rdo` | Token de serviço | Backend avisa que um RDO foi criado, alterado ou validado → reindexar |
| POST | `/v1/jobs/indexar-documento` | Token de serviço | Documento da obra enviado → ingerir |
| DELETE | `/v1/empresas/{id}/dados` | Token de serviço | Expurgo LGPD (RN19) |

Eventos SSE (`.v1`): `status` (`{ etapa, texto }`, ex.: "Consultando RDOs…") · `token` (`{ texto }`, incremental) · `citacao` (`{ tipo: "RDO", id, rotulo }`; só itens devolvidos por ferramenta nesta pergunta) · `fim` (`{ mensagem_id, conversa_id, seguintes, uso }`) · `erro` (`{ codigo, mensagem }`). Erros antes do fluxo (passe ausente ou vencido, conversa de outra pessoa, pergunta em andamento) voltam como HTTP no formato do backend (`{ statusCode, code, message }`). Documentos (`DOCUMENTO`, página, trecho) e custo entram como campos novos, sem quebrar a `.v1`.

---

## 7. Estratégia de modelos, provedores e glossário

### 7.1 Interfaces (ports)

```python
class SpeechToText(Protocol):
    async def transcrever(self, audio: AudioNormalizado, dicas: list[str], idioma: str) -> Transcricao: ...

class LLMEstruturado(Protocol):
    async def gerar(self, mensagens: list[Mensagem], schema: type[BaseModel], *, cache_prefixo: bool) -> ResultadoLLM: ...

class LLMComFerramentas(Protocol):   # Assistente
    async def conversar(self, mensagens, ferramentas, *, stream: bool) -> AsyncIterator[EventoLLM]: ...

class Embeddings(Protocol):
    async def embed(self, textos: list[str]) -> list[list[float]]: ...
```

Cada implementação (`openai.py`, `anthropic.py`, `gemini.py`, `deepgram.py`, `fake.py`) informa **custo e uso** no retorno. O provedor ativo é escolhido por configuração (`STT_PROVEDOR`, `LLM_EXTRACAO_PROVEDOR`, `LLM_EXTRACAO_MODELO`…), com possibilidade de sobrescrever por empresa (A/B e clientes Corporativos).

### 7.2 Candidatos e critérios

| Função | Candidatos | Ponto de partida | Como decidir |
|---|---|---|---|
| STT | OpenAI (Whisper e modelos de transcrição mais novos) · Deepgram (Nova, com keywords) · Google (Gemini áudio / Chirp) · AssemblyAI | **OpenAI Whisper API** (referência dos documentos de custo) | A/B no conjunto de avaliação (IA-40): **recall de termos de obra** primeiro, WER depois, custo e latência por último |
| LLM de extração | Modelos rápidos/baratos com structured output: Claude Haiku · Gemini Flash · GPT mini | O que tiver melhor F1 no conjunto de avaliação; desempate por custo | IA-27 e IA-40 |
| LLM do Assistente | Modelos intermediários com bom tool use e contexto longo; Gemini para multimodal com plantas | Decidir na IA-F6 | Avaliação do Assistente (8.5) |
| Embeddings | Modelos multilíngues com bom desempenho em PT-BR | Decidir na IA-F6 | Recall@k no conjunto de perguntas |

> **Créditos Google (Gama Fund / Google for Startups):** se entrarem, Gemini vira candidato forte para extração e Assistente (multimodal com plantas). A arquitetura não muda, só a configuração, e a decisão continua sendo por avaliação.

**Não fixe versões de modelo no código.** Nomes de modelo ficam em variáveis de ambiente e no registro de cada execução. Revise o catálogo de modelos a cada trimestre.

### 7.3 Glossário

| Aspecto | Decisão |
|---|---|
| Estrutura | `termo`, `variacoes_faladas[]` ("sina pi", "sinap"), `categoria` (servico, material, equipamento, funcao, unidade, local), `definicao_curta`, `escopo` (`GLOBAL` ou `empresa_id`), `ativo`, `origem` (`SEED`, `CORRECAO_APROVADA`) |
| Seed inicial | 150–300 termos levantados com o Carlos (IA-05): serviços (alvenaria, chapisco, reboco, contrapiso, baldrame, sapata, viga baldrame, laje, forma, armação, concretagem, impermeabilização…), materiais (CP-II, areia média, brita 1, bloco cerâmico 9×19×29, ferro 3/8…), equipamentos (betoneira, vibrador, serra circular, andaime, escora metálica…), funções (pedreiro, servente, armador, carpinteiro, eletricista, encanador…), unidades (m², m³, sc, kg, un, barra, lata, carrinho) |
| Uso no STT | Limite de dicas por provedor (o *prompt* do Whisper aceita poucas centenas de tokens): selecionar os termos **mais prováveis** = catálogo da empresa + termos da etapa atual da obra + os mais frequentes do global |
| Uso no pós-processamento | Dicionário `variacao → termo` com casamento fuzzy (rapidfuzz, limiar calibrado) só para tokens fora do vocabulário comum |
| Uso na extração | Glossário completo no prompt (com cache) para o modelo entender o jargão |
| Crescimento | Correções da revisão → candidatos (IA-51) → aprovação humana → glossário (RN57) |

### 7.4 Resiliência entre provedores

- **Retentativa** em erros transitórios (timeout, 429, 5xx): 3 tentativas, backoff exponencial com jitter.
- **Circuit breaker por provedor:** mais de 50% de falhas em 5 min → abre por 2 min e usa o provedor **secundário** configurado (ex.: STT primário OpenAI, secundário Deepgram).
- O resultado registra qual provedor foi efetivamente usado.
- **Limites de gasto** configurados no painel de cada provedor, além dos limites internos (11.3).

### 7.5 Casamento com o catálogo

Após a extração, cada `funcao`, `material` e `equipamento` é comparado ao catálogo da empresa: normalização (minúsculas, sem acento, singular) → igualdade → fuzzy (rapidfuzz `token_set_ratio`) → (opcional, Pós) similaridade por embeddings.
- Acima do limiar alto → preenche `*_catalogo_id` e usa o nome do catálogo.
- Entre os limiares → preenche com o melhor candidato e marca `NAO_CASOU_CATALOGO` com `sugestoes`.
- Abaixo → mantém o texto falado, marca incerto e sugere "cadastrar no catálogo" no app.

---

## 8. Qualidade: conjunto de avaliação e métricas

### 8.1 Conjunto de avaliação do RDO por voz

**Composição inicial (IA-04):** 30 áudios reais gravados pelo Carlos e colegas em obras de Goiânia.

| Variação | Mínimo |
|---|---|
| Ambiente silencioso / ruído moderado / ruído forte (betoneira, serra, vento) | 8 / 12 / 10 |
| Duração < 1 min / 1–3 min / 3–6 min | 8 / 15 / 7 |
| Falantes diferentes (sotaques, idades) | ≥ 5 pessoas |
| Casos difíceis: números falados, correção no meio ("três… não, quatro pedreiros"), referência a ontem, material em falta, acidente, chuva | ≥ 1 de cada |

**Anotação:** para cada áudio, (1) transcrição de referência revisada, (2) RDO esperado no schema `RdoProposto` (sem campos calculados), (3) lista de termos de obra presentes. Anotado por Heitor + Carlos, com revisão cruzada.

**Divisão:** `dev` (20 áudios, usados para ajustar prompts) e `teste` (10 áudios, **nunca** usados para ajustar; só para medir). Com o piloto, o conjunto cresce com áudios dos design partners, com consentimento.

**Armazenamento:** os áudios ficam num **bucket privado**, fora do Git (dado pessoal). No Git fica só o `manifest.jsonl` (ID, metadados, caminho no bucket, anotação).

**Consentimento (obrigatório):** termo simples assinado por quem grava e por quem pode ser ouvido ao fundo, autorizando o uso para desenvolvimento e teste. Modelo do termo em `eval/CONSENTIMENTO.md`.

### 8.2 Métricas

| Camada | Métrica | Como medir | Meta provisória* |
|---|---|---|---|
| STT | **Recall de termos de obra** | % dos termos anotados corretamente transcritos (após pós-processamento) | ≥ 90% |
| STT | WER | Taxa de erro de palavras vs. referência (normalizada) | Registrar; comparar entre provedores |
| Extração | Precisão / recall / F1 por seção | Casamento de itens (texto normalizado + tolerância numérica ±0) por equipes, atividades, materiais, equipamentos, ocorrências, clima | F1 ≥ 0,85 (equipes, clima) · ≥ 0,75 (atividades) |
| Extração | Taxa de alucinação | % de itens sem suporte na transcrição de referência | ≤ 3% |
| Calibração | **Erros silenciosos** | % de campos errados **não** marcados como incertos | ≤ 5% dos campos |
| Calibração | Excesso de incerteza | % de campos marcados incertos que estavam certos | ≤ 30% (evitar "tudo amarelo") |
| Operação | Latência p50/p95 por etapa e total | Dos registros de execução | p95 total ≤ 90 s para áudio de 3 min |
| Operação | Custo por RDO | Dos registros de execução | ≤ US$ 0,02 |

\* Metas provisórias. Após o primeiro baseline (IA-15/IA-27), revise e registre as metas oficiais aqui.

### 8.3 Ferramenta de avaliação

- `uv run python -m eval.rodar --conjunto teste --config configs/atual.yaml` → relatório Markdown + JSON em `eval/relatorios/<data>-<versao>.md`, com comparação lado a lado com a última versão aceita.
- **Modos:** `ao-vivo` (chama provedores; custo de centavos por rodada) e `gravado` (respostas gravadas, para CI determinístico e gratuito).
- **CI:** modo gravado em todo PR (testa código de pós-processamento, validação e casamento). Modo ao vivo sob demanda (label `eval` no PR) e **obrigatório** em PR que muda prompt, modelo ou provedor.
- **Regra de merge:** nenhuma métrica principal pode piorar mais que 2 pontos percentuais sem justificativa escrita no PR.

### 8.4 Métricas em produção (piloto)

| Métrica | Fonte |
|---|---|
| **Taxa de correção por campo:** % de campos gerados pela IA que o usuário alterou antes de validar | Backend envia o diff da revisão (IA-50) |
| Tempo de revisão | App |
| Taxa de regravação | App |
| Distribuição de `erro_codigo` | Serviço de IA |
| Custo por empresa/dia | Serviço de IA |

A **taxa de correção por campo** é a métrica que mais importa: ela mede a qualidade no canteiro real.

### 8.5 Avaliação do Assistente (IA-F6+)

- **Conjunto:** 50–100 perguntas reais (coletadas com Carlos e design partners) sobre uma **obra de teste sintética** com 60 dias de RDOs gerados a partir de roteiros realistas + perguntas sobre obras reais dos parceiros (com permissão).
- **Métricas:** acerto da resposta (juiz LLM + amostra revisada por pessoa), **precisão das citações** (a fonte citada contém o que foi afirmado), recusa correta ("não sei" quando não há dado), custo e latência.
- **Testes de isolamento (bloqueantes):** perguntas feitas por um usuário da empresa A sobre dados da empresa B, e de um OPERADOR sobre obra não atribuída → a resposta **não pode** conter nenhum dado indevido. Meta: **0 vazamentos**.

---

## 9. Assistente de Obra

> **Não é MVP.** Começa depois que o RDO por voz estiver estável no piloto e houver histórico acumulado (Visão V4, Seção 7). Mas as decisões abaixo já influenciam o MVP: indexar RDOs desde cedo e manter tudo com `empresa_id` e `obra_id`.

### 9.1 Camadas

| Camada | Pergunta típica | Fontes | Fase |
|---|---|---|---|
| **A — Histórico da obra** | "Quantos pedreiros trabalharam em média essa semana?", "Que dias choveu em setembro?", "O que ficou pendente da alvenaria?" | RDOs estruturados (via backend) + texto dos RDOs e transcrições (índice) | IA-F6 |
| **B — Documentos da obra** | "Qual a espessura da laje do 2º pavimento na planta?", "Quanto do aço orçado já foi recebido?" | PDFs (plantas, memoriais), planilhas (orçamento, cronograma) | IA-F7 |
| **C — Copiloto técnico** | "Quanto tempo esperar para desformar a laje?", "Que cuidado ter com trabalho em altura nesse andaime?" | Base técnica **de uso permitido** + contexto da obra | IA-F8 |

### 9.2 Arquitetura de ferramentas (registro + framework + MCP)

```
App ──SSE──▶ API do Assistente ──▶ Agente (LangGraph ou PydanticAI — IA-64a)
                                       │  pede ferramentas por nome + argumentos
                                       ▼
                    Registro de ferramentas (assistente/ferramentas/, código nosso)
                    · valida argumentos (Pydantic)  · injeta ContextoExecucao (empresa, obras visíveis, JWT)
                    · limites de chamadas/tempo     · registra custo e trace
      ┌───────────────┬────────────────┬────────────────┬───────────────┬──────────────────┐
  Dados da obra     RAG               Documentos       BIM (IFC)       Base técnica     Externos
  (backend, JWT)    (pgvector + FTS)  (PDF/planilha)   (tabelas)       (curada, IA-F8)  (clientes MCP)
                                       ▲
                     Servidor MCP `brikta-dados` (servidor_mcp/) expõe o MESMO registro a outros consumidores
```

- O agente **nunca** recebe `empresa_id`, JWT ou lista de obras como argumento que ele possa escolher. Isso vem do `ContextoExecucao`, montado a partir do token e injetado pelo registro.
- Toda ferramenta declara: nome, descrição para o modelo, schema de entrada (Pydantic), se é somente leitura, e custo/timeout máximos.
- O mesmo registro alimenta o adaptador do framework e o servidor MCP. Testes de isolamento rodam no registro, então valem para os dois caminhos.

### 9.2.1 Ferramentas da camada A

Todas são **somente leitura** e executadas pelo código do serviço, que chama o backend com o JWT do usuário.

| Ferramenta | Retorna | Fonte |
|---|---|---|
| `listar_obras()` | Obras visíveis ao usuário | Backend |
| `listar_rdos(obra_id, de, ate)` | RDOs resumidos no período | Backend |
| `obter_rdo(rdo_id)` | RDO completo | Backend |
| `resumo_efetivo(obra_id, de, ate, agrupar_por)` | Soma e média de pessoas por função/dia, **calculadas pelo backend** | Backend |
| `consumo_materiais(obra_id, de, ate, material?)` | Quantidades por material e evento | Backend |
| `listar_ocorrencias(obra_id, de, ate, tipo?)` | Ocorrências | Backend |
| `clima_periodo(obra_id, de, ate)` | Clima por dia (registrado no RDO) | Backend |
| `buscar_nos_rdos(consulta, obra_id?, de?, ate?)` | Trechos relevantes de narrativas, atividades e transcrições, com `rdo_id` e data | Índice próprio (híbrido) |

Camada B acrescenta `buscar_documentos(consulta, obra_id)`, `ler_pagina(documento_id, pagina)` (imagem para modelo multimodal), `consultar_planilha(documento_id, filtro)` e `consultar_modelo_bim(obra_id, pavimento?, tipo_elemento?, material?)` (elementos e quantitativos extraídos do IFC, 9.5). Serviços externos (ex.: `previsao_clima(obra_id)`) entram como clientes MCP (ADR-11).

### 9.3 Orquestração do agente

Implementada no framework escolhido na IA-64a, seguindo as regras abaixo, que valem independentemente do framework:


1. Mensagens: sistema (regras) + resumo do contexto (usuário, obras visíveis, data de hoje) + histórico recente da conversa (últimas N mensagens + resumo das anteriores) + pergunta.
2. O modelo pede ferramentas → o código valida os argumentos (Pydantic) e **força** o filtro de empresa e obras visíveis → executa → devolve o resultado.
3. **Limites:** no máximo 6 chamadas de ferramenta por pergunta, 30 s de orçamento de tempo, teto de tokens por pergunta.
4. Resposta final com **citações obrigatórias**. O código confere que cada citação aponta para um `rdo_id` ou documento retornado nesta pergunta; citação inválida é removida e a resposta é marcada com baixa confiança.
5. Sem evidência → "Não encontrei isso nos registros da obra." Nunca completar com conhecimento geral na camada A.

### 9.4 Indexação (índice próprio)

- **Gatilho:** o backend chama `POST /v1/index/rdo` quando um RDO é criado, alterado ou validado (evento assíncrono do lado do backend; falhas são reprocessadas por reconciliação diária).
- **Unidades indexadas:** narrativa do RDO; cada atividade e ocorrência como trecho; transcrição em blocos de ~300 palavras. Metadados: `empresa_id`, `obra_id`, `rdo_id`, `data_referencia`, `tipo`, `status_fluxo`.
- **Busca híbrida:** pgvector (similaridade) + full-text do Postgres (configuração `portuguese`, importante para jargão e nomes próprios), com combinação por *reciprocal rank fusion*. Filtro obrigatório por `empresa_id` e `obra_id IN (visíveis)` **no SQL**.
- **Troca de modelo de embeddings:** cada chunk guarda `modelo_embedding`. Trocar o modelo = reindexar em segundo plano e virar a chave.

### 9.5 Ingestão de documentos (camada B)

| Tipo | Tratamento |
|---|---|
| PDF com texto (memorial, contrato) | Extrair texto por página (PyMuPDF) → chunks com página |
| PDF de planta / digitalizado | Renderizar páginas em imagem → **descrição por modelo multimodal** (o que a folha mostra: pavimento, cotas principais, legendas) indexada como texto → na pergunta, `ler_pagina` envia a imagem ao modelo multimodal |
| Planilha (orçamento, cronograma) | XLSX/CSV → tabela estruturada no banco; consulta por ferramenta (não embeddings) |
| MS Project (.mpp) | Não suportado: orientar a exportar para XLSX |
| IFC (BIM) | **IfcOpenShell** extrai elementos (tipo, pavimento, material, quantidades, propriedades) para tabelas `bim_elementos` com `empresa_id`/`obra_id` → ferramenta `consultar_modelo_bim`. Números vêm da tabela, nunca do modelo de linguagem. Visualização 3D fora de escopo |
| DWG (CAD) | Não ler direto (conversão exige biblioteca licenciada, ex.: ODA). Pedir PDF da prancha ou IFC |

Upload pelo backend (mesmo fluxo de URL pré-assinada, tipo `DOCUMENTO`), que então dispara `POST /v1/jobs/indexar-documento`.

### 9.6 Camada C — cuidados específicos

- **Direitos autorais:** normas ABNT NBR **não** podem ser ingeridas sem licença. Fontes candidatas de uso livre: Normas Regulamentadoras do MTE (ex.: NR-18, NR-35), cadernos técnicos e composições do SINAPI (Caixa), publicações técnicas abertas. **Parecer jurídico antes (IA-80).**
- **Responsabilidade técnica:** a resposta nunca substitui o responsável técnico (ART/RRT). Um classificador de risco da pergunta (estrutural, segurança do trabalho, instalações elétricas, fundações) aciona uma política de resposta: orientação geral + fonte + "confirme com o engenheiro responsável pela obra" (RN59).
- **Sempre citar a fonte** técnica e diferenciar "o que diz a norma/fonte" de "o que está registrado na sua obra".

### 9.7 Custos e limites do Assistente

Estimativa por pergunta (a validar): 5–15 mil tokens de entrada (com cache de prompt) + 300–800 de saída + 1–3 chamadas de ferramenta. Em modelos intermediários, isso dá **cerca de US$ 0,01–0,05 por pergunta**, até 10× o custo de um RDO. Por isso: limite mensal de perguntas por plano (RN60), modelo mais barato para perguntas simples (roteamento por complexidade, Pós) e cache de respostas idênticas por obra e dia.

---

## 10. Segurança, privacidade e LGPD

### 10.1 Autenticação entre serviços

| Direção | Mecanismo |
|---|---|
| Backend → IA (jobs, índice) | `Authorization: Bearer <IA_SERVICE_TOKEN>` (segredo aleatório de 32+ bytes, rotacionável; aceitar 2 tokens durante a rotação) |
| IA → backend (callback) | HMAC-SHA256 com `IA_CALLBACK_SECRET` sobre `timestamp.corpo` + janela de 5 min |
| IA → backend (ferramentas do Assistente) | A decidir com a BE-51 (caminho natural: o mesmo passe, aceito pelo backend nessas rotas) |
| App → IA (Assistente) | **Passe do Assistente** emitido pelo backend (HS256, `IA_TICKET_SECRET`, `iss=brikta-backend`, `aud=brikta-ia`, 30 min), conferido localmente pela IA. Nunca o `JWT_SECRET` do login. Pode migrar para EdDSA sem mudar o app ([ADR-06 revisado](../decisoes/ADR-06-passe-do-assistente.md)) |
| Rede | HTTPS sempre. Jobs só pela rede interna; o Caddy publica só `/ia/v1/assistente/*` (`infra/producao/Caddyfile`) |

### 10.2 Proteções

- **Anti-SSRF:** downloads só de hosts do storage configurados (`STORAGE_HOSTS_PERMITIDOS`), sem redirecionamento, com limite de tamanho no streaming.
- **Validação de entrada:** Pydantic em todo payload; `ffprobe` antes de processar áudio; limites de duração e tamanho.
- **Injeção de prompt:** transcrições e documentos são **dados**, nunca instruções. No pipeline, o risco é baixo (o usuário só afetaria o próprio rascunho, que ele revisa). No Assistente: ferramentas somente leitura, filtros de empresa e obra aplicados em código, sem ferramenta capaz de escrever ou de acessar a internet, e documentos marcados como conteúdo não confiável no prompt.
- **Segredos** só em variáveis de ambiente do PaaS; nunca em repositório, log ou trace.
- **Dependências:** Dependabot/Renovate + `pip-audit` no CI.

### 10.3 Dados pessoais

| Dado | Onde fica | Retenção |
|---|---|---|
| Áudio original | Storage (do backend) | Mesmo prazo do RDO (RN54); o serviço de IA **não copia** |
| Arquivo temporário de áudio | Disco do worker | Apagado ao fim do job (inclusive em falha) |
| Transcrição | Banco do serviço de IA + RDO no backend | Com o RDO; expurgo com a empresa (RN19) |
| Traces de LLM (Langfuse) | Langfuse | **30 dias**; mascarar nomes próprios quando possível |
| Logs | Plataforma de logs | 30 dias; **sem** transcrição nem conteúdo de áudio, só IDs e métricas |
| Conjunto de avaliação | Bucket privado | Enquanto houver consentimento |
| Índice do Assistente | Banco do serviço de IA | Com a empresa; expurgo por `DELETE /v1/empresas/{id}/dados` |

- **Provedores de IA:** usar planos de API em que os dados **não são usados para treino** (padrão nas APIs pagas dos principais provedores; confirmar os termos de cada um) e, quando disponível, retenção zero. **Não usar camadas gratuitas** que permitam uso dos dados.
- **Transferência internacional:** provedores processam fora do Brasil. Isso precisa estar na Política de Privacidade (LGPD, art. 33) (REL-02 no backlog).
- **Pessoas ao fundo do áudio** (trabalhadores) também são titulares. Os Termos de Uso do cliente devem cobrir a obtenção de ciência deles.

---

## 11. Observabilidade, custos e operação

### 11.1 Sinais

| Sinal | Ferramenta | Conteúdo |
|---|---|---|
| Logs | structlog (JSON) → plataforma do PaaS | `job_id`, `empresa_id`, etapa, duração, erro. **Nunca** transcrição |
| Erros | Sentry | Exceções com contexto (sem dado pessoal) |
| Traces | OpenTelemetry | API → fila → worker → provedores |
| Traces de LLM | Langfuse | Prompt, resposta, tokens, custo, versão do prompt |
| Métricas de negócio | Tabela `execucoes` + painel (Metabase ou consulta SQL) | Jobs por dia, p50/p95, custo por empresa, taxa de erro por código, provedor usado |

### 11.2 Alertas

| Alerta | Condição |
|---|---|
| Taxa de falha alta | > 10% de jobs `FALHOU` em 30 min |
| Fila parada | Job mais antigo em `RECEBIDO` há > 10 min |
| Callback não entregue | Outbox com item > 1 h sem sucesso |
| Custo anormal | Gasto diário > 3× a média dos 7 dias anteriores |
| Circuit breaker aberto | Qualquer provedor |

### 11.3 Controle de custo

- Registro de custo **por execução** (tokens × preço vigente, minutos de áudio × preço), tabela de preços em configuração.
- **Limites internos:** áudios por empresa por dia (RN56), orçamento mensal por empresa (alerta em 80%, bloqueio em 120% com aviso), perguntas ao Assistente por plano.
- Limite de gasto também **no painel de cada provedor** (defesa em profundidade).
- Referência: custos por RDO em `docs/01-produto/negocio/custos-ia-storage-infra.md` (US$ 0,005–0,014).

### 11.4 Runbooks (escrever na IA-43)

`docs/runbooks/`: provedor de STT fora do ar · fila acumulando · callback falhando · custo disparado · reprocessar jobs de um período · rotacionar segredos · expurgar dados de uma empresa.

---

## 12. Infraestrutura e deploy

### 12.1 Ambientes

| Ambiente | Uso | Provedores de IA |
|---|---|---|
| `local` | Desenvolvimento, docker compose com Postgres+pgvector | Fakes por padrão; chaves reais opcionais |
| `staging` | Integração com o backend de staging e o app `preview` | Chaves reais com limite baixo |
| `production` | Piloto e clientes | Chaves reais; limites de produção |

### 12.2 Processos

Mesma imagem Docker (Python slim + `ffmpeg`), dois comandos:
- `api`: `uvicorn brikta_ia.main:app` (2 workers no início)
- `worker`: `procrastinate worker` (concorrência 4–8; o trabalho é quase todo I/O de rede)

Deploy na mesma VPS do backend, pelo compose de `infra/producao/` (decisão D2 do backlog), sem porta pública: só o backend a chama. Migrations Alembic rodam como etapa de *release*.

### 12.3 Banco

Postgres 15+ com a extensão `vector` habilitada (Supabase e a maioria dos Postgres gerenciados suportam). Banco `brikta_ia`, usuário próprio, **sem acesso** ao banco do backend.

### 12.4 Variáveis de ambiente (`.env.sample`)

```dotenv
AMBIENTE=local
LOG_NIVEL=INFO
DATABASE_URL=postgresql+asyncpg://brikta_ia:…@localhost:5432/brikta_ia

# Segurança entre serviços
IA_SERVICE_TOKENS=token-atual,token-anterior-opcional
IA_CALLBACK_SECRET=…
BACKEND_BASE_URL=http://localhost:3000/api/v1
IA_TICKET_SECRET=…               # passe do Assistente; o mesmo valor do backend (IA-66)
STORAGE_HOSTS_PERMITIDOS=storage.exemplo.com

# Provedores (nomes de modelo via configuração, não no código)
STT_PROVEDOR=openai
STT_PROVEDOR_SECUNDARIO=deepgram
STT_MODELO=…
LLM_EXTRACAO_PROVEDOR=anthropic
LLM_EXTRACAO_MODELO=…
LLM_ASSISTENTE_PROVEDOR=…        # fake | openai_compativel (protótipo: Groq)
LLM_ASSISTENTE_MODELO=…
LLM_ASSISTENTE_BASE_URL=…
LLM_ASSISTENTE_API_KEY=…
ASSISTENTE_AGENTE=laco_proprio   # até a IA-64a
ASSISTENTE_FERRAMENTAS=mock      # mock (seed da demonstração) | backend (BE-51)
ASSISTENTE_MAX_PASSOS=4
EMBEDDINGS_PROVEDOR=…
OPENAI_API_KEY=…
ANTHROPIC_API_KEY=…
GOOGLE_API_KEY=…
DEEPGRAM_API_KEY=…

# Limites
AUDIO_MAX_SEG=600
AUDIO_MAX_BYTES=26214400
LIMITE_AUDIOS_EMPRESA_DIA=50
ORCAMENTO_EMPRESA_MES_USD=5

# Observabilidade
SENTRY_DSN=…
LANGFUSE_PUBLIC_KEY=…
LANGFUSE_SECRET_KEY=…
LANGFUSE_HOST=…
OTEL_EXPORTER_OTLP_ENDPOINT=…
```

### 12.5 Custo de infraestrutura do serviço

No piloto: um container pequeno (API + worker podem até dividir a instância) e um banco no mesmo cluster. Acréscimo estimado de **US$ 10–30/mês** sobre a infraestrutura do backend, mais o consumo dos provedores (centavos por RDO).

---

## 13. Estrutura do repositório e padrões de engenharia

### 13.1 Estrutura

```
ia/
├── README.md                     # setup rápido, comandos
├── CLAUDE.md                     # convenções para agentes de código (13.4)
├── pyproject.toml / uv.lock
├── Dockerfile / docker-compose.yml / .env.sample
├── alembic/                      # migrations do banco brikta_ia
├── contracts/                    # JSON Schemas versionados (fonte para o backend)
│   ├── rdo_voz_job.v1.json
│   ├── rdo_voz_resultado.v1.json
│   └── rdo_proposto.v1.json
├── prompts/
│   ├── rdo_extracao/v1/{sistema.md, exemplos.jsonl, CHANGELOG.md}
│   └── assistente/v1/…
├── glossario/seed.csv            # termos iniciais (sem dado pessoal)
├── src/brikta_ia/
│   ├── main.py                   # app FastAPI
│   ├── config.py                 # pydantic-settings
│   ├── api/                      # rotas: jobs, assistente, index, health; auth.py
│   ├── domain/                   # rdo_schema.py, erros.py, estados.py (sem I/O)
│   ├── pipeline/rdo_voz/         # baixar, normalizar, transcrever, pos_processar, extrair, validar, orquestrador
│   ├── glossario/                # seleção de dicas, dicionário de correção, casamento com catálogo
│   ├── assistente/
│   │   ├── ferramentas/          # registro + ferramentas (independente de framework — ADR-07)
│   │   ├── agente/               # adaptador do framework escolhido (IA-64a)
│   │   └── indexacao/ ingestao/ recuperacao/
│   ├── servidor_mcp/             # servidor MCP `brikta-dados` sobre o registro (ADR-11)
│   ├── providers/{stt,llm,embeddings}/  # base.py + openai, anthropic, gemini, deepgram, fake
│   ├── integrations/             # backend_client.py, storage.py, callbacks.py (outbox)
│   ├── fila/                     # app e tarefas da fila
│   ├── db/                       # modelos SQLAlchemy, sessão
│   └── observability/            # logging, tracing, custos
├── eval/
│   ├── manifest.jsonl            # índice do conjunto (áudios no bucket privado)
│   ├── CONSENTIMENTO.md
│   ├── rodar.py / metricas/ / relatorios/
├── scripts/                      # transcrever_arquivo.py, extrair_de_texto.py, gerar_contratos.py
├── tests/{unit,integration,contract}/ + fixtures/
└── docs/
    ├── PLANO_DE_IMPLEMENTACAO.md # este documento
    ├── adr/                      # decisões de arquitetura (Seção 3)
    └── runbooks/                 # operação (11.4)
```

### 13.2 Padrões

- **Camadas:** `domain` não importa nada de I/O; `pipeline` e `assistente` dependem de *protocols* (`providers`, `integrations`), injetados na composição (`main.py`/`fila`).
- **Async** de ponta a ponta (`httpx.AsyncClient`, SQLAlchemy async).
- **Tipagem estrita** (`pyright` em modo `strict` para `domain/` e `pipeline/`).
- **Nomes de domínio em português** (como no backend: `obra`, `rdo`, `equipe`); nomes técnicos genéricos podem ficar em inglês.
- **Commits:** `feat(pipeline): …`, `fix(stt): …`, `chore(eval): …`, mesmo padrão dos outros repositórios.

### 13.3 Testes

| Tipo | O que cobre | Onde |
|---|---|---|
| Unitário | Pós-processamento, casamento com catálogo, cálculo de incertos, validação, assinatura HMAC, seleção de dicas do glossário | `tests/unit` (rápido, sem rede) |
| Contrato | Os schemas em `contracts/` batem com os modelos Pydantic; exemplos de payload válidos e inválidos | `tests/contract` |
| Integração | API → fila → worker → provedores **fake** → callback (servidor HTTP falso) | `tests/integration` (Postgres em container) |
| Avaliação | Qualidade real (Seção 8) | `eval/` |
| Ponta a ponta | Backend local + serviço de IA + provedores reais em staging | Checklist manual antes de cada release |

CI (GitHub Actions): `ruff check` → `ruff format --check` → `pyright` → `pytest` (unit + contract + integration) → avaliação em modo gravado → build da imagem.

### 13.4 `CLAUDE.md` do repositório (conteúdo sugerido)

- Comandos: `uv sync`, `uv run pytest`, `uv run pyright`, `uv run ruff check --fix`, `uv run python -m eval.rodar`.
- Regras: nunca chamar provedor fora de `providers/`; nunca logar transcrição; todo acesso a índice filtra `empresa_id` no SQL; mudança de prompt = nova versão + avaliação; mudança de contrato = nova versão em `contracts/` + aviso ao backend.
- Testes unitários sem rede; usar os provedores `fake`.

---

## 14. Plano de implementação por fases

> **Status vivo:** o estado de cada atividade (`[ ]`/`[~]`/`[x]`) é mantido em `docs/IMPLEMENTACAO.md` da pasta `ia/`. Esta seção descreve o **escopo e os critérios** de cada atividade; os checkboxes abaixo refletem o plano original.

Visão geral (em paralelo ao backlog do backend e do mobile):

| Fase | Objetivo | Tamanho estimado | Bloqueia |
|---|---|---|---|
| IA-F0 | Fundação, decisões, contratos, coleta de dados | ~1 semana | Tudo |
| IA-F1 | Transcrição confiável (script de linha de comando + avaliação) | ~1 semana | F2 |
| IA-F2 | Extração estruturada (script + avaliação) | ~1,5 semana | F3 |
| IA-F3 | Serviço: API, fila, worker, callback, integração com o backend | ~1,5 semana | MVP |
| IA-F4 | Endurecimento, A/B de provedores, produção | ~1 semana | Piloto |
| IA-F5 | Aprendizado contínuo com o piloto | Contínuo | — |
| IA-F6 | Assistente camada A | ~3 semanas | — |
| IA-F7 | Assistente camada B (documentos) | ~3 semanas | — |
| IA-F8 | Assistente camada C (copiloto técnico) | ~2–3 semanas + jurídico | — |
| IA-F9 | Inteligência de obra | Backlog | — |

**Estratégia:** F1 e F2 são construídas **primeiro como scripts de linha de comando** (arquivo → resultado) com avaliação. Só depois (F3) vira serviço. Assim a qualidade é medida antes de qualquer integração, e o time vê resultados reais com áudio de obra na segunda semana.

---

### IA-F0 — Planejamento e fundação

- [x] **IA-00** · Criar a pasta `ia/` com este plano (`docs/`), `README.md` e `CLAUDE.md`. *P*
- [ ] **IA-01** · Revisar e aceitar (ou alterar) os ADR-01 a ADR-10; registrar em `docs/decisoes/`. *P* · **Pronto quando:** cada ADR tem status Aceita ou Alterada, com data.
- [ ] **IA-02** · Esqueleto: `uv`, FastAPI com `/health`, `pydantic-settings`, `structlog`, ruff, pyright, pytest, Dockerfile com ffmpeg, docker-compose (Postgres + pgvector), GitHub Actions. *M* · **Pronto quando:** `docker compose up` sobe a API; o CI passa num PR de exemplo.
- [ ] **IA-03** · **Contratos v1** (`rdo_voz_job`, `rdo_voz_resultado`, `rdo_proposto`) escritos em Pydantic, exportados para `contracts/` e **revisados em conjunto com quem faz o backend**. *M* · **Pronto quando:** os dois lados aprovam o PR dos contratos. *Esta é a principal porta entre os times.*
- [ ] **IA-04** · Protocolo de coleta do conjunto de avaliação + termo de consentimento; Carlos grava os 30 áudios (8.1); upload no bucket privado; `manifest.jsonl`. *M* (tempo de calendário: ~1 semana de campo) · **Pronto quando:** 30 áudios com consentimento no bucket.
- [ ] **IA-05** · Glossário seed (150–300 termos) com o Carlos, em `glossario/seed.csv`. *M*
- [ ] **IA-06** · Contas nos provedores (OpenAI, Anthropic e/ou Google, Deepgram), chaves por ambiente, **limites de gasto no painel**, confirmação dos termos de não uso para treino. *P*
- [ ] **IA-07** · Anotação dos 30 áudios: transcrição de referência + RDO esperado + termos. *G* (pode andar em paralelo com a IA-F1) · **Pronto quando:** divisão dev/teste definida e congelada.

### IA-F1 — Transcrição

- [ ] **IA-10** · Protocol `SpeechToText` + provedor `fake` (lê transcrição de fixture). *P* · Depende de IA-02.
- [ ] **IA-11** · Normalização de áudio: `ffprobe` (duração, formato), conversão com ffmpeg, detecção de áudio sem fala, limites. *M*
- [ ] **IA-12** · Adaptador OpenAI (Whisper): idioma, dicas de glossário, fatiamento se necessário, retorno de segmentos e custo. *M*
- [ ] **IA-13** · Seleção de dicas do glossário (catálogo + etapa + frequentes, respeitando o limite do provedor). *P*
- [ ] **IA-14** · Pós-processamento: dicionário de correção fuzzy, números por extenso → dígitos, unidades. Testes unitários com casos reais. *M*
- [ ] **IA-15** · Avaliação de STT: WER e recall de termos; primeiro relatório de baseline em `eval/relatorios/`. *M* · Depende de IA-07 (parcial serve). **Pronto quando:** o baseline está publicado e as metas da Seção 8.2 foram revistas.
- [ ] **IA-16** · Script `scripts/transcrever_arquivo.py`: arquivo → transcrição bruta e normalizada. *P*

### IA-F2 — Extração estruturada

- [ ] **IA-20** · `RdoProposto` v1 em Pydantic (5.3) + versão reduzida para o modelo + exportação de JSON Schema. *M* · Depende de IA-03.
- [ ] **IA-21** · Protocol `LLMEstruturado` + adaptador do primeiro provedor + `fake`; structured output/tool use; cache de prompt. *M*
- [ ] **IA-22** · Prompt `rdo_extracao/v1`: sistema, regras, 3–5 exemplos few-shot com casos difíceis. *M*
- [ ] **IA-23** · Montagem de contexto (5.5) a partir do payload do job, com limites de tamanho. *M*
- [ ] **IA-24** · Validação + casamento com o catálogo (7.5) + retentativa com o erro de validação. *M*
- [ ] **IA-25** · Cálculo final de `campos_incertos` (5.6) e verificação das evidências. *M*
- [ ] **IA-26** · Script `scripts/extrair_de_texto.py` (transcrição + contexto de exemplo → `RdoProposto`). *P*
- [ ] **IA-27** · Avaliação da extração: F1 por seção, alucinação, erros silenciosos, excesso de incerteza; baseline. *G* · Depende de IA-07. **Pronto quando:** baseline publicado; pelo menos 2 provedores de LLM comparados.

### IA-F3 — Serviço e integração

- [ ] **IA-30** · Banco + Alembic: `jobs`, `execucoes`, `transcricoes`, `callbacks_outbox`, `consumo`, `glossario_termos`. *M*
- [ ] **IA-31** · Fila (Procrastinate ou tabela própria) + processo `worker`. *M*
- [ ] **IA-32** · `POST /v1/jobs/rdo-voz` (token de serviço, Idempotency-Key, validação, limite por empresa, `202`) e `GET /v1/jobs/{id}`. *M*
- [ ] **IA-33** · Orquestrador do pipeline com estados, timeouts, retentativas e limpeza de arquivos temporários. *M*
- [ ] **IA-34** · Outbox de callbacks com HMAC e backoff; reconciliação. *M*
- [ ] **IA-35** · Registro de custo e latência por etapa em `execucoes`; consumo por empresa. *P*
- [ ] **IA-36** · Testes de integração (provedores fake + backend falso) e de contrato. *M*
- [ ] **IA-37** · Teste ponta a ponta local: backend + serviço de IA via docker compose, com um áudio real. *M* · Depende de BE-40..BE-43.
- [ ] **IA-38** · Deploy em staging (PaaS, banco, segredos, migrations no release). *M* · Depende de INFRA-01..05.

### IA-F4 — Endurecimento e produção

- [ ] **IA-40** · Adaptadores de STT secundários (Deepgram, Gemini) e de LLM alternativos; **A/B no conjunto de avaliação**; relatório de decisão do provedor padrão. *G*
- [ ] **IA-41** · Observabilidade: Sentry, OpenTelemetry, Langfuse (com mascaramento e retenção de 30 dias), painel de métricas, alertas (11.2). *M*
- [ ] **IA-42** · Circuit breaker e provedor secundário; limites e orçamento por empresa. *M*
- [ ] **IA-43** · Runbooks (11.4). *P*
- [ ] **IA-44** · Teste de carga: 50 jobs simultâneos sem erro e com p95 dentro da meta. *P*
- [ ] **IA-45** · Revisão de segurança e LGPD (Seção 10): anti-SSRF, segredos, retenção, termos dos provedores. *M*
- [ ] **IA-46** · Deploy em produção. *P* · **Pronto quando:** o fluxo ponta a ponta funciona com o app de produção (build `preview`).

### IA-F5 — Aprendizado contínuo (durante o piloto)

- [ ] **IA-50** · Receber do backend o diff da revisão (IA proposto × validado) e armazenar por campo. *M* · Depende de BE-45.
- [ ] **IA-51** · Minerar candidatos a glossário (termos corrigidos repetidamente) + tela/rotina de aprovação (inicialmente: relatório semanal + aprovação via script). *M*
- [ ] **IA-52** · Glossário por empresa aplicado no STT e na extração. *M*
- [ ] **IA-53** · Crescer o conjunto de avaliação com áudios do piloto (com consentimento); rodar a avaliação semanalmente. *contínuo*
- [ ] **IA-54** · Painel de taxa de correção por campo e por empresa. *P*

### IA-F6 — Assistente de Obra, camada A (histórico)

- [ ] **IA-60** · Levantar com Carlos e os design partners 50–100 perguntas reais; montar a obra sintética de teste e o conjunto de avaliação do Assistente (8.5). *M*
- [ ] **IA-61** · Tabelas `documentos`/`chunks` (pgvector + full-text), `conversas`, `mensagens`. *M*
- [ ] **IA-62** · Indexação de RDOs (`POST /v1/index/rdo`), reconciliação diária, expurgo por empresa. *M* · Depende de BE-50.
- [ ] **IA-63** · Escolha do modelo de embeddings por recall@k. *P*
- [ ] **IA-64** · Ferramentas (9.2) com o JWT repassado e filtros forçados em código. *M* · Depende de BE-51.
- [ ] **IA-64a** · **Comparação de frameworks de agente** (LangGraph × PydanticAI; Google ADK se Gemini for o padrão): o mesmo agente com 3 ferramentas e 20 perguntas do conjunto, avaliado pelos critérios do ADR-07. Resultado registrado em `docs/decisoes/`. O escolhido entra como mais uma implementação da interface `Agente` (`assistente/agente/base.py`), ao lado do laço próprio do protótipo, usando as ferramentas por `ExecucaoFerramentas`. *M* · Depende de IA-60, IA-64.
- [ ] **IA-65** · Agente no framework escolhido, com limites, citações verificadas e recusa (9.3). *G* · Depende de IA-64a.
- [ ] **IA-66** · API de conversa com SSE e persistência; conferência do passe do Assistente emitido pelo backend (ADR-06 revisado). *M* · Protótipo feito em 15/10/2026 (sem persistência).
- [ ] **IA-67** · Avaliação do Assistente + **testes de isolamento entre empresas (bloqueantes)**. *M*
- [ ] **IA-68** · Limites por plano, custo por pergunta, cache. *P*
- [ ] **IA-69** · Beta com 1–2 design partners; coleta de feedback. *contínuo* · Depende de MOB (tela de chat).
- [ ] **IA-6M** · Servidor MCP `brikta-dados` sobre o registro de ferramentas: autenticação por JWT, transporte HTTP, os **mesmos testes de isolamento** da IA-67 rodando via MCP. *M* · Opcional nesta fase; obrigatório antes de expor a clientes externos (DP-11).

### IA-F7 — Assistente, camada B (documentos)

- [ ] **IA-70** · Job `indexar-documento`: PDF de texto, PDF de planta (render + descrição multimodal), planilhas → tabelas. *G* · Depende de BE (upload de documentos).
- [ ] **IA-71** · Ferramentas `buscar_documentos`, `ler_pagina` (multimodal), `consultar_planilha`. *M*
- [ ] **IA-72** · Avaliação com documentos reais de um design partner. *M*
- [ ] **IA-73** · Ingestão de **IFC** com IfcOpenShell → `bim_elementos`; ferramenta `consultar_modelo_bim`; avaliação com um modelo real (se algum parceiro tiver). *G*
- [ ] **IA-74** · **Clientes MCP** para serviços externos (primeiro: clima/previsão; depois Google Drive do cliente), com lista de permitidos, timeout, custo por chamada e saída tratada como não confiável. *M*

### IA-F8 — Assistente, camada C (copiloto técnico)

- [ ] **IA-80** · Parecer jurídico: fontes permitidas, direitos autorais, responsabilidade técnica, texto de aviso. *M* (externo)
- [ ] **IA-81** · Curadoria e ingestão da base técnica de uso permitido, com versão e data da fonte. *G*
- [ ] **IA-82** · Classificador de risco da pergunta + políticas de resposta (9.6). *M*
- [ ] **IA-83** · Avaliação com perguntas técnicas revisadas por um engenheiro civil. *M*

### IA-F9 — Inteligência de Obra (backlog)

Previsão de atraso por etapa · desvio de produtividade (efetivo × avanço) · alertas de clima com previsão do tempo · benchmark anônimo entre obras (exige base Termos/LGPD) · resumo semanal automático para o cliente da obra.

---

## 15. Dependências com o backend e o mobile

Itens a incluir no backlog dos outros repositórios (`docs/04-planejamento/backlog.md`, fase F4):

| ID | Repositório | Item | Necessário para |
|---|---|---|---|
| BE-40 | Backend | Port `IIaService` + cliente HTTP do serviço de IA (token de serviço, Idempotency-Key, timeout) | IA-37 |
| BE-41 | Backend | Ao confirmar um upload de **áudio**: registrar em `rdo_gravacoes`, montar o contexto (6.1), disparar o job, criar `ia_processamentos` com status; colunas novas (Dicionário v2.0, Seção 7) | IA-37 |
| BE-42 | Backend | `POST /internal/ia/callback` com verificação HMAC, janela de tempo e idempotência | IA-37 |
| BE-43 | Backend | Aplicar o `RdoProposto` ao RDO em rascunho: merge por `ref_id` (= `id_local` do item), respeitando `editado_manual` (RN52), gravar `campos_incertos` como pendências em `rdo_pendencias` (convertendo o caminho por índice para `secao` + `item_id_local` + `campo`), `texto_gerado_ia` e transcrição | IA-37 |
| BE-44 | Backend | `GET /rdos/:id/processamento` para o app + reconciliação de jobs parados (consulta `GET /v1/jobs/{id}`) | MVP |
| BE-45 | Backend | Na validação do RDO, enviar ao serviço de IA o diff proposto × validado | IA-50 |
| BE-46 | Backend | Validar os payloads contra `contracts/*.json` em teste automatizado | IA-03 |
| BE-50 | Backend | Evento de indexação (RDO criado/alterado/validado → `POST /v1/index/rdo`) + expurgo LGPD | IA-62 |
| BE-51 | Backend | Rotas `/internal/assistente/*` somente leitura (listagens e **agregações calculadas no backend**) aceitando o JWT do usuário | IA-64 |
| BE-52 | Backend | Upload de documentos da obra (tipo `DOCUMENTO`) + disparo de indexação | IA-70 |
| MOB-44 | Mobile | Estado "processando pela IA" e polling | MVP |
| MOB-45 | Mobile | Tela de revisão com `campos_incertos`, evidência (trecho) e "usar sugestão da IA" | MVP |
| MOB-8x | Mobile | Tela de chat do Assistente (SSE, citações clicáveis que abrem o RDO) | IA-69 |
| INFRA | Infra | Deploy do serviço de IA (staging e produção), banco `brikta_ia` com pgvector, segredos | IA-38 |

**Ordem de integração recomendada:** IA-03 (contratos acordados) → backend implementa BE-40..43 contra um **servidor falso** do serviço de IA (que devolve um `RdoProposto` fixo) enquanto a IA faz F1/F2 → IA-37 junta os dois.

---

## 16. Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Transcrição ruim em ruído e sotaque real | Alta | Alto | Conjunto de avaliação com áudio real desde a semana 1; A/B de provedores; glossário; orientação de gravação no app; revisão humana |
| Modelo inventa itens (alucinação) | Média | Alto | Evidência literal obrigatória por item; verificação em código; `campos_incertos`; temperatura 0 |
| Muitos campos marcados como incertos (UX ruim) | Média | Médio | Métrica de excesso de incerteza; calibrar limiares no conjunto de avaliação |
| Conjunto de avaliação pequeno ou enviesado | Alta | Médio | Variação obrigatória (8.1); crescer com o piloto; separar dev/teste |
| Mudança de preço ou descontinuação de modelo | Média | Médio | Provedores atrás de interfaces; nomes de modelo em configuração; revisão trimestral |
| Custo do Assistente fugir do controle | Média | Médio | Limites por plano, orçamento por empresa, cache, roteamento por complexidade |
| Vazamento de dados entre empresas no Assistente | Baixa | **Crítico** | Filtros em SQL/código, JWT repassado ao backend, `ContextoExecucao` injetado pelo registro (nunca escolhido pelo modelo), testes de isolamento bloqueantes (em processo e via MCP) |
| Framework de agentes muda rápido / aprisionamento | Alta | Médio | Ferramentas, guardrails e dados fora do framework; adaptador fino; versões fixadas |
| Injeção de prompt via documentos ou servidores MCP de terceiros | Média | Alto | Ferramentas somente leitura, lista de permitidos, saídas marcadas como não confiáveis, nenhuma ferramenta de escrita no Assistente |
| LGPD (voz de terceiros, transferência internacional) | Média | Alto | Consentimento, Política de Privacidade, retenção curta de traces, provedores sem treino |
| Responsabilidade técnica na camada C | Média | Alto | Parecer jurídico, fontes permitidas, política de risco, aviso de responsável técnico |
| Duas linguagens num time pequeno | Média | Baixo | Contratos em JSON Schema, CLAUDE.md, serviço pequeno e bem delimitado |

---

## 17. Decisões pendentes

| ID | Decisão | Quando | Quem |
|---|---|---|---|
| DP-1 | Confirmar os ADR-01 a ADR-10 | IA-01 | Time técnico |
| DP-2 | Procrastinate ou tabela própria para a fila | IA-31 | Time técnico |
| DP-3 | Provedor padrão de STT | IA-40 (com dados) | Time técnico |
| DP-4 | Provedor e modelo padrão de extração | IA-27/IA-40 (com dados) | Time técnico |
| DP-5 | Langfuse em nuvem ou self-hosted | IA-41 | Time técnico (custo × LGPD) |
| DP-6 | Metas oficiais de qualidade | Após IA-15 e IA-27 | Fundadores + técnico |
| DP-7 | Limites de uso por plano (áudios/dia, perguntas/mês) | Antes do piloto / IA-68 | Fundadores |
| DP-8 | Modelo de embeddings | IA-63 | Técnico |
| DP-9 | Fontes técnicas permitidas na camada C | IA-80 | Jurídico + fundadores |
| DP-10 | Framework de agentes (LangGraph × PydanticAI × ADK) | IA-64a | Time técnico |
| DP-11 | Expor o servidor MCP `brikta-dados` a clientes externos (produto/plano) | Após o beta do Assistente | Fundadores + técnico |

---

## 18. Glossário

| Termo | Significado |
|---|---|
| **RDO** | Relatório Diário de Obra: registro diário de clima, equipe, atividades, materiais, equipamentos e ocorrências |
| **STT** | *Speech-to-text*, transcrição de voz para texto |
| **WER** | *Word Error Rate*, taxa de erro de palavras de uma transcrição |
| **Structured output / tool use** | Recurso dos LLMs que obriga a resposta a seguir um schema JSON |
| **`campos_incertos`** | Campos que a IA não teve confiança para preencher e que o usuário precisa confirmar |
| **Erro silencioso** | Campo errado que **não** foi marcado como incerto |
| **Evidência (trecho)** | Parte literal da transcrição que justifica um item extraído |
| **Catálogo** | Funções, equipamentos e materiais cadastrados pela empresa no backend |
| **Glossário** | Vocabulário de obra (global e por empresa) usado para melhorar transcrição e extração |
| **Outbox** | Tabela de mensagens a entregar, com retentativas, garantindo que nenhum callback se perca |
| **HMAC** | Assinatura do corpo da requisição com um segredo compartilhado, para provar a origem |
| **Agente** | Modelo de linguagem que decide, em várias etapas, quais ferramentas chamar para responder |
| **MCP** | *Model Context Protocol*: padrão aberto para expor ferramentas e dados a modelos e agentes |
| **LangGraph / PydanticAI** | Frameworks de orquestração de agentes (candidatos da IA-64a) |
| **pgvector** | Extensão do PostgreSQL para busca por similaridade de vetores (embeddings) |
| **Busca híbrida** | Combinação de busca por similaridade semântica com busca por palavras-chave |
| **SSE** | *Server-Sent Events*: resposta em fluxo (texto aparecendo aos poucos) |
| **Tenant / `empresa_id`** | A empresa cliente; todo dado pertence a exatamente uma |
| **GESTOR / FISCAL / OPERADOR** | Perfis: dono/admin · responsável técnico · usuário de campo |
