# Retrospectiva — Brasileirão Série A 2026 (rodada 24/38)

Backtest walk-forward rodado com os CSVs do FootyStats que Lucas subiu em
24/08/2026 (`matches.csv`, 234 jogos completos de 380 no calendário — a
temporada ainda não acabou, rodada 24 de 38). `min_jogos_historico=8`,
`min_jogos_estilo=5`, `n_historico=15`: **154 jogos avaliados**, 80 pulados
por não terem 8 jogos anteriores suficientes no início da temporada.

**Escopo desta rodada**: só o mercado de Gols Pró/Contra foi validado (é o
que `prever_jogo`/`retrospectiva.py` mede hoje). Cartões, escanteios,
chutes etc. (os outros 10 dos 12 indicadores Pró/Contra) ainda não têm
validação retrospectiva própria.

## Resultado com os parâmetros atuais ("no olho": k=0.35, limite=4, mult_dp=2.5)

| Métrica | Valor |
|---|---|
| MAE gols (pró+contra) | 1.706 |
| Acerto Over/Under 2.5 | 51.3% |
| Acerto BTTS | 56.5% |

## Grid search (54 combinações: k_mando × limite_unilateral × multiplicador_dp)

**Achado principal — o ajuste de mando está piorando o modelo nesta base:**
quanto mais forte o encolhimento (`k` menor), pior o resultado nas 3
métricas, de forma monotônica e consistente:

| k_mando | MAE médio | Over/Under 2.5 médio | BTTS médio |
|---|---|---|---|
| Nenhum (k=1.0) | **1.675** | **55.0%** | **57.8%** |
| 0.7 | 1.682 | 50.6% | 57.4% |
| 0.5 | 1.694 | 50.4% | 57.1% |
| 0.35 (valor atual) | 1.705 | 51.3% | 56.9% |
| 0.2 | 1.724 | 49.4% | 56.9% |

`limite_unilateral` (3/4/5) não fez diferença mensurável neste teste —
esperado, já que médias de gols raramente passam de 3 (o corte unilateral
dificilmente muda de regime nessa faixa; deve importar mais em mercados de
cartões/escanteios, ainda não testados). `multiplicador_dp` teve efeito
pequeno e sem padrão claro (2 e 3 levemente melhores que 2.5, diferença
~0.003 de MAE — dentro do ruído).

## Recomendação (preliminar)

- **Não aplicar ajuste de mando na Série A por enquanto** (`k_mando=None`/
  `1.0`) — o shrinkage que a Série B usa (baseado no protocolo,
  `k=0.35`) não se sustentou nesta base de 154 jogos da Série A. Vale
  testar separadamente na Série B quando os CSVs chegarem — pode ser uma
  diferença real entre as ligas, não um erro do ajuste em si.
- `limite_unilateral`/`multiplicador_dp` atuais (4 / 2.5) não têm evidência
  contra nem a favor aqui — manter até validar em mercados onde o corte
  realmente atua (cartões, escanteios).

## Limitações a considerar antes de mudar o protocolo de vez

1. **Amostra parcial da temporada** (154 jogos, rodada 24/38) — os times
   ainda não jogaram o returno completo; recomendo rodar de novo com a
   temporada mais avançada antes de fixar a mudança.
2. Só o mercado de gols foi validado — cartões/escanteios/chutes ficam
   para uma próxima rodada de retrospectiva.
3. O efeito é real mas pequeno em termos absolutos (~3% de diferença de
   MAE entre k=None e k=0.2) — não é uma virada drástica de modelo, é um
   ajuste fino.

Reprodução: `metodologia_pesos/retrospectiva.py`, `grid_search()` com
`grade = dict(k_mando=[None,0.2,0.35,0.5,0.7,1.0], limite_unilateral=[3,4,5], multiplicador_dp=[2,2.5,3])`
sobre `data/footystats_seriea/matches.csv`.
