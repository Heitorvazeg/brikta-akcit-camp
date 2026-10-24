# Conjunto de avaliação

Plano, Seção 8. Mede a qualidade real do RDO por voz (e depois do Assistente) com dados de canteiro.

- **Áudios NÃO ficam no Git** (dado pessoal). Ficam num bucket privado; aqui fica só o `manifest.jsonl`.
- Todo áudio exige **consentimento** assinado (modelo em `CONSENTIMENTO.md`).
- Divisão fixa: `dev` (ajustar prompts) e `teste` (só medir; nunca usar para ajustar).

## Formato do `manifest.jsonl` (uma linha por áudio)

```json
{"id": "a001", "divisao": "dev", "caminho_bucket": "eval/audios/a001.m4a", "duracao_seg": 94,
 "ruido": "forte", "falante": "f03", "casos": ["numero_falado", "referencia_ontem"],
 "transcricao_referencia": "anotacoes/a001.txt", "rdo_esperado": "anotacoes/a001.json",
 "termos": ["alvenaria", "chapisco"], "consentimento": "c001"}
```

Relatórios em `relatorios/<data>-<versao>.md`. Os oficiais são commitados; os locais usam o sufixo `.local`.
