"""Ponto de entrada da API (processo `api`).

Rotas previstas (Plano, Seção 6):
- GET  /health                              — pronto
- POST /v1/assistente/*                     — protótipo (IA-66): conversa em SSE com o passe
- POST /v1/jobs/resumo                      — Resumo IA diário (202 + callback assinado)
- POST /v1/jobs/rdo-voz, GET /v1/jobs/{id}  — IA-32
- /v1/index/*                               — IA-F6
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from brikta_ia import __version__
from brikta_ia.api import assistente, health, jobs
from brikta_ia.assistente.fabrica import criar_servico
from brikta_ia.config import get_settings
from brikta_ia.domain.assistente import ErroAssistenteCodigo
from brikta_ia.observability.logging import configurar_logging, get_logger
from brikta_ia.pipeline.resumo.servico import criar_servico_resumo
from brikta_ia.providers.llm.base import LLMComFerramentas


def criar_app(llm_assistente: LLMComFerramentas | None = None) -> FastAPI:
    settings = get_settings()
    configurar_logging(settings.log_nivel)

    app = FastAPI(
        title="Brikta IA",
        description="Serviço de orquestração de IA do Brikta: RDO por voz e Assistente de Obra.",
        version=__version__,
    )
    app.include_router(health.router)

    app.state.servico_conversas = criar_servico(settings, llm_assistente)
    if not settings.ia_ticket_secret.get_secret_value():
        # Sobe assim mesmo (jobs do RDO não dependem disso), mas o Assistente recusa tudo.
        get_logger(__name__).warning(
            "assistente.desligado",
            motivo="IA_TICKET_SECRET vazio ou fraco: defina o mesmo valor do backend "
            "(openssl rand -hex 32)",
        )
    app.include_router(assistente.router)

    app.state.settings = settings
    app.state.servico_resumo = criar_servico_resumo(settings, llm_assistente)
    app.include_router(jobs.router)

    @app.exception_handler(assistente.ErroAssistenteHttp)
    async def _erro_assistente(_: Request, erro: assistente.ErroAssistenteHttp) -> JSONResponse:
        return assistente.resposta_de_erro(erro)

    @app.exception_handler(RequestValidationError)
    async def _validacao(request: Request, erro: RequestValidationError) -> JSONResponse:
        # Corpo inválido no formato de erro do backend (o app decide pelo `code`).
        return assistente.resposta_de_erro(
            assistente.ErroAssistenteHttp(
                422, ErroAssistenteCodigo.DADOS_INVALIDOS, "Dados inválidos"
            )
        )

    return app


app = criar_app()
