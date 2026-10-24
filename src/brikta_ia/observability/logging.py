"""Logs estruturados em JSON.

Regra (Plano, Seção 10.3): NUNCA logar transcrição, conteúdo de áudio ou texto de documentos.
Logue apenas IDs (job_id, empresa_id, gravacao_id), etapas, durações e códigos de erro.
"""

import logging

import structlog


def configurar_logging(nivel: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", level=nivel.upper())
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(nivel.upper())),
        cache_logger_on_first_use=True,
    )


def get_logger(nome: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(nome)
