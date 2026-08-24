# Recalibração com amostra ampliada (2025 completo + 2026 parcial)

Mesmo grid search de 24/08 (`k_mando` × `usar_estilo` × `filtro_aderencia`,
48 combinações), agora contra temporada 2025 completa (380/380 jogos) +
2026 parcial combinadas — **508 jogos avaliados na Série A (vs 154
antes) e 492 na Série B (vs 156 antes)**, ~3.3x mais dado.

**Isto revisa as conclusões da rodada anterior — leia antes de aplicar
qualquer parâmetro.**

## Série A

| k_mando | MAE médio | Over/Under 2.5 médio | BTTS médio |
|---|---|---|---|
| 0.7 | **1.8000** (melhor MAE) | 0.498 | 0.515 |
| 0.5 | 1.8015 | 0.497 | **0.514** |
| Nenhum (k=1.0) | 1.8061 | **0.501** (melhor) | 0.508 |
| 0.35 | 1.8102 | 0.501 | 0.508 |
| 0.2 | 1.8298 (pior) | 0.489 (pior) | 0.509 |

A config que a rodada anterior validou como "vencedora clara" (k=None,
estilo ativo, filtro 65%) caiu pra **posição 15 de 48** — ainda razoável,
mas não é mais destaque. Os 10 melhores resultados ficam todos entre
MAE 1.788-1.794 (faixa de 0.3%) — **não há um "k certo" com sinal forte
aqui**, é um platô raso entre 0.5 e 1.0 (None).

## Série B

| k_mando | MAE médio | Over/Under 2.5 médio | BTTS médio |
|---|---|---|---|
| 0.5 | **1.6236** (melhor MAE) | 0.555 | **0.518** (melhor) |
| 0.7 | 1.6239 | 0.548 | 0.513 |
| Nenhum (k=1.0) | 1.6239 | 0.552 | 0.510 |
| 0.35 (valor em uso) | 1.6315 | **0.562** | 0.511 |
| 0.2 | 1.6469 (pior MAE) | **0.565** (melhor Over25) | 0.513 |

Aqui o padrão que já tínhamos visto (MAE favorece MENOS encolhimento,
Over/Under 2.5 favorece MAIS encolhimento) **se confirma e fica mais
nítido** com mais dado — não foi ruído. `k=0.35` caiu pra posição 25/48
no ranking geral de MAE, mas continua competitivo em Over/Under 2.5.

## `usar_estilo` (ablação) — sinal mudou de "indiferente" pra "levemente negativo"

| Liga | MAE com estilo | MAE sem estilo | Diferença |
|---|---|---|---|
| Série A | 1.8125 | 1.8054 | Sem estilo é **0.4% melhor** |
| Série B | 1.6301 | 1.6278 | Sem estilo é **0.1% melhor** |

Na rodada anterior (amostra menor) a diferença era \<0.1% e classificamos
como "indiferente, dentro do ruído". Com mais dado, o sinal é mais
consistente (sempre a favor de tirar o estilo, nas duas ligas) mas ainda
pequeno — não é uma virada de "não importa" pra "atrapalha muito", é um
sinal fraco mas agora mais confiável de que **não ajuda**.

## `filtro_aderencia`

Continua parecido: 0/0.5/0.65 ficam próximos (diferença <1%) nas duas
ligas; **0.8 continua claramente pior** (único caso com sinal forte e
replicado nas duas amostras, nas duas rodadas).

## Conclusão — o que isso ensina

**A amostra pequena (154-156 jogos) da rodada anterior gerou pelo menos
uma conclusão que não se sustentou**: "zerar o mando na Série A vence
nas 3 métricas de forma clara" — isso era, em boa parte, ruído
estatístico. Com 3.3x mais dado, o quadro é mais plano e ambíguo pro
`k_mando` (nas duas ligas), mais confiável (embora ainda pequeno) pra
`usar_estilo` (leve sinal negativo), e o achado de `filtro_aderencia=0.8`
ser ruim é o único que se replicou com força nas duas rodadas.

## Recomendação revisada

- **`k_mando`: não vale mais tratar como "resolvido" em nenhuma das duas
  ligas.** A diferença entre 0.5/0.7/None é ruído-nível (~1-2%). Dado que
  MAE e Over/Under 2.5 apontam em direções opostas nas duas ligas, a
  escolha depende de qual métrica pesa mais pra decisão de aposta —
  recomendo manter os valores atuais (Série A: sem ajuste; Série B: 0.35)
  como escolha razoável dentro do platô, não como "o parâmetro
  validado", até: (a) termos ainda mais dado, ou (b) decidirmos junto com
  o Lucas se o que importa mais é erro de gols (MAE) ou acerto de
  Over/Under 2.5 especificamente.
- **`usar_estilo`**: sinal (fraco, mas agora consistente) de que **não
  ajuda** — mantenho ativo por enquanto (não é prejudicial o bastante pra
  forçar mudança de código/skill), mas reforça que os proxies de estilo
  merecem revisão antes de continuar confiando neles.
- **`filtro_aderencia=0.65`**: mantido, é o único parâmetro com evidência
  replicada e consistente (0.8 é ruim, resto é parecido).

## Limitações

Mesmo 2025 completo, ainda é 1 temporada e meia por liga — bom avanço em
relação à rodada anterior, mas continua sendo pouco pra "provar"
qualquer parâmetro com alta confiança estatística (efeitos de ~1-2% em
amostras de ~500 jogos binários têm margem de erro grande). Tratar como
"melhor estimativa disponível hoje", não como validação definitiva.

Reprodução: mesma `grid_search()`, agora com
`pd.concat([2025, 2026])` antes de filtrar `status=='complete'`.
