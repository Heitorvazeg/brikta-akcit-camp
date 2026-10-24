# Prompts versionados (ADR-08)

```
prompts/<tarefa>/<versão>/
  sistema.md        instruções do sistema
  exemplos.jsonl    few-shot (transcrição → RdoProposto)
  CHANGELOG.md      o que mudou e o resultado da avaliação
```

- A versão (ex.: `rdo_extracao/v3`) é gravada em cada resultado (`metadados.llm.versao_prompt`).
- **Nunca edite uma versão já usada em produção:** crie a próxima.
- Toda nova versão precisa de um relatório de avaliação comparando com a anterior (ADR-10).

Tarefas previstas: `rdo_extracao` (IA-22), `assistente` (IA-65), `descricao_planta` (IA-70).
