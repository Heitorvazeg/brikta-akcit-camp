"""Adaptador para provedores compatíveis com a API da OpenAI (Groq, Cerebras, OpenRouter…).

Único lugar que importa o SDK `openai` no Assistente. Modelo, endereço e chave vêm da
configuração (`LLM_ASSISTENTE_*`), nunca do código.
"""

import json
from collections.abc import AsyncIterator, Sequence
from typing import Any

import openai
from openai import AsyncOpenAI

from brikta_ia.providers.llm.base import (
    ChamadaFerramenta,
    DefinicaoFerramenta,
    EventoLLM,
    FimTurno,
    MensagemTurno,
    ProvedorIndisponivel,
    TextoParcial,
)


class LLMOpenAICompativel:
    nome = "openai_compativel"

    def __init__(
        self,
        *,
        modelo: str,
        base_url: str,
        api_key: str,
        timeout_seg: float = 30.0,
        cliente: AsyncOpenAI | None = None,
    ) -> None:
        if not modelo:
            raise ValueError("LLM_ASSISTENTE_MODELO não configurado")
        self._modelo = modelo
        self._cliente = cliente or AsyncOpenAI(
            base_url=base_url or None, api_key=api_key, timeout=timeout_seg, max_retries=3
        )

    async def turno(
        self, mensagens: Sequence[MensagemTurno], ferramentas: Sequence[DefinicaoFerramenta]
    ) -> AsyncIterator[EventoLLM]:
        try:
            fluxo = await self._cliente.chat.completions.create(
                model=self._modelo,
                messages=[_mensagem(m) for m in mensagens],  # type: ignore[arg-type]
                tools=[_ferramenta(f) for f in ferramentas] or openai.NOT_GIVEN,  # type: ignore[arg-type]
                stream=True,
                stream_options={"include_usage": True},
                temperature=0.2,
            )
            # Chamadas chegam em pedaços, indexadas: junta id, nome e argumentos.
            chamadas: dict[int, dict[str, str]] = {}
            entrada = saida = 0
            async for pedaco in fluxo:
                if pedaco.usage:
                    entrada, saida = pedaco.usage.prompt_tokens, pedaco.usage.completion_tokens
                if not pedaco.choices:
                    continue
                delta = pedaco.choices[0].delta
                if delta.content:
                    yield TextoParcial(delta.content)
                for c in delta.tool_calls or []:
                    atual = chamadas.setdefault(c.index, {"id": "", "nome": "", "args": ""})
                    if c.id:
                        atual["id"] = c.id
                    if c.function and c.function.name:
                        atual["nome"] += c.function.name
                    if c.function and c.function.arguments:
                        atual["args"] += c.function.arguments
        except (openai.APIConnectionError, openai.APIStatusError, openai.APITimeoutError) as erro:
            raise ProvedorIndisponivel(type(erro).__name__) from erro

        yield FimTurno(
            chamadas=tuple(_chamada(i, c) for i, c in sorted(chamadas.items())),
            tokens_entrada=entrada,
            tokens_saida=saida,
        )


def _chamada(indice: int, c: dict[str, str]) -> ChamadaFerramenta:
    try:
        argumentos = json.loads(c["args"]) if c["args"] else {}
    except json.JSONDecodeError:
        # Argumento malformado: o registro recusa e o erro volta ao modelo.
        argumentos = {"_invalido": c["args"]}
    if not isinstance(argumentos, dict):
        argumentos = {"_invalido": argumentos}
    return ChamadaFerramenta(
        id=c["id"] or f"chamada-{indice}", nome=c["nome"], argumentos=argumentos
    )


def _mensagem(m: MensagemTurno) -> dict[str, Any]:
    if m.papel == "tool":
        return {"role": "tool", "tool_call_id": m.chamada_id, "content": m.conteudo}
    saida: dict[str, Any] = {"role": m.papel, "content": m.conteudo}
    if m.chamadas:
        saida["tool_calls"] = [
            {
                "id": c.id,
                "type": "function",
                "function": {"name": c.nome, "arguments": json.dumps(c.argumentos)},
            }
            for c in m.chamadas
        ]
    return saida


def _ferramenta(f: DefinicaoFerramenta) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {"name": f.nome, "description": f.descricao, "parameters": f.parametros},
    }
