# CLAUDE.md

Guia para agentes de código no serviço de IA (complementa o `AGENTS.md` da raiz do monorepo, com as regras entre componentes). Comece por `docs/VISAO_GERAL.md` e `docs/IMPLEMENTACAO.md`; o desenho completo está em `docs/planos/plano-de-implementacao.md` (leia as Seções 2, 3 e 5 antes de mudar comportamento).

## Comandos

```bash
uv sync
uv run pytest                                  # ou: uv run pytest tests/unit/test_x.py
uv run ruff check --fix . && uv run ruff format .
uv run pyright
uv run python scripts/gerar_contratos.py       # após mudar domain/contratos.py ou domain/rdo_schema.py
```

Fluxo ao terminar uma mudança: `ruff` → `pyright` → `pytest`.

## Regras que não são óbvias pelo código

- **Provedores:** só `providers/` importa SDKs de modelo (OpenAI, Anthropic, Google, Deepgram…). O resto usa os `Protocol` de `providers/*/base.py`. Nomes de modelo vêm da configuração, **nunca** fixos no código.
- **Testes sem rede:** use `FakeSpeechToText` / `FakeLLMEstruturado`. Chamadas reais só no `eval/`.
- **Dados pessoais:** nunca logar transcrição, conteúdo de áudio ou texto de documento. Logue IDs, etapas, durações e códigos de erro. Nunca commitar áudio (o `.gitignore` bloqueia).
- **Contratos:** `domain/contratos.py` e `domain/rdo_schema.py` definem o que o backend recebe. Mudou? Rode `scripts/gerar_contratos.py` e commite `contracts/`. Mudança incompatível = **nova versão** (`.v2`), nunca editar a `.v1` em uso; avise quem cuida do backend.
- **Prompts:** ficam em `prompts/<tarefa>/<versão>/`. Mudou o prompt = nova versão + rodar a avaliação (ADR-08, ADR-10).
- **RDO por voz é pipeline determinístico, sem agente** (ADR-07). Estados em `domain/estados.py`; use `transicao_valida`.
- **Assistente:** toda ferramenta vai no `RegistroFerramentas` (`assistente/ferramentas/`), independente do framework de agentes. `empresa_id`, JWT e obras visíveis vêm do `ContextoExecucao`, **nunca** de argumento escolhido pelo modelo. Só ferramentas somente leitura. Nada de acesso direto ao banco do backend nem texto → SQL (ADR-11). Dado de negócio = backend com o JWT do usuário repassado.
- **Índice próprio (pgvector):** toda consulta filtra `empresa_id` e `obra_id` **no SQL**.
- **Números vêm de código**, não do modelo: somas, médias e quantitativos são calculados por backend/SQL.
- **Idioma:** nomes de domínio em português (`obra`, `rdo`, `equipe`), como no backend.
- **Documentos:** `docs/VISAO_GERAL.md` (o que é o serviço), `docs/IMPLEMENTACAO.md` (**status vivo** — atualize no mesmo PR que avança uma atividade `IA-xx`) e `docs/planos/plano-de-implementacao.md` (desenho e critérios). Se a implementação divergir do plano, registre na Seção 5 do `IMPLEMENTACAO.md`.
