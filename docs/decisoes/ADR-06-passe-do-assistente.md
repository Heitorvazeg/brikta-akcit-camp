# ADR-06 (revisão de 15/10/2026): passe do Assistente emitido pelo backend

**Status:** Aceita para o protótipo (IA-66). Substitui o trecho "JWT do backend validado pela IA" do ADR-06 original (Plano, Seção 3).

## Contexto

O ADR-06 previa o app chamando a IA com o JWT do login, validado pela IA com a chave pública do backend (assinatura assimétrica). O plano 09 do backend saiu com HS256 e `JWT_SECRET`, e a troca para assinatura assimétrica mudaria o login de todos os clientes. Dar o `JWT_SECRET` à IA está fora de questão: quem tivesse a chave forjaria login.

## Decisão

- O backend emite um **passe do Assistente**: `POST /api/v1/assistente/sessao` (JWT do login) devolve `{ token_ia, expira_em }`. É um JWT HS256 assinado com uma **chave própria** (`IA_TICKET_SECRET`), com `iss=brikta-backend`, `aud=brikta-ia`, `sub`, `empresa_id`, `role`, `obras` (visíveis na emissão, pela regra do `GET /obras`), `jti` e validade de **30 minutos**.
- A IA confere o passe **localmente** em toda requisição (assinatura, `aud`, `iss`, validade) e monta o `ContextoExecucao` a partir dele. Nunca do corpo da requisição nem do modelo.
- O passe é da **sessão do usuário**, não de uma obra: perguntas que cruzam obras continuam possíveis. A obra escolhida no app é só o foco.
- **Renovar não perde a conversa:** o histórico fica no servidor por usuário e conversa. Passe vencido = `401 TOKEN_EXPIRADO` antes do fluxo; o app pede outro e repete a pergunta com o mesmo `cliente_mensagem_id`.
- Fica igual: cada pergunta é um `POST` com resposta em SSE; cancelar = fechar a conexão.

## Consequências

- **Segredo nunca bloqueia a operação:** `IA_TICKET_SECRET` vazio ou fraco não impede backend, IA nem deploy de subirem; só desliga o Assistente, com aviso no log. Nos servidores há uma fonte só, o `producao.env` que o compose entrega ao backend e à IA: em staging, `/opt/brikta/shared/producao.env`, gerado pelo `setup-vps.sh` se faltar ([guia de staging](../../../infra/producao/README.md)); no fluxo manual, `infra/producao/.env`, gerado pelo `producao:subir`. Localmente, `npm run segredos:local` iguala os dois `.env`. Valores diferentes aparecem no log da IA como `assistente.passe_recusado motivo=assinatura_nao_confere`.

- Duas chaves separadas: a do passe não serve para forjar login no backend (o `aud` também é outro).
- **Revogação em até 30 min:** usuário desativado ou obra retirada continuam no passe até ele vencer (o dobro da janela do login). A renovação passa pelo backend, que recusa quem foi desativado.
- Empresa com muitas obras deixa o passe grande. Se virar problema: acima de um limite, o passe não leva a lista e a IA a busca no início da conversa.
- Pode migrar para assinatura assimétrica (EdDSA) sem mudar o app: só a chave muda.
- **Em aberto para a BE-51:** com que credencial as ferramentas da IA chamam as rotas de leitura do backend. Caminho natural: o backend aceitar o mesmo passe nessas rotas (`aud=brikta-ia`), conferindo o usuário no banco como o `JwtAuthGuard` faz. Decidir junto com a BE-51.
