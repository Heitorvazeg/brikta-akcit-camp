"""Servidor MCP `brikta-dados` (ADR-11, IA-6M).

Exporá as ferramentas de `assistente.ferramentas.RegistroFerramentas` via Model Context
Protocol (SDK oficial em Python), autenticando cada sessão com o JWT do usuário e montando
o `ContextoExecucao` a partir dele, exatamente como a API do Assistente faz.
Nunca expor acesso direto ao banco (ADR-11, item 4).
"""
