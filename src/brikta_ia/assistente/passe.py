"""Conferência do passe do Assistente, emitido pelo backend (`POST /api/v1/assistente/sessao`).

HS256 com `IA_TICKET_SECRET` (o mesmo valor nos dois serviços; nunca o `JWT_SECRET` do
login). Conferido em toda requisição, localmente, sem chamar o backend. Empresa, usuário,
perfil e obras visíveis vêm do passe e viram o `ContextoExecucao`; nunca do corpo da
requisição nem do modelo.
"""

from typing import Literal

import jwt
from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError

from brikta_ia.assistente.ferramentas.registro import ContextoExecucao
from brikta_ia.domain.assistente import ErroAssistenteCodigo

EMISSOR = "brikta-backend"
PUBLICO = "brikta-ia"


class ClaimsPasse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sub: str
    empresa_id: str
    role: Literal["GESTOR", "FISCAL", "OPERADOR"]
    obras: list[str]
    jti: str
    exp: int


class PasseInvalido(Exception):
    def __init__(self, codigo: ErroAssistenteCodigo, mensagem: str, motivo: str) -> None:
        super().__init__(mensagem)
        self.codigo = codigo
        self.mensagem = mensagem
        #: Para o log (nunca vai ao app): diz o que conferir.
        self.motivo = motivo


def conferir_passe(token: str, segredo: SecretStr) -> ContextoExecucao:
    chave = segredo.get_secret_value()
    if not chave:
        raise PasseInvalido(
            ErroAssistenteCodigo.NAO_AUTENTICADO, "Assistente não configurado", "sem_segredo"
        )
    try:
        bruto = jwt.decode(
            token,
            chave,
            algorithms=["HS256"],
            audience=PUBLICO,
            issuer=EMISSOR,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except jwt.ExpiredSignatureError as erro:
        raise PasseInvalido(
            ErroAssistenteCodigo.TOKEN_EXPIRADO, "Passe vencido", "vencido"
        ) from erro
    except jwt.InvalidSignatureError as erro:
        # Quase sempre: IA_TICKET_SECRET diferente entre backend e IA.
        raise PasseInvalido(
            ErroAssistenteCodigo.NAO_AUTENTICADO, "Passe inválido", "assinatura_nao_confere"
        ) from erro
    except jwt.InvalidTokenError as erro:
        raise PasseInvalido(
            ErroAssistenteCodigo.NAO_AUTENTICADO, "Passe inválido", type(erro).__name__
        ) from erro
    try:
        claims = ClaimsPasse.model_validate(bruto)
    except ValidationError as erro:
        raise PasseInvalido(
            ErroAssistenteCodigo.NAO_AUTENTICADO, "Passe incompleto", "claims_incompletos"
        ) from erro
    return ContextoExecucao(
        empresa_id=claims.empresa_id,
        usuario_id=claims.sub,
        role=claims.role,
        obras_visiveis=frozenset(claims.obras),
        jwt=SecretStr(token),
    )
