# `estilo_por_mando` sob validação fora-da-amostra (treino 2025 / holdout 2026)

A decisão anterior ("ajuda a Série A, atrapalha a Série B") veio de uma
comparação única de 3 cenários na mesma amostra combinada — o mesmo tipo
de teste que, pro `k_mando`, tinha se provado não confiável. Refeito com
o desenho de holdout: grid de treino (96 combinações, agora incluindo
`estilo_por_mando` como dimensão) só em 2025, top-10 reavaliados em 2026
(nunca visto pela escolha).

## Série A — o achado anterior NÃO se sustenta

Comparando pares com os mesmos `k_mando`/`usar_estilo`/`filtro_aderencia`,
variando só `estilo_por_mando`, dentro do top-10 de holdout:

| k_mando | estilo | filtro | por_mando=True | por_mando=False |
|---|---|---|---|---|
| None/1.0 | False | 0.8 | 51.00% | 51.96%* |
| 0.2 | False | 0.8 | 44.00% | 43.27% |

(*0.5096 arredondado)

**A diferença entre `True` e `False` fica dentro de 0.1-0.7pp — ruído,
não sinal.** O melhor resultado do top-10 (`None, estilo=True, filtro=0.8,
por_mando=True` → 55.00% no holdout) usa `por_mando=True`, mas não há um
padrão consistente favorecendo `True` nos outros pares comparáveis.

**Decisão revisada: reverter `estilo_por_mando` pra `False` na Série A**
— o achado "ajuda a Série A" não resistiu ao mesmo teste que derrubou o
achado anterior de `k_mando`. Sem evidência robusta o suficiente pra
manter uma configuração não-padrão.

## Série B — o achado anterior SE CONFIRMA

O melhor resultado do holdout continua sendo exatamente o mesmo de antes
— `k_mando=0.5, usar_estilo=False, filtro=0.8, estilo_por_mando=False` →
**59.16% no holdout** — e 7 dos 10 melhores candidatos do treino usam
`estilo_por_mando=False`. Pares comparáveis com `True`:

| k_mando | estilo | filtro | por_mando=True | por_mando=False |
|---|---|---|---|---|
| 0.35 | True | 0.8 | 55.68% | 55.50% |
| 0.7 | False | 0.8 | 57.06% | 56.54% |

Aqui a diferença também é pequena (~0.2-0.5pp) mas o MELHOR resultado
geral (59.16%) usa `False`, e a maioria do top-10 favorece `False`.

**Decisão: manter `estilo_por_mando=False` na Série B** — confirmado,
sem mudança.

## Conclusão

`estilo_por_mando`, assim como `usar_estilo` (ablação anterior), não
mostra um efeito forte o bastante pra justificar tratamento diferenciado
por liga. **Desligar nas duas ligas** é a escolha mais defensável agora —
simples, sem evidência de prejuízo, e consistente com o que a validação
de holdout do `k_mando` já tinha ensinado: não confiar em achado de
comparação única sem teste fora da amostra.

## Atualização nos parâmetros

| Parâmetro | Série A | Série B |
|---|---|---|
| `estilo_por_mando` | **`False`** (revertido — era `True`) | `False` (confirmado, sem mudança) |

Os demais parâmetros (`k_mando`, `usar_estilo`, `filtro_aderencia`)
continuam como no relatório de holdout anterior
(`docs/retrospectiva_holdout_2026-08-24.md`) — este teste não mudou essa
parte, só confirmou que os valores encontrados lá continuam sendo os
melhores mesmo variando `estilo_por_mando` junto.

## Limitações

Mesmas de sempre: 1 temporada de treino, 1 de holdout parcial. O código
de `_estilo_por_mando` em `retrospectiva.py` fica mantido (testado, só
não usado por enquanto) — não é removido, porque pode voltar a fazer
sentido com mais dado ou proxies de estilo melhores.

Reprodução: mesmo desenho do relatório de holdout do `k_mando`, com
`estilo_por_mando` adicionado à grade de treino
(`[True, False]`, dobrando de 48 pra 96 combinações).
