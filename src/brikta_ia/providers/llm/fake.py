"""LLMs falsos para testes, sem rede."""

from collections.abc import AsyncIterator, Sequence
from typing import Any

from pydantic import BaseModel

from brikta_ia.providers.llm.base import (
    ChamadaFerramenta,
    DefinicaoFerramenta,
    EventoLLM,
    FimTurno,
    Mensagem,
    MensagemTurno,
    ResultadoLLM,
    TextoParcial,
)


class FakeLLMEstruturado:
    nome = "fake"

    def __init__(self, resposta: dict[str, Any]) -> None:
        self._resposta = resposta
        self.chamadas: list[list[Mensagem]] = []

    async def gerar[T: BaseModel](
        self, mensagens: list[Mensagem], schema: type[T], *, cache_prefixo: bool = True
    ) -> ResultadoLLM[T]:
        self.chamadas.append(mensagens)
        return ResultadoLLM(
            dados=schema.model_validate(self._resposta), provedor="fake", modelo="fake"
        )


class FakeLLMComFerramentas:
    """Turnos roteirizados: cada item é o que o modelo "responde" naquele turno.

    Cada item é uma lista de pedaços de texto e/ou `ChamadaFerramenta` (o modelo pede
    ferramentas, podendo escrever algo antes). Uma exceção simula a queda do provedor.
    """

    nome = "fake"

    def __init__(self, turnos: list[list[str | ChamadaFerramenta] | Exception]) -> None:
        self._turnos = list(turnos)
        self.chamadas: list[list[MensagemTurno]] = []

    async def turno(
        self, mensagens: Sequence[MensagemTurno], ferramentas: Sequence[DefinicaoFerramenta]
    ) -> AsyncIterator[EventoLLM]:
        self.chamadas.append(list(mensagens))
        roteiro = self._turnos.pop(0) if self._turnos else ["(sem roteiro)"]
        if isinstance(roteiro, Exception):
            raise roteiro
        pedidas = tuple(p for p in roteiro if isinstance(p, ChamadaFerramenta))
        for p in roteiro:
            if isinstance(p, str):
                yield TextoParcial(p)
        yield FimTurno(chamadas=pedidas, tokens_entrada=10, tokens_saida=5)
