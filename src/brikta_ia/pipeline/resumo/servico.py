"""Monta o pipeline do Resumo IA a partir da configuração e guarda a idempotência dos jobs."""

import uuid

from brikta_ia.assistente.agente.base import Agente
from brikta_ia.assistente.fabrica import criar_agente, criar_registro
from brikta_ia.assistente.ferramentas.registro import RegistroFerramentas
from brikta_ia.config import Settings
from brikta_ia.domain.resumo import ResumoJob, ResumoResultado
from brikta_ia.pipeline.resumo.gerar import gerar_resumo
from brikta_ia.providers.llm.base import LLMComFerramentas


class ServicoResumo:
    def __init__(self, agente: Agente | None, registro: RegistroFerramentas, modelo: str) -> None:
        self._agente = agente
        self._registro = registro
        self._modelo = modelo
        self._por_chave: dict[str, str] = {}

    def job_para(self, chave: str | None) -> str | None:
        return self._por_chave.get(chave) if chave else None

    def registrar(self, chave: str | None) -> str:
        job_id = uuid.uuid4().hex
        if chave:
            self._por_chave[chave] = job_id
        return job_id

    async def gerar(self, job: ResumoJob, job_id: str) -> ResumoResultado:
        return await gerar_resumo(
            job, job_id, agente=self._agente, registro=self._registro, modelo=self._modelo
        )


def criar_servico_resumo(settings: Settings, llm: LLMComFerramentas | None = None) -> ServicoResumo:
    """Sem provedor real (`fake`) e sem LLM injetado, o texto sai de código (desenvolvimento)."""
    sem_modelo = llm is None and settings.llm_assistente_provedor == "fake"
    return ServicoResumo(
        None if sem_modelo else criar_agente(settings, llm),
        criar_registro(settings),
        "codigo" if sem_modelo else (settings.llm_assistente_modelo or "fake"),
    )
