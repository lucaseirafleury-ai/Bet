# Recalibração por ROI com 3 temporadas de treino (2023+2024+2025 → holdout 2026)

## Contexto

`docs/retrospectiva_roi_calibracao_holdout_2026-08-25.md` (treino só
2025) concluiu que nenhuma combinação batia os parâmetros neutros.
Lucas subiu **2024 e 2023 completos** (Série A e B, 380 jogos/liga cada)
depois disso — mesma sugestão do relatório anterior ("mais dado pode
ajudar a separar sinal de ruído na Série B"). Este relatório repete o
mesmo grid (48 combinações × 4 limiares de edge × 2 mercados), agora
treinado em **2023+2024+2025** (~1.140 jogos/liga) e validado no mesmo
holdout de sempre (2026).

## O baseline neutro mudou com mais histórico — em direções opostas por liga

Antes de comparar o grid, vale recalcular o baseline neutro
(`k_mando=None, usar_estilo=True, filtro_aderencia=0.65`) com o
histórico maior, já que o holdout usa jogos de 2026 cujo "últimos 15
jogos" agora podem incluir mais de 2023/2024 em vez de ficarem sem dado
suficiente:

| Liga | Mercado | Edge | n | ROI | z-score | ROI/z anterior (treino só 2025) |
|---|---|---|---|---|---|---|
| Série A | Over 2.5 | 8% | 42 | +35.8% | **+2.24** | igual (mesmo achado) |
| Série A | BTTS | 8% | 44 | +37.8% | **+2.91** | melhorou (era +35.7%/z=2.72) |
| Série B | Over 2.5 | 0% | 85 | **−7.9%** | −0.63 | piorou (era +6.8%/z=0.53) |
| Série B | Over 2.5 | 5% | 57 | **−21.4%** | −1.42 | piorou (era −4.0%/z=−0.27) |
| Série B | BTTS | 0% | 79 | +0.1% | +0.01 | parecido (era +1.3%/z=0.12) |

**Série A ficou mais forte ainda** com mais histórico — reforça que o
achado de edge=8% é real, não fruto de pouco dado. **Série B piorou**:
o que antes parecia "levemente positivo" em Over 2.5 (ROI+6.8%) vira
claramente negativo (ROI−7.9% a −21.4%) com histórico mais robusto —
sinal de que a estimativa anterior era ruído, não vantagem real.

## O grid, desta vez, encontrou algo pra Série B — mas só em BTTS

| Liga | Mercado | Config | Edge | n | ROI holdout | z-score | Bate o neutro? |
|---|---|---|---|---|---|---|---|
| Série A | Over 2.5 | melhor do grid | 8% | 41 | +23.0% | +1.40 | **Não** (neutro: z=2.24) |
| Série A | BTTS | melhor do grid | 5% | 63 | +17.0% | +1.45 | **Não** (neutro: z=2.91) |
| Série B | Over 2.5 | melhor do grid | 0% | 85 | −3.7% | −0.30 | Não bate, mas menos ruim que o neutro (−0.63) |
| Série B | BTTS | `k=0.2, estilo=True, filtro=0/0.5`, edge=5% | — | 53 | **+13.8%** | **+1.04** | **Sim** (neutro: z≈0.01) |
| Série B | BTTS | `k=0.2, estilo=True, filtro=0.65`, edge=5% | — | 54 | +11.7% | +0.89 | Sim (candidato vizinho, mesmo padrão) |

Como nas rodadas anteriores, o grid **não supera o neutro na Série A**
— o padrão de sempre: otimizar por ROI de treino tende a escolher
limiares de edge mais baixos/populosos, mas o sinal genuíno mora no
limiar mais seletivo (8%), que segue sub-representado no treino mesmo
com 3x mais dado.

**Na Série B BTTS, pela primeira vez, o grid encontra algo melhor que o
neutro** — `k_mando=0.2, usar_estilo=True, filtro_aderencia∈{0, 0.5,
0.65}, limiar_edge=5%`. Não é uma única célula isolada (sinal de sorte):
3 valores vizinhos de `filtro_aderencia` dão resultado parecido
(ROI +11,7% a +13,8%, z 0,89-1,04) — mais parecido com um platô robusto
que com um pico de ruído. Ainda assim, `z≈1` está longe do limiar de
significância (~2) usado nas outras rodadas — **é promissor, não
comprovado**.

## Recomendação atualizada

1. **Série A**: mantém — parâmetros neutros, `limiar_edge≥8%` em Over
   2.5/BTTS. Achado reforçado com mais dado (BTTS z subiu de 2,72 pra
   2,91).
2. **Série B Over 2.5**: mantém — não apostar por este critério. Ficou
   ainda mais claro que não há vantagem aqui (ROI negativo em todos os
   limiares testados, com neutro ou grid).
3. **Série B BTTS**: **atualiza** — considerar
   `k_mando=0.2, usar_estilo=True, filtro_aderencia=0.65,
   limiar_edge=5%` como critério de aposta em vez do neutro puro (que
   está em z≈0). `z≈0,9-1,0` não é prova, mas é o primeiro sinal
   positivo mais consistente que a Série B mostrou em qualquer rodada
   até agora — vale observar mais holdout antes de tratar como
   validado.

## Limitações

- Mesma ressalva de sempre, mas atenuada: agora são 3 temporadas de
  treino (2023-2025, ~1.140 jogos/liga) e 1 de holdout (2026 parcial) —
  ainda 1 holdout só, mas a base de treino triplicou.
- `n` de holdout continua pequeno (36-86 apostas por linha) — os
  z-scores aqui são estimativas, não certezas.
- Mesmas 2 limitações estruturais de sempre: só Over 2.5/BTTS simulados;
  Over 2.5 usa odd sem remover margem (só um lado disponível no CSV).

Reprodução: mesmo `metodologia_pesos/retrospectiva.py`
(`rodar_retrospectiva`/`simular_apostas`), scripts de orquestração
ad-hoc trocando as fontes de treino pra
`data/footystats_{liga}_2023|2024|2025/matches.csv` concatenados.
