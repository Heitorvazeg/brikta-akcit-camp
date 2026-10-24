"""Conversas do Assistente e onde ficam guardadas.

`RepositorioConversas` é a porta; hoje só existe `ConversasEmMemoria` (protótipo). A IA-61
acrescenta a versão em Postgres (tabelas `conversas` e `mensagens`) sem mexer no serviço.

Em memória, exige um único processo da API (o `Dockerfile` sobe um worker): com dois,
cada um teria um histórico diferente. Reiniciar a IA apaga as conversas.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from brikta_ia.domain.assistente import Evento

#: Conversa sem uso há mais que isso deixa de existir.
VALIDADE_CONVERSA_SEG = 24 * 3600


@dataclass
class Troca:
    pergunta: str
    resposta: str


@dataclass
class Conversa:
    id: str
    usuario_id: str
    empresa_id: str
    obra_foco: str | None
    usada_em: float
    #: Texto trazido pelo app ao criar a conversa (ex.: Resumo IA); entra no prompt como dado.
    contexto_inicial: str | None = None
    trocas: list[Troca] = field(default_factory=list[Troca])
    #: Respostas concluídas por `cliente_mensagem_id` (idempotência): repetir devolve igual.
    respostas: dict[str, list[Evento]] = field(default_factory=dict[str, list[Evento]])
    #: `cliente_mensagem_id` da pergunta em andamento (uma por vez).
    em_andamento: str | None = None


class RepositorioConversas(Protocol):
    def criar(self, conversa: Conversa) -> None: ...

    def obter(self, conversa_id: str) -> Conversa | None: ...

    def salvar(self, conversa: Conversa) -> None:
        """Grava as mudanças (em memória é o próprio objeto; no Postgres, um UPDATE)."""
        ...


class ConversasEmMemoria:
    def __init__(self, relogio: Callable[[], float] = time.monotonic) -> None:
        self._relogio = relogio
        self._conversas: dict[str, Conversa] = {}

    def criar(self, conversa: Conversa) -> None:
        self._expurgar()
        self._conversas[conversa.id] = conversa

    def obter(self, conversa_id: str) -> Conversa | None:
        return self._conversas.get(conversa_id)

    def salvar(self, conversa: Conversa) -> None:
        self._conversas[conversa.id] = conversa

    def _expurgar(self) -> None:
        limite = self._relogio() - VALIDADE_CONVERSA_SEG
        for cid in [c.id for c in self._conversas.values() if c.usada_em < limite]:
            del self._conversas[cid]
