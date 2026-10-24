"""Agente com laço PRÓPRIO e TEMPORÁRIO (protótipo; desvio do ADR-07 registrado no
IMPLEMENTACAO.md). Será substituído pelo framework escolhido na IA-64a, que implementa a
mesma interface `Agente` (`base.py`).

A cada passo: o modelo responde (texto em fluxo) ou pede ferramentas; as ferramentas
rodam por `ExecucaoFerramentas` e o resultado volta ao modelo. Para em `max_passos`.
"""

from collections.abc import AsyncIterator, Sequence

from brikta_ia.assistente.agente.base import (
    CitacaoAgente,
    ErroAgente,
    EventoAgente,
    FimAgente,
    StatusAgente,
    TextoAgente,
)
from brikta_ia.assistente.ferramentas.execucao import ExecucaoFerramentas
from brikta_ia.domain.assistente import ErroAssistenteCodigo
from brikta_ia.providers.llm.base import (
    DefinicaoFerramenta,
    FimTurno,
    LLMComFerramentas,
    MensagemTurno,
    ProvedorIndisponivel,
    TextoParcial,
)

STATUS_POR_FERRAMENTA = {
    "consultar_rdos": "Consultando RDOs…",
    "buscar_documentos": "Buscando nos documentos da obra…",
    "ler_pagina": "Lendo a página do documento…",
    "consultar_modelo_bim": "Consultando o modelo BIM…",
    "consultar_mcp": "Consultando dados externos…",
}


class AgenteLacoProprio:
    nome = "laco_proprio"

    def __init__(self, llm: LLMComFerramentas, *, max_passos: int) -> None:
        self._llm = llm
        self._max_passos = max_passos

    async def responder(
        self, mensagens: Sequence[MensagemTurno], ferramentas: ExecucaoFerramentas
    ) -> AsyncIterator[EventoAgente]:
        historico = list(mensagens)
        definicoes = [
            DefinicaoFerramenta(
                nome=d["nome"], descricao=d["descricao"], parametros=d["parametros"]
            )
            for d in ferramentas.definicoes()
        ]
        texto_total = ""
        entrada = saida = 0

        for passo in range(1, self._max_passos + 1):
            texto_turno = ""
            fim = FimTurno()
            try:
                async for evento in self._llm.turno(historico, definicoes):
                    if isinstance(evento, TextoParcial):
                        texto_turno += evento.texto
                        yield TextoAgente(evento.texto)
                    else:
                        fim = evento
            except ProvedorIndisponivel as erro:
                raise ErroAgente(
                    ErroAssistenteCodigo.PROVEDOR_INDISPONIVEL,
                    "Muitas perguntas ao mesmo tempo. Tente de novo em alguns segundos."
                    if str(erro) == "RateLimitError"
                    else "O assistente está indisponível agora. Tente de novo em instantes.",
                ) from erro
            entrada += fim.tokens_entrada
            saida += fim.tokens_saida
            texto_total += texto_turno

            if not fim.chamadas:
                yield FimAgente(texto_total, passo, entrada, saida)
                return

            historico.append(MensagemTurno("assistant", texto_turno, chamadas=fim.chamadas))
            if texto_turno:
                # o texto do turno que pediu ferramentas não pode grudar no da resposta
                texto_total += "\n\n"
                yield TextoAgente("\n\n")
            for chamada in fim.chamadas:
                yield StatusAgente(
                    etapa=f"consultando_{chamada.nome}",
                    texto=STATUS_POR_FERRAMENTA.get(chamada.nome, "Consultando os registros…"),
                )
                r = await ferramentas.executar(chamada.nome, chamada.argumentos)
                for c in r.novas_citacoes:
                    yield CitacaoAgente(tipo=c.tipo, id=c.id, rotulo=c.referencia or c.id)
                historico.append(MensagemTurno("tool", r.conteudo, chamada_id=chamada.id))

        raise ErroAgente(
            ErroAssistenteCodigo.LIMITE_PASSOS,
            "Não consegui concluir essa resposta. Tente perguntar de forma mais direta.",
        )
