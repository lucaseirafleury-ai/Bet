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

## Liga Profesional (Argentina)

### BTTS (casa bet365, edge>=5%)

48 de 48 combinações avaliáveis. Top 8 por z de TREINO (2024-2025), com o holdout 2026 ao lado — holdout é o que vale:

| k_mando | estilo | filtro | dp | outlier | TREINO | HOLDOUT 2026 | n p/ z=2 |
|---|---|---|---|---|---|---|---|
| 0.7 | não | 0.8 | 1.5 | 2 | n=92 ROI=+5.2% z=+0.43 | n=58 ROI=-13.0% z=-0.91 | — |
| 0.35 | não | 0.8 | 1.5 | 2 | n=112 ROI=+2.5% z=+0.23 | n=66 ROI=-9.7% z=-0.72 | — |
| 0.5 | não | 0.8 | 1.5 | 2 | n=97 ROI=-0.0% z=-0.00 | n=62 ROI=-7.4% z=-0.53 | — |
| 0.2 | não | 0.8 | 1.5 | 2 | n=128 ROI=-0.1% z=-0.01 | n=72 ROI=-8.4% z=-0.65 | — |
| 0.35 | sim | 0.8 | 1.5 | 2 | n=125 ROI=-3.4% z=-0.33 | n=84 ROI=-10.6% z=-0.89 | — |
| 0.5 | sim | 0.5 | 1.5 | 2 | n=76 ROI=-6.1% z=-0.46 | n=56 ROI=-5.5% z=-0.37 | — |
| None | não | 0.8 | 1.5 | 2 | n=99 ROI=-6.1% z=-0.52 | n=60 ROI=-12.7% z=-0.91 | — |
| 1.0 | não | 0.8 | 1.5 | 2 | n=99 ROI=-6.1% z=-0.52 | n=60 ROI=-12.7% z=-0.91 | — |

**Melhor por holdout**: k_mando=None, estilo=sim, filtro=0.65 → holdout n=53 ROI=+5.5% z=+0.35. Ano a ano (período todo): 2024 n=25 ROI=+1.4% z=+0.06; 2025 n=49 ROI=-32.0% z=-2.05; 2026 n=53 ROI=+5.5% z=+0.35

### Over 2.5 (casa Sbo, edge>=8%)

Nenhuma combinação com n>=15 em treino E holdout — liga sem amostra suficiente pra este mercado.

### Cartões+Árbitro (bet365, edge>=10%)

18 de 18 combinações avaliáveis:

| k_mando | peso árbitro | outlier cartões | TREINO | HOLDOUT 2026 | n p/ z=2 |
|---|---|---|---|---|---|
| 0.7 | 0.5 | 2 | n=231 ROI=+4.9% z=+0.80 | n=150 ROI=+2.3% z=+0.30 | 2285 |
| 0.7 | 0.5 | 3.8 | n=231 ROI=+4.1% z=+0.67 | n=157 ROI=+5.7% z=+0.78 | 1511 |
| 0.7 | 0.3 | 2 | n=284 ROI=+3.2% z=+0.59 | n=193 ROI=+2.4% z=+0.37 | 4022 |
| None | 0.5 | 2 | n=242 ROI=+3.4% z=+0.57 | n=150 ROI=+7.5% z=+1.01 | 1369 |
| None | 0.5 | 3.8 | n=246 ROI=+3.2% z=+0.54 | n=151 ROI=+8.0% z=+1.08 | 1338 |
| None | 0.3 | 2 | n=292 ROI=+2.8% z=+0.52 | n=189 ROI=+2.8% z=+0.42 | 4329 |
| None | 0.0 | 3.8 | n=443 ROI=+0.6% z=+0.12 | n=248 ROI=+2.4% z=+0.41 | 23715 |
| 0.7 | 0.3 | 3.8 | n=286 ROI=+0.7% z=+0.12 | n=192 ROI=+3.9% z=+0.59 | 8909 |
| None | 0.3 | 3.8 | n=290 ROI=+0.2% z=+0.03 | n=190 ROI=+4.1% z=+0.61 | 11418 |
| 0.35 | 0.5 | 2 | n=229 ROI=+0.2% z=+0.03 | n=152 ROI=-1.9% z=-0.26 | — |
| 0.35 | 0.5 | 3.8 | n=228 ROI=-0.3% z=-0.05 | n=157 ROI=-1.1% z=-0.15 | — |
| 0.35 | 0.0 | 3.8 | n=452 ROI=-1.1% z=-0.24 | n=264 ROI=+0.8% z=+0.15 | — |
| None | 0.0 | 2 | n=443 ROI=-1.2% z=-0.26 | n=249 ROI=+1.3% z=+0.23 | — |
| 0.7 | 0.0 | 3.8 | n=444 ROI=-1.2% z=-0.26 | n=255 ROI=+1.7% z=+0.30 | — |
| 0.35 | 0.0 | 2 | n=446 ROI=-1.5% z=-0.33 | n=267 ROI=+0.6% z=+0.10 | — |
| 0.35 | 0.3 | 2 | n=289 ROI=-2.6% z=-0.47 | n=191 ROI=+3.1% z=+0.47 | — |
| 0.7 | 0.0 | 2 | n=443 ROI=-2.2% z=-0.51 | n=256 ROI=+1.4% z=+0.25 | — |
| 0.35 | 0.3 | 3.8 | n=298 ROI=-5.3% z=-0.99 | n=195 ROI=+2.7% z=+0.41 | — |

