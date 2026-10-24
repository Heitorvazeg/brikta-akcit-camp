"""Ferramentas de DOCUMENTOS da obra (protótipo): memorial, projetos, contrato, atas, laudos.

Mock: os documentos vêm de `exemplo/documentos.json`. O fluxo é o real (validação, obra do
passe, timeout, citação com documento e página); só o miolo muda quando a ingestão existir
(IA-70..72, índice próprio com filtro de obra no SQL), mantendo entrada e saída.
"""

import json
import re
import unicodedata
from functools import cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from brikta_ia.assistente.ferramentas.registro import (
    AcessoNegado,
    Citacao,
    ContextoExecucao,
    ErroFerramenta,
    Ferramenta,
    RegistroFerramentas,
    ResultadoFerramenta,
)

DADOS = Path(__file__).parent / "exemplo" / "documentos.json"
MAX_TRECHOS = 5
TAMANHO_TRECHO = 280


@cache
def documentos_exemplo() -> list[dict[str, Any]]:
    return json.loads(DADOS.read_text(encoding="utf-8"))["documentos"]


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sem_acento if unicodedata.category(c) != "Mn")


def _termos(texto: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", _normalizar(texto)) if len(t) > 2}


class BuscarDocumentosEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    obra_id: str = Field(description="Id da obra (da lista de obras do contexto).")
    consulta: str = Field(min_length=2, max_length=200, description="O que procurar.")


class LerPaginaEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documento_id: str = Field(description="Id do documento (vem de buscar_documentos).")
    pagina: int = Field(ge=1, description="Número da página.")


def _rotulo(doc: dict[str, Any], pagina: int) -> str:
    return f"{doc['titulo']}, p. {pagina}"


async def buscar_documentos(
    entrada: BuscarDocumentosEntrada, _contexto: ContextoExecucao
) -> ResultadoFerramenta:
    termos = _termos(entrada.consulta)
    achados: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    for doc in documentos_exemplo():
        if doc["obra_id"] != entrada.obra_id:
            continue
        titulo = _termos(doc["titulo"])
        for pag in doc["paginas"]:
            pontos = len(termos & _termos(pag["texto"])) + len(termos & titulo)
            if pontos:
                achados.append((pontos, doc, pag))
    achados.sort(key=lambda a: (-a[0], a[1]["id"], a[2]["n"]))
    top = achados[:MAX_TRECHOS]
    return ResultadoFerramenta(
        dados={
            "consulta": entrada.consulta,
            "trechos": [
                {
                    "documento_id": d["id"],
                    "documento": d["titulo"],
                    "tipo": d["tipo"],
                    "pagina": p["n"],
                    "trecho": p["texto"][:TAMANHO_TRECHO],
                }
                for _, d, p in top
            ],
        },
        citacoes=[
            Citacao(
                tipo="DOCUMENTO",
                id=d["id"],
                referencia=_rotulo(d, p["n"]),
                trecho=p["texto"][:TAMANHO_TRECHO],
            )
            for _, d, p in top
        ],
    )


async def ler_pagina(entrada: LerPaginaEntrada, contexto: ContextoExecucao) -> ResultadoFerramenta:
    doc = next((d for d in documentos_exemplo() if d["id"] == entrada.documento_id), None)
    # Documento de obra fora do passe é tratado como inexistente (sem vazar que existe).
    if doc is None or doc["obra_id"] not in contexto.obras_visiveis:
        raise AcessoNegado("Documento não encontrado ou sem permissão")
    pag = next((p for p in doc["paginas"] if p["n"] == entrada.pagina), None)
    if pag is None:
        raise ErroFerramenta(f"O documento tem {len(doc['paginas'])} página(s).")
    return ResultadoFerramenta(
        dados={
            "documento": doc["titulo"],
            "tipo": doc["tipo"],
            "pagina": pag["n"],
            "total_paginas": len(doc["paginas"]),
            "texto": pag["texto"],
        },
        citacoes=[
            Citacao(
                tipo="DOCUMENTO",
                id=doc["id"],
                referencia=_rotulo(doc, pag["n"]),
                trecho=pag["texto"][:TAMANHO_TRECHO],
            )
        ],
    )


def registrar_ferramentas_documentos(registro: RegistroFerramentas) -> None:
    registro.registrar(
        Ferramenta(
            nome="buscar_documentos",
            descricao=(
                "Busca trechos nos documentos da obra (memorial, projetos, contrato, atas, "
                "laudos). Devolve até 5 trechos com documento e página."
            ),
            entrada=BuscarDocumentosEntrada,
            executar=buscar_documentos,
        )
    )
    registro.registrar(
        Ferramenta(
            nome="ler_pagina",
            descricao="Lê uma página inteira de um documento achado por buscar_documentos.",
            entrada=LerPaginaEntrada,
            executar=ler_pagina,
        )
    )
