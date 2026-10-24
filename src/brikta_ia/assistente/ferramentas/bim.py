"""Ferramenta do modelo BIM da obra (protótipo): elementos, quantidades e status.

Mock: `exemplo/bim.json` simula o que a ingestão IFC (IA-73) vai gravar. Totais e
percentuais são calculados aqui, nunca pelo modelo.
"""

import json
from collections import defaultdict
from functools import cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from brikta_ia.assistente.ferramentas.registro import (
    Citacao,
    ContextoExecucao,
    Ferramenta,
    RegistroFerramentas,
    ResultadoFerramenta,
)

DADOS = Path(__file__).parent / "exemplo" / "bim.json"


@cache
def bim_exemplo() -> dict[str, Any]:
    return json.loads(DADOS.read_text(encoding="utf-8"))


class ConsultarBimEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    obra_id: str = Field(description="Id da obra (da lista de obras do contexto).")
    pavimento: str | None = Field(default=None, description="Ex.: '2º pavimento', 'Fundação'.")
    tipo: str | None = Field(default=None, description="Ex.: PILAR, LAJE, VIGA, PAREDE.")


def _igual(a: str | None, b: str) -> bool:
    return a is None or a.strip().lower() == b.lower()


async def consultar_modelo_bim(
    entrada: ConsultarBimEntrada, _contexto: ContextoExecucao
) -> ResultadoFerramenta:
    modelo = bim_exemplo()
    itens = [
        e
        for e in modelo["elementos"]
        if e["obra_id"] == entrada.obra_id
        and _igual(entrada.pavimento, e["pavimento"])
        and _igual(entrada.tipo, e["tipo"])
    ]
    por_tipo: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"quantidade_total": 0.0, "unidade": "", "executado": 0.0}
    )
    for e in itens:
        t = por_tipo[e["tipo"]]
        t["quantidade_total"] += e["quantidade"]
        t["unidade"] = e["unidade"]
        if e["status"] == "EXECUTADO":
            t["executado"] += e["quantidade"]
    totais = {
        tipo: {
            **v,
            "percentual_executado": round(100 * v["executado"] / v["quantidade_total"], 1)
            if v["quantidade_total"]
            else 0,
        }
        for tipo, v in sorted(por_tipo.items())
    }
    por_pavimento: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for e in itens:
        por_pavimento[e["pavimento"]][e["status"]] += 1
    escopo = " · ".join(x for x in (entrada.pavimento, entrada.tipo) if x) or "obra toda"
    return ResultadoFerramenta(
        dados={
            "modelo": modelo["modelo"],
            "escopo": escopo,
            "totais_por_tipo": totais,
            "elementos_por_pavimento_e_status": {k: dict(v) for k, v in por_pavimento.items()},
            "elementos": itens,
        },
        citacoes=[
            Citacao(tipo="BIM", id=f"{entrada.obra_id}:bim", referencia=f"Modelo BIM · {escopo}")
        ]
        if itens
        else [],
    )


def registrar_ferramentas_bim(registro: RegistroFerramentas) -> None:
    registro.registrar(
        Ferramenta(
            nome="consultar_modelo_bim",
            descricao=(
                "Consulta o modelo BIM da obra: elementos (pilares, lajes, vigas, paredes…) por "
                "pavimento e tipo, com quantidade, status (PROJETADO, EM_EXECUCAO, EXECUTADO) e "
                "totais já calculados."
            ),
            entrada=ConsultarBimEntrada,
            executar=consultar_modelo_bim,
        )
    )
