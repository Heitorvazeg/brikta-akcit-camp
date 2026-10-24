"""Jobs chamados pelo backend com token de serviço.

`POST /v1/jobs/resumo`: recebe os fatos, responde 202 e gera o Resumo IA em segundo plano;
o resultado volta por callback assinado. `Idempotency-Key` repetido devolve o mesmo job sem
gerar de novo (memória do processo; fila e banco entram com a IA-30/31).
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Header, Request
from fastapi.responses import JSONResponse

from brikta_ia.api.auth import TokenServico
from brikta_ia.config import Settings
from brikta_ia.domain.contratos import JobAceito
from brikta_ia.domain.estados import StatusJob
from brikta_ia.domain.resumo import ResumoJob
from brikta_ia.integrations.backend import enviar_callback
from brikta_ia.observability.logging import get_logger
from brikta_ia.pipeline.resumo.servico import ServicoResumo

router = APIRouter(prefix="/v1/jobs", tags=["jobs"], dependencies=[TokenServico])
log = get_logger(__name__)


async def _processar(
    servico: ServicoResumo, settings: Settings, job: ResumoJob, job_id: str
) -> None:
    try:
        resultado = await servico.gerar(job, job_id)
        await enviar_callback(settings, resultado)
        log.info("resumo.entregue", job_id=job_id, status=resultado.status.value)
    except Exception:
        log.exception("resumo.erro_inesperado", job_id=job_id)


@router.post("/resumo", status_code=202, response_model=JobAceito)
async def criar_job_resumo(
    job: ResumoJob,
    request: Request,
    tarefas: BackgroundTasks,
    idempotency_key: Annotated[str | None, Header()] = None,
) -> JobAceito | JSONResponse:
    servico: ServicoResumo = request.app.state.servico_resumo
    settings: Settings = request.app.state.settings
    job_id = servico.job_para(idempotency_key)
    if job_id is None:
        job_id = servico.registrar(idempotency_key)
        tarefas.add_task(_processar, servico, settings, job, job_id)
    return JobAceito(job_id=job_id, status=StatusJob.RECEBIDO)