**Melhor por holdout**: k_mando=None, peso_arbitro=0.5 → holdout n=151 ROI=+8.0% z=+1.08. Ano a ano: 2024 n=53 ROI=+0.9% z=+0.07; 2025 n=193 ROI=+3.8% z=+0.57; 2026 n=151 ROI=+8.0% z=+1.08

## MLS (EUA/Canadá)

### BTTS (casa bet365, edge>=5%)

48 de 48 combinações avaliáveis. Top 8 por z de TREINO (2024-2025), com o holdout 2026 ao lado — holdout é o que vale:

| k_mando | estilo | filtro | dp | outlier | TREINO | HOLDOUT 2026 | n p/ z=2 |
|---|---|---|---|---|---|---|---|
| None | sim | 0.0 | 1.5 | 2 | n=156 ROI=+2.9% z=+0.47 | n=68 ROI=-4.2% z=-0.47 | 40693 |
| None | sim | 0.5 | 1.5 | 2 | n=156 ROI=+2.9% z=+0.47 | n=69 ROI=-3.4% z=-0.39 | 24451 |
| 1.0 | sim | 0.0 | 1.5 | 2 | n=156 ROI=+2.9% z=+0.47 | n=68 ROI=-4.2% z=-0.47 | 40693 |
| 1.0 | sim | 0.5 | 1.5 | 2 | n=156 ROI=+2.9% z=+0.47 | n=69 ROI=-3.4% z=-0.39 | 24451 |
| None | sim | 0.65 | 1.5 | 2 | n=166 ROI=+1.7% z=+0.28 | n=67 ROI=+1.3% z=+0.15 | 9183 |
| 1.0 | sim | 0.65 | 1.5 | 2 | n=166 ROI=+1.7% z=+0.28 | n=67 ROI=+1.3% z=+0.15 | 9183 |
| 0.7 | não | 0.0 | 1.5 | 2 | n=158 ROI=+1.4% z=+0.22 | n=67 ROI=+2.7% z=+0.30 | 7335 |
| 0.7 | não | 0.5 | 1.5 | 2 | n=158 ROI=+1.4% z=+0.22 | n=67 ROI=+2.7% z=+0.30 | 7335 |

**Melhor por holdout**: k_mando=0.5, estilo=não, filtro=0.8 → holdout n=75 ROI=+7.7% z=+0.91. Ano a ano (período todo): 2024 n=97 ROI=-2.4% z=-0.30; 2025 n=103 ROI=-4.5% z=-0.58; 2026 n=75 ROI=+7.7% z=+0.91

### Over 2.5 (casa Sbo, edge>=8%)

48 de 48 combinações avaliáveis. Top 8 por z de TREINO (2024-2025), com o holdout 2026 ao lado — holdout é o que vale:

| k_mando | estilo | filtro | dp | outlier | TREINO | HOLDOUT 2026 | n p/ z=2 |
|---|---|---|---|---|---|---|---|
| 0.2 | não | 0.65 | 1.5 | 2 | n=92 ROI=+1.4% z=+0.16 | n=42 ROI=-5.1% z=-0.38 | — |
| 0.2 | sim | 0.0 | 1.5 | 2 | n=89 ROI=+1.2% z=+0.13 | n=41 ROI=-15.0% z=-1.09 | — |
| 0.2 | sim | 0.5 | 1.5 | 2 | n=89 ROI=+1.2% z=+0.13 | n=41 ROI=-15.0% z=-1.09 | — |
| 0.2 | não | 0.0 | 1.5 | 2 | n=91 ROI=+0.7% z=+0.08 | n=42 ROI=-5.1% z=-0.38 | — |
| 0.2 | não | 0.5 | 1.5 | 2 | n=91 ROI=+0.7% z=+0.08 | n=42 ROI=-5.1% z=-0.38 | — |
| 0.7 | sim | 0.0 | 1.5 | 2 | n=54 ROI=+0.7% z=+0.06 | n=24 ROI=-10.5% z=-0.56 | — |
| 0.7 | sim | 0.5 | 1.5 | 2 | n=54 ROI=+0.7% z=+0.06 | n=24 ROI=-10.5% z=-0.56 | — |
| 0.35 | sim | 0.0 | 1.5 | 2 | n=74 ROI=-1.4% z=-0.14 | n=33 ROI=-19.8% z=-1.27 | — |

