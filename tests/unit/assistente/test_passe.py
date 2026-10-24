import jwt
import pytest
from pydantic import SecretStr
from tests.unit.assistente.apoio import IPE, SEGREDO, passe

from brikta_ia.assistente.passe import PasseInvalido, conferir_passe
from brikta_ia.domain.assistente import ErroAssistenteCodigo

CHAVE = SecretStr(SEGREDO)


def test_passe_valido_vira_contexto_com_as_obras_do_passe() -> None:
    ctx = conferir_passe(passe(obras=[IPE], role="GESTOR"), CHAVE)
    assert ctx.usuario_id == "usuario-1"
    assert ctx.empresa_id == "empresa-1"
    assert ctx.role == "GESTOR"
    assert ctx.obras_visiveis == frozenset({IPE})


def test_passe_vencido_e_token_expirado() -> None:
    with pytest.raises(PasseInvalido) as erro:
        conferir_passe(passe(validade_seg=-10), CHAVE)
    assert erro.value.codigo == ErroAssistenteCodigo.TOKEN_EXPIRADO


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(passe(segredo="outra-chave-qualquer-com-32-caracteres!!"), id="outra chave"),
        pytest.param(passe(aud="brikta"), id="aud do login do backend"),
        pytest.param(passe(iss="outro-emissor"), id="outro emissor"),
        pytest.param(
            jwt.encode({"sub": "x", "aud": "brikta-ia", "iss": "brikta-backend"}, None, "none"),
            id="alg none",
        ),
        pytest.param("nao-e-jwt", id="lixo"),
    ],
)
def test_passe_recusado_e_nao_autenticado(token: str) -> None:
    with pytest.raises(PasseInvalido) as erro:
        conferir_passe(token, CHAVE)
    assert erro.value.codigo == ErroAssistenteCodigo.NAO_AUTENTICADO


def test_passe_sem_claims_obrigatorios_e_recusado() -> None:
    token = passe()
    bruto = jwt.decode(token, SEGREDO, algorithms=["HS256"], audience="brikta-ia")
    del bruto["obras"]
    with pytest.raises(PasseInvalido):
        conferir_passe(jwt.encode(bruto, SEGREDO, algorithm="HS256"), CHAVE)


def test_sem_segredo_configurado_recusa_tudo() -> None:
    with pytest.raises(PasseInvalido):
        conferir_passe(passe(), SecretStr(""))


def test_assinatura_que_nao_confere_aponta_o_segredo_no_motivo() -> None:
    with pytest.raises(PasseInvalido) as erro:
        conferir_passe(passe(segredo="outra-chave-qualquer-com-32-caracteres!!"), CHAVE)
    assert erro.value.motivo == "assinatura_nao_confere"


def test_segredo_fraco_nao_impede_de_subir_mas_desliga_o_assistente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from brikta_ia.config import Settings

    for fraco in ("curto", "troque-" + "x" * 40):
        monkeypatch.setenv("IA_TICKET_SECRET", fraco)
        assert Settings().ia_ticket_secret.get_secret_value() == ""
    monkeypatch.setenv("IA_TICKET_SECRET", SEGREDO)
    assert Settings().ia_ticket_secret.get_secret_value() == SEGREDO
