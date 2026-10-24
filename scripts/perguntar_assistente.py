"""Conversa com o Assistente pelo terminal, sem app e sem backend (teste manual).

Uso (lê o .env da IA: LLM_ASSISTENTE_*, ASSISTENTE_*):
    uv run python scripts/perguntar_assistente.py
    uv run python scripts/perguntar_assistente.py --perfil OPERADOR --obra de300000-...a1

Monta o mesmo serviço da API (agente, ferramentas e conversas) e um contexto como o passe
traria. Com LLM_ASSISTENTE_PROVEDOR=openai_compativel, chama o provedor de verdade.
Não loga nem guarda as perguntas.
"""

import argparse
import asyncio
import uuid

from pydantic import SecretStr

from brikta_ia.assistente.fabrica import criar_servico
from brikta_ia.assistente.ferramentas.exemplo import dados_exemplo
from brikta_ia.assistente.ferramentas.registro import ContextoExecucao
from brikta_ia.config import get_settings
from brikta_ia.domain.assistente import (
    EventoCitacao,
    EventoErro,
    EventoFim,
    EventoStatus,
    EventoToken,
    NovaMensagem,
)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--perfil", default="GESTOR", choices=["GESTOR", "FISCAL", "OPERADOR"])
    parser.add_argument("--obra", default=None, help="Obra em foco (padrão: a primeira)")
    args = parser.parse_args()

    obras = [o["id"] for o in dados_exemplo()["obras"]]
    contexto = ContextoExecucao(
        empresa_id="empresa-demonstracao",
        usuario_id="terminal",
        role=args.perfil,
        obras_visiveis=frozenset(obras),
        jwt=SecretStr(""),
    )
    servico = criar_servico(get_settings())
    conversa = servico.criar(contexto, args.obra or obras[0])
    print("Assistente de Obra (Ctrl+D para sair)\n")
    while True:
        try:
            pergunta = (await asyncio.to_thread(input, "você> ")).strip()
        except EOFError:
            break
        if not pergunta:
            continue
        mensagem = NovaMensagem(cliente_mensagem_id=uuid.uuid4(), texto=pergunta)
        print("ia> ", end="", flush=True)
        async for evento in servico.perguntar(contexto, conversa, mensagem):
            match evento:
                case EventoStatus(texto=texto):
                    print(f"[{texto}] ", end="", flush=True)
                case EventoToken(texto=texto):
                    print(texto, end="", flush=True)
                case EventoCitacao(rotulo=rotulo):
                    print(f"\n  fonte: {rotulo}", end="")
                case EventoFim(uso=uso):
                    tokens = f"{uso.tokens_entrada}+{uso.tokens_saida}"
                    print(f"\n  ({uso.passos} passo(s), {tokens} tokens)\n")
                case EventoErro(codigo=codigo, mensagem=msg):
                    print(f"\n  erro {codigo}: {msg}\n")


if __name__ == "__main__":
    asyncio.run(main())
