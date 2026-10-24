from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from brikta_ia.api.auth import verificar_token_servico
from brikta_ia.config import Settings, get_settings
from brikta_ia.main import criar_app


def test_health_responde_ok() -> None:
    cliente = TestClient(criar_app())
    resposta = cliente.get("/health")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ok"


def _app_protegido(tokens: list[str]) -> TestClient:
    app = FastAPI()

    @app.get("/protegido", dependencies=[Depends(verificar_token_servico)])
    def protegido() -> dict[str, bool]:
        return {"ok": True}

    app.dependency_overrides[get_settings] = lambda: Settings(
        ia_service_tokens=[SecretStr(t) for t in tokens]
    )
    return TestClient(app)


def test_token_de_servico_valido_e_rotacao() -> None:
    cliente = _app_protegido(["token-atual", "token-anterior"])
    for token in ("token-atual", "token-anterior"):
        resposta = cliente.get("/protegido", headers={"Authorization": f"Bearer {token}"})
        assert resposta.status_code == 200


def test_token_de_servico_ausente_ou_invalido() -> None:
    cliente = _app_protegido(["token-atual"])
    assert cliente.get("/protegido").status_code == 401
    resposta = cliente.get("/protegido", headers={"Authorization": "Bearer errado"})
    assert resposta.status_code == 401


def test_sem_tokens_configurados_rejeita_tudo() -> None:
    cliente = _app_protegido([])
    resposta = cliente.get("/protegido", headers={"Authorization": "Bearer "})
    assert resposta.status_code == 401


def test_settings_separa_listas_de_variaveis_de_ambiente(monkeypatch) -> None:
    monkeypatch.setenv("IA_SERVICE_TOKENS", "a, b ,")
    monkeypatch.setenv("STORAGE_HOSTS_PERMITIDOS", "s3.exemplo.com,cdn.exemplo.com")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert [t.get_secret_value() for t in settings.ia_service_tokens] == ["a", "b"]
    assert settings.storage_hosts_permitidos == ["s3.exemplo.com", "cdn.exemplo.com"]


def test_data_de_referencia_vazia_vale_como_sem_data() -> None:
    settings = Settings(assistente_data_referencia="")  # type: ignore[call-arg,arg-type]
    assert settings.assistente_data_referencia is None
