"""Apoio dos testes do Assistente: passes assinados como o backend assina."""

import time
import uuid
from typing import Any

import jwt
from pydantic import SecretStr

from brikta_ia.assistente.ferramentas.registro import ContextoExecucao

SEGREDO = "segredo-do-passe-de-teste-com-32-caracteres-ou-mais"
IPE = "de300000-0000-4000-8000-0000000000a1"
AURORA = "de300000-0000-4000-8000-0000000000a2"
RECANTO = "de300000-0000-4000-8000-0000000000a3"


def passe(
    *,
    sub: str = "usuario-1",
    empresa_id: str = "empresa-1",
    role: str = "OPERADOR",
    obras: list[str] | None = None,
    validade_seg: int = 1800,
    segredo: str = SEGREDO,
    **extra: Any,
) -> str:
    agora = int(time.time())
    claims: dict[str, Any] = {
        "iss": "brikta-backend",
        "aud": "brikta-ia",
        "sub": sub,
        "jti": uuid.uuid4().hex,
        "iat": agora,
        "exp": agora + validade_seg,
        "empresa_id": empresa_id,
        "role": role,
        "obras": [IPE, RECANTO] if obras is None else obras,
        **extra,
    }
    return jwt.encode(claims, segredo, algorithm="HS256")


def contexto(obras: frozenset[str] = frozenset({IPE, RECANTO})) -> ContextoExecucao:
    return ContextoExecucao(
        empresa_id="empresa-1",
        usuario_id="usuario-1",
        role="OPERADOR",
        obras_visiveis=obras,
        jwt=SecretStr("passe"),
    )
