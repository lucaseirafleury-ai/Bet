# Green vs Red no Over 2.5 (Sbo): o que diferencia os dois grupos

## Contexto

Lucas pediu uma análise exploratória: dentro das 80 apostas do
critério Over 2.5 recalibrado (Série A, base Sbo, `k_mando=0.35,
usar_estilo=False, filtro_aderencia=0.65, multiplicador_dp=1.5,
limite_unilateral=4, n_historico=15, limiar_edge=8%`), separar as que
deram green das que deram red e procurar algo em comum que sirva de
filtro adicional — sem deixar nenhum subgrupo abaixo da amostra mínima
usada o projeto todo (`n≥15`), e checando ano a ano, não só o agregado.

**Aviso logo de cara**: n=80 já é uma amostra pequena; qualquer corte
aqui, mesmo o mais promissor, é uma HIPÓTESE pra monitorar, não uma
promoção automática. Testei 11 features candidatas e vários pontos de
corte — isso é, em si, uma busca de múltiplas comparações (mesmo
princípio já flagrado o projeto inteiro pra grid search de parâmetro).

## Base: 80 apostas, 58,8% de acerto, ROI+47,2%

| Ano | Green | Red | Total |
|---|---|---|---|
| 2024 | 13 | 8 | 21 |
| 2025 | 17 | 17 | 34 |
| 2026 | 17 | 8 | 25 |

## O que foi testado

Uma nova fonte de dado entrou nesta análise: **`predictions` do
Sportmonks** (`include=predictions`, `type_id=235` = "Over/Under 2.5
Probability" — a previsão do PRÓPRIO modelo do Sportmonks pra esse
mercado). Confirmado que existe retroativo (testado em fixtures de
2025, já finalizados) e com cobertura completa (25/25 numa amostra de
teste) — pode ser puxado em lote junto com os outros dados, sem custo
extra de chamadas por jogo.

Termo importante: "xG do modelo" aqui = `gf_pred`/`ga_pred`/
`total_pred` (a expectativa de gols do NOSSO modelo pra aquele jogo
específico, calculada em `retrospectiva.prever_jogo`) — não é xG real
(Sportmonks não tem isso pra Série A/B, já confirmado antes).

Features comparadas (média/mediana GREEN vs RED, agregado): odd,
edge, probabilidade do modelo, probabilidade implícita de mercado,
`total_pred`, `gf_pred`/`ga_pred` separados, `floor(gf_pred)+floor(ga_pred)`,
`abs(gf_pred-ga_pred)`, probabilidade do Sportmonks, e a diferença
entre as duas probabilidades (nosso modelo vs Sportmonks).

**Resultado da comparação simples (média/mediana)**: quase todas as
features têm diferença pequena entre green e red — nada que salte aos
olhos olhando só média/mediana. O sinal aparece nos CORTES (abaixo),
não na comparação de médias.

## Achado 1 — Odd baixa prevê acerto melhor (mais forte e mais consistente)

| Corte | n | Acerto | ROI | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| odd ≤ 1,95 | 14 | 85,7% | +116,7% | — | — | — |
| odd ≤ 2,00 | 19 | 73,7% | +74,7% | — | — | — |
| odd ≤ 2,05 | 27 | 74,1% | +83,3% | 83% (n=6) | 67% (n=12) | 78% (n=9) |
| odd ≤ 2,15 | 37 | 70,3% | +75,5% | — | — | — |
| odd ≤ 2,20 | 46 | 69,6% | +78,6% | — | — | — |
| **odd > 2,20** | **34** | **44,1%** | **+4,8%** | — | — | — |

Testei 6 limiares diferentes entre 1,95 e 2,20 — o padrão é
**monotônico em todos eles**: quanto menor a odd, maior o acerto e o
ROI, sem exceção. No corte pela mediana (2,165, n=40 de cada lado),
2024/2025/2026 do lado de odd baixa são 75%/60%/71% (nenhum ano fraco)
contra 54%/42%/62% do lado de odd alta.

**Interpretação**: isso é esperado ATÉ certo ponto — odd baixa =
mercado já acha o jogo mais provável de passar de 2,5 gols, então uma
correlação com acerto maior não é 100% "informação nova" (é
parcialmente mecânico). Mas o tamanho do efeito (quase dobra o acerto
entre os extremos) e a consistência em TODOS os limiares testados
tornam isso o achado mais forte desta análise — no mesmo espírito do
"teto de odd máxima" já usado antes no projeto pra Over 2.5/BTTS
(`docs/retrospectiva_odd_maxima_2026-08-25.md`), mas agora pra este
critério específico (Sbo), que nunca tinha sido testado com teto.

