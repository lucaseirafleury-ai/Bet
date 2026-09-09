# De acerto pra vantagem real: simulação de aposta contra odd de mercado

Até aqui toda calibração media **acerto** (Over/Under 2.5, BTTS) contra
o resultado real. Isso não mede vantagem competitiva — uma taxa de
acerto de 55% pode não valer nada se a odd de mercado já embutia 55% ou
mais de probabilidade. Vantagem real é **a probabilidade do modelo ser
maior que a probabilidade implícita na odd real**, e só then vale apostar.

## O que foi construído

- `pesos.probabilidade_over(media_total_gols, linha)` — converte os gols
  esperados do modelo numa probabilidade de Over/Under via Poisson (soma
  de duas Poisson independentes = Poisson da soma, não precisa modelar a
  dependência entre os times pra isso).
- `pesos.probabilidade_btts(gols_pró, gols_contra)` — mesma ideia pro BTTS.
- `pesos.probabilidade_implicita`/`probabilidade_implicita_2vias` —
  converte odd real em probabilidade, removendo a margem da casa quando
  os dois lados do mercado estão disponíveis (BTTS Sim/Não). Over 2.5 só
  tem a odd de um lado no CSV do FootyStats — a implícita fica sem
  remover margem (superestima um pouco a probabilidade real do mercado).
- `retrospectiva.simular_apostas(jogos, mercado, limiar_edge, stake)` —
  só aposta quando `prob_modelo - prob_mercado >= limiar_edge`, com odd e
  resultado reais. Retorna lucro, ROI, taxa de acerto DAS APOSTAS FEITAS
  (diferente da taxa de acerto de todos os jogos avaliados).

**Limite importante**: só simula apostar no lado "over"/"sim" — o CSV não
traz a odd do lado oposto (Under 2.5), então não dá pra simular apostar
contra o modelo nesse mercado ainda.

## Resultado — holdout 2026, parâmetros já validados por liga

| Liga | Mercado | Limiar edge | Apostas | Taxa acerto | Lucro | ROI | z-score |
|---|---|---|---|---|---|---|---|
| Série A | Over 2.5 | 0% | 93 | 51.6% | +8.33u | **+9.0%** | 0.81 |
| Série A | Over 2.5 | 5% | 50 | 58.0% | +10.95u | **+21.9%** | 1.47 |
| Série A | Over 2.5 | 8% | 42 | 64.3% | +15.03u | **+35.8%** | **2.24** |
| Série A | BTTS | 0% | 101 | 55.4% | +3.83u | +3.8% | 0.41 |
| Série A | BTTS | 5% | 65 | 61.5% | +10.32u | +15.9% | 1.38 |
| Série A | BTTS | 8% | 43 | 72.1% | +15.34u | **+35.7%** | **2.72** |
| Série B | Over 2.5 | 0% | 81 | 46.9% | +5.51u | +6.8% | 0.53 |
| Série B | Over 2.5 | 5% | 59 | 42.4% | −2.34u | −4.0% | −0.27 |
| Série B | Over 2.5 | 8% | 43 | 41.9% | −2.46u | −5.7% | −0.33 |
| Série B | BTTS | 0-8% | 38-76 | ~51-53% | ~+1u | ~+1-3% | ~0.1-0.2 |

(z-score = lucro médio por aposta ÷ erro-padrão — acima de ~2 é
estatisticamente distinguível de zero mesmo numa amostra pequena; abaixo
de ~1.5 trata como ruído.)

## Achado principal — inverte a intuição que vínhamos construindo

**A Série A (parâmetros "neutros", nunca validados por acerto) mostra
vantagem real e crescente com a exigência de edge — inclusive
estatisticamente significativa nos limiares mais altos** (z=2.24 e
z=2.72). Quanto mais o modelo discorda da odd, mais ele acerta — é
exatamente a assinatura de uma probabilidade bem calibrada.

**A Série B (parâmetros escolhidos porque maximizavam ACERTO de
Over/Under no holdout) não mostra vantagem nenhuma contra a odd real** —
e piora conforme se exige mais edge no mercado de Over 2.5 (ROI vai de
+6.8% pra −5.7%). Ou seja: **o parâmetro que mais acerta não é o mesmo
que mais bate a odd de mercado.**

Interpretação: `k=0.5, sem estilo, filtro=0.8` (o "vencedor" da Série B)
provavelmente aprendeu a concordar mais com o consenso do mercado — acerta
mais porque replica o que a odd já dizia, não porque enxerga algo que o
mercado não vê. Isso explica acerto alto e edge baixo/negativo ao mesmo
tempo. A Série A, sem esse ajuste, pode estar preservando desacordos
genuínos com o mercado que se provam certos com mais frequência.

## Isso muda o que "parâmetro bom" significa

Otimizar por acerto (Over/Under, BTTS) e otimizar por vantagem real
(edge contra a odd) **não são a mesma coisa — podem apontar em direções
opostas**, como esse resultado mostra na Série B. Se o objetivo é vantagem
competitiva de verdade (não só taxa de acerto), a métrica de otimização
tem que virar ROI/edge simulado, não `acerto_over25`.

## Recomendação

1. **Refazer a calibração de `k_mando`/`usar_estilo`/`filtro_aderencia`
   otimizando por ROI simulado (`simular_apostas`), não por acerto** —
   provável próximo passo de maior alavancagem pra vantagem competitiva
   real. O grid/holdout já existe, só troca a métrica de ordenação.
2. Tratar o resultado da Série A como promissor mas preliminar — só 1
   temporada de holdout, `n` de 42-93 apostas por linha. `z>2` é um bom
   sinal, não uma prova; vale confirmar com mais dado antes de apostar
   dinheiro real nisso.
3. Conseguir a odd do lado "Under" (hoje só temos "Over") permitiria
   simular apostar dos dois lados, não só a favor do Over/BTTS.

## Limitações

- Só 2 mercados simulados (Over 2.5, BTTS) — os outros 10 indicadores
  Pró/Contra não têm probabilidade/odd implementada ainda.
- Over 2.5 usa probabilidade implícita SEM remover margem (só a odd de um
  lado) — o edge real pode ser um pouco menor do que o calculado aqui.
- 1 temporada de holdout — mesma ressalva de sempre.
- O modelo de probabilidade (Poisson simples sobre os gols esperados) é
  uma aproximação — não modela correlação entre os times nem viés de
  favorito/zebra que o mercado às vezes precifica separadamente.

Reprodução: `metodologia_pesos/retrospectiva.py`, `simular_apostas()`
sobre `rodar_retrospectiva(..., timestamp_minimo=<2026>)["jogos"]`.
