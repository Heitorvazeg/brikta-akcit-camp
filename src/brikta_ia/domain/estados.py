"""Estados do job de RDO por voz (Plano, Seção 5.1)."""

from enum import StrEnum


class StatusJob(StrEnum):
    RECEBIDO = "RECEBIDO"
    BAIXANDO = "BAIXANDO"
    NORMALIZANDO = "NORMALIZANDO"
    TRANSCREVENDO = "TRANSCREVENDO"
    EXTRAINDO = "EXTRAINDO"
    VALIDANDO = "VALIDANDO"
    ENTREGANDO = "ENTREGANDO"
    CONCLUIDO = "CONCLUIDO"
    CONCLUIDO_PARCIAL = "CONCLUIDO_PARCIAL"  # transcrição ok, extração falhou
    FALHOU = "FALHOU"

    @property
    def terminal(self) -> bool:
        return self in _TERMINAIS


_TERMINAIS = frozenset({StatusJob.CONCLUIDO, StatusJob.CONCLUIDO_PARCIAL, StatusJob.FALHOU})

# Ordem das etapas do pipeline; transições só avançam (ou vão para um estado terminal).
ORDEM_ETAPAS: tuple[StatusJob, ...] = (
    StatusJob.RECEBIDO,
    StatusJob.BAIXANDO,
    StatusJob.NORMALIZANDO,
    StatusJob.TRANSCREVENDO,
    StatusJob.EXTRAINDO,
    StatusJob.VALIDANDO,
    StatusJob.ENTREGANDO,
    StatusJob.CONCLUIDO,
)


def transicao_valida(atual: StatusJob, proximo: StatusJob) -> bool:
    """Regra de transição: nunca sai de estado terminal; avança uma etapa ou termina.

    CONCLUIDO_PARCIAL só a partir de EXTRAINDO/VALIDANDO (já existe transcrição).
    """
    if atual.terminal:
        return False
    if proximo is StatusJob.FALHOU:
        return True
    if proximo is StatusJob.CONCLUIDO_PARCIAL:
        return atual in (StatusJob.EXTRAINDO, StatusJob.VALIDANDO)
    if proximo not in ORDEM_ETAPAS:
        return False
    return ORDEM_ETAPAS.index(proximo) == ORDEM_ETAPAS.index(atual) + 1
