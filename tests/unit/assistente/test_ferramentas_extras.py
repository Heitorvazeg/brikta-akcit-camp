import pytest
from tests.unit.assistente.apoio import IPE, RECANTO, contexto

from brikta_ia.assistente.fabrica import criar_registro
from brikta_ia.assistente.ferramentas.bim import registrar_ferramentas_bim
from brikta_ia.assistente.ferramentas.documentos import (
    documentos_exemplo,
    registrar_ferramentas_documentos,
)
from brikta_ia.assistente.ferramentas.execucao import ExecucaoFerramentas
from brikta_ia.assistente.ferramentas.mcp import registrar_ferramentas_mcp
from brikta_ia.assistente.ferramentas.registro import (
    AcessoNegado,
    ErroFerramenta,
    RegistroFerramentas,
)
from brikta_ia.config import Settings

AURORA = "de300000-0000-4000-8000-0000000000a2"


@pytest.fixture
def registro() -> RegistroFerramentas:
    r = RegistroFerramentas()
    registrar_ferramentas_documentos(r)
    registrar_ferramentas_bim(r)
    registrar_ferramentas_mcp(r)
    return r


def test_registro_padrao_inclui_extras_e_flag_desliga() -> None:
    assert {"buscar_documentos", "ler_pagina", "consultar_modelo_bim", "consultar_mcp"} <= set(
        criar_registro(Settings()).nomes()
    )
    assert criar_registro(Settings(assistente_ferramentas_extras="")).nomes() == [
        "consultar_rdos",
        "listar_obras",
    ]
    assert (
        "consultar_mcp"
        not in criar_registro(Settings(assistente_ferramentas_extras="documentos,bim")).nomes()
    )


async def test_buscar_documentos_acha_trecho_com_pagina_e_citacao(
    registro: RegistroFerramentas,
) -> None:
    r = await registro.executar(
        "buscar_documentos", {"obra_id": IPE, "consulta": "desforma"}, contexto()
    )
    trechos = r.dados["trechos"]
    assert trechos and trechos[0]["documento_id"] == "doc-ipe-memorial"
    assert trechos[0]["pagina"] == 2
    assert {c.tipo for c in r.citacoes} == {"DOCUMENTO"}
    assert r.citacoes[0].referencia == "Memorial descritivo - Bloco A, p. 2"


async def test_buscar_documentos_nao_mistura_obras(registro: RegistroFerramentas) -> None:
    r = await registro.executar(
        "buscar_documentos",
        {"obra_id": RECANTO, "consulta": "impermeabilização baldrame"},
        contexto(),
    )
    ids = {t["documento_id"] for t in r.dados["trechos"]}
    donos = {d["id"]: d["obra_id"] for d in documentos_exemplo()}
    assert ids and all(donos[i] == RECANTO for i in ids)


async def test_buscar_documentos_obra_fora_do_passe(registro: RegistroFerramentas) -> None:
    with pytest.raises(AcessoNegado):
        await registro.executar(
            "buscar_documentos", {"obra_id": AURORA, "consulta": "grua"}, contexto()
        )


async def test_ler_pagina_e_limites(registro: RegistroFerramentas) -> None:
    r = await registro.executar(
        "ler_pagina", {"documento_id": "doc-ipe-contrato", "pagina": 2}, contexto()
    )
    assert "Multa" in r.dados["texto"] and r.dados["total_paginas"] == 2
    with pytest.raises(ErroFerramenta, match="2 página"):
        await registro.executar(
            "ler_pagina", {"documento_id": "doc-ipe-contrato", "pagina": 9}, contexto()
        )
    # documento de obra fora do passe: mesma resposta de "não existe"
    with pytest.raises(AcessoNegado):
        await registro.executar(
            "ler_pagina", {"documento_id": "doc-aur-ata", "pagina": 1}, contexto()
        )
    with pytest.raises(AcessoNegado):
        await registro.executar(
            "ler_pagina", {"documento_id": "nao-existe", "pagina": 1}, contexto()
        )


async def test_bim_totais_calculados_em_codigo(registro: RegistroFerramentas) -> None:
    r = await registro.executar(
        "consultar_modelo_bim", {"obra_id": IPE, "tipo": "pilar"}, contexto()
    )
    pilares = r.dados["totais_por_tipo"]["PILAR"]
    assert pilares["quantidade_total"] == 36 and pilares["executado"] == 24
    assert pilares["percentual_executado"] == 66.7
    assert r.citacoes[0].tipo == "BIM"


async def test_bim_sem_elementos_nao_cita(registro: RegistroFerramentas) -> None:
    r = await registro.executar(
        "consultar_modelo_bim", {"obra_id": IPE, "pavimento": "10º pavimento"}, contexto()
    )
    assert r.dados["elementos"] == [] and r.citacoes == []


async def test_mcp_clima_e_indice_com_citacao_externa(registro: RegistroFerramentas) -> None:
    clima = await registro.executar(
        "consultar_mcp",
        {"servidor": "clima", "ferramenta": "previsao", "argumentos": {"cidade": "Goiânia"}},
        contexto(),
    )
    assert len(clima.dados["previsao"]) == 5
    assert any(d["chuva_forte"] for d in clima.dados["previsao"])
    assert clima.citacoes[0].tipo == "EXTERNO"
    indice = await registro.executar(
        "consultar_mcp",
        {
            "servidor": "indicadores",
            "ferramenta": "indice_custo",
            "argumentos": {"indice": "INCC-M"},
        },
        contexto(),
    )
    assert indice.dados["variacao_12m_pct"] == 6.1


async def test_mcp_desconhecido_lista_o_catalogo(registro: RegistroFerramentas) -> None:
    with pytest.raises(ErroFerramenta, match=r"clima\.previsao"):
        await registro.executar(
            "consultar_mcp", {"servidor": "drive", "ferramenta": "listar"}, contexto()
        )
    with pytest.raises(ErroFerramenta, match="Disponíveis"):
        await registro.executar(
            "consultar_mcp",
            {"servidor": "clima", "ferramenta": "previsao", "argumentos": {"cidade": "Marte"}},
            contexto(),
        )


async def test_execucao_so_cita_o_que_foi_consultado(registro: RegistroFerramentas) -> None:
    execucao = ExecucaoFerramentas(registro, contexto())
    a = await execucao.executar("buscar_documentos", {"obra_id": IPE, "consulta": "formas laje"})
    b = await execucao.executar("ler_pagina", {"documento_id": "doc-ipe-memorial", "pagina": 2})
    assert a.novas_citacoes
    # a página já citada na busca não duplica a fonte
    assert not any(c.id == "doc-ipe-memorial" and c in a.novas_citacoes for c in b.novas_citacoes)
    erro = await execucao.executar("consultar_mcp", {"servidor": "x", "ferramenta": "y"})
    assert erro.erro and erro.novas_citacoes == []
