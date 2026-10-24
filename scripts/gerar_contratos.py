"""Gera os JSON Schemas de `contracts/` a partir dos modelos Pydantic (ADR-01, IA-03).

Uso:
    uv run python scripts/gerar_contratos.py           # escreve os arquivos
    uv run python scripts/gerar_contratos.py --check   # falha se estiverem desatualizados

Esses arquivos são a fonte para o backend validar os payloads (BE-46).
Mudança incompatível = nova versão do contrato (novo arquivo), nunca editar a anterior.
"""

import argparse
import json
import sys
from pathlib import Path

from brikta_ia.domain.contratos import CONTRATOS

PASTA = Path(__file__).resolve().parent.parent / "contracts"


def renderizar(nome: str) -> str:
    schema = CONTRATOS[nome].model_json_schema()
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": nome, **schema}
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    PASTA.mkdir(exist_ok=True)
    desatualizados: list[str] = []
    for nome in CONTRATOS:
        arquivo = PASTA / f"{nome}.json"
        conteudo = renderizar(nome)
        atual = arquivo.read_text(encoding="utf-8") if arquivo.exists() else None
        if atual == conteudo:
            continue
        if args.check:
            desatualizados.append(arquivo.name)
        else:
            arquivo.write_text(conteudo, encoding="utf-8")
            print(f"atualizado: {arquivo.name}")

    if desatualizados:
        print("Contratos desatualizados (rode scripts/gerar_contratos.py):", *desatualizados)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
