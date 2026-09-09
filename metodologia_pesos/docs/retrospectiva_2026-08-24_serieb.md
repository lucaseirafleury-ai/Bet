# Retrospectiva — Brasileirão Série B 2026 (rodada 24/38)

Mesmo backtest walk-forward da Série A, agora contra `matches.csv` da
Série B (236 jogos completos de 380, rodada 24/38). `min_jogos_historico=8`,
`min_jogos_estilo=5`, `n_historico=15`: **156 jogos avaliados**, 80 pulados
por histórico insuficiente no início da temporada. Mesmo escopo: só o
mercado de Gols Pró/Contra foi validado.

## Resultado com os parâmetros atuais ("no olho": k=0.35, limite=4, mult_dp=2.5)

| Métrica | Valor |
|---|---|
| MAE gols (pró+contra) | 1.689 |
| Acerto Over/Under 2.5 | 59.0% |
| Acerto BTTS | 53.8% |

## Grid search (mesmas 54 combinações da Série A)

**Ao contrário da Série A, aqui o sinal é misto — as métricas discordam
entre si:**

| k_mando | MAE médio | Over/Under 2.5 médio | BTTS médio |
|---|---|---|---|
| 0.7 | **1.670** (melhor MAE) | 54.9% | 51.5% |
| 0.5 | 1.672 | 57.5% | 52.8% |
| Nenhum (k=1.0) | 1.677 | 54.1% | 50.0% (pior) |
| **0.35 (valor atual)** | 1.683 | **59.2% (melhor)** | 52.8% |
| 0.2 | 1.700 (pior MAE) | 59.0% | **53.8% (melhor)** |

Diferente da Série A (onde `k=None` vencia nas 3 métricas de forma
consistente), aqui **quem minimiza o erro médio de gols (MAE) não é quem
mais acerta os mercados derivados** (Over/Under 2.5, BTTS) — pelo
contrário: mais encolhimento de mando (k menor) piora o MAE mas melhora o
acerto de Over/Under 2.5 e BTTS. O valor atual (`k=0.35`) fica no meio do
grupo em MAE, mas é o melhor ou quase melhor nos dois mercados derivados.

`limite_unilateral` de novo sem efeito mensurável (mesma razão da Série
A: médias de gols raramente cruzam a faixa 3-5). `multiplicador_dp=2`
levemente melhor que 2.5/3 em MAE, mas a diferença é pequena
(1.676 vs 1.681 vs 1.682) — provavelmente dentro do ruído amostral.

## Recomendação (preliminar)

- **Manter `k=0.35` na Série B** — diferente da Série A, aqui não há
  evidência clara de que zerar o ajuste de mando ajude; pelo contrário,
  o valor atual entrega o melhor acerto de Over/Under 2.5 desta amostra.
  Isso é coerente com o protocolo já registrar mando de campo mais forte
  na Série B (~23% de vantagem, vs. favoritismo mais fraco na B em geral).
- `k=0.5` é um candidato de meio-termo (MAE quase igual ao melhor, acerto
  de Over/Under 2.5 segundo melhor) se algum dia quiser testar mudar —
  mas não há sinal forte o suficiente pra trocar agora.
- Isso reforça a decisão de NÃO generalizar o achado da Série A pra Série
  B — as ligas se comportam diferente aqui.

## Limitações (mesmas da Série A)

1. Amostra parcial de temporada (156 jogos, rodada 24/38).
2. Só mercado de gols validado — cartões/escanteios/chutes ficam para
   depois.
3. Diferenças entre configurações são pequenas em termos absolutos — não
   é uma virada drástica de modelo em nenhuma das duas ligas.

Reprodução: mesma chamada de `grid_search()` da Série A, trocando o `df`
para `data/footystats_serieb/matches.csv`.
