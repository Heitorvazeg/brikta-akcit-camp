"""Códigos de erro devolvidos ao backend (Plano, Seção 5.7)."""

from enum import StrEnum


class ErroCodigo(StrEnum):
    AUDIO_INVALIDO = "AUDIO_INVALIDO"
    AUDIO_LONGO = "AUDIO_LONGO"
    AUDIO_SEM_FALA = "AUDIO_SEM_FALA"
    STT_INDISPONIVEL = "STT_INDISPONIVEL"
    EXTRACAO_FALHOU = "EXTRACAO_FALHOU"
    LIMITE_EXCEDIDO = "LIMITE_EXCEDIDO"
    ERRO_INTERNO = "ERRO_INTERNO"


class ErroPipeline(Exception):
    """Falha esperada do pipeline, com código estável para o app."""

    def __init__(self, codigo: ErroCodigo, detalhe: str = "") -> None:
        super().__init__(f"{codigo}: {detalhe}" if detalhe else codigo.value)
        self.codigo = codigo
        self.detalhe = detalhe