**Melhor por holdout**: k_mando=0.7, estilo=não, filtro=0.8 → holdout n=36 ROI=+3.0% z=+0.20. Ano a ano (período todo): 2024 n=45 ROI=+20.2% z=+1.64; 2025 n=49 ROI=-29.7% z=-2.41; 2026 n=36 ROI=+3.0% z=+0.20

### Cartões+Árbitro (bet365, edge>=10%)

18 de 18 combinações avaliáveis:

| k_mando | peso árbitro | outlier cartões | TREINO | HOLDOUT 2026 | n p/ z=2 |
|---|---|---|---|---|---|
| None | 0.5 | 2 | n=256 ROI=+4.8% z=+0.85 | n=127 ROI=+4.9% z=+0.60 | 1419 |
| None | 0.3 | 3.8 | n=321 ROI=+4.2% z=+0.83 | n=156 ROI=-0.4% z=-0.06 | 4588 |
| 0.7 | 0.3 | 3.8 | n=308 ROI=+3.4% z=+0.66 | n=169 ROI=+4.9% z=+0.69 | 2152 |
| None | 0.5 | 3.8 | n=256 ROI=+3.5% z=+0.61 | n=126 ROI=+5.6% z=+0.68 | 1908 |
| None | 0.3 | 2 | n=323 ROI=+3.0% z=+0.59 | n=163 ROI=-0.0% z=-0.00 | 8359 |
| 0.7 | 0.3 | 2 | n=306 ROI=+3.0% z=+0.58 | n=174 ROI=+2.0% z=+0.29 | 4750 |
| 0.7 | 0.5 | 2 | n=251 ROI=+2.2% z=+0.37 | n=125 ROI=+3.6% z=+0.43 | 4908 |
| 0.7 | 0.0 | 3.8 | n=529 ROI=+1.0% z=+0.25 | n=209 ROI=-8.2% z=-1.27 | — |
| 0.7 | 0.5 | 3.8 | n=258 ROI=+1.4% z=+0.24 | n=123 ROI=+5.3% z=+0.63 | 4861 |
| None | 0.0 | 2 | n=539 ROI=+0.4% z=+0.11 | n=218 ROI=-8.8% z=-1.39 | — |
| None | 0.0 | 3.8 | n=530 ROI=+0.4% z=+0.09 | n=212 ROI=-7.9% z=-1.24 | — |
| 0.7 | 0.0 | 2 | n=531 ROI=+0.0% z=+0.01 | n=217 ROI=-10.6% z=-1.68 | — |
| 0.35 | 0.5 | 2 | n=259 ROI=-1.7% z=-0.30 | n=124 ROI=+13.7% z=+1.67 | 3142 |
| 0.35 | 0.3 | 2 | n=317 ROI=-1.8% z=-0.34 | n=163 ROI=-0.5% z=-0.07 | — |
| 0.35 | 0.0 | 3.8 | n=536 ROI=-1.6% z=-0.39 | n=217 ROI=-9.9% z=-1.56 | — |
| 0.35 | 0.0 | 2 | n=546 ROI=-1.6% z=-0.41 | n=219 ROI=-13.1% z=-2.09 | — |
| 0.35 | 0.3 | 3.8 | n=308 ROI=-2.5% z=-0.47 | n=159 ROI=+0.8% z=+0.12 | — |
| 0.35 | 0.5 | 3.8 | n=257 ROI=-3.7% z=-0.64 | n=122 ROI=+12.7% z=+1.52 | 13493 |

**Melhor por holdout**: k_mando=0.35, peso_arbitro=0.5 → holdout n=124 ROI=+13.7% z=+1.67. Ano a ano: 2024 n=82 ROI=+1.3% z=+0.13; 2025 n=177 ROI=-3.1% z=-0.45; 2026 n=124 ROI=+13.7% z=+1.67

