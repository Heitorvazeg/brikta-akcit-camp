# assistente

## v2 (15/10/2026)

Os períodos (hoje, ontem, esta semana, semana passada, este mês, mês passado) chegam calculados
em código, e cada RDO devolvido por `consultar_rdos` traz o dia da semana. Motivo: no teste manual
com o Groq (`openai/gpt-oss-120b`), a v1 calculou "semana passada" como 16–22/09 (o certo, com
hoje em 29/09, é 21–27/09) e chamou 17/09 (quinta) de segunda-feira. Datas, como números, vêm de
código. Sem avaliação automática ainda (IA-60/IA-67); conferido à mão com as mesmas perguntas.
