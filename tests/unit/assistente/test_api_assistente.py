"""Rotas do Assistente ponta a ponta na API (modelo falso, sem rede)."""

import json
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from tests.unit.assistente.apoio import AURORA, IPE, SEGREDO, passe

from brikta_ia.config import get_settings
from brikta_ia.domain.assistente import EVENTOS
from brikta_ia.main import criar_app
from brikta_ia.providers.llm.base import ChamadaFerramenta, ProvedorIndisponivel
from brikta_ia.providers.llm.fake import FakeLLMComFerramentas

SEMANA = {"obra_id": IPE, "data_inicio": "2026-09-21", "data_fim": "2026-09-27"}


@pytest.fixture(autouse=True)
def _config(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("IA_TICKET_SECRET", SEGREDO)
    monkeypatch.setenv("ASSISTENTE_DATA_REFERENCIA", "2026-09-29")
    monkeypatch.setenv("ASSISTENTE_FERRAMENTAS", "mock")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _cliente(
    turnos: list[list[str | ChamadaFerramenta] | Exception],
) -> tuple[TestClient, FakeLLMComFerramentas]:
    llm = FakeLLMComFerramentas(turnos)
    return TestClient(criar_app(llm_assistente=llm)), llm


def _auth(token: str | None = None) -> dict[str, str]:
    return {"Authorization": f"Bearer {token or passe()}"}


def _eventos(texto: str) -> list[tuple[str, dict[str, Any]]]:
    saida = []
    for bloco in texto.strip().split("\n\n"):
        linhas = dict(linha.split(": ", 1) for linha in bloco.splitlines())
        saida.append((linhas["event"], json.loads(linhas["data"])))
    return saida


def _conversa(cliente: TestClient, token: str | None = None, obra: str | None = IPE) -> str:
    r = cliente.post("/v1/assistente/conversas", json={"obra_id": obra}, headers=_auth(token))
    assert r.status_code == 201, r.text
    return r.json()["conversa_id"]


def _perguntar(
    cliente: TestClient,
    conversa: str,
    texto: str,
    *,
    token: str | None = None,
    mid: str | None = None,
):
    return cliente.post(
        f"/v1/assistente/conversas/{conversa}/mensagens",
        json={"cliente_mensagem_id": mid or str(uuid.uuid4()), "texto": texto},
        headers=_auth(token),
    )


def test_pergunta_com_consulta_em_sse_no_formato_do_contrato() -> None:
    cliente, llm = _cliente(
        [[ChamadaFerramenta("c1", "consultar_rdos", SEMANA)], ["Foram ", "64 pessoas-dia."]]
    )
    conversa = _conversa(cliente)
    r = _perguntar(cliente, conversa, "Quantas pessoas trabalharam semana passada?")

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    eventos = _eventos(r.text)
    for nome, dados in eventos:
        EVENTOS[nome].model_validate(dados)  # cada evento bate com o contrato .v1
    nomes = [n for n, _ in eventos]
    assert nomes[0] == "status" and nomes[-1] == "fim"
    assert "citacao" in nomes
    assert "".join(d["texto"] for n, d in eventos if n == "token") == "Foram 64 pessoas-dia."
    assert eventos[-1][1]["conversa_id"] == conversa
    # o modelo recebeu o "hoje" da demonstração e o nome da obra em foco
    sistema = llm.chamadas[0][0].conteudo
    assert "2026-09-29" in sistema and "Residencial Ipê Amarelo" in sistema


def test_sem_passe_passe_invalido_e_vencido() -> None:
    cliente, _ = _cliente([])
    assert cliente.post("/v1/assistente/conversas", json={}).json()["code"] == "NAO_AUTENTICADO"
    r = cliente.post("/v1/assistente/conversas", json={}, headers=_auth("lixo"))
    assert r.status_code == 401 and r.json()["code"] == "NAO_AUTENTICADO"
    r = cliente.post("/v1/assistente/conversas", json={}, headers=_auth(passe(validade_seg=-5)))
    assert r.status_code == 401
    assert r.json() == {"statusCode": 401, "code": "TOKEN_EXPIRADO", "message": "Passe vencido"}


def test_obra_em_foco_fora_do_passe_e_recusada() -> None:
    cliente, _ = _cliente([])
    r = cliente.post("/v1/assistente/conversas", json={"obra_id": AURORA}, headers=_auth())
    assert r.status_code == 404 and r.json()["code"] == "OBRA_NAO_ENCONTRADA"


def test_contexto_inicial_chega_ao_prompt_como_dado_e_nao_vira_historico() -> None:
    cliente, llm = _cliente([["Posso falar sobre isso."]])
    resumo = "Resumo da obra: média de 9 pessoas por dia."
    r = cliente.post(
        "/v1/assistente/conversas",
        json={"obra_id": IPE, "contexto_inicial": resumo},
        headers=_auth(),
    )
    assert r.status_code == 201, r.text
    resposta = _perguntar(cliente, r.json()["conversa_id"], "E a ocorrência?")
    assert _eventos(resposta.text)[-1][0] == "fim"

    mensagens = llm.chamadas[0]
    assert resumo in mensagens[0].conteudo  # no prompt de sistema, entre marcadores
    assert "nunca instrução" in mensagens[0].conteudo
    assert [m.papel for m in mensagens] == ["system", "user"]  # o resumo não é uma troca
    assert resumo not in mensagens[1].conteudo


def test_contexto_inicial_grande_demais_e_recusado() -> None:
    cliente, _ = _cliente([])
    r = cliente.post(
        "/v1/assistente/conversas",
        json={"contexto_inicial": "x" * 4001},
        headers=_auth(),
    )
    assert r.status_code == 422


def test_conversa_de_outra_pessoa_ou_empresa_nao_existe_para_quem_pergunta() -> None:
    cliente, _ = _cliente([["oi"]])
    conversa = _conversa(cliente)
    for intruso in (passe(sub="outra-pessoa"), passe(empresa_id="outra-empresa")):
        r = _perguntar(cliente, conversa, "oi", token=intruso)
        assert r.status_code == 404 and r.json()["code"] == "CONVERSA_NAO_ENCONTRADA"


def test_passe_renovado_continua_a_conversa_com_o_historico() -> None:
    cliente, llm = _cliente([["Bom dia!"], ["Era sobre a obra Ipê."]])
    conversa = _conversa(cliente)
    _perguntar(cliente, conversa, "Bom dia")
    r = _perguntar(cliente, conversa, "Do que falamos?", token=passe())  # passe novo, mesma pessoa
    assert r.status_code == 200
    segundo = [(m.papel, m.conteudo) for m in llm.chamadas[1]]
    assert ("user", "Bom dia") in segundo and ("assistant", "Bom dia!") in segundo


def test_mesmo_cliente_mensagem_id_repete_a_resposta_sem_chamar_o_modelo() -> None:
    cliente, llm = _cliente([["Resposta única."]])
    conversa = _conversa(cliente)
    mid = str(uuid.uuid4())
    primeira = _perguntar(cliente, conversa, "oi", mid=mid)
    segunda = _perguntar(cliente, conversa, "oi", mid=mid)
    assert _eventos(primeira.text) == _eventos(segunda.text)
    assert len(llm.chamadas) == 1


def test_falha_do_provedor_vira_evento_erro_e_nada_e_guardado() -> None:
    cliente, llm = _cliente([ProvedorIndisponivel("429"), ["Agora foi."]])
    conversa = _conversa(cliente)
    mid = str(uuid.uuid4())
    eventos = _eventos(_perguntar(cliente, conversa, "oi", mid=mid).text)
    assert eventos == [
        ("erro", {"codigo": "PROVEDOR_INDISPONIVEL", "mensagem": eventos[0][1]["mensagem"]})
    ]
    # repetir o mesmo id refaz a pergunta (a falha não foi guardada)
    assert _eventos(_perguntar(cliente, conversa, "oi", mid=mid).text)[-1][0] == "fim"
    assert len(llm.chamadas) == 2


def test_corpo_invalido_no_formato_de_erro_do_backend() -> None:
    cliente, _ = _cliente([])
    conversa = _conversa(cliente)
    r = cliente.post(
        f"/v1/assistente/conversas/{conversa}/mensagens",
        json={"cliente_mensagem_id": "nao-e-uuid", "texto": ""},
        headers=_auth(),
    )
    assert r.status_code == 422 and r.json()["code"] == "DADOS_INVALIDOS"
