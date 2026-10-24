"""Interface de embeddings (Assistente de Obra, IA-F6). Modelo escolhido na IA-63."""

from typing import Protocol


class Embeddings(Protocol):
    nome: str
    modelo: str
    dimensao: int

    async def embed(self, textos: list[str]) -> list[list[float]]: ...
