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

## 3º achado — o painel continuava preso mesmo com as duas correções

Depois de corrigir e revalidar as duas causas acima, o painel
CONTINUOU mostrando "Goiás x São Bernardo — Under 4,5" em 3 execuções
seguidas da rotina (18:10, 18:45 e 19:14 BRT), mesmo já com o código
corrigido disponível no repo. Investigando `gerar_painel_dia.py`/
`ledger_apostas.py`: o painel não recalcula as sugestões pendentes a
cada execução — `registrar_novas_sugestoes` só ACRESCENTA sugestões
novas ao `data/ledger_sugestoes.json` quando a combinação
`(fixture_id, critério)` ainda não existe lá; se já existe (pendente
ou resolvida), nunca é sobrescrita. O card do Goiás tinha sido
registrado em **27/08/2026** (`data_registro`), bem antes das duas
correções de hoje — ficou congelado com o valor errado (Under 4,5, odd
1,80, edge 19,9%) e nenhuma rotina nova, mesmo com o código certo,
jamais o corrigiria sozinho, porque o design do ledger deliberadamente
nunca reescreve uma entrada pendente já registrada (proteção contra
mudar a odd de uma aposta que o Lucas talvez já tenha feito).

Esse design continua correto — o problema foi só ter uma entrada
registrada com dado errado ANTES da correção existir. Recomputei os 5
jogos "Cartões+Árbitro" pendentes no ledger com o código já corrigido:
só o Goiás realmente mudava de LINHA (era o único caso de empate
`linha_mais_liquida` de verdade); os outros 4 mudaram só um pouco de
odd/edge (movimento normal de mercado entre o registro e agora, não
bug) — não mexi neles, o ledger deve refletir a odd real no momento em
que a sugestão foi feita, não ficar "atualizando" toda vez que a odd
de mercado se move.

**Correção manual, pontual**: editei
`data/ledger_sugestoes.json` só a entrada do Goiás (fixture_id
19667192) pra "Under 3,5 cartões, odd 1,83, edge 3,08%" (recalculado
com o pipeline já corrigido, contra a odd real da bet365 no momento),
com uma nota (`nota_correcao`) explicando a correção manual — não fiz
isso via rotina porque o jogo começava em minutos, sem tempo pra mais
um ciclo completo. **Nota importante**: o edge caiu de 19,9% pra
3,08% — a linha 4,5 (errada) tinha uma odd claramente mais generosa
(por ser desequilibrada) que a linha 3,5 (real, quase 50/50); a
sugestão original não só apontava pra uma linha inexistente, como
inflava a atratividade aparente da aposta.

## Recomendação final

As duas correções de código (`linha_mais_liquida` + detecção de estado
do fixture) resolvem a causa raiz pra sugestões NOVAS a partir de
agora. `pytest metodologia_pesos/` passando (192 testes). Nenhuma
mudança nos parâmetros/critérios em si — só correção de dado/seleção,
que afeta qualquer critério que dependa de
`puxar_fixtures_futuros`/`puxar_fixtures_finalizados` (ou seja, todo o
painel), não só cartões. A entrada específica do Goiás no ledger foi
corrigida manualmente (documentado acima) porque já estava congelada
antes da correção existir — não é um padrão recorrente, é um resíduo
pontual de um bug já fechado.
