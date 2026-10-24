"""Assinatura HMAC-SHA256 dos callbacks para o backend (Plano, Seções 6.3 e 10.1).

Headers enviados:
    X-Brikta-Timestamp: <unix em segundos>
    X-Brikta-Signature: sha256=<hex(HMAC(segredo, f"{timestamp}.{corpo}"))>

O backend deve rejeitar assinatura inválida ou timestamp fora da janela (5 min).
A mesma função `verificar` serve de referência para a implementação no NestJS (BE-42).
"""

import hashlib
import hmac
import time

JANELA_PADRAO_SEG = 300
PREFIXO = "sha256="


def assinar(segredo: bytes, corpo: bytes, timestamp: int | None = None) -> dict[str, str]:
    ts = int(time.time()) if timestamp is None else timestamp
    mensagem = f"{ts}.".encode() + corpo
    assinatura = hmac.new(segredo, mensagem, hashlib.sha256).hexdigest()
    return {"X-Brikta-Timestamp": str(ts), "X-Brikta-Signature": PREFIXO + assinatura}


def verificar(
    segredo: bytes,
    corpo: bytes,
    timestamp: str,
    assinatura: str,
    *,
    agora: int | None = None,
    janela_seg: int = JANELA_PADRAO_SEG,
) -> bool:
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    referencia = int(time.time()) if agora is None else agora
    if abs(referencia - ts) > janela_seg:
        return False
    esperado = assinar(segredo, corpo, ts)["X-Brikta-Signature"]
    return hmac.compare_digest(esperado, assinatura)
