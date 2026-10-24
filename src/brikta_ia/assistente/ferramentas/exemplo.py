"""Ferramentas de EXEMPLO do Assistente (protótipo, `ASSISTENTE_FERRAMENTAS=mock`).

Os dados são os do seed da demonstração do backend (`exemplo/dados.json`, gerado por
`scripts/gerar_dados_do_seed.py`). O id do RDO é o `rdo_local_id` do seed, que o app usa como
id local: a citação abre o RDO certo.
Quando a BE-51 existir, as mesmas ferramentas passam a chamar o backend com o mesmo
contrato de entrada e saída.

Números (totais, médias, pico) são calculados aqui, nunca pelo modelo.
"""

import json
from collections import Counter
from datetime import date, timedelta
from functools import cache
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from brikta_ia.assistente.ferramentas.registro import (
    Citacao,
    ContextoExecucao,
    Ferramenta,
    RegistroFerramentas,
    ResultadoFerramenta,
)

DADOS = Path(__file__).parent / "exemplo" / "dados.json"
PERIODO_MAXIMO_DIAS = 31
# Até este período o RDO vem completo (equipe por função, equipamentos, materiais…);
# acima disso só atividades e ocorrências, para caber no limite de tokens do modelo.
PERIODO_DETALHADO_DIAS = 7
DIAS = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")


@cache
def dados_exemplo() -> dict[str, Any]:
    return json.loads(DADOS.read_text(encoding="utf-8"))


class ListarObrasEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConsultarRdosEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    obra_id: str = Field(description="Id da obra (da lista de obras do contexto).")
    data_inicio: date = Field(description="Primeiro dia do período (AAAA-MM-DD).")
    data_fim: date = Field(description="Último dia do período, inclusive (AAAA-MM-DD).")

    @model_validator(mode="after")
    def _periodo_valido(self) -> Self:
        if self.data_fim < self.data_inicio:
            raise ValueError("data_fim antes de data_inicio")
        if (self.data_fim - self.data_inicio).days >= PERIODO_MAXIMO_DIAS:
            raise ValueError(f"período maior que {PERIODO_MAXIMO_DIAS} dias: divida a consulta")
        return self


def _rotulo(d: str) -> str:
    return f"RDO {d[8:10]}/{d[5:7]}"


def _servico(a: dict[str, Any]) -> str:
    local = f"{a['local']}: " if a.get("local") else ""
    pct = f", {a['progresso']}%" if a.get("progresso") is not None else ""
    return f"{local}{a['descricao']} ({a['status']}{pct})"


def _ocorrencia(o: dict[str, Any]) -> str:
    atraso = ", atrasa o cronograma" if o["impacto_cronograma"] else ""
    return f"{o['tipo']} ({o['gravidade']}{atraso}): {o['descricao']}"


def _item(r: dict[str, Any], chuva: dict[str, Any], detalhado: bool) -> dict[str, Any]:
    """Um RDO em texto curto (cada linha custa tokens): o modelo lê, não recalcula."""
    item: dict[str, Any] = {
        "rdo_id": r["id"],
        "data": r["data"],
        "dia_da_semana": DIAS[date.fromisoformat(r["data"]).weekday()],
        "numero": r["numero"],
        "autor": r["autor"],
        "situacao": "VALIDADO" if r["status"] == "APROVADO" else f"RASCUNHO ({r['status']})",
        "pessoas": r["equipe"],
        "fotos": r["fotos"],
        "clima": chuva.get(r["data"], "sem chuva registrada"),
        "servicos_executados": [_servico(a) for a in r["atividades"]],
        "ocorrencias": [_ocorrencia(o) for o in r["ocorrencias_detalhe"]],
    }
    if detalhado:
        item["equipe_por_funcao"] = [
            f"{e['funcao']} x{e['quantidade']}" for e in r["equipe_por_funcao"]
        ]
        item["equipamentos"] = [f"{q['nome']} ({q['status']})" for q in r["equipamentos"]]
        item["materiais"] = [
            f"{m['descricao']} {m['quantidade']:g} {m['unidade']} ({m['evento']})"
            for m in r["materiais"]
        ]
        item["proximas_atividades"] = r["proximas_atividades"]
    return item


