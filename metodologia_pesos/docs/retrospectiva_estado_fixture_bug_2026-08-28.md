# Retrospectiva — bug de detecção "jogo já começou" (28/08/2026)

## O relato (parte 2)

Depois da correção de `linha_mais_liquida` (ver
`docs/retrospectiva_linha_cartoes_bug_2026-08-28.md`), Lucas reportou
que o painel CONTINUAVA mostrando "Goiás x São Bernardo — Under 4,5
cartões" mesmo depois de "atualizar" — inclusive depois de eu disparar
a rotina manualmente com o código já corrigido.

## Investigação

Rodei a função corrigida direto contra as odds reais atuais da bet365
pra esse jogo (fixture `19667192`) e ela escolhia **3,5 corretamente**
— a correção em si estava certa. Então por que o painel não refletia
isso?

Reproduzi a chamada exata que a produção usa
(`sportmonks_client.puxar_fixtures_futuros`, Série B, `dias_a_frente=3`)
e o jogo do Goiás **simplesmente não aparecia na lista** — mesmo estando
dentro da janela de datas e com state normal. Comparando com a chamada
bruta à API (sem o filtro da nossa função), o jogo aparecia lá
normalmente.

**Causa raiz**: `puxar_fixtures_futuros` decidia "o jogo já foi jogado,
não é mais futuro" checando `flat["home_goals"] is None` — mas o
Sportmonks, pouco antes do jogo começar, já publica uma entrada
`"CURRENT"` em `scores` com `goals: 0` pros dois times (um placeholder
0-0), mesmo o jogo ainda **não tendo começado de verdade**
(`state_id` continuava `1` = "NS", Not Started, confirmado via
`/fixtures/{id}?include=state`). Isso faz `home_goals` virar `0` (não
`None`), e o filtro (que só olha "tem gol registrado ou não") passa a
tratar um jogo que nem começou como "já jogado" — ele simplesmente
desaparece da lista de sugestões, e o painel fica preso mostrando a
última sugestão computada antes desse placeholder aparecer (por isso a
correção de `linha_mais_liquida` não tinha efeito visível: o jogo já
não estava mais sendo reavaliado).

**Risco mais sério, ainda não confirmado como tendo ocorrido de
verdade**: o mesmo problema, na direção oposta, afeta
`puxar_fixtures_finalizados`/`atualizar_fixtures_finalizados` (que
constroem o histórico usado pelo motor de walk-forward) — eles
decidiam "jogo terminou, pode entrar no histórico" com a mesma lógica
(`home_goals is not None`). Se a rotina diária rodasse nesse intervalo
exato (placeholder 0-0 publicado, jogo ainda não realmente terminado),
um placar **0-0 falso** entraria permanentemente no histórico — e como
o pull incremental (`atualizar_fixtures_finalizados`) só ADICIONA
fixtures novos por `fixture_id` (nunca corrige um já existente), esse
placar fantasma nunca seria corrigido depois, mesmo quando o resultado
real ficasse disponível. Chequei o `data/sportmonks_serieb/
fixtures.jsonl`/`sportmonks_seriea/fixtures.jsonl` locais (desatualizados,
não refletem execuções de hoje das rotinas) e não achei nenhum caso
óbvio — mas não dá pra confirmar com certeza que isso nunca aconteceu
numa execução anterior da rotina, já que o pull incremental nunca se
autocorrige.

## A correção

`flatten_fixture` (`sportmonks_client.py`) agora também extrai
`state_id` (campo base do fixture, sempre presente, não depende de
nenhum `include` extra). Duas constantes novas: `ESTADO_NAO_INICIADO =
1` (NS) e `ESTADOS_FINALIZADOS = {5, 7, 8}` (FT/AET/FT_PEN — confirmado
via `/states` da própria API do Sportmonks, não chutado).

- `puxar_fixtures_futuros`: agora inclui um fixture como "ainda não
  jogado" quando `state_id == ESTADO_NAO_INICIADO`, não mais quando
  `home_goals is None`.
- `puxar_fixtures_finalizados`/`atualizar_fixtures_finalizados`: agora
  só tratam um fixture como "finalizado" (entra no histórico) quando
  `state_id in ESTADOS_FINALIZADOS`, não mais quando os gols estão
  presentes.

Testes novos em `test_sportmonks_client.py` reproduzindo o bug exato
(fixture NS com placeholder 0-0): confirma que ele continua aparecendo
em `puxar_fixtures_futuros` e continua sendo IGNORADO por
`atualizar_fixtures_finalizados` (não polui o histórico); mais um teste
confirmando que um jogo genuinamente em andamento (`state_id` de
in-play) é corretamente excluído das sugestões.

## Verificação final

Rodei a chamada real (API ao vivo) com a correção: `puxar_fixtures_futuros`
agora traz 9 jogos da Série B (antes só 8 — o Goiás estava sumindo),
Goiás x São Bernardo aparece com `state_id=1`, e a linha de cartões
escolhida é **3,5** (odd 1,83 nos dois lados), batendo com o que a
bet365 real mostra.

## Recomendação final

As duas correções (`linha_mais_liquida` + detecção de estado do
fixture) juntas resolvem o caso relatado. `pytest metodologia_pesos/`
passando (192 testes). Nenhuma mudança nos parâmetros/critérios em si
— só correção de dado/seleção, que afeta qualquer critério que dependa
de `puxar_fixtures_futuros`/`puxar_fixtures_finalizados` (ou seja,
todo o painel), não só cartões.
