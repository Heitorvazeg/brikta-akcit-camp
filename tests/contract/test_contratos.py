"""Os arquivos em contracts/ precisam refletir os modelos Pydantic (IA-03, BE-46)."""

import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from brikta_ia.domain.assistente import EVENTOS, EventoToken, NovaMensagem, nome_do_evento
from brikta_ia.domain.contratos import CONTRATOS, RdoVozJob, RdoVozResultado
from scripts.gerar_contratos import PASTA, renderizar


@pytest.mark.parametrize("nome", list(CONTRATOS))
def test_contrato_commitado_esta_atualizado(nome: str) -> None:
    arquivo = PASTA / f"{nome}.json"
    assert arquivo.exists(), f"Falta {arquivo.name}: rode scripts/gerar_contratos.py"
    assert arquivo.read_text(encoding="utf-8") == renderizar(nome), (
        f"{arquivo.name} desatualizado: rode scripts/gerar_contratos.py"
    )


EXEMPLOS = Path(__file__).parent / "exemplos"


def test_exemplo_de_job_valido() -> None:
    dados = json.loads((EXEMPLOS / "rdo_voz_job.v1.json").read_text(encoding="utf-8"))
    job = RdoVozJob.model_validate(dados)
    assert job.contexto.rdo_atual.equipes[0].editado_manual is True


def test_exemplo_de_resultado_valido() -> None:
    dados = json.loads((EXEMPLOS / "rdo_voz_resultado.v1.json").read_text(encoding="utf-8"))
    resultado = RdoVozResultado.model_validate(dados)
    assert resultado.rdo_proposto is not None


def test_exemplo_de_eventos_do_assistente_valido() -> None:
    eventos = json.loads((EXEMPLOS / "assistente_eventos.v1.json").read_text(encoding="utf-8"))
    for item in eventos:
        modelo = EVENTOS[item["event"]].model_validate(item["data"])
        assert nome_do_evento(modelo) == item["event"]  # type: ignore[arg-type]


def test_evento_com_campo_desconhecido_e_recusado() -> None:
    with pytest.raises(ValidationError):
        EventoToken.model_validate({"texto": "a", "extra": 1})


def test_nova_mensagem_exige_uuid_e_texto() -> None:
    with pytest.raises(ValidationError):
        NovaMensagem.model_validate({"cliente_mensagem_id": "nao-e-uuid", "texto": "oi"})
    with pytest.raises(ValidationError):
        NovaMensagem.model_validate({"cliente_mensagem_id": str(uuid4()), "texto": ""})
