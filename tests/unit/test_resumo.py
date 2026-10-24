"""Resumo IA: fatos de código + texto do modelo + job HTTP com callback."""

import json
from collections.abc import Iterator
from datetime import UTC, date, datetime
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, SecretStr

from brikta_ia.assistente.agente.laco_proprio import AgenteLacoProprio
from brikta_ia.assistente.fabrica import criar_registro
from brikta_ia.config import Settings, get_settings
from brikta_ia.domain.estados import StatusJob
from brikta_ia.domain.resumo import ResumoJob, ResumoResultado
from brikta_ia.integrations.assinatura import verificar
from brikta_ia.integrations.backend import enviar_callback
from brikta_ia.main import criar_app
from brikta_ia.pipeline.resumo.gerar import (
    ResumoInvalido,
    gerar_resumo,
    interpretar_resposta,
    para_texto_rico,
)
from brikta_ia.providers.llm.base import ChamadaFerramenta
from brikta_ia.providers.llm.fake import FakeLLMComFerramentas

IPE = "de300000-0000-4000-8000-0000000000a1"
AURORA = "de300000-0000-4000-8000-0000000000a2"
TOKEN = "token-de-servico"


def _rdo(rdo_id: str, dia: int, **extra: Any) -> dict[str, Any]:
    return {
        "rdo_id": rdo_id,
        "data": f"2026-10-{dia:02d}",
        "numero": dia,
        "situacao": "VALIDADO",
        "pessoas": 10,
        "proximas_atividades": ["Concretar a laje L3"],
        **extra,
    }


def _job(escopo: str = "geral") -> dict[str, Any]:
    ocorrencia = {
        "tipo": "Atraso de material",
        "gravidade": "MEDIA",
        "descricao": "Aço CA-50 chegou 3 dias depois.",
        "impacto_cronograma": True,
    }
    obras = [
        {
            "obra_id": IPE,
            "nome": "Residencial Ipê Amarelo",
            "progresso_percentual": 68,
            "rdos": [_rdo("r1", 14), _rdo("r2", 15, pessoas=14, ocorrencias=[ocorrencia])],
        },
        {"obra_id": AURORA, "nome": "Edifício Aurora", "rdos": [_rdo("r3", 15)]},
    ]
    return {
        "empresa_id": "empresa-1",
        "escopo": escopo,
        "obra_id": IPE if escopo == "obra" else None,
        "data_referencia": "2026-10-20",
        "periodo_inicio": "2026-10-13",
        "periodo_fim": "2026-10-19",
        "obras": obras if escopo == "geral" else obras[:1],
    }


RESPOSTA = (
    "TEXTO: Residencial Ipê Amarelo teve 2 RDOs e o aço chegou atrasado.\n"
    "ALERTAS:\n- Residencial Ipê Amarelo · aço CA-50 atrasou 3 dias.\n"
)


async def _gerar(job: dict[str, Any], turnos: list[Any]) -> ResumoResultado:
    return await gerar_resumo(
        ResumoJob.model_validate(job),
        "job-1",
        agente=AgenteLacoProprio(FakeLLMComFerramentas(turnos), max_passos=4),
        registro=criar_registro(Settings()),
        modelo="fake",
        agora=datetime(2026, 10, 20, 6, 0, tzinfo=UTC),
    )


async def test_geral_calcula_destaques_fontes_e_marca_o_texto() -> None:
    r = await _gerar(_job(), [[RESPOSTA]])
    assert r.status is StatusJob.CONCLUIDO and r.resumo
    assert [(d.rotulo, d.valor) for d in r.resumo.destaques] == [
        ("Obras em execução", "2"),
        ("RDOs no período", "3"),
        ("Ocorrências", "1"),
    ]
    assert r.resumo.base_rdos == 3 and r.resumo.periodo == "13/10 a 19/10"
    # última RDO de cada obra, com o id do servidor
    assert [f.rdo_id for f in r.resumo.fontes] == ["r2", "r3"]
    estilos = {(t.t, t.s) for t in r.resumo.texto if t.s}
    assert ("Residencial Ipê Amarelo", "b") in estilos and ("2", "num") in estilos
    assert len(r.resumo.alertas) == 1
    assert r.resumo.proximos[0][0].t == "Residencial Ipê Amarelo · "
    assert len(r.resumo.proximos) == 1  # mesma atividade nas duas obras: não repete


async def test_obra_destaques_e_proximos_sem_prefixo() -> None:
    r = await _gerar(_job("obra"), [[RESPOSTA]])
    assert r.resumo
    assert [(d.rotulo, d.valor) for d in r.resumo.destaques] == [
        ("Andamento", "68%"),
        ("Equipe média", "12"),
        ("Ocorrências", "1"),
    ]
    assert [x.t for x in r.resumo.proximos[0]] == ["Concretar a laje L3"]
    assert [f.rdo_id for f in r.resumo.fontes] == ["r2", "r1"]


async def test_ferramentas_viram_outras_fontes_e_so_das_obras_do_job() -> None:
    turnos: list[Any] = [
        [ChamadaFerramenta("1", "buscar_documentos", {"obra_id": IPE, "consulta": "prazo multa"})],
        [RESPOSTA],
    ]
    r = await _gerar(_job("obra"), turnos)
    assert r.resumo and r.resumo.outras_fontes
    assert {f.tipo for f in r.resumo.outras_fontes} == {"DOCUMENTO"}
    # pedir obra fora do job não vaza: a ferramenta devolve erro e o resumo segue
    fora: list[Any] = [
        [ChamadaFerramenta("1", "buscar_documentos", {"obra_id": AURORA, "consulta": "grua"})],
        [RESPOSTA],
    ]
    r2 = await _gerar(_job("obra"), fora)
    assert r2.status is StatusJob.CONCLUIDO and r2.resumo and not r2.resumo.outras_fontes


