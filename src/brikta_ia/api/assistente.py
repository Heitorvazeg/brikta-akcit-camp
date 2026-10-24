"""Rotas do Assistente (Plano, Seção 6.4; contrato `assistente_*.v1`).

O app chama direto, com o passe do backend no `Authorization`. Erros antes do fluxo voltam
como HTTP comum no formato do backend (`{statusCode, code, message}`); depois que o fluxo
abriu, só pelo evento `erro`. Fechar a conexão cancela o agente.
"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse

from brikta_ia.assistente.ferramentas.registro import ContextoExecucao
from brikta_ia.assistente.passe import PasseInvalido, conferir_passe
from brikta_ia.assistente.servico import ErroConversa, ServicoConversas
from brikta_ia.config import Settings, get_settings
from brikta_ia.domain.assistente import (
    ConversaCriada,
    ErroAssistenteCodigo,
    ErroHttp,
    Evento,
    NovaConversa,
    NovaMensagem,
    nome_do_evento,
)
from brikta_ia.observability.logging import get_logger

router = APIRouter(prefix="/v1/assistente", tags=["Assistente"])
log = get_logger(__name__)


class ErroAssistenteHttp(Exception):
    def __init__(self, status: int, codigo: ErroAssistenteCodigo, mensagem: str) -> None:
        self.status = status
        self.codigo = codigo
        self.mensagem = mensagem


def resposta_de_erro(erro: ErroAssistenteHttp) -> JSONResponse:
    corpo = ErroHttp(statusCode=erro.status, code=erro.codigo, message=erro.mensagem)
    return JSONResponse(corpo.model_dump(mode="json"), status_code=erro.status)


def servico(request: Request) -> ServicoConversas:
    return request.app.state.servico_conversas


def contexto_do_passe(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> ContextoExecucao:
    if not authorization or not authorization.startswith("Bearer "):
        raise ErroAssistenteHttp(401, ErroAssistenteCodigo.NAO_AUTENTICADO, "Passe ausente")
    try:
        return conferir_passe(
            authorization.removeprefix("Bearer ").strip(), settings.ia_ticket_secret
        )
    except PasseInvalido as erro:
        if erro.motivo != "vencido":  # vencer é o normal; o resto aponta configuração errada
            log.warning(
                "assistente.passe_recusado",
                motivo=erro.motivo,
                dica="confira se o IA_TICKET_SECRET é o mesmo no backend e na IA"
                if erro.motivo in ("assinatura_nao_confere", "sem_segredo")
                else None,
            )
        raise ErroAssistenteHttp(401, erro.codigo, erro.mensagem) from erro


Contexto = Annotated[ContextoExecucao, Depends(contexto_do_passe)]
Servico = Annotated[ServicoConversas, Depends(servico)]


@router.post("/conversas", status_code=201)
def criar_conversa(corpo: NovaConversa, contexto: Contexto, svc: Servico) -> ConversaCriada:
    try:
        return ConversaCriada(
            conversa_id=svc.criar(contexto, corpo.obra_id, corpo.contexto_inicial).id
        )
    except ErroConversa as erro:
        raise ErroAssistenteHttp(erro.status, erro.codigo, erro.mensagem) from erro


@router.post("/conversas/{conversa_id}/mensagens")
def enviar_mensagem(
    conversa_id: str, corpo: NovaMensagem, contexto: Contexto, svc: Servico
) -> StreamingResponse:
    try:
        conversa = svc.obter(contexto, conversa_id)
        eventos = svc.perguntar(contexto, conversa, corpo)
    except ErroConversa as erro:
        raise ErroAssistenteHttp(erro.status, erro.codigo, erro.mensagem) from erro
    return StreamingResponse(
        _sse(eventos),
        media_type="text/event-stream",
        # sem cache e sem buffer em proxies: o texto tem de chegar aos poucos
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _sse(eventos: AsyncIterator[Evento]) -> AsyncIterator[str]:
    async for evento in eventos:
        yield f"event: {nome_do_evento(evento)}\ndata: {evento.model_dump_json()}\n\n"
