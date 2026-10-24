import pytest
from tests.unit.assistente.apoio import AURORA, IPE, contexto

from brikta_ia.assistente.agente.base import (
    CitacaoAgente,
    ErroAgente,
    EventoAgente,
    FimAgente,
    StatusAgente,
    TextoAgente,
)
from brikta_ia.assistente.agente.laco_proprio import AgenteLacoProprio
from brikta_ia.assistente.ferramentas.execucao import ExecucaoFerramentas
from brikta_ia.assistente.ferramentas.exemplo import registrar_ferramentas_exemplo
from brikta_ia.assistente.ferramentas.registro import RegistroFerramentas
from brikta_ia.domain.assistente import ErroAssistenteCodigo
from brikta_ia.providers.llm.base import ChamadaFerramenta, MensagemTurno, ProvedorIndisponivel
from brikta_ia.providers.llm.fake import FakeLLMComFerramentas

SEMANA = {"obra_id": IPE, "data_inicio": "2026-09-21", "data_fim": "2026-09-27"}
PERGUNTA = [MensagemTurno("system", "regras"), MensagemTurno("user", "Quantas pessoas?")]


def _execucao() -> ExecucaoFerramentas:
    registro = RegistroFerramentas()
    registrar_ferramentas_exemplo(registro)
    return ExecucaoFerramentas(registro, contexto())


async def _rodar(llm: FakeLLMComFerramentas, max_passos: int = 4) -> list[EventoAgente]:
    agente = AgenteLacoProprio(llm, max_passos=max_passos)
    return [e async for e in agente.responder(PERGUNTA, _execucao())]


async def test_responde_sem_consultar() -> None:
    eventos = await _rodar(FakeLLMComFerramentas([["Bom ", "dia!"]]))
    assert [e for e in eventos if isinstance(e, TextoAgente)] == [
        TextoAgente("Bom "),
        TextoAgente("dia!"),
    ]
    assert eventos[-1] == FimAgente("Bom dia!", passos=1, tokens_entrada=10, tokens_saida=5)


async def test_consulta_cita_e_devolve_o_resultado_ao_modelo() -> None:
    llm = FakeLLMComFerramentas(
        [[ChamadaFerramenta("c1", "consultar_rdos", SEMANA)], ["Foram 64 pessoas-dia."]]
    )
    eventos = await _rodar(llm)

    assert isinstance(eventos[0], StatusAgente) and eventos[0].texto == "Consultando RDOs…"
    citacoes = [e for e in eventos if isinstance(e, CitacaoAgente)]
    assert citacoes and all(c.id.startswith("demo-") for c in citacoes)
    fim = eventos[-1]
    assert isinstance(fim, FimAgente) and fim.passos == 2
    # o segundo turno recebeu o pedido do modelo e o resultado da ferramenta
    segundo = llm.chamadas[1]
    assert segundo[-2].chamadas[0].nome == "consultar_rdos"
    assert segundo[-1].papel == "tool" and '"pessoas_dia"' in segundo[-1].conteudo


async def test_erro_da_ferramenta_volta_ao_modelo_sem_citar() -> None:
    fora = {**SEMANA, "obra_id": AURORA}
    llm = FakeLLMComFerramentas(
        [[ChamadaFerramenta("c1", "consultar_rdos", fora)], ["Não encontrei essa obra."]]
    )
    eventos = await _rodar(llm)
    assert not [e for e in eventos if isinstance(e, CitacaoAgente)]
    assert '"erro"' in llm.chamadas[1][-1].conteudo
    assert isinstance(eventos[-1], FimAgente)


async def test_limite_de_passos() -> None:
    sempre_consulta: list[list[str | ChamadaFerramenta] | Exception] = [
        [ChamadaFerramenta(f"c{i}", "consultar_rdos", SEMANA)] for i in range(5)
    ]
    with pytest.raises(ErroAgente) as erro:
        await _rodar(FakeLLMComFerramentas(sempre_consulta), max_passos=3)
    assert erro.value.codigo == ErroAssistenteCodigo.LIMITE_PASSOS


async def test_provedor_fora_do_ar() -> None:
    with pytest.raises(ErroAgente) as erro:
        await _rodar(FakeLLMComFerramentas([ProvedorIndisponivel("429")]))
    assert erro.value.codigo == ErroAssistenteCodigo.PROVEDOR_INDISPONIVEL


async def test_limite_de_tokens_do_provedor_tem_mensagem_propria() -> None:
    with pytest.raises(ErroAgente) as erro:
        await _rodar(FakeLLMComFerramentas([ProvedorIndisponivel("RateLimitError")]))
    assert erro.value.codigo == ErroAssistenteCodigo.PROVEDOR_INDISPONIVEL
    assert "Muitas perguntas" in str(erro.value)


def test_toda_ferramenta_tem_status_proprio() -> None:
    from brikta_ia.assistente.agente.laco_proprio import STATUS_POR_FERRAMENTA
    from brikta_ia.assistente.fabrica import criar_registro
    from brikta_ia.config import Settings

    nomes = set(criar_registro(Settings()).nomes_para_modelo())
    assert nomes <= set(STATUS_POR_FERRAMENTA), nomes - set(STATUS_POR_FERRAMENTA)


async def test_texto_antes_da_consulta_nao_gruda_na_resposta() -> None:
    llm = FakeLLMComFerramentas(
        [["Vou ver.", ChamadaFerramenta("c1", "consultar_rdos", SEMANA)], ["Pronto."]]
    )
    eventos = await _rodar(llm)
    fim = eventos[-1]
    assert isinstance(fim, FimAgente) and fim.texto == "Vou ver.\n\nPronto."
