# Início de temporada não explica a queda de ROI — sem padrão consistente

## Contexto

Depois de notar que o Over 2.5 caiu de n=221/ROI+16,0% (dado só
2023-2026) para n=278/ROI+8,7% (dado completo 2016-2026, mais jogos de
início de 2023 entrando na conta por terem histórico suficiente agora),
Lucas perguntou se esse padrão — jogos de início de temporada saindo
pior — é consistente TODO ano, testando separar especificamente os
primeiros jogos de cada temporada.

## Abordagem

Usando a coluna `Game Week` do CSV (número da rodada), separamos as
apostas de 2023-2026 (Over 2.5 e BTTS, critérios campeões) em
"primeiras N rodadas" vs. "demais rodadas", com N∈{5,10}, e comparamos
ROI/z dos dois grupos — além do ano a ano dentro do grupo "início".

## Resultado — o padrão não é consistente

**Over 2.5:**

| Corte | Início | Resto |
|---|---|---|
| 5 rodadas | n=56, ROI+15,6%, z=+1,11 | n=222, ROI+7,0%, z=+0,97 |
| 10 rodadas | n=110, ROI+0,6%, z=+0,06 | n=168, ROI+14,0%, z=+1,70 |

**BTTS:**

| Corte | Início | Resto |
|---|---|---|
| 5 rodadas | n=57, ROI+13,8%, z=+1,06 | n=199, ROI+16,6%, z=+2,40 |
| 10 rodadas | n=98, ROI+20,3%, z=+2,07 | n=158, ROI+13,3%, z=+1,70 |

O resultado **inverte de sinal** dependendo do corte escolhido (5 vs.
10 rodadas) nos dois mercados — às vezes o início parece melhor que o
resto, às vezes pior. Ano a ano dentro do grupo "início" também não
mostra consistência (Over 2.5, primeiras 5 rodadas: 2023 +2,6%, 2024
+34,3%, 2025 −6,7%, 2026 +44,4% — sem padrão, e com n=11-20 por ano,
não conclusivo isoladamente).

## Interpretação

Não há evidência de que "jogos de início de temporada" sejam
sistematicamente piores pra estes dois critérios — se houvesse, o
padrão apareceria de forma consistente em ambos os cortes e nos dois
mercados, o que não acontece. A queda de ROI observada ao estender o
histórico (n=221→278 no Over 2.5) provavelmente reflete algo mais
simples: os ~57 jogos adicionais eram especificamente do **início de
2023** (o único momento em que a falta de histórico anterior a
2016-2022 causava o corte por `min_jogos_historico`) — um efeito único
de bootstrap do conjunto de dados, não um padrão recorrente de "início
de cada temporada é pior".

## O que isso muda na prática

Nada — não criamos nenhuma regra de excluir jogos de início de
temporada do critério, porque os números não sustentam essa hipótese.
Mantém a recomendação já vigente sem alteração.

## Limitações

- `n` por bloco é pequeno (11-56 por ano/corte) — o padrão observado
  (inconsistência) é o achado em si, mas nenhum bloco individual é
  conclusivo isoladamente.
- Não testamos cortes intermediários (6, 7, 8, 9 rodadas) — a inversão
  entre 5 e 10 rodadas sugere que rodadas específicas dentro dessa
  janela concentram o efeito, mas não isolamos exatamente quais.

Reprodução: `metodologia_pesos/retrospectiva.py`
(`rodar_retrospectiva`/`simular_apostas`), script de orquestração
ad-hoc (não versionado), usando a coluna `Game Week` dos CSVs do
FootyStats.
