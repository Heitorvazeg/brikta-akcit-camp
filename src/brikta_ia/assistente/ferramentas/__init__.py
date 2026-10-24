"""Ferramentas do Assistente de Obra (Plano, 9.2).

Cada ferramenta real (IA-64, IA-71, IA-73, IA-74) é um módulo neste pacote que declara uma
`Ferramenta` e é registrada no `RegistroFerramentas`. Ex. previstos:
    dados_obra.py   listar_rdos, resumo_efetivo, consumo_materiais… (backend, JWT repassado)
    busca.py        buscar_nos_rdos, buscar_documentos (índice próprio, filtro no SQL)
    documentos.py   ler_pagina, consultar_planilha
    bim.py          consultar_modelo_bim
    externos.py     clientes MCP permitidos (clima, Drive)
"""

from brikta_ia.assistente.ferramentas.registro import (
    AcessoNegado,
    Citacao,
    ContextoExecucao,
    ErroFerramenta,
    Ferramenta,
    RegistroFerramentas,
    ResultadoFerramenta,
)

__all__ = [
    "AcessoNegado",
    "Citacao",
    "ContextoExecucao",
    "ErroFerramenta",
    "Ferramenta",
    "RegistroFerramentas",
    "ResultadoFerramenta",
]
