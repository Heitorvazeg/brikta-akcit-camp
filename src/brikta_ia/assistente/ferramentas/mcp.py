"""Cliente de servidores MCP externos (protótipo): clima e índices da construção.

Mock: `exemplo/mcp.json` faz o papel dos servidores. Só há uma lista fechada de
servidores/ferramentas (ADR-11: nada de MCP arbitrário). O cliente real (IA-74) mantém esta
entrada e saída; o dado externo sempre volta com citação do tipo EXTERNO.
"""

import json
from datetime import date, timedelta
from functools import cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from brikta_ia.assistente.ferramentas.registro import (
    Citacao,
    ContextoExecucao,
    ErroFerramenta,
    Ferramenta,
    RegistroFerramentas,
    ResultadoFerramenta,
)

DADOS = Path(__file__).parent / "exemplo" / "mcp.json"


@cache
def mcp_exemplo() -> dict[str, Any]:
    return json.loads(DADOS.read_text(encoding="utf-8"))["servidores"]


def catalogo() -> str:
    return "; ".join(
        f"{s}.{f}: {d['descricao']}"
        for s, srv in mcp_exemplo().items()
        for f, d in srv["ferramentas"].items()
    )


class ConsultarMcpEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    servidor: str = Field(description="Servidor MCP (ex.: clima, indicadores).")
    ferramenta: str = Field(description="Ferramenta do servidor (ex.: previsao, indice_custo).")
    argumentos: dict[str, str] = Field(
        default_factory=dict, description="Argumentos da ferramenta."
    )


async def consultar_mcp(
    entrada: ConsultarMcpEntrada, _contexto: ContextoExecucao
) -> ResultadoFerramenta:
    servidor = mcp_exemplo().get(entrada.servidor)
    definicao = servidor["ferramentas"].get(entrada.ferramenta) if servidor else None
    if servidor is None or definicao is None:
        raise ErroFerramenta(f"Servidor ou ferramenta MCP desconhecidos. Disponíveis: {catalogo()}")

    if entrada.servidor == "clima":
        cidade = entrada.argumentos.get("cidade", "").split(" - ")[0].strip()
        dias = definicao["previsao_por_cidade"].get(cidade)
        if dias is None:
            cidades = ", ".join(definicao["previsao_por_cidade"])
            raise ErroFerramenta(f"Cidade sem previsão. Disponíveis: {cidades}")
        hoje = date.today()
        dados: dict[str, Any] = {
            "cidade": cidade,
            "previsao": [
                {
                    "data": (hoje + timedelta(days=i)).isoformat(),
                    "condicao": condicao,
                    "chuva_mm": mm,
                    "chuva_forte": mm >= 30,
                }
                for i, (condicao, mm) in enumerate(dias)
            ],
        }
    else:
        indice = entrada.argumentos.get("indice", "")
        valor = definicao["valores"].get(indice)
        if valor is None:
            raise ErroFerramenta(f"Índice sem dado. Disponíveis: {', '.join(definicao['valores'])}")
        dados = {"indice": indice, **valor}

    return ResultadoFerramenta(
        dados=dados,
        citacoes=[
            Citacao(
                tipo="EXTERNO",
                id=f"{entrada.servidor}.{entrada.ferramenta}",
                referencia=servidor["rotulo"],
            )
        ],
    )


def registrar_ferramentas_mcp(registro: RegistroFerramentas) -> None:
    registro.registrar(
        Ferramenta(
            nome="consultar_mcp",
            descricao=(
                "Consulta um servidor MCP externo autorizado (dados de fora do Brikta). "
                f"Disponíveis: {catalogo()}"
            ),
            entrada=ConsultarMcpEntrada,
            executar=consultar_mcp,
        )
    )
