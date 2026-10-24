"""Regras do serviço que a API não exercita bem: uma pergunta por vez e cancelamento."""

import uuid

import pytest
from tests.unit.assistente.apoio import IPE, contexto

from brikta_ia.assistente.agente.laco_proprio import AgenteLacoProprio
from brikta_ia.assistente.conversas import VALIDADE_CONVERSA_SEG, ConversasEmMemoria
from brikta_ia.assistente.ferramentas.bim import registrar_ferramentas_bim
from brikta_ia.assistente.ferramentas.documentos import registrar_ferramentas_documentos
from brikta_ia.assistente.ferramentas.exemplo import registrar_ferramentas_exemplo
from brikta_ia.assistente.ferramentas.mcp import registrar_ferramentas_mcp
from brikta_ia.assistente.ferramentas.registro import RegistroFerramentas
from brikta_ia.assistente.servico import ErroConversa, ServicoConversas
from brikta_ia.domain.assistente import EventoCitacao, EventoFim, NovaMensagem
from brikta_ia.providers.llm.base import ChamadaFerramenta
from brikta_ia.providers.llm.fake import FakeLLMComFerramentas


def _servico(
    turnos: list[list[str | ChamadaFerramenta] | Exception], relogio: list[float] | None = None
) -> ServicoConversas:
    registro = RegistroFerramentas()
    registrar_ferramentas_exemplo(registro)
    agora = relogio or [0.0]
    return ServicoConversas(
        AgenteLacoProprio(FakeLLMComFerramentas(turnos), max_passos=4),
        registro,
        ConversasEmMemoria(relogio=lambda: agora[0]),
        relogio=lambda: agora[0],
    )


def _msg(texto: str = "oi") -> NovaMensagem:
    return NovaMensagem(cliente_mensagem_id=uuid.uuid4(), texto=texto)


async def test_segunda_pergunta_enquanto_a_primeira_responde_e_recusada() -> None:
    svc = _servico([["primeira"], ["segunda"]])
    ctx = contexto()
    conversa = svc.criar(ctx, IPE)
    fluxo = svc.perguntar(ctx, conversa, _msg())
    await anext(fluxo)  # a primeira começou
    with pytest.raises(ErroConversa) as erro:
        svc.perguntar(ctx, conversa, _msg())
    assert erro.value.status == 409
    async for _ in fluxo:
        pass
    # terminou: a próxima pode
    eventos = [e async for e in svc.perguntar(ctx, conversa, _msg())]
    assert isinstance(eventos[-1], EventoFim)


async def test_app_fechou_no_meio_libera_a_conversa_e_nao_guarda_a_resposta() -> None:
    svc = _servico([["pedaço 1 ", "pedaço 2"], ["de novo"]])
    ctx = contexto()
    conversa = svc.criar(ctx, IPE)
    msg = _msg()
    fluxo = svc.perguntar(ctx, conversa, msg)
    await anext(fluxo)
    await fluxo.aclose()  # o que o Starlette faz quando o app desconecta
    assert conversa.em_andamento is None
    assert str(msg.cliente_mensagem_id) not in conversa.respostas
    assert conversa.trocas == []


async def test_conversa_velha_some_da_memoria() -> None:
    agora = [0.0]
    svc = _servico([], relogio=agora)
    ctx = contexto()
    velha = svc.criar(ctx, IPE)
    agora[0] = VALIDADE_CONVERSA_SEG + 1
    svc.criar(ctx, IPE)  # criar expurga
    with pytest.raises(ErroConversa):
        svc.obter(ctx, velha.id)


async def test_fluxo_com_documentos_bim_e_mcp_cita_as_tres_fontes() -> None:
    registro = RegistroFerramentas()
    registrar_ferramentas_documentos(registro)
    registrar_ferramentas_bim(registro)
    registrar_ferramentas_mcp(registro)
    turnos: list[list[str | ChamadaFerramenta] | Exception] = [
        [
            ChamadaFerramenta("1", "buscar_documentos", {"obra_id": IPE, "consulta": "desforma"}),
            ChamadaFerramenta("2", "consultar_modelo_bim", {"obra_id": IPE, "tipo": "LAJE"}),
            ChamadaFerramenta(
                "3",
                "consultar_mcp",
                {
                    "servidor": "clima",
                    "ferramenta": "previsao",
                    "argumentos": {"cidade": "Goiânia"},
                },
            ),
        ],
        ["Pelo memorial a desforma é após 14 dias."],
    ]
    svc = ServicoConversas(
        AgenteLacoProprio(FakeLLMComFerramentas(turnos), max_passos=4),
        registro,
        ConversasEmMemoria(),
    )
    ctx = contexto()
    eventos = [e async for e in svc.perguntar(ctx, svc.criar(ctx, IPE), _msg("quando desformar?"))]
    citacoes = [e for e in eventos if isinstance(e, EventoCitacao)]
    assert {c.tipo for c in citacoes} == {"DOCUMENTO", "BIM", "EXTERNO"}
    assert any("p. 2" in c.rotulo for c in citacoes)
    assert isinstance(eventos[-1], EventoFim)


async def test_contexto_traz_dados_da_obra_e_o_modelo_nao_recebe_listar_obras() -> None:
    llm = FakeLLMComFerramentas([["ok"]])
    registro = RegistroFerramentas()
    registrar_ferramentas_exemplo(registro)
    svc = ServicoConversas(
        AgenteLacoProprio(llm, max_passos=4),
        registro,
        ConversasEmMemoria(relogio=lambda: 0.0),
        relogio=lambda: 0.0,
    )
    ctx = contexto()
    conversa = svc.criar(ctx, IPE)
    [_ async for _ in svc.perguntar(ctx, conversa, _msg())]

    sistema = llm.chamadas[0][0].conteudo
    assert "Residencial Ipê Amarelo (Bloco A; Goiânia - GO; etapa Estrutura" in sistema
    assert "resp. Rafael Moura" in sistema
    assert "listar_obras" not in sistema
