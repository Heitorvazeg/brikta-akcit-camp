"""Contrato do Resumo IA (job diário): backend → IA (fatos) e IA → backend (callback).

O backend manda os FATOS dos últimos RDOs já calculados no banco. A IA escreve o texto e os
alertas, e devolve no formato que o app mostra (`TextoRico`). Números, destaques e fontes saem
de código, nunca do modelo.
"""

from datetime import date, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brikta_ia.domain.estados import StatusJob


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OcorrenciaFato(_Base):
    tipo: str
    gravidade: str | None = None
    descricao: str
    impacto_cronograma: bool = False


class RdoFato(_Base):
    rdo_id: str
    data: date
    numero: int | None = None
    situacao: str
    pessoas: int = Field(ge=0, description="Pessoas na obra no dia (soma da equipe).")
    clima_manha: str | None = None
    clima_tarde: str | None = None
    clima_impactou: bool | None = None
    atividades: list[str] = Field(default_factory=list[str])
    ocorrencias: list[OcorrenciaFato] = Field(default_factory=list[OcorrenciaFato])
    equipamentos_com_defeito: list[str] = Field(default_factory=list[str])
    materiais_em_falta: list[str] = Field(default_factory=list[str])
    proximas_atividades: list[str] = Field(default_factory=list[str])


class ObraFatos(_Base):
    obra_id: str
    nome: str
    etapa_atual: str | None = None
    progresso_percentual: int | None = Field(default=None, ge=0, le=100)
    rdos: list[RdoFato] = Field(default_factory=list[RdoFato])


class ResumoJob(_Base):
    versao_contrato: Literal["resumo_job.v1"] = "resumo_job.v1"
    empresa_id: str
    escopo: Literal["geral", "obra"]
    obra_id: str | None = Field(default=None, description="Obrigatório quando o escopo é 'obra'.")
    data_referencia: date = Field(
        description="Obra: o dia em que o resumo é gerado. Geral (semanal): a segunda-feira da "
        "semana em que é gerado; o período cobre a semana anterior."
    )
    periodo_inicio: date
    periodo_fim: date
    obras: list[ObraFatos] = Field(min_length=1)

    @model_validator(mode="after")
    def _coerente(self) -> Self:
        if self.escopo == "obra" and self.obra_id not in {o.obra_id for o in self.obras}:
            raise ValueError("escopo 'obra' exige obra_id entre as obras enviadas")
        if self.periodo_fim < self.periodo_inicio:
            raise ValueError("periodo_fim antes de periodo_inicio")
        return self


# ── Resultado: IA → backend (callback) ─────────────────────────────────────


class Trecho(_Base):
    t: str
    s: Literal["num", "b", "mark"] | None = None


type TextoRico = list[Trecho]


class Destaque(_Base):
    icone: str = Field(description="Nome Ionicons usado pelo app.")
    rotulo: str
    valor: str


class FonteRdo(_Base):
    rotulo: str
    rdo_id: str


class OutraFonte(_Base):
    tipo: Literal["DOCUMENTO", "BIM", "EXTERNO"]
    rotulo: str


class ResumoConteudo(_Base):
    periodo: str
    base_rdos: int = Field(ge=0)
    gerado_em: datetime
    texto: list[Trecho]
    destaques: list[Destaque] = Field(default_factory=list[Destaque])
    alertas: list[list[Trecho]] = Field(default_factory=list[list[Trecho]])
    proximos: list[list[Trecho]] = Field(default_factory=list[list[Trecho]])
    fontes: list[FonteRdo] = Field(default_factory=list[FonteRdo])
    outras_fontes: list[OutraFonte] = Field(default_factory=list[OutraFonte])


class MetadadosResumo(_Base):
    versao_prompt: str
    modelo: str
    passos: int = 0
    tokens_entrada: int = 0
    tokens_saida: int = 0
    latencia_ms: int = 0


class ResumoResultado(_Base):
    versao_contrato: Literal["resumo_resultado.v1"] = "resumo_resultado.v1"
    job_id: str
    empresa_id: str
    escopo: Literal["geral", "obra"]
    obra_id: str | None = None
    data_referencia: date
    status: Literal[StatusJob.CONCLUIDO, StatusJob.FALHOU]
    erro_mensagem: str | None = None
    resumo: ResumoConteudo | None = None
    metadados: MetadadosResumo