def _pessoas_por_funcao(rdos: list[dict[str, Any]]) -> dict[str, int]:
    """Pessoas-dia por função no período (somado aqui, o modelo não soma)."""
    total: Counter[str] = Counter()
    for r in rdos:
        for e in r["equipe_por_funcao"]:
            total[e["funcao"]] += e["quantidade"]
    return dict(total.most_common())


def _dias_sem_rdo(inicio: date, fim: date, rdos: list[dict[str, Any]]) -> list[str]:
    """Dias úteis (seg–sáb) do período sem RDO: o modelo não deve supor que houve trabalho."""
    feitos = {r["data"] for r in rdos}
    dias = (inicio + timedelta(days=i) for i in range((fim - inicio).days + 1))
    return [d.isoformat() for d in dias if d.weekday() < 6 and d.isoformat() not in feitos]


async def listar_obras(_: ListarObrasEntrada, contexto: ContextoExecucao) -> ResultadoFerramenta:
    obras = [o for o in dados_exemplo()["obras"] if o["id"] in contexto.obras_visiveis]
    return ResultadoFerramenta(dados={"obras": obras})


async def consultar_rdos(
    entrada: ConsultarRdosEntrada, _contexto: ContextoExecucao
) -> ResultadoFerramenta:
    # A obra já foi conferida contra as obras do passe pelo registro.
    d = dados_exemplo()
    inicio, fim = entrada.data_inicio.isoformat(), entrada.data_fim.isoformat()
    chuva = d["clima_com_chuva"].get(entrada.obra_id, {})
    rdos = sorted(
        (r for r in d["rdos"] if r["obra_id"] == entrada.obra_id and inicio <= r["data"] <= fim),
        key=lambda r: r["data"],
    )

    detalhado = (entrada.data_fim - entrada.data_inicio).days < PERIODO_DETALHADO_DIAS
    itens = [_item(r, chuva, detalhado) for r in rdos]
    pessoas = [r["equipe"] for r in rdos]
    pico = max(rdos, key=lambda r: r["equipe"]) if rdos else None
    totais = {
        "rdos": len(rdos),
        "pessoas_dia": sum(pessoas),
        "media_pessoas_por_dia": round(sum(pessoas) / len(pessoas), 1) if pessoas else 0,
        "pico": {"data": pico["data"], "pessoas": pico["equipe"]} if pico else None,
        "dias_com_chuva": sum(1 for r in rdos if r["data"] in chuva),
        "dias_em_que_a_chuva_impactou": sum(
            1 for r in rdos if chuva.get(r["data"], {}).get("impactou")
        ),
        "ocorrencias": sum(r["ocorrencias"] for r in rdos),
        "pessoas_dia_por_funcao": _pessoas_por_funcao(rdos),
        "atividades_registradas": sum(len(r["atividades"]) for r in rdos),
        "equipamentos_usados": sorted({q["nome"] for r in rdos for q in r["equipamentos"]}),
        "dias_sem_rdo": _dias_sem_rdo(entrada.data_inicio, entrada.data_fim, rdos),
    }
    return ResultadoFerramenta(
        dados={
            "periodo": {"inicio": inicio, "fim": fim},
            "detalhe": "completo" if detalhado else "resumido (atividades e ocorrências)",
            "totais": totais,
            "rdos": itens,
        },
        citacoes=[Citacao(tipo="RDO", id=r["id"], referencia=_rotulo(r["data"])) for r in rdos],
    )


def registrar_ferramentas_exemplo(registro: RegistroFerramentas) -> None:
    registro.registrar(
        Ferramenta(
            nome="listar_obras",
            descricao="Lista as obras que o usuário pode consultar (id, nome, etapa, progresso).",
            entrada=ListarObrasEntrada,
            executar=listar_obras,
            interna=True,  # o servidor a chama para montar o contexto; o modelo já recebe a lista
        )
    )
    registro.registrar(
        Ferramenta(
            nome="consultar_rdos",
            descricao=(
                "RDOs de uma obra num período (até 31 dias): por dia, serviços executados, pessoas "
                "(por função, em períodos de até 7 dias), equipamentos, materiais, clima, "
                "ocorrências e situação; e os totais já calculados (pessoas-dia, média, pico, "
                "dias de chuva, dias sem RDO). Para 'hoje' ou 'ontem' use data_inicio = data_fim. "
                "Use os totais para responder números."
            ),
            entrada=ConsultarRdosEntrada,
            executar=consultar_rdos,
        )
    )