async def test_resposta_fora_do_formato_vira_falhou() -> None:
    r = await _gerar(_job(), [["Aqui está o resumo da semana…"]])
    assert r.status is StatusJob.FALHOU and r.resumo is None and r.erro_mensagem


def test_interpretar_resposta() -> None:
    texto, alertas = interpretar_resposta("TEXTO: Tudo bem.\nALERTAS:\n- a\n• b\n")
    assert texto == "Tudo bem." and alertas == ["a", "b"]
    assert interpretar_resposta("TEXTO: Só texto")[1] == []
    with pytest.raises(ResumoInvalido):
        interpretar_resposta("ALERTAS:\n- a")


def test_para_texto_rico_preserva_o_texto() -> None:
    original = "Ipê Amarelo teve 12 pessoas (68%) e 3,5 m² de laje."
    trechos = para_texto_rico(original, ["Ipê Amarelo"])
    assert "".join(t.t for t in trechos) == original
    assert [t.s for t in trechos if t.s] == ["b", "num", "num", "num"]


def test_job_escopo_obra_exige_obra_id_entre_as_enviadas() -> None:
    ruim = _job("obra")
    ruim["obra_id"] = AURORA
    with pytest.raises(ValueError, match="obra_id"):
        ResumoJob.model_validate(ruim)


# ── HTTP ──────────────────────────────────────────────────────────────────


@pytest.fixture
def entregas(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[BaseModel]]:
    monkeypatch.setenv("IA_SERVICE_TOKENS", TOKEN)
    monkeypatch.setenv("LLM_ASSISTENTE_PROVEDOR", "fake")
    get_settings.cache_clear()
    capturadas: list[BaseModel] = []

    async def falso(_settings: Settings, resultado: BaseModel, **_: Any) -> bool:
        capturadas.append(resultado)
        return True

    monkeypatch.setattr("brikta_ia.api.jobs.enviar_callback", falso)
    yield capturadas
    get_settings.cache_clear()


def test_job_http_responde_202_gera_sem_modelo_e_entrega(entregas: list[BaseModel]) -> None:
    cliente = TestClient(criar_app())
    h = {"Authorization": f"Bearer {TOKEN}", "Idempotency-Key": "chave-1"}
    r = cliente.post("/v1/jobs/resumo", json=_job(), headers=h)
    assert r.status_code == 202 and r.json()["status"] == "RECEBIDO"
    assert len(entregas) == 1
    res = entregas[0]
    assert isinstance(res, ResumoResultado) and res.job_id == r.json()["job_id"]
    assert res.status is StatusJob.CONCLUIDO and res.metadados.modelo == "codigo"
    assert res.resumo and res.resumo.alertas  # alerta de código: ocorrência com impacto
    # mesma chave: mesmo job, sem gerar de novo
    r2 = cliente.post("/v1/jobs/resumo", json=_job(), headers=h)
    assert r2.json()["job_id"] == r.json()["job_id"] and len(entregas) == 1


def test_job_http_exige_token_e_valida_corpo(entregas: list[BaseModel]) -> None:
    cliente = TestClient(criar_app())
    assert cliente.post("/v1/jobs/resumo", json=_job()).status_code == 401
    h = {"Authorization": f"Bearer {TOKEN}"}
    assert cliente.post("/v1/jobs/resumo", json={"escopo": "geral"}, headers=h).status_code == 422
    assert entregas == []


# ── Callback assinado ─────────────────────────────────────────────────────


async def test_callback_assina_com_hmac_e_repete_em_5xx() -> None:
    chamadas: list[httpx.Request] = []

    def responder(req: httpx.Request) -> httpx.Response:
        chamadas.append(req)
        return httpx.Response(503 if len(chamadas) == 1 else 200)

    settings = Settings(ia_callback_secret=SecretStr("segredo-do-callback"))
    resultado = ResumoResultado.model_validate(
        {
            "job_id": "j1",
            "empresa_id": "e1",
            "escopo": "geral",
            "data_referencia": date(2026, 10, 20),
            "status": "FALHOU",
            "erro_mensagem": "x",
            "metadados": {"versao_prompt": "resumo/v1", "modelo": "fake"},
        }
    )
    import brikta_ia.integrations.backend as modulo

    modulo.ESPERA_BASE_SEG = 0
    async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as http:
        assert await enviar_callback(settings, resultado, cliente=http) is True
    assert len(chamadas) == 2
    req = chamadas[-1]
    assert req.url.path.endswith("/internal/ia/callback")
    assert verificar(
        b"segredo-do-callback",
        req.content,
        req.headers["x-brikta-timestamp"],
        req.headers["x-brikta-signature"],
    )
    assert json.loads(req.content)["versao_contrato"] == "resumo_resultado.v1"


async def test_callback_sem_segredo_nao_envia() -> None:
    class Vazio(BaseModel):
        pass

    assert await enviar_callback(Settings(), Vazio()) is False


def test_data_dd_mm_nao_vira_numero_destacado() -> None:
    trechos = para_texto_rico("RDOs entre 13/10 a 19/10: 24 registros", [])
    assert "".join(t.t for t in trechos) == "RDOs entre 13/10 a 19/10: 24 registros"
    assert [t.t for t in trechos if t.s] == ["24"]
