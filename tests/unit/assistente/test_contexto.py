from datetime import date

from tests.unit.assistente.apoio import IPE, contexto

from brikta_ia.assistente.contexto import mensagem_de_sistema, periodos

TERCA = date(2026, 9, 29)


def test_periodos_calculados_em_codigo() -> None:
    p = periodos(TERCA)
    assert p["esta semana"] == (date(2026, 9, 28), TERCA)
    assert p["semana passada"] == (date(2026, 9, 21), date(2026, 9, 27))
    assert p["ontem"] == (date(2026, 9, 28), date(2026, 9, 28))
    assert p["mês passado"] == (date(2026, 8, 1), date(2026, 8, 31))


def test_periodos_na_virada_do_ano_e_no_domingo() -> None:
    p = periodos(date(2026, 1, 4))  # domingo
    assert p["esta semana"] == (date(2025, 12, 29), date(2026, 1, 4))
    assert p["mês passado"] == (date(2025, 12, 1), date(2025, 12, 31))


def test_mensagem_de_sistema_leva_hoje_periodos_e_obra_em_foco() -> None:
    texto = mensagem_de_sistema(
        contexto(), hoje=TERCA, nomes_das_obras={IPE: "Residencial Ipê"}, obra_foco=IPE
    )
    assert "2026-09-29 (terça-feira)" in texto
    assert "semana passada: 2026-09-21 a 2026-09-27" in texto
    assert f"{IPE}: Residencial Ipê" in texto
