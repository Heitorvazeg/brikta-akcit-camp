"""Serviço de conversa do Assistente: o que é igual para qualquer agente.

- dono da conversa (usuário + empresa do passe); conversa de outra pessoa = não encontrada;
- obra em foco só se estiver no passe;
- `cliente_mensagem_id` idempotente e uma pergunta por vez por conversa;
- histórico no servidor (o app nunca manda o histórico: evita forjar mensagens);
- tradução dos eventos neutros do agente para o contrato `assistente_eventos.v1`;
- log por pergunta só com IDs, passos, duração e código de erro (nada de texto).

O agente (`agente/`), o repositório (`conversas.py`) e as ferramentas (`ferramentas/`)
chegam prontos pela fábrica (`fabrica.py`).
"""

import time
import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

from brikta_ia.assistente.agente.base import (
    Agente,
    CitacaoAgente,
    ErroAgente,
    FimAgente,
    StatusAgente,
    TextoAgente,
)
from brikta_ia.assistente.contexto import com_contexto_inicial, mensagem_de_sistema
from brikta_ia.assistente.conversas import Conversa, RepositorioConversas, Troca
from brikta_ia.assistente.ferramentas.execucao import ExecucaoFerramentas
from brikta_ia.assistente.ferramentas.registro import (
    ContextoExecucao,
    ErroFerramenta,
    RegistroFerramentas,
)
from brikta_ia.domain.assistente import (
    ErroAssistenteCodigo,
    Evento,
    EventoCitacao,
    EventoErro,
    EventoFim,
    EventoStatus,
    EventoToken,
    NovaMensagem,
    Uso,
)
from brikta_ia.observability.logging import get_logger
from brikta_ia.providers.llm.base import MensagemTurno

log = get_logger(__name__)

FUSO_OBRA = ZoneInfo("America/Sao_Paulo")
#: Trocas anteriores (pergunta + resposta) enviadas ao modelo.
JANELA_HISTORICO = 6


class ErroConversa(Exception):
    """Recusa antes de abrir o fluxo (vira HTTP comum)."""

    def __init__(self, status: int, codigo: ErroAssistenteCodigo, mensagem: str) -> None:
        super().__init__(mensagem)
        self.status = status
        self.codigo = codigo
        self.mensagem = mensagem


