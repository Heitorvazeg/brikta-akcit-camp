import json

import pytest
from tests.unit.assistente.apoio import AURORA, IPE, contexto

from brikta_ia.assistente.ferramentas.execucao import ExecucaoFerramentas
from brikta_ia.assistente.ferramentas.exemplo import dados_exemplo, registrar_ferramentas_exemplo
from brikta_ia.assistente.ferramentas.registro import (
    AcessoNegado,
    ErroFerramenta,
    RegistroFerramentas,
)


@pytest.fixture
def registro() -> RegistroFerramentas:
    r = RegistroFerramentas()
    registrar_ferramentas_exemplo(r)
    return r


async def test_listar_obras_nao_e_ferramenta_do_modelo(registro: RegistroFerramentas) -> None:
    assert "listar_obras" not in registro.nomes_para_modelo()
    assert "listar_obras" not in [s["nome"] for s in registro.schemas_para_modelo()]
    with pytest.raises(ErroFerramenta):  # o modelo não consegue pedi-la
        await registro.executar("listar_obras", {}, contexto(frozenset({IPE})))


async def test_listar_obras_so_as_do_passe(registro: RegistroFerramentas) -> None:
    r = await registro.executar("listar_obras", {}, contexto(frozenset({IPE})), interna=True)
    assert [o["id"] for o in r.dados["obras"]] == [IPE]


async def test_consultar_rdos_totais_batem_com_a_soma(registro: RegistroFerramentas) -> None:
    r = await registro.executar(
        "consultar_rdos",
        {"obra_id": IPE, "data_inicio": "2026-09-21", "data_fim": "2026-09-27"},
        contexto(),
    )
    rdos = r.dados["rdos"]
    assert rdos, "a semana de exemplo tem RDOs"
    assert r.dados["totais"]["pessoas_dia"] == sum(x["pessoas"] for x in rdos)
    assert r.dados["totais"]["rdos"] == len(rdos)
    assert r.dados["totais"]["pico"]["pessoas"] == max(x["pessoas"] for x in rdos)
    # citações com o rdo_local_id do seed (o app abre o RDO certo) (abrem o RDO certo)
    ids_do_app = {x["id"] for x in dados_exemplo()["rdos"]}
    assert {c.id for c in r.citacoes} == {x["rdo_id"] for x in rdos} <= ids_do_app
    assert r.citacoes[0].referencia == f"RDO {rdos[0]['data'][8:10]}/{rdos[0]['data'][5:7]}"


async def test_periodo_sem_rdo_devolve_zero(registro: RegistroFerramentas) -> None:
    r = await registro.executar(
        "consultar_rdos",
        {"obra_id": IPE, "data_inicio": "2025-01-01", "data_fim": "2025-01-07"},
        contexto(),
    )
    assert r.dados["totais"]["rdos"] == 0
    assert r.dados["totais"]["pico"] is None
    assert r.citacoes == []


@pytest.mark.parametrize(
    ("inicio", "fim"), [("2026-09-10", "2026-09-01"), ("2026-08-01", "2026-09-30")]
)
async def test_periodo_invalido_e_recusado(
    registro: RegistroFerramentas, inicio: str, fim: str
) -> None:
    with pytest.raises(ErroFerramenta):
        await registro.executar(
            "consultar_rdos", {"obra_id": IPE, "data_inicio": inicio, "data_fim": fim}, contexto()
        )


async def test_obra_fora_do_passe_e_acesso_negado(registro: RegistroFerramentas) -> None:
    with pytest.raises(AcessoNegado):
        await registro.executar(
            "consultar_rdos",
            {"obra_id": AURORA, "data_inicio": "2026-09-21", "data_fim": "2026-09-27"},
            contexto(frozenset({IPE})),
        )


async def test_execucao_limita_chamadas_e_nao_repete_citacao(
    registro: RegistroFerramentas,
) -> None:
    exec_ = ExecucaoFerramentas(registro, contexto(), max_chamadas=2)
    args = {"obra_id": IPE, "data_inicio": "2026-09-21", "data_fim": "2026-09-27"}
    primeira = await exec_.executar("consultar_rdos", args)
    segunda = await exec_.executar("consultar_rdos", args)
    terceira = await exec_.executar("consultar_rdos", args)
    assert primeira.novas_citacoes and not segunda.novas_citacoes
    assert terceira.erro and "Limite" in json.loads(terceira.conteudo)["erro"]


async def test_execucao_devolve_erro_ao_modelo_sem_levantar(
    registro: RegistroFerramentas,
) -> None:
    exec_ = ExecucaoFerramentas(registro, contexto(frozenset({IPE})))
    r = await exec_.executar(
        "consultar_rdos", {"obra_id": AURORA, "data_inicio": "2026-09-21", "data_fim": "2026-09-27"}
    )
    assert r.erro
    assert r.novas_citacoes == []
    assert "permissão" in json.loads(r.conteudo)["erro"]


async def test_cada_rdo_traz_o_dia_da_semana(registro: RegistroFerramentas) -> None:
    r = await registro.executar(
        "consultar_rdos",
        {"obra_id": IPE, "data_inicio": "2026-10-12", "data_fim": "2026-10-18"},
        contexto(),
    )
    dias = {x["data"]: x["dia_da_semana"] for x in r.dados["rdos"]}
    assert dias["2026-10-15"] == "quinta"


async def test_rdo_traz_os_servicos_executados(registro: RegistroFerramentas) -> None:
    recanto = "de300000-0000-4000-8000-0000000000a3"
    r = await registro.executar(
        "consultar_rdos",
        {"obra_id": recanto, "data_inicio": "2026-10-19", "data_fim": "2026-10-19"},
        contexto(frozenset({recanto})),
    )
    rdo = r.dados["rdos"][0]
    assert rdo["servicos_executados"], "o RDO do dia tem atividades no seed"
    assert isinstance(rdo["servicos_executados"][0], str)
    assert r.dados["detalhe"] == "completo"
    assert "equipe_por_funcao" in rdo


async def test_periodo_longo_vem_resumido_e_dia_sem_rdo_e_informado(
    registro: RegistroFerramentas,
) -> None:
    r = await registro.executar(
        "consultar_rdos",
        {"obra_id": IPE, "data_inicio": "2026-10-10", "data_fim": "2026-10-20"},
        contexto(frozenset({IPE})),
    )
    assert r.dados["detalhe"].startswith("resumido")
    assert "equipamentos" not in r.dados["rdos"][0]
    assert "2026-10-20" in r.dados["totais"]["dias_sem_rdo"]
