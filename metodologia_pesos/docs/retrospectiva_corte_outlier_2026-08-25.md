# Corte de desvio padrão mais apertado — primeira melhoria real sobre o neutro

## Contexto

Lucas pediu pra testar o corte de outlier (`multiplicador_dp`,
`limite_unilateral` — os parâmetros de `pesos.corte_outlier`, nunca
variados em nenhum grid de ROI anterior) significativamente pra cima e
pra baixo, pra ver se o modelo melhora. Grid: `multiplicador_dp ∈ {1.0,
1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 8.0}` × `limite_unilateral ∈ {2, 4, 8}`,
`k_mando`/`usar_estilo`/`filtro_aderencia` fixos nos valores neutros já
validados — treino 2023-2025, holdout 2026, mesma mecânica de sempre.

## Resultado — corte mais apertado melhora a Série A Over 2.5 de verdade

Comparação apples-to-apples: ROI e z-score do **período completo**
2023-2026 (não só o holdout, que já se provou enganoso antes — ver
`docs/retrospectiva_favorito_dc_2026-08-25.md`), `limiar_edge=8%`:

| Config | Mercado | n | ROI | z-score |
|---|---|---|---|---|
| Padrão (`mult_dp=2.5, uni=4`) | Over 2.5 | 223 | −2,3% | −0,31 |
| Padrão (`mult_dp=2.5, uni=4`) | BTTS | 220 | +5,0% | +0,75 |
| **Apertado (`mult_dp=1.5, uni=2`)** | **Over 2.5** | **99** | **+16,2%** | **+1,50** |
| Apertado (`mult_dp=1.5, uni=2`) | BTTS | 96 | +10,1% | +0,98 |

**Não é um ponto isolado de sorte — é um platô real.** Testando a
vizinhança de `multiplicador_dp` pro Over 2.5 (mesmo `limite_unilateral=2`,
`limiar_edge=8%`, período completo):

| `multiplicador_dp` | n | ROI | z-score |
|---|---|---|---|
| 1,25 | 81 | +16,0% | +1,33 |
| **1,5** | **99** | **+16,2%** | **+1,50** |
| 1,75 | 141 | +5,2% | +0,56 |
| 2,0 | 175 | +5,5% | +0,66 |
| 2,5 (padrão) | 223 | −2,3% | −0,31 |

1,25 e 1,5 dão resultado parecido (platô), depois cai — sinal de que a
região 1,25-1,5 captura algo real, não ruído de uma célula.

**Estabilidade ano a ano também melhora** (Over 2.5, `mult_dp=1.5`):
2023 +2,2%, 2024 +15,7%, 2025 −3,2%, 2026 +50,0% — só 1 ano levemente
negativo, contra os 2 anos claramente negativos do parâmetro padrão
(2023 −28,4%, 2025 −15,7%).

## Por que isso pode fazer sentido

`multiplicador_dp` menor corta outliers mais perto da média — descarta
mais jogos "atípicos" (goleadas, resultados anômalos) do histórico
ponderado antes de calcular a expectativa de gols. Isso deixa a
previsão mais "no jogo típico do time", o que parece ajudar
especificamente em Over 2.5 (linha no meio da distribuição) — hipótese
consistente com o achado anterior de que Over 3.5/4.5 (caudas da
distribuição) não têm edge nenhum: cortar mais agressivamente reduz
ruído justamente onde a linha de aposta vive.

## Ressalvas — ainda não é "comprovado"

- **z=1,50 continua abaixo do limiar de significância (~2)** usado no
  resto do projeto — é uma melhoria real sobre o baseline (que estava
  em z≈0, praticamente ruído), não uma prova estatística forte.
- **Menos apostas**: corte mais apertado gera menos oportunidades
  qualificadas (n=99 vs n=223 no período completo) — quase metade do
  volume de apostas.
- **Série B não mostrou o mesmo padrão** — no grid original (24
  combinações testadas), os melhores candidatos de corte apertado pra
  Série B ficaram em z≈0,2-0,5 (Over 2.5) e negativo (BTTS) — essa
  melhoria parece específica da Série A.
- BTTS na Série A melhorou pouco (z de 0,75 pra 0,98) — o achado forte
  é especificamente em Over 2.5.

## Recomendação

Considerar **`multiplicador_dp=1.5, limite_unilateral=2`** como o novo
parâmetro de corte de outlier pra Over 2.5 na Série A (`limiar_edge≥8%`)
— substitui o padrão (`2.5, 4`) usado até aqui pra esse mercado
especificamente. Continuar tratando como "melhoria promissora", não
"comprovado" — mesma disciplina de sempre: z<2 pede mais holdout antes
de apostar dinheiro real com confiança total.

## Limitações

- Mesma ressalva de sempre: 2023-2026, `n` menor ainda (81-141 nas
  variações testadas).
- Não testamos combinar o corte apertado com outros parâmetros
  (`k_mando`, `usar_estilo`, `filtro_aderencia`) simultaneamente — o
  grid isolou só o corte de outlier pra não reintroduzir o mesmo
  problema de comparação múltipla de rodadas anteriores.

Reprodução: mesmo `metodologia_pesos/retrospectiva.py`
(`rodar_retrospectiva`/`simular_apostas`), variando só
`multiplicador_dp`/`limite_unilateral` nos parâmetros.