## Achado 2 — Concordância com o modelo do Sportmonks

| Corte (mediana, prob_sportmonks=0,464) | n | Acerto | ROI | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| Sportmonks também gosta (>0,464) | 40 | 67,5% | +78,5% | 69% (n=13) | 55% (n=11) | 75% (n=16) |
| Sportmonks neutro/contra (≤0,464) | 40 | 50,0% | +15,9% | 50% (n=8) | 48% (n=23) | 56% (n=9) |

Sinal real e consistente nos 3 anos (nenhum negativo, nenhuma
inversão), mas mais fraco que o de odd.

## Achado 3 (o mais acionável) — interseção dos dois sinais

| Grupo | n | Acerto | ROI | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| Odd baixa E Sportmonks concorda | 27 | 66,7% | +61,3% | 71% (n=7) | 62% (n=8) | 67% (n=12) |
| Só odd baixa | 13 | 69,2% | +74,6% | — | — | — |
| **Nenhum dos dois** (odd alta E Sportmonks neutro/contra) | **27** | **40,7%** | **−12,3%** | 43% (n=7) | 44% (n=16) | 25% (n=4) |

O grupo "nenhum dos dois" é o único com ROI NEGATIVO da análise
inteira, com os 3 anos fracos (nenhum vira positivo isoladamente) — é
o subgrupo mais claramente identificável como "correlato de red".
`n=27` (acima do mínimo de 15), mas o detalhamento por ano fica fino
em 2026 (`n=4`) — não dá pra confiar nesse ano isolado, só no padrão
agregado + 2024/2025 mais robustos.

## O que NÃO funcionou (e um alerta)

- `gf_pred`/`ga_pred`/`total_pred`/`floor_total`/`abs_diff`: nenhuma
  separação clara entre green e red.
- `floor_total==3` parecia pior à primeira vista (52,9% vs 60,7% pra
  `==2`), mas o detalhamento por ano mostra que é puxado por um único
  ano ruim (2025, `n=6`, 17% de acerto) — não é um padrão confiável,
  amostra pequena demais pra esse recorte específico.
- **Edge mais alto teve acerto PIOR, não melhor** (edge ≤ mediana:
  62,5% acerto; edge > mediana: 55,0%) — e o padrão por ano se INVERTE
  entre 2024 (44% vs 75%) e 2025/2026 (61%/77% vs 38%/58%) — sinal de
  ruído, não de padrão real. **Não usar edge mais alto como filtro de
  qualidade neste critério** — é a direção oposta da intuição comum
  ("edge maior = aposta melhor"), documentado aqui pra não repetir o
  teste depois achando que seria óbvio.

## Recomendação

Dois candidatos reais, ambos com direção consistente nos 3 anos e
`n≥27` (acima do mínimo do projeto):

1. **Teto de odd** (ex.: não apostar Over 2.5-Sbo com odd > ~2,20) —
   sinal mais forte e mais simples de aplicar.
2. **Exigir concordância com o `predictions` do Sportmonks** — sinal
   mais fraco sozinho, mas adiciona uma fonte de dado independente
   (nunca usada antes no projeto) que reforça o sinal de odd quando
   combinado.

Nenhum dos dois está sendo aplicado à produção nesta rodada — fica
documentado como achado, à espera de decisão do Lucas (mesmo padrão de
sempre: amostra pequena o suficiente pra pedir cautela antes de virar
regra automática). Se ele quiser adotar, a forma mais simples e
defensável é o teto de odd sozinho (achado mais forte, mais fácil de
implementar e explicar) — a versão combinada com o Sportmonks fica
como refinamento posterior, condicionado a mais dado confirmando o
padrão.

## Verificação

- `n` de cada grupo/corte reportado em toda tabela, nunca abaixo de 13
  (a maioria acima de 27); nenhum corte final recomendado com `n<15`.
- Checagem ano a ano em todos os achados reportados como candidatos —
  o achado de `floor_total==3` foi DESCARTADO justamente por falhar
  nessa checagem (um ano ruim isolado inflando o agregado).
- Reprodução: `/tmp/.../scratchpad/puxar_predictions_over25.py` (pull
  do `predictions` do Sportmonks), `analise_green_red_over25.py`
  (junta tudo, calcula por-feature), `analise_cortes.py` (testa os
  cortes/interseções) — ad-hoc, não versionados, mesmo padrão de
  sempre.
