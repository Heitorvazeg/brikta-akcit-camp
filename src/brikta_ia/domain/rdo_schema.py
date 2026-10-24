"""Schema de saída da extração: `RdoProposto` v1 (Plano, Seção 5.3).

Alinhado ao `SyncRdoDto` do backend e às colunas planejadas no Dicionário de Dados v2.0.
Mudança incompatível = nova versão (`rdo_proposto.v2`) + novo arquivo em `contracts/`.

Campos marcados como "preenchido por código" NÃO são pedidos ao modelo; a etapa de
validação (IA-24/IA-25) os calcula. Ver `SCHEMA_PARA_MODELO`.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CondicaoClima = Literal["SOL", "NUBLADO", "CHUVA", "CHUVA_FORTE"]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Clima(_Base):
    manha: CondicaoClima | None = None
    tarde: CondicaoClima | None = None
    impactou_atividades: bool | None = None


class Evidencia(_Base):
    trecho: str = Field(
        description="Substring LITERAL da transcrição normalizada que justifica o item."
    )
    inicio_seg: float | None = Field(
        default=None, description="Preenchido por código (segmentos do STT)."
    )
    fim_seg: float | None = Field(
        default=None, description="Preenchido por código (segmentos do STT)."
    )


class ItemBase(_Base):
    ref_id: str | None = Field(
        default=None,
        description="id de item JÁ EXISTENTE no RDO atual que este item atualiza; null = novo.",
    )
    evidencia: Evidencia


class Equipe(ItemBase):
    funcao: str
    funcao_catalogo_id: str | None = Field(default=None, description="Preenchido por código.")
    quantidade: int = Field(ge=0)
    horas_trabalhadas: float | None = Field(default=None, ge=0)


class Atividade(ItemBase):
    descricao: str
    local_obra: str | None = None
    status: Literal["INICIADA", "EM_ANDAMENTO", "CONCLUIDA"] | None = None
    progresso_percentual: int | None = Field(default=None, ge=0, le=100)
    id_local: str | None = Field(
        default=None, description="Preenchido por código (vínculo de fotos)."
    )


class Material(ItemBase):
    descricao: str
    material_catalogo_id: str | None = Field(default=None, description="Preenchido por código.")
    quantidade: float | None = Field(default=None, ge=0)
    unidade: str | None = None
    evento: Literal["RECEBIDO", "UTILIZADO", "EM_FALTA"]


class Equipamento(ItemBase):
    nome: str
    equipamento_catalogo_id: str | None = Field(default=None, description="Preenchido por código.")
    status: Literal["EM_USO", "DISPONIVEL", "COM_DEFEITO"] | None = None
    horimetro_inicial: float | None = Field(default=None, ge=0)
    horimetro_final: float | None = Field(default=None, ge=0)


TipoOcorrencia = Literal[
    "ATRASO_MATERIAL",
    "CLIMA",
    "ACIDENTE",
    "PROBLEMA_EXECUCAO",
    "FALTA_MAO_DE_OBRA",
    "EQUIPAMENTO",
    "OUTRO",
]


class Ocorrencia(ItemBase):
    tipo: TipoOcorrencia
    descricao: str
    gravidade: Literal["BAIXA", "MEDIA", "ALTA"]
    impacto_cronograma: bool


MotivoIncerteza = Literal[
    "BAIXA_CONFIANCA_STT",
    "AMBIGUO",
    "NAO_CASOU_CATALOGO",
    "VALOR_IMPLAUSIVEL",
    "SEM_EVIDENCIA",
    "MODELO_INCERTO",
]


class CampoIncerto(_Base):
    caminho: str = Field(description='Ex.: "equipes[1].quantidade", "clima.tarde".')
    motivo: MotivoIncerteza
    sugestoes: list[str] = Field(default_factory=list[str])


class RdoProposto(_Base):
    versao_schema: Literal["rdo_proposto.v1"] = "rdo_proposto.v1"
    clima: Clima = Field(default_factory=Clima)
    equipes: list[Equipe] = Field(default_factory=list[Equipe])
    atividades: list[Atividade] = Field(default_factory=list[Atividade])
    materiais: list[Material] = Field(default_factory=list[Material])
    equipamentos: list[Equipamento] = Field(default_factory=list[Equipamento])
    ocorrencias: list[Ocorrencia] = Field(default_factory=list[Ocorrencia])
    observacoes_gerais: str | None = None
    proximas_atividades: str | None = None
    narrativa: str = Field(description="Texto corrido do dia → rdos.texto_gerado_ia.")
    campos_incertos: list[CampoIncerto] = Field(default_factory=list[CampoIncerto])


# Campos calculados por código e que devem ser REMOVIDOS do schema enviado ao LLM (IA-20).
CAMPOS_PREENCHIDOS_POR_CODIGO: frozenset[str] = frozenset(
    {
        "funcao_catalogo_id",
        "material_catalogo_id",
        "equipamento_catalogo_id",
        "id_local",
        "inicio_seg",
        "fim_seg",
    }
)
