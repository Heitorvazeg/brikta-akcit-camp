"""Configuração do serviço, lida de variáveis de ambiente (ver .env.sample)."""

from datetime import date
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ambiente: Literal["local", "test", "staging", "production"] = "local"
    log_nivel: str = "INFO"

    database_url: str = "postgresql+asyncpg://brikta_ia:brikta_ia@localhost:5432/brikta_ia"

    # Segurança entre serviços (Plano, Seção 10.1)
    ia_service_tokens: Annotated[list[SecretStr], NoDecode] = Field(default_factory=list)
    ia_callback_secret: SecretStr = SecretStr("")
    backend_base_url: str = "http://localhost:3000/api/v1"
    # Passe do Assistente, emitido pelo backend (POST /api/v1/assistente/sessao). Mesmo valor
    # nos dois .env. Vazio = rotas do Assistente recusam tudo.
    ia_ticket_secret: SecretStr = SecretStr("")
    storage_hosts_permitidos: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # Provedores (Plano, Seção 7)
    stt_provedor: str = "fake"
    stt_provedor_secundario: str = ""
    stt_modelo: str = ""
    llm_extracao_provedor: str = "fake"
    llm_extracao_modelo: str = ""

    # Assistente (IA-66, protótipo). Provedor compatível com a API da OpenAI (Groq e outros).
    llm_assistente_provedor: Literal["fake", "openai_compativel"] = "fake"
    llm_assistente_modelo: str = ""
    llm_assistente_base_url: str = ""
    llm_assistente_api_key: SecretStr = SecretStr("")
    # Só `mock` por enquanto: dados de exemplo (gerados do seed da demonstração). Real = BE-51.
    assistente_ferramentas: Literal["mock"] = "mock"
    #: Ferramentas simuladas além de RDOs, separadas por vírgula: documentos, bim, mcp.
    assistente_ferramentas_extras: str = "documentos,bim,mcp"
    # Laço próprio (protótipo) até a IA-64a escolher o framework.
    assistente_agente: Literal["laco_proprio"] = "laco_proprio"
    assistente_max_passos: int = Field(default=4, ge=1, le=8)
    # "Hoje" fixo (dados de exemplo gerados em `hoje_demonstracao`). Vazio = data local da obra.
    assistente_data_referencia: date | None = None

    # Limites (Plano, Seções 5.2 e 11.3)
    audio_max_seg: int = 600
    audio_max_bytes: int = 25 * 1024 * 1024
    limite_audios_empresa_dia: int = 50
    orcamento_empresa_mes_usd: float = 5.0

    @field_validator("assistente_data_referencia", mode="before")
    @classmethod
    def _data_vazia(cls, valor: object) -> object:
        return None if isinstance(valor, str) and not valor.strip() else valor

    @field_validator("ia_service_tokens", mode="before")
    @classmethod
    def _separar_tokens(cls, valor: object) -> object:
        if isinstance(valor, str):
            return [t.strip() for t in valor.split(",") if t.strip()]
        return valor

    @field_validator("ia_ticket_secret")
    @classmethod
    def _segredo_do_passe_forte(cls, valor: SecretStr) -> SecretStr:
        # Igual ao backend: nunca impede a IA de subir. Fraco não é usado (permitiria forjar
        # passes): vira vazio, e o Assistente fica desligado com aviso no log (main.py).
        bruto = valor.get_secret_value()
        if bruto and (len(bruto) < 32 or bruto.lower().startswith("troque")):
            return SecretStr("")
        return valor

    @field_validator("storage_hosts_permitidos", mode="before")
    @classmethod
    def _separar_hosts(cls, valor: object) -> object:
        if isinstance(valor, str):
            return [h.strip() for h in valor.split(",") if h.strip()]
        return valor


@lru_cache
def get_settings() -> Settings:
    return Settings()
