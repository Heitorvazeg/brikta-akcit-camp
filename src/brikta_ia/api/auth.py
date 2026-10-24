"""Autenticação das rotas chamadas pelo backend (token de serviço).

O backend envia `Authorization: Bearer <IA_SERVICE_TOKEN>`. Aceitamos mais de um token
para permitir rotação sem downtime (Plano, Seção 10.1).
O JWT do Supabase (rotas do Assistente) entra na IA-F6.
"""

import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from brikta_ia.config import Settings, get_settings


def verificar_token_servico(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token de serviço ausente")
    recebido = authorization.removeprefix("Bearer ").strip().encode()
    validos = [t.get_secret_value().encode() for t in settings.ia_service_tokens]
    if not any(hmac.compare_digest(recebido, v) for v in validos if v):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token de serviço inválido")


TokenServico = Depends(verificar_token_servico)
