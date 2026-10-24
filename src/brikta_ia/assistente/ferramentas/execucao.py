"""Execução das ferramentas de UMA pergunta, independente do agente (ADR-07, item 3).

Qualquer agente (laço próprio, framework da IA-64a, servidor MCP) chama ferramentas por
aqui. Ficam neste lugar, e não no agente:
- o `ContextoExecucao` (empresa, usuário, obras do passe), que o modelo nunca escolhe;
- o limite de chamadas por pergunta (Plano, 9.3: no máximo 6);
- as citações: só viram fonte os itens que uma ferramenta devolveu NESTA pergunta (9.3,
  item 4), então o modelo não consegue citar algo que não consultou.
"""

import json
from dataclasses import dataclass, field
from typing import Any

from brikta_ia.assistente.ferramentas.registro import (
    Citacao,
    ContextoExecucao,
    ErroFerramenta,
    RegistroFerramentas,
)

MAX_CHAMADAS_POR_PERGUNTA = 6


@dataclass(frozen=True)
class ResultadoChamada:
    #: O que volta ao modelo (JSON em texto). Erro também volta, para ele tentar outro caminho.
    conteudo: str
    #: Fontes que esta chamada trouxe pela primeira vez na pergunta.
    novas_citacoes: list[Citacao] = field(default_factory=list[Citacao])
    erro: bool = False


class ExecucaoFerramentas:
    def __init__(
        self,
        registro: RegistroFerramentas,
        contexto: ContextoExecucao,
        *,
        max_chamadas: int = MAX_CHAMADAS_POR_PERGUNTA,
    ) -> None:
        self._registro = registro
        self._contexto = contexto
        self._max_chamadas = max_chamadas
        self.chamadas = 0
        self.citacoes: dict[str, Citacao] = {}

    def definicoes(self) -> list[dict[str, Any]]:
        """Nome, descrição e JSON Schema de cada ferramenta (formato neutro)."""
        return self._registro.schemas_para_modelo()

    async def executar(self, nome: str, argumentos: dict[str, Any]) -> ResultadoChamada:
        if self.chamadas >= self._max_chamadas:
            return _erro("Limite de consultas desta pergunta atingido: responda com o que tem.")
        self.chamadas += 1
        try:
            resultado = await self._registro.executar(nome, argumentos, self._contexto)
        except ErroFerramenta as erro:
            return _erro(str(erro))
        novas = [c for c in resultado.citacoes if f"{c.tipo}:{c.id}" not in self.citacoes]
        for c in novas:
            self.citacoes[f"{c.tipo}:{c.id}"] = c
        conteudo = json.dumps(resultado.dados, ensure_ascii=False, default=str)
        return ResultadoChamada(conteudo=conteudo, novas_citacoes=novas)


def _erro(mensagem: str) -> ResultadoChamada:
    return ResultadoChamada(json.dumps({"erro": mensagem}, ensure_ascii=False), erro=True)
