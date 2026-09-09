# Recalibração por ROI (treino 2025 / holdout 2026) — não bateu o neutro

## Contexto

`docs/retrospectiva_roi_2026-08-24.md` mostrou que **acerto e vantagem
real (ROI contra odd de mercado) não são a mesma coisa** — os parâmetros
"vencedores" da Série B por acerto (`k=0.5, sem estilo, filtro=0.8`) têm
ROI negativo contra o mercado, enquanto os parâmetros neutros da Série A
mostram edge real e crescente. A recomendação de lá era: recalibrar
`k_mando`/`usar_estilo`/`filtro_aderencia` otimizando **ROI simulado**, não
acerto — é isso que esta rodada faz. Lucas confirmou: *"O que importa de
verdade é ter um modelo que vença das odds pré jogo."*

## Metodologia

Para cada liga: grid de 48 combinações
(`k_mando ∈ {None, 0.2, 0.35, 0.5, 0.7, 1.0} × usar_estilo ∈ {True,
False} × filtro_aderencia ∈ {0, 0.5, 0.65, 0.8}`), treinado **só em
2025** (`min_jogos_historico=8, min_jogos_estilo=5, n_historico=15`).
Para cada combinação, `simular_apostas` em 4 limiares de edge (`0%, 2%,
5%, 8%`) × 2 mercados (Over 2.5, BTTS) — 384 avaliações por liga.
Filtrando por `n_apostas ≥ 15` (evita "vencedor" de amostra minúscula),
os 10 melhores ROI de treino por mercado foram revalidados em **holdout
2026** (mesmo padrão de sempre: `timestamp_minimo` no primeiro jogo de
2026, histórico pode usar 2025+início de 2026).

## Resultado — o padrão de overfitting apareceu de novo

A mesma armadilha que já tinha derrubado o "vencedor" de `k_mando` (Série
A) e de `estilo_por_mando` se repetiu, agora pra ROI:

| Liga | Mercado | Combo (treino) | Edge | Treino ROI | Treino n | Holdout ROI | Holdout n |
|---|---|---|---|---|---|---|---|
| Série B | Over 2.5 | `k=0.2, estilo=True, filtro=0.8` | 5% | **+2.9%** | 81 | **−7.4%** | 53 |
| Série B | Over 2.5 | `k=None, estilo=True, filtro=0.8` | 5% | **+2.7%** | 84 | **−12.8%** | 56 |
| Série B | BTTS | `k=None, estilo=False, filtro=0/0.5` | 2% | **+22.1%** | 108 | **−13.7%** | 57 |
| Série A | BTTS | (todos os top-10 do treino) | 5-8% | **negativo** (−1.5% a −5.5%) | 50-82 | **positivo** (+2.6% a +17.3%) | 35-101 |

Na Série B, os candidatos com MELHOR ROI de treino viram os PIORES no
holdout — inclusive trocando de sinal (+22% → −14%). Na Série A/BTTS
aconteceu o oposto: nenhum candidato teve ROI de treino positivo, mas
TODOS tiveram ROI de holdout positivo — sinal de que o ranking por ROI de
treino, sozinho, não é uma bússola confiável pra nenhuma das duas ligas
com o volume de dado atual.

## O achado real: o método de seleção prefere o limiar de edge errado

Comparando os melhores candidatos encontrados por este grid (com
z-score calculado sobre os lucros individuais do holdout, `lucro_médio /
erro-padrão`) contra os **parâmetros neutros já documentados**
(`k_mando=None, usar_estilo=True, filtro_aderencia=0.65` — nunca
"vencedores" de nenhum grid) do relatório de 24/08:

