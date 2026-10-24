"""Interface dos agentes do Assistente e os eventos neutros que eles emitem.

Os eventos não são o contrato HTTP (`domain/assistente.py`): o serviço traduz. Assim uma
versão nova do contrato não mexe no agente, e trocar o agente não mexe no contrato.
"""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Protocol

from brikta_ia.assistente.ferramentas.execucao import ExecucaoFerramentas
from brikta_ia.domain.assistente import ErroAssistenteCodigo, TipoCitacao
from brikta_ia.providers.llm.base import MensagemTurno


@dataclass(frozen=True)
class StatusAgente:
    etapa: str
    texto: str


@dataclass(frozen=True)
class TextoAgente:
    texto: str


@dataclass(frozen=True)
class CitacaoAgente:
    tipo: TipoCitacao
    id: str
    rotulo: str


@dataclass(frozen=True)
class FimAgente:
    texto: str
    passos: int
    tokens_entrada: int = 0
    tokens_saida: int = 0


type EventoAgente = StatusAgente | TextoAgente | CitacaoAgente | FimAgente


class ErroAgente(Exception):
    """Falha que encerra a resposta com um código estável (vira o evento `erro`)."""

    def __init__(self, codigo: ErroAssistenteCodigo, mensagem: str) -> None:
        super().__init__(mensagem)
        self.codigo = codigo
        self.mensagem = mensagem


class Agente(Protocol):
    nome: str

    def responder(
        self, mensagens: Sequence[MensagemTurno], ferramentas: ExecucaoFerramentas
    ) -> AsyncIterator[EventoAgente]:
        """Emite status, texto e citações; termina com `FimAgente` ou levanta `ErroAgente`.

        `mensagens` = sistema + histórico + pergunta. Cancelar o iterador cancela o agente.
        """
        ...
