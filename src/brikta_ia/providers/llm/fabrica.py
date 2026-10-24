"""Escolhe o provedor do Assistente pela configuração (`LLM_ASSISTENTE_*`)."""

from collections.abc import AsyncIterator, Sequence

from brikta_ia.config import Settings
from brikta_ia.providers.llm.base import (
    DefinicaoFerramenta,
    EventoLLM,
    FimTurno,
    LLMComFerramentas,
    MensagemTurno,
    TextoParcial,
)


class LLMDesenvolvimento:
    """Sem provedor configurado (`fake`): responde sempre o mesmo texto, sem rede."""

    nome = "fake"

    async def turno(
        self, mensagens: Sequence[MensagemTurno], ferramentas: Sequence[DefinicaoFerramenta]
    ) -> AsyncIterator[EventoLLM]:
        yield TextoParcial(
            "Sou o assistente de exemplo, sem modelo configurado. "
            "Defina LLM_ASSISTENTE_PROVEDOR para respostas de verdade."
        )
        yield FimTurno()


def criar_llm_assistente(settings: Settings) -> LLMComFerramentas:
    if settings.llm_assistente_provedor == "openai_compativel":
        from brikta_ia.providers.llm.openai_compativel import LLMOpenAICompativel

        return LLMOpenAICompativel(
            modelo=settings.llm_assistente_modelo,
            base_url=settings.llm_assistente_base_url,
            api_key=settings.llm_assistente_api_key.get_secret_value(),
        )
    return LLMDesenvolvimento()
