# Cartões+Árbitro parou de gerar sugestão — bug real, corrigido (16/09/2026)

## Contexto

Lucas notou: Cartões+Árbitro (Série B) gerou 5 sinais entre 27-28/08/2026
(quando o critério entrou em produção) e depois nunca mais — 19 dias sem
nenhuma sugestão nova, enquanto BTTS e Over 2.5 continuaram gerando
normalmente no mesmo período. Pediu pra confirmar se o critério está
rodando corretamente.

## Causa raiz

Bug real, introduzido por mim mesmo no fix do sentinela `-1` do dia
02/09/2026 (`docs/retrospectiva_ligas_nordicas_2026-09-02.md`) — um efeito
colateral que não tinha sido percebido até agora.

`retrospectiva.prever_jogo` só incluía um mercado (`cartoes_pro`,
`cartoes_contra`, etc.) no dict `mercados` quando TANTO a previsão
(`pred`) QUANTO o resultado real (`real`) estavam disponíveis:

```python
real = _valor_real(row, campo)
if ind["media_final"] is None or real is None:
    continue
mercados[campo] = dict(pred=..., real=real, erro=...)
```

Isso é correto pra BACKTEST (onde o jogo já terminou e o resultado real
deveria existir) — mas pra um jogo FUTURO (ainda não jogado, é
exatamente o caso da previsão ao vivo em `previsao_dia.py`), o resultado
real de cartões genuinamente não existe ainda. Antes do fix do sentinela
(02/09), colunas de cartão ausentes caíam pra `0` (`or 0`) — então
`_valor_real` retornava `0.0` (não `None`) mesmo pra jogo futuro, e o
mercado entrava no dict por "acidente" (com um `real=0` falso, nunca
usado na previsão ao vivo). Depois do fix do sentinela, cartão ausente
vira `-1` corretamente — `_valor_real` passou a retornar `None` de
verdade pra jogo futuro — e o mercado nunca mais entrava no dict.

Consequência: `previsao_dia.avaliar_cartoes_arbitro` (que só precisa de
`mercados["cartoes_pro"]["pred"]`/`["cartoes_contra"]["pred"]`) sempre
recebia `None` pros dois, retornava `None` incondicionalmente — **TODO
jogo futuro de Cartões+Árbitro era descartado antes mesmo de calcular
edge**, desde 02/09. Confirmado ao vivo com os 2 jogos futuros de Série B
disponíveis hoje: os dois falhavam com "SEM mercado cartoes_pro/contra na
previsão", antes de qualquer chance de ter edge.

Importante: os mercados de GOLS (`gols_pro`/`gols_contra`, usados por
BTTS/Over 2.5) não têm esse problema — `home_team_goal_count` de um jogo
futuro não passa pelo sentinela de "estatística de detalhe ausente"
(isso é específico de `CAMPOS_DETALHE`, que inclui cartões/escanteios/
chutes/posse, não o placar) — por isso BTTS/Over 2.5 continuaram
funcionando normalmente o tempo todo.

## Correção

`retrospectiva.prever_jogo`: só GOLS continua exigindo `real` não-nulo
pra entrar em `mercados` (é o mercado obrigatório, usado no retorno
central da função). Todo outro mercado (cartões/escanteios/chutes/
gols_1t) agora entra em `mercados` assim que `pred` está disponível,
independente de `real` — com `real`/`erro` como `None` quando o
resultado ainda não existe. Quem precisa avaliar resultado (backtest)
passa a checar `real is not None` explicitamente.

Dois consumidores precisaram do mesmo ajuste, pra manter o comportamento
de backtest EXATAMENTE igual (só pular jogos sem resultado real
conhecido, nunca deixar `None` vazar pra uma soma):
- `retrospectiva.rodar_retrospectiva` (agregação de MAE por mercado).
- `checar_decaimento._checagem_cartoes_arbitro` (o próprio backtest
  mensal de Cartões+Árbitro).

2 testes novos em `test_retrospectiva.py` cobrindo exatamente esse
cenário (jogo com cartões sentinelados = "ainda não jogado" continua
com `pred` disponível, `real`/`erro` viram `None`; agregação de MAE
ignora esses pontos sem inflar `n`).

## Verificação — backtest não mudou (só cresceu organicamente)

Rechecagem de Cartões+Árbitro (Série B) e dos dois critérios de gols
logo após o fix, comparado ao último número documentado (08/09):

| Critério | Antes (08/09) | Depois (16/09) |
|---|---|---|
| Cartões+Árbitro (acumulado) | n=208 ROI+16,0% z=+2,56 | n=218 ROI+15,1% z=+2,47 |
| BTTS (acumulado) | n=189 ROI+21,6% z=+3,02 | n=192 ROI+22,5% z=+3,18 |
| Over 2.5 (acumulado) | n=71 ROI+29,7% z=+2,42 | n=72 ROI+30,6% z=+2,52 |

O `n` cresceu só pelo número normal de jogos novos terminados na semana
(mesmo padrão de sempre) — nenhuma mudança de lógica de backtest, os 208
testes antigos (+2 novos) continuam passando sem alteração.

## Verificação — caminho ao vivo desbloqueado

Rodei o diagnóstico ao vivo de novo, nos 2 jogos futuros de Série B
disponíveis hoje (16/09): os dois agora chegam até o cálculo de edge —
um é descartado porque o árbitro ainda não tem os 10 jogos mínimos de
histórico (`n_jogos_arb=5`), o outro porque o bet365 não cota cartões
pra esse jogo específico — as DUAS são razões legítimas e específicas do
jogo, não mais um bloqueio sistemático do critério inteiro. A partir de
agora, jogos que passem nesses dois filtros voltam a poder gerar
sugestão normalmente.

## Nota — "América" nos logs de diagnóstico

Durante a investigação, "América Mineiro" apareceu nos jogos com aviso
de estatística ausente (não relacionado ao bug de cartões em si — é
outro time, outra situação). Não confundir com a pergunta anterior do
Lucas sobre um sinal de escanteios do "América" perdido no sistema ao
vivo — são times/times e sistemas diferentes.
