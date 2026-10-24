"""Gera os dados das ferramentas de exemplo do Assistente a partir do seed da demonstração.

Uso (banco com `seed:demonstracao` e `seed:demonstracao:volume` já rodados, o mesmo do staging):
    uv run python scripts/gerar_dados_do_seed.py --hoje 2026-10-20 \
        --psql "docker exec -i brikta-postgres-teste psql -U brikta -d brikta_mockgen"

Lê obras, RDOs, equipe e ocorrências com `psql` e grava
`src/brikta_ia/assistente/ferramentas/exemplo/dados.json`. O `id` do RDO é o `rdo_local_id`
(`demo-<obra>-<data>`), que o seed fixa e o app usa como id local: a citação abre o RDO certo.
O seed conta 20 dias úteis até ontem, então regere quando semear de novo em outro dia.
"""

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

DESTINO = (
    Path(__file__).resolve().parent.parent
    / "src/brikta_ia/assistente/ferramentas/exemplo/dados.json"
)

STATUS = {
    "VALIDADO": "APROVADO",
    "PRONTO_PARA_VALIDAR": "AGUARDANDO_VALIDACAO",
    "EM_PREENCHIMENTO": "PREENCHENDO",
}
CHUVA = {"CHUVA", "CHUVA_FORTE"}

SQL = """
select json_build_object(
  'obras', (select coalesce(json_agg(json_build_object(
      'id', o.id, 'nome', o.nome, 'unidade', o.unidade,
      'cidade', o.cidade || ' - ' || o.uf, 'etapa_atual', o.etapa_atual,
      'progresso', o.progresso_percentual, 'responsavel', o.responsavel_tecnico
    ) order by o.id), '[]') from obras o),
  'rdos', (select coalesce(json_agg(json_build_object(
      'id', r.rdo_local_id, 'obra_id', r.obra_id, 'numero', r.numero,
      'data', to_char(r.data_referencia, 'YYYY-MM-DD'), 'autor', u.nome,
      'situacao', r.situacao, 'manha', r.clima_manha, 'tarde', r.clima_tarde,
      'impactou', coalesce(r.clima_impactou, false),
      'equipe', coalesce((select sum(e.quantidade) from rdo_equipes e where e.rdo_id = r.id), 0),
      'ocorrencias', (select count(*) from rdo_ocorrencias c where c.rdo_id = r.id),
      'fotos', (select count(*) from midia_evidencias m where m.rdo_id = r.id),
      'atividades', (select coalesce(json_agg(json_build_object(
          'descricao', a.descricao, 'local', a.local_obra, 'status', a.status,
          'progresso', a.progresso_percentual) order by a.id), '[]')
          from rdo_atividades a where a.rdo_id = r.id),
      'equipe_por_funcao', (select coalesce(json_agg(json_build_object(
          'funcao', e.especialidade, 'quantidade', e.quantidade,
          'horas', e.horas_trabalhadas) order by e.especialidade), '[]')
          from rdo_equipes e where e.rdo_id = r.id),
      'equipamentos', (select coalesce(json_agg(json_build_object(
          'nome', q.nome, 'status', q.status) order by q.nome), '[]')
          from rdo_equipamentos q where q.rdo_id = r.id),
      'materiais', (select coalesce(json_agg(json_build_object(
          'descricao', m.descricao, 'quantidade', m.quantidade, 'unidade', m.unidade,
          'evento', m.evento) order by m.descricao), '[]')
          from rdo_materiais m where m.rdo_id = r.id),
      'proximas_atividades', (select coalesce(json_agg(p.descricao order by p.ordem), '[]')
          from rdo_proximas_atividades p where p.rdo_id = r.id),
      'ocorrencias_detalhe', (select coalesce(json_agg(json_build_object(
          'tipo', c.tipo, 'descricao', c.descricao, 'gravidade', c.gravidade,
          'impacto_cronograma', c.impacto_cronograma) order by c.id), '[]')
          from rdo_ocorrencias c where c.rdo_id = r.id)
    ) order by r.obra_id, r.data_referencia), '[]')
    from rdos r join usuarios u on u.id = r.usuario_id)
);
"""


def _consultar(psql: str) -> dict[str, Any]:
    saida = subprocess.run(
        [*shlex.split(psql), "-At", "-c", SQL], capture_output=True, text=True, check=True
    ).stdout
    return json.loads(saida.strip())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hoje", required=True, help="Data (AAAA-MM-DD) em que o seed rodou")
    parser.add_argument("--psql", required=True, help="Comando psql que conecta no banco do seed")
    args = parser.parse_args()

    bruto = _consultar(args.psql)
    rdos, chuva, descritas = [], {}, {}
    for r in bruto["rdos"]:
        rdos.append(
            {
                "id": r["id"],
                "obra_id": r["obra_id"],
                "numero": r["numero"],
                "data": r["data"],
                "autor": r["autor"],
                "status": STATUS[r["situacao"]],
                "equipe": r["equipe"],
                "ocorrencias": r["ocorrencias"],
                "fotos": r["fotos"],
                "atividades": r["atividades"],
                "equipe_por_funcao": r["equipe_por_funcao"],
                "equipamentos": r["equipamentos"],
                "materiais": r["materiais"],
                "proximas_atividades": r["proximas_atividades"],
                "ocorrencias_detalhe": r["ocorrencias_detalhe"],
            }
        )
        if r["manha"] in CHUVA or r["tarde"] in CHUVA:
            chuva.setdefault(r["obra_id"], {})[r["data"]] = {
                "manha": r["manha"],
                "tarde": r["tarde"],
                "impactou": r["impactou"],
            }
        if r["ocorrencias_detalhe"]:
            descritas.setdefault(r["obra_id"], {})[r["data"]] = r["ocorrencias_detalhe"][0]

    dados = {
        "origem": "seed da demonstração do backend (seed:demonstracao + seed:demonstracao:volume)",
        "hoje_demonstracao": args.hoje,
        "obras": bruto["obras"],
        "rdos": rdos,
        "clima_com_chuva": chuva,
        "ocorrencias_descritas": descritas,
    }
    DESTINO.write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"gravado: {DESTINO.name} ({len(rdos)} RDOs, {len(bruto['obras'])} obras)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
