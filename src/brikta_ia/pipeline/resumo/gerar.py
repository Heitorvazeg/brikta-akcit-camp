"""Gera o Resumo IA a partir dos fatos do backend.

Divisão de trabalho (mesma regra do Assistente: número vem de código):
- código: base de RDOs, destaques, fontes, próximos passos e a marcação de números e de nomes
  de obra no texto;
- modelo (laço de ferramentas do Assistente): só o parágrafo e os alertas.
Sem modelo configurado (`fake`) o texto sai de um modelo de frase em código, para o fluxo
completo funcionar em desenvolvimento.
"""

import json
import re
import time
from datetime import UTC, datetime

from pydantic import SecretStr

from brikta_ia.assistente.agente.base import (
    Agente,
    CitacaoAgente,
    ErroAgente,
    FimAgente,
    TextoAgente,
)
from brikta_ia.assistente.contexto import PASTA_PROMPTS
from brikta_ia.assistente.ferramentas.execucao import ExecucaoFerramentas
from brikta_ia.assistente.ferramentas.registro import ContextoExecucao, RegistroFerramentas
from brikta_ia.domain.estados import StatusJob
from brikta_ia.domain.resumo import (
    Destaque,
    FonteRdo,
    MetadadosResumo,
    ObraFatos,
    OutraFonte,
    RdoFato,
    ResumoConteudo,
    ResumoJob,
    ResumoResultado,
    Trecho,
)
from brikta_ia.providers.llm.base import MensagemTurno

VERSAO_PROMPT = "resumo/v1"
MAX_FONTES = 3
MAX_PROXIMOS = 3
GRAVIDADES_ALTAS = {"ALTA"}
_DATA = re.compile(r"\d{1,2}/\d{1,2}")
_NUMERO = re.compile(r"\d+(?:[.,]\d+)?(?:\s?(?:%|pessoas|m²|m³|kg|h)\b|%)?")


class ResumoInvalido(Exception):
    """A resposta do modelo não seguiu o formato (TEXTO / ALERTAS)."""


def _ddmm(d: object) -> str:
    iso = str(d)
    return f"{iso[8:10]}/{iso[5:7]}"


def periodo_legivel(job: ResumoJob) -> str:
    return f"{_ddmm(job.periodo_inicio)} a {_ddmm(job.periodo_fim)}"


# ── Pedaços calculados em código ──────────────────────────────────────────


def _rdos(job: ResumoJob) -> list[tuple[ObraFatos, RdoFato]]:
    return [(o, r) for o in job.obras for r in o.rdos]


def calcular_destaques(job: ResumoJob) -> list[Destaque]:
    rdos = [r for _, r in _rdos(job)]
    ocorrencias = sum(len(r.ocorrencias) for r in rdos)
    if job.escopo == "obra":
        obra = job.obras[0]
        media = round(sum(r.pessoas for r in rdos) / len(rdos)) if rdos else 0
        return [
            Destaque(
                icone="trending-up-outline",
                rotulo="Andamento",
                valor=f"{obra.progresso_percentual or 0}%",
            ),
            Destaque(icone="people-outline", rotulo="Equipe média", valor=str(media)),
            Destaque(icone="warning-outline", rotulo="Ocorrências", valor=str(ocorrencias)),
        ]
    return [
        Destaque(icone="business-outline", rotulo="Obras em execução", valor=str(len(job.obras))),
        Destaque(icone="document-text-outline", rotulo="RDOs no período", valor=str(len(rdos))),
        Destaque(icone="warning-outline", rotulo="Ocorrências", valor=str(ocorrencias)),
    ]


def calcular_fontes(job: ResumoJob) -> list[FonteRdo]:
    """Último RDO de cada obra (geral) ou os três mais recentes (obra)."""
    if job.escopo == "obra":
        recentes = sorted(job.obras[0].rdos, key=lambda r: r.data, reverse=True)[:MAX_FONTES]
        return [
            FonteRdo(rotulo=f"RDO nº {r.numero or '—'} · {_ddmm(r.data)}", rdo_id=r.rdo_id)
            for r in recentes
        ]
    fontes: list[FonteRdo] = []
    for obra in job.obras:
        if obra.rdos:
            r = max(obra.rdos, key=lambda x: x.data)
            fontes.append(
                FonteRdo(
                    rotulo=f"{obra.nome} · RDO nº {r.numero or '—'} · {_ddmm(r.data)}",
                    rdo_id=r.rdo_id,
                )
            )
    return fontes


