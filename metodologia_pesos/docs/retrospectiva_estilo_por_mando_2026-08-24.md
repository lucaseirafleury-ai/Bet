# Estilo por mando (casa vs fora) — vale a pena?

Hipótese do Lucas: muitos times jogam diferente em casa e fora — calcular
o estilo misturando os últimos 5 jogos (qualquer mando) pode estar
diluindo um sinal real. Testado calculando o estilo separadamente:
`_estilo_por_mando(time, mando, n=5)` usa só os últimos 5 jogos NAQUELE
mando específico (só em casa, ou só fora), tanto pro alvo de hoje (o
visitante joga fora hoje → usa o estilo dele jogando fora) quanto pra
cada adversário do histórico (se o time da linha jogou em casa naquele
jogo passado, o adversário jogou fora → usa o estilo do adversário
jogando fora, e vice-versa).

**Métrica priorizada: acerto de Over/Under 2.5** (decisão do Lucas — o
que importa é acertar a linha de aposta, não o erro do placar exato).

Comparação de 3 cenários, com `k_mando`/`filtro_aderencia` já nos valores
em uso (Série A: sem ajuste de mando; Série B: 0.35; filtro 0.65 nas
duas), contra a base 2025+2026 combinada:

## Série A

| Cenário | n avaliados | Over/Under 2.5 | BTTS | MAE gols |
|---|---|---|---|---|
| Sem estilo | 508 | 50.20% | 50.79% | 1.7935 |
| Estilo misto (atual) | 508 | 49.61% (pior) | 50.98% | 1.7954 |
| **Estilo por mando (novo)** | 480 | **50.62% (melhor)** | **51.67% (melhor)** | 1.7987 |

## Série B

| Cenário | n avaliados | Over/Under 2.5 | BTTS | MAE gols |
|---|---|---|---|---|
| Sem estilo | 492 | 56.10% | 51.02% | 1.6287 |
| **Estilo misto (atual)** | 492 | **56.71% (melhor)** | 51.63% | 1.6266 |
| Estilo por mando (novo) | 458 | 55.02% (pior) | **52.62% (melhor)** | **1.6130 (melhor)** |

## Leitura

**Ajuda na Série A, atrapalha na Série B** — mais uma vez as duas ligas
divergem (mesmo padrão já visto em `k_mando`). Na Série A, estilo por
mando é a melhor das 3 opções tanto em Over/Under 2.5 quanto em BTTS. Na
Série B, é a pior em Over/Under 2.5 (mas a melhor em MAE de gols e BTTS
— sinal genuinamente misto até dentro da própria liga).

**Custo**: estilo por mando exige mais dado (5 jogos NAQUELE mando
específico, não 5 jogos quaisquer) — avalia ~5-7% menos jogos (480 vs
508 na Série A; 458 vs 492 na Série B) porque times no início da amostra
ainda não tinham jogos suficientes num mando específico. Os conjuntos de
jogos avaliados não são idênticos entre os 3 cenários (diferença de
amostra, não só de método) — as comparações acima não são um teste
perfeitamente controlado por causa disso; tratar as diferenças pequenas
(<1pp) com mais cautela ainda.

## Recomendação

- **Série A**: trocar pra estilo por mando (`estilo_por_mando=True`) —
  é a melhor opção na métrica que importa (Over/Under 2.5), com uma
  margem pequena mas consistente também em BTTS.
- **Série B**: manter o estilo misto atual (`estilo_por_mando=False`) —
  estilo por mando piora justamente o Over/Under 2.5 aqui, mesmo sendo
  melhor em MAE/BTTS.
- Ainda não é uma prova definitiva (efeitos de ~1pp em amostras de
  ~500 jogos), mas é a primeira variação de estilo que mostra ganho real
  na métrica prioritária — vale manter ativa na Série A e re-testar
  quando houver mais dado.

## Como usar

```python
from retrospectiva import rodar_retrospectiva, prever_jogo

# Série A: liga o estilo por mando
rel = rodar_retrospectiva(df, params=dict(k_mando=None, estilo_por_mando=True), min_jogos_historico=8)

# Série B: mantém o estilo misto (comportamento padrão, sem mudança)
rel = rodar_retrospectiva(df, params=dict(k_mando=0.35, estilo_por_mando=False), min_jogos_historico=8)
```

Reprodução: `metodologia_pesos/retrospectiva.py`, `_estilo_por_mando()` e
o parâmetro `estilo_por_mando` em `prever_jogo`/`rodar_retrospectiva`/
`grid_search`.
