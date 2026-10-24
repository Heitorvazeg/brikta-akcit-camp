from brikta_ia.integrations.assinatura import assinar, verificar

SEGREDO = b"segredo-de-teste"
CORPO = b'{"job_id":"123","status":"CONCLUIDO"}'


def test_assinatura_valida_e_verificavel() -> None:
    headers = assinar(SEGREDO, CORPO, timestamp=1_700_000_000)
    assert headers["X-Brikta-Signature"].startswith("sha256=")
    assert verificar(
        SEGREDO,
        CORPO,
        headers["X-Brikta-Timestamp"],
        headers["X-Brikta-Signature"],
        agora=1_700_000_100,
    )


def test_rejeita_corpo_alterado_segredo_errado_e_timestamp_velho() -> None:
    headers = assinar(SEGREDO, CORPO, timestamp=1_700_000_000)
    ts, sig = headers["X-Brikta-Timestamp"], headers["X-Brikta-Signature"]
    assert not verificar(SEGREDO, CORPO + b" ", ts, sig, agora=1_700_000_000)
    assert not verificar(b"outro", CORPO, ts, sig, agora=1_700_000_000)
    assert not verificar(SEGREDO, CORPO, ts, sig, agora=1_700_000_000 + 301)
    assert not verificar(SEGREDO, CORPO, "nao-numero", sig, agora=1_700_000_000)