def calcular_proximos(job: ResumoJob) -> list[list[Trecho]]:
    """Próximas atividades do RDO mais recente de cada obra (sem repetir)."""
    saida: list[list[Trecho]] = []
    vistos: set[str] = set()
    for obra in job.obras:
        if not obra.rdos:
            continue
        ultimo = max(obra.rdos, key=lambda r: r.data)
        for texto in ultimo.proximas_atividades:
            if texto in vistos:
                continue
            vistos.add(texto)
            prefixo = [Trecho(t=f"{obra.nome} · ", s="b")] if job.escopo == "geral" else []
            saida.append([*prefixo, Trecho(t=texto)])
    return saida[:MAX_PROXIMOS]


def _alertas_de_codigo(job: ResumoJob) -> list[str]:
    """Alertas objetivos dos fatos; usados no modo sem modelo."""
    alertas: list[str] = []
    for obra, r in _rdos(job):
        for o in r.ocorrencias:
            if o.impacto_cronograma or (o.gravidade in GRAVIDADES_ALTAS):
                alertas.append(f"{obra.nome} · {o.tipo.lower()} em {_ddmm(r.data)}: {o.descricao}")
        for e in r.equipamentos_com_defeito:
            alertas.append(f"{obra.nome} · {e} com defeito em {_ddmm(r.data)}.")
        for m in r.materiais_em_falta:
            alertas.append(f"{obra.nome} · falta de {m} em {_ddmm(r.data)}.")
    return alertas[:4]


# ── Marcação do texto ────────────────────────────────────────────────────


def para_texto_rico(texto: str, nomes_obras: list[str]) -> list[Trecho]:
    """Nomes de obra em negrito e números em destaque; o resto como veio."""
    nomes = sorted({n for n in nomes_obras if n}, key=len, reverse=True)
    padrao = re.compile("|".join([*(re.escape(n) for n in nomes), _DATA.pattern, _NUMERO.pattern]))
    trechos: list[Trecho] = []
    posicao = 0
    for m in padrao.finditer(texto):
        if m.start() > posicao:
            trechos.append(Trecho(t=texto[posicao : m.start()]))
        achado = m.group(0)
        estilo = "b" if achado in nomes else None if _DATA.fullmatch(achado) else "num"
        trechos.append(Trecho(t=achado, s=estilo))
        posicao = m.end()
    if posicao < len(texto):
        trechos.append(Trecho(t=texto[posicao:]))
    return trechos or [Trecho(t=texto)]


# ── Resposta do modelo ───────────────────────────────────────────────────


def interpretar_resposta(texto: str) -> tuple[str, list[str]]:
    achado = re.search(r"TEXTO:\s*(.+?)\s*(?:\n\s*ALERTAS:|\Z)", texto, re.S)
    if not achado or not achado.group(1).strip():
        raise ResumoInvalido("Resposta sem a seção TEXTO")
    corpo = achado.group(1).strip()
    parte = re.search(r"ALERTAS:\s*(.*)\Z", texto, re.S)
    alertas = (
        [
            re.sub(r"^[-•*]\s*", "", linha.strip())
            for linha in parte.group(1).splitlines()
            if linha.strip()
        ]
        if parte
        else []
    )
    return corpo, [a for a in alertas if a]


def _texto_de_codigo(job: ResumoJob) -> tuple[str, list[str]]:
    rdos = _rdos(job)
    ocorrencias = sum(len(r.ocorrencias) for _, r in rdos)
    if job.escopo == "obra":
        obra = job.obras[0]
        base = f"{obra.nome}: {len(rdos)} RDOs entre {periodo_legivel(job)}"
    else:
        base = f"{len(job.obras)} obras em execução, {len(rdos)} RDOs entre {periodo_legivel(job)}"
    final = (
        f", com {ocorrencias} ocorrências registradas."
        if ocorrencias
        else ", sem ocorrências registradas."
    )
    return base + final, _alertas_de_codigo(job)