class ServicoConversas:
    def __init__(
        self,
        agente: Agente,
        registro: RegistroFerramentas,
        conversas: RepositorioConversas,
        *,
        data_referencia: date | None = None,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self._agente = agente
        self._registro = registro
        self._conversas = conversas
        self._data_referencia = data_referencia
        self._relogio = relogio

    # ── Conversas ─────────────────────────────────────────────────────────

    def criar(
        self,
        contexto: ContextoExecucao,
        obra_id: str | None,
        contexto_inicial: str | None = None,
    ) -> Conversa:
        if obra_id is not None and obra_id not in contexto.obras_visiveis:
            raise ErroConversa(404, ErroAssistenteCodigo.OBRA_NAO_ENCONTRADA, "Obra não encontrada")
        conversa = Conversa(
            id=uuid.uuid4().hex,
            usuario_id=contexto.usuario_id,
            empresa_id=contexto.empresa_id,
            obra_foco=obra_id,
            usada_em=self._relogio(),
            contexto_inicial=contexto_inicial,
        )
        self._conversas.criar(conversa)
        log.info("assistente.conversa_criada", conversa_id=conversa.id)
        return conversa

    def obter(self, contexto: ContextoExecucao, conversa_id: str) -> Conversa:
        conversa = self._conversas.obter(conversa_id)
        if (
            conversa is None
            or conversa.usuario_id != contexto.usuario_id
            or conversa.empresa_id != contexto.empresa_id
        ):
            # de outra pessoa ou inexistente: a mesma resposta, sem revelar que existe
            raise ErroConversa(
                404, ErroAssistenteCodigo.CONVERSA_NAO_ENCONTRADA, "Conversa não encontrada"
            )
        return conversa

    # ── Perguntas ─────────────────────────────────────────────────────────

    def perguntar(
        self, contexto: ContextoExecucao, conversa: Conversa, mensagem: NovaMensagem
    ) -> AsyncGenerator[Evento]:
        """Confere tudo ANTES do fluxo (erros viram HTTP) e devolve os eventos da resposta."""
        chave = str(mensagem.cliente_mensagem_id)
        if chave in conversa.respostas:
            return _repetir(conversa.respostas[chave])
        if conversa.em_andamento is not None:
            raise ErroConversa(
                409,
                ErroAssistenteCodigo.MENSAGEM_EM_ANDAMENTO,
                "Ainda estou respondendo a pergunta anterior.",
            )
        conversa.em_andamento = chave
        conversa.usada_em = self._relogio()
        self._conversas.salvar(conversa)
        return self._responder(contexto, conversa, chave, mensagem.texto)

    async def _responder(
        self, contexto: ContextoExecucao, conversa: Conversa, chave: str, texto: str
    ) -> AsyncGenerator[Evento]:
        inicio = time.monotonic()
        emitidos: list[Evento] = []
        ferramentas = ExecucaoFerramentas(self._registro, contexto)
        codigo: str | None = None
        passos = 0
        try:
            mensagens = [
                MensagemTurno("system", await self._sistema(contexto, conversa)),
                *_historico(conversa),
                MensagemTurno("user", texto),
            ]
            async for evento in self._agente.responder(mensagens, ferramentas):
                if isinstance(evento, FimAgente):
                    passos = evento.passos
                    fim = EventoFim(
                        mensagem_id=uuid.uuid4().hex,
                        conversa_id=conversa.id,
                        uso=Uso(
                            passos=evento.passos,
                            tokens_entrada=evento.tokens_entrada,
                            tokens_saida=evento.tokens_saida,
                        ),
                    )
                    emitidos.append(fim)
                    conversa.trocas.append(Troca(texto, evento.texto))
                    conversa.respostas[chave] = emitidos
                    yield fim
                    return
                saida = _para_contrato(evento)
                emitidos.append(saida)
                yield saida
        except ErroAgente as erro:
            codigo = erro.codigo
            yield EventoErro(codigo=erro.codigo, mensagem=erro.mensagem)
        except Exception:
            codigo = ErroAssistenteCodigo.ERRO_INTERNO
            log.exception("assistente.erro_interno", conversa_id=conversa.id)
            yield EventoErro(
                codigo=ErroAssistenteCodigo.ERRO_INTERNO,
                mensagem="Algo deu errado ao responder. Tente de novo.",
            )
        finally:
            # cancelada (o app fechou) ou com erro: nada guardado; repetir o id refaz a pergunta
            conversa.em_andamento = None
            self._conversas.salvar(conversa)
            log.info(
                "assistente.pergunta",
                conversa_id=conversa.id,
                usuario_id=contexto.usuario_id,
                agente=self._agente.nome,
                passos=passos,
                chamadas_ferramenta=ferramentas.chamadas,
                duracao_ms=round((time.monotonic() - inicio) * 1000),
                codigo_erro=codigo,
                concluida=chave in conversa.respostas,
            )

    async def _sistema(self, contexto: ContextoExecucao, conversa: Conversa) -> str:
        sistema = mensagem_de_sistema(
            contexto,
            hoje=self._data_referencia or datetime.now(FUSO_OBRA).date(),
            nomes_das_obras=await self._nomes_das_obras(contexto),
            obra_foco=conversa.obra_foco,
        )
        return com_contexto_inicial(sistema, conversa.contexto_inicial)

    async def _nomes_das_obras(self, contexto: ContextoExecucao) -> dict[str, str]:
        nomes = dict.fromkeys(contexto.obras_visiveis, "sem nome")
        if "listar_obras" not in self._registro.nomes():
            return nomes
        try:
            r = await self._registro.executar("listar_obras", {}, contexto, interna=True)
        except ErroFerramenta:
            return nomes
        return nomes | {o["id"]: _rotulo_obra(o) for o in r.dados["obras"]}


def _rotulo_obra(o: dict[str, object]) -> str:
    """Nome e dados cadastrais curtos: o modelo responde cidade, etapa e responsável sem passo
    extra (cada passo reenvia o prompt inteiro e o provedor limita tokens por minuto)."""
    extras = [str(o[k]) for k in ("unidade", "cidade") if o.get(k)]
    if o.get("etapa_atual"):
        progresso = f", {o['progresso']}%" if o.get("progresso") is not None else ""
        extras.append(f"etapa {o['etapa_atual']}{progresso}")
    if o.get("responsavel"):
        extras.append(f"resp. {o['responsavel']}")
    return f"{o['nome']} ({'; '.join(extras)})" if extras else str(o["nome"])


def _historico(conversa: Conversa) -> list[MensagemTurno]:
    mensagens: list[MensagemTurno] = []
    for t in conversa.trocas[-JANELA_HISTORICO:]:
        mensagens += [MensagemTurno("user", t.pergunta), MensagemTurno("assistant", t.resposta)]
    return mensagens


def _para_contrato(evento: StatusAgente | TextoAgente | CitacaoAgente) -> Evento:
    match evento:
        case StatusAgente(etapa=etapa, texto=texto):
            return EventoStatus(etapa=etapa, texto=texto)
        case TextoAgente(texto=texto):
            return EventoToken(texto=texto)
        case CitacaoAgente(tipo=tipo, id=id_, rotulo=rotulo):
            return EventoCitacao(tipo=tipo, id=id_, rotulo=rotulo)


async def _repetir(eventos: list[Evento]) -> AsyncGenerator[Evento]:
    for evento in eventos:
        yield evento
