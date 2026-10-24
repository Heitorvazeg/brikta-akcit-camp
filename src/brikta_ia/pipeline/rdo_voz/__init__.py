"""Pipeline do RDO por voz (Plano, Seção 5).

Etapas previstas, cada uma num módulo:
    baixar.py         IA-33  URL pré-assinada → arquivo temporário (anti-SSRF, limites, checksum)
    normalizar.py     IA-11  ffprobe/ffmpeg → mono 16 kHz, detecção de áudio sem fala
    transcrever.py    IA-12  SpeechToText + dicas do glossário
    pos_processar.py  IA-14  dicionário de correção, números e unidades
    extrair.py        IA-21  LLMEstruturado → RdoProposto
    validar.py        IA-24  catálogo, evidência, campos_incertos (IA-25)
    orquestrador.py   IA-33  estados (domain/estados.py), timeouts, retentativas
"""
