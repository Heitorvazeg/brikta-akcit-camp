"""Registro de ferramentas do Assistente — independente de framework (ADR-07, ADR-11).

O mesmo registro alimenta:
- o adaptador do framework de agentes (`assistente/agente/`, escolhido na IA-64a);
- o servidor MCP `brikta-dados` (`servidor_mcp/`, IA-6M).

Garantias aplicadas AQUI (e não no framework nem no prompt):
- argumentos validados por Pydantic antes de executar;
- `ContextoExecucao` (empresa, usuário, obras visíveis, JWT) injetado pelo registro —
  o modelo nunca escolhe nem vê esses valores;
- qualquer argumento `obra_id` / `obra_ids` precisa estar entre as obras visíveis;
- timeout por ferramenta.
"""

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from brikta_ia.domain.assistente import TipoCitacao


@dataclass(frozen=True)
class ContextoExecucao:
    """Montado a partir do JWT validado. Nunca vem do modelo."""

    empresa_id: str
    usuario_id: str
    role: Literal["GESTOR", "FISCAL", "OPERADOR", "VIEWER"]
    obras_visiveis: frozenset[str]
    jwt: SecretStr = field(repr=False)


class Citacao(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo: TipoCitacao
    id: str
    referencia: str | None = Field(default=None, description="Data do RDO, página do documento…")
    trecho: str | None = None


class ResultadoFerramenta(BaseModel):
    dados: Any
    citacoes: list[Citacao] = Field(default_factory=list)


class ErroFerramenta(Exception):
    """Erro devolvido ao agente como resultado (ele pode tentar outra abordagem)."""


class AcessoNegado(ErroFerramenta):
    """Tentativa de acessar obra/recurso fora do contexto do usuário."""


Executor = Callable[[Any, ContextoExecucao], Awaitable[ResultadoFerramenta]]

CAMPOS_DE_OBRA = ("obra_id", "obra_ids")


@dataclass(frozen=True)
class Ferramenta:
    nome: str
    descricao: str
    entrada: type[BaseModel]
    executar: Executor
    somente_leitura: bool = True
    timeout_seg: float = 15.0
    #: Só o servidor chama (monta o contexto); o modelo não a vê nem consegue pedir.
    interna: bool = False


class RegistroFerramentas:
    def __init__(self) -> None:
        self._ferramentas: dict[str, Ferramenta] = {}

    def registrar(self, ferramenta: Ferramenta) -> None:
        if ferramenta.nome in self._ferramentas:
            raise ValueError(f"Ferramenta já registrada: {ferramenta.nome}")
        if not ferramenta.somente_leitura:
            # ADR-11: nenhuma ferramenta de escrita no Assistente. Mudar isso exige novo ADR.
            raise ValueError(f"Ferramentas de escrita não são permitidas: {ferramenta.nome}")
        self._ferramentas[ferramenta.nome] = ferramenta

    def nomes(self) -> list[str]:
        return sorted(self._ferramentas)

    def nomes_para_modelo(self) -> list[str]:
        return sorted(n for n, f in self._ferramentas.items() if not f.interna)

    def schemas_para_modelo(self) -> list[dict[str, Any]]:
        """Formato neutro (nome, descrição, JSON Schema) — cada adaptador converte para o seu."""
        return [
            {
                "nome": f.nome,
                "descricao": f.descricao,
                "parametros": _sem_titulos(f.entrada.model_json_schema()),
            }
            for f in sorted(self._ferramentas.values(), key=lambda f: f.nome)
            if not f.interna
        ]

    async def executar(
        self,
        nome: str,
        argumentos: Mapping[str, Any],
        contexto: ContextoExecucao,
        *,
        interna: bool = False,
    ) -> ResultadoFerramenta:
        ferramenta = self._ferramentas.get(nome)
        if ferramenta is None or (ferramenta.interna and not interna):
            raise ErroFerramenta(f"Ferramenta desconhecida: {nome}")

        try:
            entrada = ferramenta.entrada.model_validate(dict(argumentos))
        except ValidationError as erro:
            raise ErroFerramenta(f"Argumentos inválidos para {nome}: {erro}") from erro

        _garantir_obras_visiveis(entrada, contexto)

        try:
            async with asyncio.timeout(ferramenta.timeout_seg):
                return await ferramenta.executar(entrada, contexto)
        except TimeoutError as erro:
            raise ErroFerramenta(f"Tempo esgotado em {nome}") from erro


def _garantir_obras_visiveis(entrada: BaseModel, contexto: ContextoExecucao) -> None:
    for campo in CAMPOS_DE_OBRA:
        valor = getattr(entrada, campo, None)
        if valor is None:
            continue
        pedidas = {valor} if isinstance(valor, str) else set(valor)
        if not pedidas <= contexto.obras_visiveis:
            raise AcessoNegado("Obra não encontrada ou sem permissão")


def _sem_titulos(schema: Any) -> Any:
    """Tira os `title` que o Pydantic gera (repetem o nome do campo): cada passo do agente reenvia
    o schema de todas as ferramentas, e o provedor limita tokens por minuto."""
    if isinstance(schema, dict):
        return {
            k: _sem_titulos(v) for k, v in schema.items() if k != "title" or not isinstance(v, str)
        }
    if isinstance(schema, list):
        return [_sem_titulos(v) for v in schema]
    return schema
