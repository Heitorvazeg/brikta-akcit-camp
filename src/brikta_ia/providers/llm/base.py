"""Interfaces de LLM (Plano, Seção 7.1).

- `LLMEstruturado`: extração com structured output / tool use (RDO por voz, IA-21).
- `LLMComFerramentas`: um turno do modelo com ferramentas e streaming (Assistente, IA-66).
  O laço (chamar ferramentas e voltar ao modelo) é do agente, não do provedor.
"""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel


@dataclass(frozen=True)
class Mensagem:
    papel: Literal["system", "user", "assistant"]
    conteudo: str


@dataclass(frozen=True)
class ResultadoLLM[T: BaseModel]:
    dados: T
    provedor: str
    modelo: str
    tokens_entrada: int = 0
    tokens_saida: int = 0
    custo_usd: float = 0.0


class LLMEstruturado(Protocol):
    nome: str

    async def gerar[T: BaseModel](
        self, mensagens: list[Mensagem], schema: type[T], *, cache_prefixo: bool = True
    ) -> ResultadoLLM[T]: ...


# ── Assistente: um turno do modelo com ferramentas ────────────────────────


@dataclass(frozen=True)
class ChamadaFerramenta:
    id: str
    nome: str
    argumentos: dict[str, Any]


@dataclass(frozen=True)
class MensagemTurno:
    """Mensagem do histórico de um turno com ferramentas (formato neutro).

    - `assistant` pode trazer `chamadas` (o que o modelo pediu);
    - `tool` traz o resultado de uma chamada (`chamada_id`) em texto (JSON).
    """

    papel: Literal["system", "user", "assistant", "tool"]
    conteudo: str = ""
    chamadas: tuple[ChamadaFerramenta, ...] = ()
    chamada_id: str | None = None


@dataclass(frozen=True)
class TextoParcial:
    texto: str


@dataclass(frozen=True)
class FimTurno:
    """Fim do turno: com `chamadas`, o modelo quer ferramentas; sem, a resposta acabou."""

    chamadas: tuple[ChamadaFerramenta, ...] = ()
    tokens_entrada: int = 0
    tokens_saida: int = 0


type EventoLLM = TextoParcial | FimTurno


@dataclass(frozen=True)
class DefinicaoFerramenta:
    """Formato neutro (`RegistroFerramentas.schemas_para_modelo`); cada adaptador converte."""

    nome: str
    descricao: str
    parametros: dict[str, Any] = field(default_factory=dict[str, Any])


class ProvedorIndisponivel(Exception):
    """Falha do provedor (rede, limite, erro 5xx). O agente encerra com PROVEDOR_INDISPONIVEL.

    `str(erro)` é o tipo do erro do provedor; `RateLimitError` = limite de tokens por minuto.
    """


class LLMComFerramentas(Protocol):
    nome: str

    def turno(
        self, mensagens: Sequence[MensagemTurno], ferramentas: Sequence[DefinicaoFerramenta]
    ) -> AsyncIterator[EventoLLM]:
        """Texto em pedaços (`TextoParcial`) e, por último, um `FimTurno`."""
        ...
