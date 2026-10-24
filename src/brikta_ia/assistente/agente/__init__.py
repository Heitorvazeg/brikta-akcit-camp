"""Agentes do Assistente (ADR-07).

`base.py` define a interface `Agente` e os eventos neutros que qualquer implementação
emite. Hoje existe só `laco_proprio.py` (temporário, protótipo). O framework escolhido na
IA-64a entra como outra implementação (ex.: `langgraph.py`, `pydantic_ai.py`), escolhida por
`ASSISTENTE_AGENTE`, sem mexer no serviço, nas rotas nem nas ferramentas.

Um agente recebe as mensagens e um `ExecucaoFerramentas` (ferramentas desta pergunta, com
contexto, limites e citações já aplicados): ele só decide O QUE chamar. Guardrails, filtros
de empresa/obra e citações NÃO moram aqui.
"""
