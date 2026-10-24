"""Contratos com o backend (Plano, Seção 6) — fonte dos JSON Schemas em `contracts/`.

Gere/atualize os schemas com `uv run python scripts/gerar_contratos.py`.
O teste `tests/contract` falha se os arquivos em `contracts/` estiverem desatualizados.
IA-03: estes modelos precisam ser revisados em conjunto com quem implementa o backend.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from brikta_ia.domain.assistente import EventosAssistente, PedidosAssistente
from brikta_ia.domain.erros import ErroCodigo
from brikta_ia.domain.estados import StatusJob
from brikta_ia.domain.rdo_schema import RdoProposto
from brikta_ia.domain.resumo import ResumoJob, ResumoResultado


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ── Job: backend → IA ─────────────────────────────────────────────────────


class AudioDoJob(_Base):
    url: str = Field(description="URL pré-assinada de LEITURA do áudio (curta duração).")
    expira_em: datetime
    content_type: str
    tamanho_bytes: int = Field(gt=0)
    checksum_sha256: str
    duracao_seg: float | None = None
    capturado_em: datetime | None = None


class ObraContexto(_Base):
    nome: str
    localizacao: str | None = None
    status: str | None = None


class ItemCatalogo(_Base):
    id: str
    nome: str
    unidade_padrao: str | None = None


class CatalogoContexto(_Base):
    funcoes: list[ItemCatalogo] = Field(default_factory=list[ItemCatalogo])
    equipamentos: list[ItemCatalogo] = Field(default_factory=list[ItemCatalogo])
    materiais: list[ItemCatalogo] = Field(default_factory=list[ItemCatalogo])


class ResumoRdoAnterior(_Base):
    data_referencia: date
    resumo: str
    atividades_em_andamento: list[str] = Field(default_factory=list[str])


class ItemRdoAtual(BaseModel):
    """Item já existente no rascunho. Campos específicos variam por seção (extra permitido)."""

    model_config = ConfigDict(extra="allow")

    id: str
    origem: Literal["MANUAL", "IA"]
    editado_manual: bool


class RdoAtual(_Base):
    equipes: list[ItemRdoAtual] = Field(default_factory=list[ItemRdoAtual])
    atividades: list[ItemRdoAtual] = Field(default_factory=list[ItemRdoAtual])
    materiais: list[ItemRdoAtual] = Field(default_factory=list[ItemRdoAtual])
    equipamentos: list[ItemRdoAtual] = Field(default_factory=list[ItemRdoAtual])
    ocorrencias: list[ItemRdoAtual] = Field(default_factory=list[ItemRdoAtual])


class TermoGlossario(_Base):
    termo: str
    significado: str | None = None


class ContextoJob(_Base):
    obra: ObraContexto
    catalogo: CatalogoContexto = Field(default_factory=CatalogoContexto)
    ultimos_rdos: list[ResumoRdoAnterior] = Field(default_factory=list[ResumoRdoAnterior])
    rdo_atual: RdoAtual = Field(default_factory=RdoAtual)
    glossario_empresa: list[TermoGlossario] = Field(default_factory=list[TermoGlossario])


class OpcoesJob(_Base):
    idioma: str = "pt-BR"


class RdoVozJob(_Base):
    versao_contrato: Literal["rdo_voz_job.v1"] = "rdo_voz_job.v1"
    empresa_id: str
    obra_id: str
    rdo_id: str | None = None
    rdo_local_id: str
    gravacao_id: str
    data_referencia: date
    audio: AudioDoJob
    contexto: ContextoJob
    opcoes: OpcoesJob = Field(default_factory=OpcoesJob)


class JobAceito(_Base):
    job_id: str
    status: StatusJob


# ── Resultado: IA → backend (callback) ─────────────────────────────────────


class Correcao(_Base):
    de: str
    para: str


class Transcricao(_Base):
    bruta: str
    normalizada: str
    correcoes: list[Correcao] = Field(default_factory=list[Correcao])


class MetadadosStt(_Base):
    provedor: str
    modelo: str
    duracao_audio_seg: float


class MetadadosLlm(_Base):
    provedor: str
    modelo: str
    versao_prompt: str
    tokens_entrada: int
    tokens_saida: int


class Latencias(_Base):
    total: int
    stt: int | None = None
    extracao: int | None = None


class Metadados(_Base):
    versao_pipeline: str
    stt: MetadadosStt | None = None
    llm: MetadadosLlm | None = None
    custo_usd: float
    latencia_ms: Latencias


class RdoVozResultado(_Base):
    versao_contrato: Literal["rdo_voz_resultado.v1"] = "rdo_voz_resultado.v1"
    job_id: str
    gravacao_id: str
    empresa_id: str
    rdo_local_id: str
    status: Literal[StatusJob.CONCLUIDO, StatusJob.CONCLUIDO_PARCIAL, StatusJob.FALHOU]
    erro_codigo: ErroCodigo | None = None
    transcricao: Transcricao | None = None
    rdo_proposto: RdoProposto | None = None
    metadados: Metadados


# Registro usado por scripts/gerar_contratos.py e pelos testes de contrato.
CONTRATOS: dict[str, type[BaseModel]] = {
    "rdo_voz_job.v1": RdoVozJob,
    "rdo_voz_resultado.v1": RdoVozResultado,
    "rdo_proposto.v1": RdoProposto,
    # Resumo IA diário: backend → IA (fatos) e IA → backend (callback)
    "resumo_job.v1": ResumoJob,
    "resumo_resultado.v1": ResumoResultado,
    # Assistente (app → IA, com o passe do backend): IA-66
    "assistente_conversa.v1": PedidosAssistente,
    "assistente_eventos.v1": EventosAssistente,
}
