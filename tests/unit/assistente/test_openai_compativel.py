"""Adaptador compatível com OpenAI contra um servidor falso (MockTransport), sem rede."""

import json
from typing import Any

import httpx2 as httpx  # o transporte do SDK openai 3.x (fork do httpx)
import pytest
from openai import AsyncOpenAI

from brikta_ia.providers.llm.base import (
    DefinicaoFerramenta,
    EventoLLM,
    FimTurno,
    MensagemTurno,
    ProvedorIndisponivel,
    TextoParcial,
)
from brikta_ia.providers.llm.openai_compativel import LLMOpenAICompativel


def _pedaco(delta: dict[str, Any] | None = None, uso: dict[str, int] | None = None) -> str:
    corpo: dict[str, Any] = {
        "id": "x",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": "m",
        "choices": [] if delta is None else [{"index": 0, "delta": delta}],
    }
    if uso:
        corpo["usage"] = {**uso, "total_tokens": sum(uso.values())}
    return f"data: {json.dumps(corpo)}\n\n"


def _llm(resposta: httpx.Response, pedidos: list[httpx.Request]) -> LLMOpenAICompativel:
    def responder(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        return resposta

    cliente = AsyncOpenAI(
        api_key="k",
        base_url="https://provedor.teste/v1",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(responder)),
    )
    return LLMOpenAICompativel(modelo="modelo-x", base_url="", api_key="", cliente=cliente)


async def _coletar(llm: LLMOpenAICompativel) -> list[EventoLLM]:
    ferramenta = DefinicaoFerramenta("listar_obras", "Lista", {"type": "object"})
    return [e async for e in llm.turno([MensagemTurno("user", "oi")], [ferramenta])]


async def test_texto_em_pedacos_e_uso() -> None:
    corpo = (
        _pedaco({"content": "Bom "})
        + _pedaco({"content": "dia"})
        + _pedaco(None, {"prompt_tokens": 12, "completion_tokens": 3})
        + "data: [DONE]\n\n"
    )
    pedidos: list[httpx.Request] = []
    llm = _llm(
        httpx.Response(200, text=corpo, headers={"content-type": "text/event-stream"}), pedidos
    )
    eventos = await _coletar(llm)

    assert eventos == [TextoParcial("Bom "), TextoParcial("dia"), FimTurno((), 12, 3)]
    enviado = json.loads(pedidos[0].content)
    assert enviado["model"] == "modelo-x" and enviado["stream"] is True
    assert enviado["tools"][0]["function"]["name"] == "listar_obras"


async def test_chamada_de_ferramenta_em_pedacos() -> None:
    def chamada(**f: Any) -> dict[str, Any]:
        return {"tool_calls": [{"index": 0, **f}]}

    corpo = (
        _pedaco(
            chamada(id="c1", type="function", function={"name": "consultar_rdos", "arguments": ""})
        )
        + _pedaco(chamada(function={"arguments": '{"obra_id": "o1", '}))
        + _pedaco(chamada(function={"arguments": '"data_inicio": "2026-09-21"}'}))
        + "data: [DONE]\n\n"
    )
    llm = _llm(httpx.Response(200, text=corpo, headers={"content-type": "text/event-stream"}), [])
    fim = (await _coletar(llm))[-1]
    assert isinstance(fim, FimTurno)
    assert fim.chamadas[0].nome == "consultar_rdos"
    assert fim.chamadas[0].argumentos == {"obra_id": "o1", "data_inicio": "2026-09-21"}


async def test_argumento_malformado_vai_para_o_registro_recusar() -> None:
    corpo = (
        _pedaco(
            {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "listar_obras", "arguments": "{quebrado"},
                    }
                ]
            }
        )
        + "data: [DONE]\n\n"
    )
    llm = _llm(httpx.Response(200, text=corpo, headers={"content-type": "text/event-stream"}), [])
    fim = (await _coletar(llm))[-1]
    assert isinstance(fim, FimTurno) and "_invalido" in fim.chamadas[0].argumentos


@pytest.mark.parametrize("status", [429, 500, 503])
async def test_erro_do_provedor_vira_provedor_indisponivel(status: int) -> None:
    llm = _llm(httpx.Response(status, json={"error": {"message": "x"}}), [])
    with pytest.raises(ProvedorIndisponivel):
        await _coletar(llm)