def montar_prompt(job: ResumoJob) -> str:
    fatos = json.dumps(
        [o.model_dump(mode="json") for o in job.obras], ensure_ascii=False, separators=(",", ":")
    )
    modelo = (PASTA_PROMPTS / VERSAO_PROMPT / "sistema.md").read_text(encoding="utf-8")
    return modelo.format(
        escopo="geral semanal (todas as obras, sobre a semana anterior)"
        if job.escopo == "geral"
        else f"obra {job.obras[0].nome} (últimos dias)",
        periodo=periodo_legivel(job),
        hoje=job.data_referencia.isoformat(),
        fatos=fatos,
    )


async def _perguntar(
    agente: Agente, registro: RegistroFerramentas, job: ResumoJob
) -> tuple[str, list[OutraFonte], FimAgente]:
    contexto = ContextoExecucao(
        empresa_id=job.empresa_id,
        usuario_id="sistema:resumo-ia",
        role="GESTOR",
        obras_visiveis=frozenset(o.obra_id for o in job.obras),
        jwt=SecretStr(""),
    )
    execucao = ExecucaoFerramentas(registro, contexto)
    mensagens = [
        MensagemTurno("system", montar_prompt(job)),
        MensagemTurno("user", "Escreva o resumo."),
    ]
    texto = ""
    fim: FimAgente | None = None
    fontes: list[OutraFonte] = []
    async for evento in agente.responder(mensagens, execucao):
        if isinstance(evento, TextoAgente):
            texto += evento.texto
        elif isinstance(evento, CitacaoAgente) and evento.tipo in ("DOCUMENTO", "BIM", "EXTERNO"):
            fontes.append(OutraFonte(tipo=evento.tipo, rotulo=evento.rotulo))
        elif isinstance(evento, FimAgente):
            fim = evento
    if fim is None:
        raise ResumoInvalido("O agente terminou sem resposta")
    return texto, fontes, fim


async def gerar_resumo(
    job: ResumoJob,
    job_id: str,
    *,
    agente: Agente | None,
    registro: RegistroFerramentas,
    modelo: str,
    agora: datetime | None = None,
) -> ResumoResultado:
    """`agente=None` = sem modelo: texto de código. Nunca levanta: falha vira `FALHOU`."""
    inicio = time.monotonic()
    nomes = [o.nome for o in job.obras]
    meta = MetadadosResumo(versao_prompt=VERSAO_PROMPT, modelo=modelo)
    base = {
        "job_id": job_id,
        "empresa_id": job.empresa_id,
        "escopo": job.escopo,
        "obra_id": job.obra_id,
        "data_referencia": job.data_referencia,
    }
    try:
        outras: list[OutraFonte] = []
        if agente is None:
            texto, alertas = _texto_de_codigo(job)
        else:
            bruto, outras, fim = await _perguntar(agente, registro, job)
            texto, alertas = interpretar_resposta(bruto)
            meta = meta.model_copy(
                update={
                    "passos": fim.passos,
                    "tokens_entrada": fim.tokens_entrada,
                    "tokens_saida": fim.tokens_saida,
                }
            )
    except (ResumoInvalido, ErroAgente) as erro:
        mensagem = erro.mensagem if isinstance(erro, ErroAgente) else str(erro)
        meta = meta.model_copy(update={"latencia_ms": int((time.monotonic() - inicio) * 1000)})
        return ResumoResultado(
            **base, status=StatusJob.FALHOU, erro_mensagem=mensagem, metadados=meta
        )

    rdos = _rdos(job)
    conteudo = ResumoConteudo(
        periodo=periodo_legivel(job),
        base_rdos=len(rdos),
        gerado_em=agora or datetime.now(UTC),
        texto=para_texto_rico(texto, nomes),
        destaques=calcular_destaques(job),
        alertas=[para_texto_rico(a, nomes) for a in alertas],
        proximos=calcular_proximos(job),
        fontes=calcular_fontes(job),
        outras_fontes=list({(f.tipo, f.rotulo): f for f in outras}.values()),
    )
    meta = meta.model_copy(update={"latencia_ms": int((time.monotonic() - inicio) * 1000)})
    return ResumoResultado(**base, status=StatusJob.CONCLUIDO, resumo=conteudo, metadados=meta)
