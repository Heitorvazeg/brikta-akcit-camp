"""Garantias do registro de ferramentas (ADR-07/ADR-11). Valem para o agente e para o MCP."""

import asyncio

import pytest
from pydantic import BaseModel, SecretStr

from brikta_ia.assistente.ferramentas import (
    AcessoNegado,
    ContextoExecucao,
    ErroFerramenta,
    Ferramenta,
    RegistroFerramentas,
    ResultadoFerramenta,
)

CONTEXTO = ContextoExecucao(
    empresa_id="empresa-a",
    usuario_id="usuario-1",
    role="OPERADOR",
    obras_visiveis=frozenset({"obra-1", "obra-2"}),
    jwt=SecretStr("jwt-do-usuario"),
)


class EntradaObra(BaseModel):
    obra_id: str


class EntradaVariasObras(BaseModel):
    obra_ids: list[str]


async def _eco(entrada: BaseModel, contexto: ContextoExecucao) -> ResultadoFerramenta:
    return ResultadoFerramenta(
        dados={"entrada": entrada.model_dump(), "empresa": contexto.empresa_id}
    )


def _registro() -> RegistroFerramentas:
    registro = RegistroFerramentas()
    registro.registrar(Ferramenta("obter_obra", "Detalha uma obra", EntradaObra, _eco))
    registro.registrar(Ferramenta("comparar_obras", "Compara obras", EntradaVariasObras, _eco))
    return registro


async def test_executa_com_contexto_injetado() -> None:
    resultado = await _registro().executar("obter_obra", {"obra_id": "obra-1"}, CONTEXTO)
    assert resultado.dados["empresa"] == "empresa-a"


@pytest.mark.parametrize(
    ("nome", "argumentos"),
    [
        ("obter_obra", {"obra_id": "obra-de-outra-empresa"}),
        ("comparar_obras", {"obra_ids": ["obra-1", "obra-3"]}),
    ],
)
async def test_bloqueia_obra_nao_visivel(nome: str, argumentos: dict) -> None:
    with pytest.raises(AcessoNegado):
        await _registro().executar(nome, argumentos, CONTEXTO)


async def test_argumentos_invalidos_e_ferramenta_desconhecida() -> None:
    registro = _registro()
    with pytest.raises(ErroFerramenta):
        await registro.executar("obter_obra", {}, CONTEXTO)
    with pytest.raises(ErroFerramenta):
        await registro.executar("apagar_tudo", {}, CONTEXTO)


async def test_timeout() -> None:
    async def lenta(entrada: BaseModel, contexto: ContextoExecucao) -> ResultadoFerramenta:
        await asyncio.sleep(1)
        return ResultadoFerramenta(dados=None)

    registro = RegistroFerramentas()
    registro.registrar(Ferramenta("lenta", "Lenta", EntradaObra, lenta, timeout_seg=0.01))
    with pytest.raises(ErroFerramenta, match="Tempo esgotado"):
        await registro.executar("lenta", {"obra_id": "obra-1"}, CONTEXTO)


def test_nao_aceita_ferramenta_de_escrita_nem_nome_repetido() -> None:
    registro = _registro()
    with pytest.raises(ValueError, match="escrita"):
        registro.registrar(
            Ferramenta("alterar_rdo", "Altera RDO", EntradaObra, _eco, somente_leitura=False)
        )
    with pytest.raises(ValueError, match="já registrada"):
        registro.registrar(Ferramenta("obter_obra", "Duplicada", EntradaObra, _eco))


def test_schemas_para_modelo_nao_expoem_contexto() -> None:
    schemas = _registro().schemas_para_modelo()
    assert [s["nome"] for s in schemas] == ["comparar_obras", "obter_obra"]
    texto = str(schemas)
    for segredo in ("empresa_id", "jwt", "obras_visiveis"):
        assert segredo not in texto


def test_schemas_para_modelo_sem_titulos_repetidos() -> None:
    assert '"title"' not in str(_registro().schemas_para_modelo()).replace("'", '"')


def test_contexto_nao_vaza_jwt_no_repr() -> None:
    assert "jwt-do-usuario" not in repr(CONTEXTO)
