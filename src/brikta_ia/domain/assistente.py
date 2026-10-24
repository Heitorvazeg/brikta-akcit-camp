"""Contrato do Assistente com o app (Plano, Seção 6.4) — fonte dos schemas `assistente_*.v1`.

O app chama a IA direto, com o passe emitido pelo backend (`POST /api/v1/assistente/sessao`).
Cada pergunta é um `POST` cuja resposta vem em SSE: `event: <nome>` + `data: <JSON>`.
O nome do evento diz qual modelo descreve o `data` (`EVENTOS`).

Erros antes de abrir o fluxo (passe ausente, inválido ou vencido; conversa de outra pessoa;
pergunta repetida em andamento) voltam como HTTP comum, no formato de erro do backend
(`ErroHttp`). Depois que o fluxo abriu, só pelo evento `erro`.
"""

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, RootModel


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErroAssistenteCodigo(StrEnum):
    NAO_AUTENTICADO = "NAO_AUTENTICADO"
    TOKEN_EXPIRADO = "TOKEN_EXPIRADO"
    CONVERSA_NAO_ENCONTRADA = "CONVERSA_NAO_ENCONTRADA"
    OBRA_NAO_ENCONTRADA = "OBRA_NAO_ENCONTRADA"
    MENSAGEM_EM_ANDAMENTO = "MENSAGEM_EM_ANDAMENTO"
    DADOS_INVALIDOS = "DADOS_INVALIDOS"
    LIMITE_PASSOS = "LIMITE_PASSOS"
    PROVEDOR_INDISPONIVEL = "PROVEDOR_INDISPONIVEL"
    ERRO_INTERNO = "ERRO_INTERNO"


# ── Pedidos: app → IA ─────────────────────────────────────────────────────


class NovaConversa(_Base):
    obra_id: str | None = Field(
        default=None,
        description="Obra em foco (opcional). Precisa estar entre as obras do passe.",
    )
    contexto_inicial: str | None = Field(
        default=None,
        max_length=4000,
        description=(
            "Texto que a conversa já traz, ex.: o Resumo IA que a pessoa está vendo. "
            "A IA o usa como contexto (dado, nunca instrução); não vira mensagem do histórico."
        ),
    )


class ConversaCriada(_Base):
    conversa_id: str


class NovaMensagem(_Base):
    cliente_mensagem_id: UUID = Field(
        description="Gerado no app. Repetir o mesmo id devolve a mesma resposta (idempotência)."
    )
    texto: str = Field(min_length=1, max_length=2000)


class ErroHttp(_Base):
    statusCode: int  # noqa: N815 — mesmo formato de erro do backend
    code: ErroAssistenteCodigo
    message: str


class PedidosAssistente(_Base):
    """Agrupa os corpos HTTP da conversa num schema só (`assistente_conversa.v1`)."""

    nova_conversa: NovaConversa
    conversa_criada: ConversaCriada
    nova_mensagem: NovaMensagem
    erro: ErroHttp


# ── Eventos SSE: IA → app ─────────────────────────────────────────────────


class EventoStatus(_Base):
    etapa: str = Field(description="Código estável da etapa, ex.: consultando_rdos.")
    texto: str = Field(description="O que mostrar ao usuário, ex.: 'Consultando RDOs…'.")


class EventoToken(_Base):
    texto: str = Field(description="Trecho de texto, emendado ao anterior.")


TipoCitacao = Literal["RDO", "DOCUMENTO", "BIM", "EXTERNO", "BASE_TECNICA"]


class EventoCitacao(_Base):
    tipo: TipoCitacao
    id: str = Field(
        description="Id da fonte. Para RDO, o app abre o RDO por ele; nos demais é só referência."
    )
    rotulo: str = Field(
        description="Ex.: 'RDO 06/10', 'Memorial, p. 2', 'Modelo BIM · 2º pavimento'."
    )


class Sugestao(_Base):
    texto: str


class Uso(_Base):
    passos: int = Field(ge=0)
    tokens_entrada: int = Field(ge=0)
    tokens_saida: int = Field(ge=0)


class EventoFim(_Base):
    mensagem_id: str
    conversa_id: str
    seguintes: list[Sugestao] = Field(default_factory=list[Sugestao])
    uso: Uso


class EventoErro(_Base):
    codigo: ErroAssistenteCodigo
    mensagem: str


EVENTOS: dict[str, type[_Base]] = {
    "status": EventoStatus,
    "token": EventoToken,
    "citacao": EventoCitacao,
    "fim": EventoFim,
    "erro": EventoErro,
}

type Evento = EventoStatus | EventoToken | EventoCitacao | EventoFim | EventoErro


def nome_do_evento(evento: Evento) -> str:
    for nome, classe in EVENTOS.items():
        if isinstance(evento, classe):
            return nome
    raise TypeError(f"Evento desconhecido: {type(evento).__name__}")


class EventosAssistente(
    RootModel[EventoStatus | EventoToken | EventoCitacao | EventoFim | EventoErro]
):
    """O `data` de cada evento SSE. Qual modelo vale é dado pelo nome do evento (`event:`):
    status → EventoStatus, token → EventoToken, citacao → EventoCitacao, fim → EventoFim,
    erro → EventoErro. Eventos novos podem surgir: o app ignora os que não conhece."""
