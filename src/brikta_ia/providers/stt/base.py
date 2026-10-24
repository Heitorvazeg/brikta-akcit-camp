"""Interface de voz → texto (Plano, Seção 7.1).

Toda implementação real (openai.py, deepgram.py, gemini.py…) fica neste pacote e
nunca é chamada diretamente fora de `providers/`. Nomes de modelo vêm da configuração.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class AudioNormalizado:
    caminho: Path
    duracao_seg: float
    content_type: str


@dataclass(frozen=True)
class Segmento:
    texto: str
    inicio_seg: float
    fim_seg: float
    confianca: float | None = None


@dataclass(frozen=True)
class Transcricao:
    texto: str
    segmentos: list[Segmento] = field(default_factory=list[Segmento])
    provedor: str = ""
    modelo: str = ""
    custo_usd: float = 0.0


class SpeechToText(Protocol):
    nome: str

    async def transcrever(
        self, audio: AudioNormalizado, dicas: list[str], idioma: str
    ) -> Transcricao: ...
