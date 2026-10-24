"""STT falso para testes e desenvolvimento sem chave de API.

Devolve o texto configurado; se não houver, procura um `.txt` com o mesmo nome do áudio.
"""

from brikta_ia.providers.stt.base import AudioNormalizado, Segmento, Transcricao


class FakeSpeechToText:
    nome = "fake"

    def __init__(self, texto_fixo: str | None = None) -> None:
        self._texto_fixo = texto_fixo

    async def transcrever(
        self, audio: AudioNormalizado, dicas: list[str], idioma: str
    ) -> Transcricao:
        texto = self._texto_fixo
        if texto is None:
            fixture = audio.caminho.with_suffix(".txt")
            texto = fixture.read_text(encoding="utf-8") if fixture.exists() else ""
        return Transcricao(
            texto=texto,
            segmentos=[
                Segmento(texto=texto, inicio_seg=0.0, fim_seg=audio.duracao_seg, confianca=1.0)
            ],
            provedor="fake",
            modelo="fake",
        )
