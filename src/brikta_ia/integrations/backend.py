"""Callback assinado da IA para o backend (`POST {BACKEND_BASE_URL}/internal/ia/callback`).

Assinatura HMAC (`assinatura.py`, segredo `IA_CALLBACK_SECRET`); o backend rejeita assinatura
inválida, timestamp fora da janela e `job_id` repetido (idempotência). Falha de rede tem
poucas tentativas com espera crescente; esgotadas, o erro é registrado e o job fica sem
entrega (o backend repete no próximo ciclo do job diário).
"""

import asyncio

import httpx
from pydantic import BaseModel

from brikta_ia.config import Settings
from brikta_ia.integrations.assinatura import assinar
from brikta_ia.observability.logging import get_logger

TENTATIVAS = 3
ESPERA_BASE_SEG = 2.0
log = get_logger(__name__)


async def enviar_callback(
    settings: Settings, resultado: BaseModel, *, cliente: httpx.AsyncClient | None = None
) -> bool:
    segredo = settings.ia_callback_secret.get_secret_value()
    if not segredo:
        log.warning("callback.sem_segredo", motivo="IA_CALLBACK_SECRET vazio")
        return False
    corpo = resultado.model_dump_json().encode()
    cabecalhos = {
        "Content-Type": "application/json",
        **assinar(segredo.encode(), corpo),
    }
    url = f"{settings.backend_base_url.rstrip('/')}/internal/ia/callback"
    proprio = cliente is None
    http = cliente or httpx.AsyncClient(timeout=10)
    try:
        for tentativa in range(1, TENTATIVAS + 1):
            try:
                r = await http.post(url, content=corpo, headers=cabecalhos)
                if r.is_success:
                    return True
                log.warning("callback.recusado", status=r.status_code, tentativa=tentativa)
                if r.status_code < 500:
                    return False  # 4xx não melhora repetindo
            except httpx.HTTPError as erro:
                log.warning("callback.rede", erro=type(erro).__name__, tentativa=tentativa)
            if tentativa < TENTATIVAS:
                await asyncio.sleep(ESPERA_BASE_SEG * tentativa)
        return False
    finally:
        if proprio:
            await http.aclose()
