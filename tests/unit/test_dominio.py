import pytest
from pydantic import ValidationError

from brikta_ia.domain.estados import StatusJob, transicao_valida
from brikta_ia.domain.rdo_schema import RdoProposto

RDO_EXEMPLO = {
    "clima": {"manha": "SOL", "tarde": "CHUVA", "impactou_atividades": True},
    "equipes": [
        {"funcao": "Pedreiro", "quantidade": 3, "evidencia": {"trecho": "três pedreiros"}},
    ],
    "atividades": [
        {
            "descricao": "Alvenaria do 2º pavimento",
            "status": "EM_ANDAMENTO",
            "evidencia": {"trecho": "subimos a alvenaria do segundo"},
        }
    ],
    "materiais": [
        {
            "descricao": "Cimento",
            "evento": "EM_FALTA",
            "evidencia": {"trecho": "faltou cimento de tarde"},
        }
    ],
    "ocorrencias": [
        {
            "tipo": "ATRASO_MATERIAL",
            "descricao": "Cimento não entregue",
            "gravidade": "MEDIA",
            "impacto_cronograma": True,
            "evidencia": {"trecho": "faltou cimento"},
        }
    ],
    "narrativa": "Três pedreiros na alvenaria do 2º pavimento; faltou cimento à tarde.",
    "campos_incertos": [{"caminho": "clima.tarde", "motivo": "AMBIGUO"}],
}


def test_rdo_proposto_valido() -> None:
    rdo = RdoProposto.model_validate(RDO_EXEMPLO)
    assert rdo.versao_schema == "rdo_proposto.v1"
    assert rdo.equipes[0].quantidade == 3
    assert rdo.equipes[0].ref_id is None  # item novo


@pytest.mark.parametrize(
    ("caminho", "valor"),
    [
        (("equipes", 0, "quantidade"), -1),
        (("clima", "manha"), "ENSOLARADO"),
        (("atividades", 0, "progresso_percentual"), 150),
    ],
)
def test_rdo_proposto_rejeita_valores_invalidos(caminho: tuple, valor: object) -> None:
    import copy

    dados = copy.deepcopy(RDO_EXEMPLO)
    alvo = dados
    for chave in caminho[:-1]:
        alvo = alvo[chave]
    alvo[caminho[-1]] = valor
    with pytest.raises(ValidationError):
        RdoProposto.model_validate(dados)


def test_rdo_proposto_rejeita_campos_desconhecidos() -> None:
    with pytest.raises(ValidationError):
        RdoProposto.model_validate({**RDO_EXEMPLO, "campo_inventado": 1})


def test_transicoes_do_job() -> None:
    assert transicao_valida(StatusJob.RECEBIDO, StatusJob.BAIXANDO)
    assert not transicao_valida(StatusJob.RECEBIDO, StatusJob.EXTRAINDO)  # não pula etapa
    assert transicao_valida(StatusJob.TRANSCREVENDO, StatusJob.FALHOU)
    assert transicao_valida(StatusJob.EXTRAINDO, StatusJob.CONCLUIDO_PARCIAL)
    assert not transicao_valida(StatusJob.BAIXANDO, StatusJob.CONCLUIDO_PARCIAL)  # sem transcrição
    assert not transicao_valida(StatusJob.CONCLUIDO, StatusJob.FALHOU)  # terminal