| Liga | Mercado | Config | Edge | n | ROI | z-score |
|---|---|---|---|---|---|---|
| Série A | Over 2.5 | grid (`k=0.7, sem estilo, filtro=0`) | 0% | 89 | +11.4% | **+1.01** |
| Série A | Over 2.5 | **neutro** | 8% | 42 | +35.8% | **+2.24** |
| Série A | BTTS | grid (`k=0.7, estilo, filtro=0.65`) | 5% | 64 | +17.3% | **+1.50** |
| Série A | BTTS | **neutro** | 8% | 43 | +35.7% | **+2.72** |
| Série B | Over 2.5 | grid (`k=0.2, estilo, filtro=0`) | 0% | 74 | +3.6% | +0.27 |
| Série B | Over 2.5 | **neutro** | 0% | 81 | +6.8% | +0.53 |
| Série B | BTTS | grid (`k=0.2, estilo, filtro=0`) | 5% | 45 | +12.6% | +0.86 |
| Série B | BTTS | **neutro** | 0-8% | 38-76 | +1-3% | ~0.1-0.2 |

**Em nenhum caso o grid superou o parâmetro neutro no critério que
importa (z-score/significância estatística).** Na Série A, o grid até
"achou" candidatos com ROI positivo — mas mais fracos (z≈1.0-1.5) que o
que já estava documentado (z=2.24/2.72). Isso não é coincidência: o
critério "maior ROI no treino" naturalmente prefere limiares de edge
BAIXOS (0-5%), porque têm mais apostas no treino e por isso ROI mais
"estável" nessa amostra pequena — mas o sinal genuíno está exatamente no
limiar mais ALTO (8%, mais seletivo), que fica sub-representado no treino
(poucas apostas ali) e por isso nunca vence o ranking por ROI de treino.
**Otimizar o limiar de edge pelo mesmo critério que otimiza os parâmetros
do modelo introduz o mesmo viés de comparação múltipla que a validação
fora-da-amostra deveria evitar.**

Na Série B, o achado de 24/08 se confirma e fica mais forte: nenhuma
combinação testada (nem as 384 daqui, nem a neutra) passa de z≈0.9 —
**não há evidência de vantagem real na Série B ainda**, em nenhum dos
dois mercados simulados.

## Recomendação

**Manter os parâmetros neutros para fins de aposta (ROI) nas duas
ligas** — `k_mando=None, usar_estilo=True, filtro_aderencia=0.65,
estilo_por_mando=False` — e não os "vencedores por acerto" da tabela de
`docs/protocolo.md` (que otimizam uma métrica diferente e mostraram
edge negativo/nulo quando testados contra odd real).

- **Série A**: exigir `limiar_edge ≥ 8%` em Over 2.5 e BTTS antes de
  apostar — é o único ponto com sinal estatisticamente defensável
  (z>2) encontrado até agora, em qualquer rodada.
- **Série B**: **não apostar por este critério ainda** — nenhuma
  configuração testada (neutra ou grid) passou de z≈0.9. Precisa de mais
  dado (mais temporadas) antes de confiar em qualquer parâmetro aqui.
- Não vale a pena manter um `limiar_edge`/parâmetro "otimizado por ROI de
  treino" — o método, do jeito que foi tentado aqui, não gera vantagem
  sobre simplesmente não ajustar nada.

## Limitações

- Mesmas de sempre: 1 temporada de treino (2025), 1 de holdout (2026
  parcial) — `n` de 35-101 apostas por linha, amostra pequena.
- Novo limite identificado nesta rodada: ranquear por ROI de treino é
  enviesado a favor de limiares de edge mais populosos/baixos — qualquer
  grid search futuro por ROI precisa considerar isso (ex.: normalizar por
  erro-padrão em vez de ROI bruto, ou fixar o limiar de edge fora do
  grid).
- Só 2 mercados simulados (Over 2.5, BTTS); só o lado "a favor"
  (Over/Sim) tem odd disponível no CSV.

Reprodução: `metodologia_pesos/retrospectiva.py`
(`rodar_retrospectiva`/`simular_apostas`/`grid_search`), scripts de
orquestração ad-hoc (não versionados — mesma mecânica de
`grid_search(..., ordenar_por="roi_over25"/"roi_btts")`, mas com edge
variável por fora pra não re-rodar o walk-forward a cada limiar).
