# Grid com holdout nas 3 ligas novas (2026-09-18)

Cada liga calibrada por conta própria (inclusive fator casa `k_mando`),
treino 2024-2025 e **holdout 2026** — o holdout nunca participa da escolha.

Grid de gols: 192 combinações (`k_mando × usar_estilo × filtro_aderencia ×`
`multiplicador_dp × limite_unilateral`), mesmo espaço usado no Brasileirão.
Grid de cartões: 18 combinações (`k_mando × peso_arbitro × outlier de cartões`) —
`peso_arbitro=0.0` é o teste de ablação: mede se o árbitro agrega algo de verdade.

**Aviso de comparação múltipla**: com centenas de combinações, o melhor z de TREINO
é quase sempre sorte. A coluna que importa é o HOLDOUT. `n p/ z=2` = quantas apostas
seriam necessárias pro ROI observado virar significante (distingue 'sem edge' de
'sem amostra').

## Championship (Inglaterra)

### BTTS (casa bet365, edge>=5%)

192 de 192 combinações avaliáveis. Top 8 por z de TREINO (2024-2025), com o holdout 2026 ao lado — holdout é o que vale:

| k_mando | estilo | filtro | dp | outlier | TREINO | HOLDOUT 2026 | n p/ z=2 |
|---|---|---|---|---|---|---|---|
| None | sim | 0.5 | 1.5 | 4 | n=74 ROI=+20.4% z=+1.88 | n=22 ROI=+9.3% z=+0.46 | 108 |
| 1.0 | sim | 0.5 | 1.5 | 4 | n=74 ROI=+20.4% z=+1.88 | n=22 ROI=+9.3% z=+0.46 | 108 |
| 0.7 | sim | 0.8 | 2.5 | 2 | n=177 ROI=+12.6% z=+1.76 | n=64 ROI=+4.5% z=+0.41 | 316 |
| 0.7 | sim | 0.8 | 2.5 | 4 | n=177 ROI=+12.6% z=+1.76 | n=64 ROI=+4.5% z=+0.41 | 316 |
| None | sim | 0.5 | 1.5 | 2 | n=75 ROI=+18.8% z=+1.74 | n=22 ROI=+9.3% z=+0.46 | 125 |
| 1.0 | sim | 0.5 | 1.5 | 2 | n=75 ROI=+18.8% z=+1.74 | n=22 ROI=+9.3% z=+0.46 | 125 |
| None | sim | 0.0 | 1.5 | 4 | n=74 ROI=+17.7% z=+1.62 | n=22 ROI=+8.8% z=+0.44 | 141 |
| 1.0 | sim | 0.0 | 1.5 | 4 | n=74 ROI=+17.7% z=+1.62 | n=22 ROI=+8.8% z=+0.44 | 141 |

**Melhor por holdout**: k_mando=0.2, estilo=sim, filtro=0.8 → holdout n=51 ROI=+18.7% z=+1.57. Ano a ano (período todo): 2024 n=30 ROI=-13.2% z=-0.76; 2025 n=104 ROI=+6.5% z=+0.68; 2026 n=51 ROI=+18.7% z=+1.57

### Over 2.5 (casa Sbo, edge>=8%)

146 de 192 combinações avaliáveis. Top 8 por z de TREINO (2024-2025), com o holdout 2026 ao lado — holdout é o que vale:

| k_mando | estilo | filtro | dp | outlier | TREINO | HOLDOUT 2026 | n p/ z=2 |
|---|---|---|---|---|---|---|---|
| 0.2 | não | 0.8 | 1.5 | 4 | n=77 ROI=-1.7% z=-0.14 | n=32 ROI=+7.6% z=+0.41 | 43207 |
| 0.2 | não | 0.8 | 1.5 | 2 | n=82 ROI=-2.5% z=-0.22 | n=36 ROI=+5.4% z=+0.32 | — |
| 0.5 | sim | 0.8 | 1.5 | 4 | n=92 ROI=-2.9% z=-0.26 | n=35 ROI=+28.5% z=+1.65 | 1320 |
| 0.2 | sim | 0.65 | 1.5 | 4 | n=63 ROI=-3.5% z=-0.26 | n=25 ROI=+45.1% z=+2.39 | 411 |
| 0.5 | sim | 0.8 | 1.5 | 2 | n=97 ROI=-3.8% z=-0.36 | n=37 ROI=+27.5% z=+1.63 | 1896 |
| 0.2 | sim | 0.65 | 1.5 | 2 | n=66 ROI=-4.9% z=-0.38 | n=28 ROI=+42.2% z=+2.39 | 519 |
| 0.7 | sim | 0.8 | 1.5 | 4 | n=87 ROI=-4.4% z=-0.39 | n=31 ROI=+19.8% z=+1.05 | 11103 |
| 0.7 | sim | 0.8 | 1.5 | 2 | n=91 ROI=-4.4% z=-0.40 | n=33 ROI=+19.2% z=+1.05 | 12212 |

**Melhor por holdout**: k_mando=0.2, estilo=sim, filtro=0.65 → holdout n=25 ROI=+45.1% z=+2.39. Ano a ano (período todo): 2024 n=19 ROI=+5.9% z=+0.25; 2025 n=44 ROI=-7.6% z=-0.47; 2026 n=25 ROI=+45.1% z=+2.39

