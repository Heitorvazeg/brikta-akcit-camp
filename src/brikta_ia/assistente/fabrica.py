"""Monta o Assistente a partir da configuração. É o único lugar que escolhe implementações:

| Peça | Variável | Hoje | Depois |
|---|---|---|---|
| Agente | `ASSISTENTE_AGENTE` | `laco_proprio` | framework da IA-64a |
| Modelo | `LLM_ASSISTENTE_*` | `fake`, `openai_compativel` (Groq) | escolha por avaliação (7.2) |
| Ferramentas | `ASSISTENTE_FERRAMENTAS` | `mock` (seed da demonstração) | `backend` (BE-51) |
| Extras | `ASSISTENTE_FERRAMENTAS_EXTRAS` | documentos, bim, mcp (mock) | ingestão IA-70..74 |
| Conversas | — | em memória | Postgres (IA-61) |
"""

from brikta_ia.assistente.agente.base import Agente
from brikta_ia.assistente.agente.laco_proprio import AgenteLacoProprio
from brikta_ia.assistente.conversas import ConversasEmMemoria
from brikta_ia.assistente.ferramentas.bim import registrar_ferramentas_bim
from brikta_ia.assistente.ferramentas.documentos import registrar_ferramentas_documentos
from brikta_ia.assistente.ferramentas.exemplo import registrar_ferramentas_exemplo
from brikta_ia.assistente.ferramentas.mcp import registrar_ferramentas_mcp
from brikta_ia.assistente.ferramentas.registro import RegistroFerramentas
from brikta_ia.assistente.servico import ServicoConversas
from brikta_ia.config import Settings
from brikta_ia.providers.llm.base import LLMComFerramentas
from brikta_ia.providers.llm.fabrica import criar_llm_assistente


def criar_registro(settings: Settings) -> RegistroFerramentas:
    registro = RegistroFerramentas()
    if settings.assistente_ferramentas == "mock":
        registrar_ferramentas_exemplo(registro)
        extras = {e.strip() for e in settings.assistente_ferramentas_extras.split(",") if e.strip()}
        if "documentos" in extras:
            registrar_ferramentas_documentos(registro)
        if "bim" in extras:
            registrar_ferramentas_bim(registro)
        if "mcp" in extras:
            registrar_ferramentas_mcp(registro)
    return registro


def criar_agente(settings: Settings, llm: LLMComFerramentas | None = None) -> Agente:
    # Um `match settings.assistente_agente` entra aqui quando houver o segundo agente.
    return AgenteLacoProprio(
        llm or criar_llm_assistente(settings), max_passos=settings.assistente_max_passos
    )


def criar_servico(settings: Settings, llm: LLMComFerramentas | None = None) -> ServicoConversas:
    return ServicoConversas(
        criar_agente(settings, llm),
        criar_registro(settings),
        ConversasEmMemoria(),
        data_referencia=settings.assistente_data_referencia,
    )
