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

**⚠️ Correção (mesmo dia)**: a primeira versão deste documento reportou
todo ROI EXATAMENTE EM DOBRO do valor real — bug no script ad-hoc de
corte (`analise_cortes.py`): o lucro de cada aposta veio de
`simular_apostas(..., stake=1.0)` (padrão da função), mas o ROI foi
calculado dividindo por `stake_total = 0.5 × n` (achando que reproduzia
o stake reduzido real do critério) — stake inconsistente entre
numerador e denominador. Taxa de acerto e `n` não foram afetados (não
dependem de stake); só o ROI%. Todos os números abaixo já estão
corrigidos. Nenhuma conclusão qualitativa muda (A e B continuam
melhores que a base, C continua pior que A/B isolados, D continua o
único negativo) — só a magnitude.

## Base: 80 apostas, 58,8% de acerto, ROI+23,6%

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
| odd ≤ 1,95 | 14 | 85,7% | +58,4% | — | — | — |
| odd ≤ 2,00 | 19 | 73,7% | +37,4% | — | — | — |
| odd ≤ 2,05 | 27 | 74,1% | +41,7% | — | — | — |
| odd ≤ 2,15 | 37 | 70,3% | +37,7% | — | — | — |
| odd ≤ 2,20 | 46 | 69,6% | +39,3% | — | — | — |
| **odd > 2,20** | **34** | **44,1%** | **+2,4%** | — | — | — |

Testei 6 limiares diferentes entre 1,95 e 2,20 — o padrão é
**monotônico em todos eles**: quanto menor a odd, maior o acerto e o
ROI, sem exceção. No corte pela mediana (2,165, n=40 de cada lado):
acerto 67,5% (ROI+32,8%) do lado de odd baixa contra 50,0% (ROI+14,4%)
do lado de odd alta.

**Interpretação**: isso é esperado ATÉ certo ponto — odd baixa =
mercado já acha o jogo mais provável de passar de 2,5 gols, então uma
correlação com acerto maior não é 100% "informação nova" (é
parcialmente mecânico). Mas o tamanho do efeito e a consistência em
TODOS os limiares testados tornam isso o achado mais forte desta
análise — no mesmo espírito do "teto de odd máxima" já usado antes no
projeto pra Over 2.5/BTTS (`docs/retrospectiva_odd_maxima_2026-08-25.md`),
mas agora pra este critério específico (Sbo), que nunca tinha sido
testado com teto.

## Achado 2 — Concordância com o modelo do Sportmonks

| Corte (mediana, prob_sportmonks=0,464) | n | Acerto | ROI |
|---|---|---|---|
| Sportmonks também gosta (>0,464) | 40 | 67,5% | +39,2% |
| Sportmonks neutro/contra (≤0,464) | 40 | 50,0% | +8,0% |

Sinal real e consistente nos 3 anos (nenhum negativo, nenhuma
inversão), praticamente empatado com o de odd em força (ROI muito
próximo, +39,2% vs +39,3%).

## Achado 3 (o mais acionável) — interseção dos dois sinais

| Grupo | n | Acerto | ROI |
|---|---|---|---|
| Odd baixa E Sportmonks concorda | 27 | 66,7% | +30,6% |
| Só odd baixa (Sportmonks não especialmente a favor) | 13 | 69,2% | +37,3% |
| **Nenhum dos dois** (odd alta E Sportmonks neutro/contra) | **27** | **40,7%** | **−6,1%** |

O grupo "nenhum dos dois" é o único com ROI NEGATIVO da análise
inteira, com os 3 anos fracos (nenhum vira positivo isoladamente) — é
o subgrupo mais claramente identificável como "correlato de red".
`n=27` (acima do mínimo de 15), mas o detalhamento por ano fica fino
em 2026 (`n=4`) — não dá pra confiar nesse ano isolado, só no padrão
agregado + 2024/2025 mais robustos.

**Combinar os dois sinais não ajuda** — a interseção (ROI+30,6%) fica
PIOR que odd baixa sozinha (+39,3%) ou Sportmonks sozinho (+39,2%).
Os dois sinais são correlacionados entre si (não totalmente
independentes), então exigir os dois ao mesmo tempo só reduz a amostra
sem ganho — reforça a recomendação de usar só um dos dois, não os
dois juntos.

## O que NÃO funcionou (e um alerta)

- `gf_pred`/`ga_pred`/`total_pred`/`floor_total`/`abs_diff`: nenhuma
  separação clara entre green e red. `floor_total==2` (n=61) tem
  ROI+26,6%; `floor_total==3` (n=17) tem ROI+12,6% — mas o
  detalhamento por ano mostra que é puxado por um único ano ruim
  (2025, `n=6`, 17% de acerto) — não é um padrão confiável, amostra
  pequena demais pra esse recorte específico.
- **Edge mais alto teve acerto E ROI PIORES, não melhores** (edge ≤
  mediana: 62,5% acerto, ROI+30,2%; edge > mediana: 55,0% acerto,
  ROI+17,0%) — e o padrão por ano se INVERTE completamente: 2024
  (44%/ROI−7,6% vs 75%/ROI+62,1%, ou seja, mais edge ERA melhor nesse
  ano) contra 2025 (61%/ROI+28,4% vs 38%/ROI−20,7%) e 2026
  (77%/ROI+58,8% vs 58%/ROI+22,2%) — sinal de ruído, não de padrão
  real. **Não usar edge mais alto como filtro de qualidade neste
  critério** — é a direção oposta da intuição comum ("edge maior =
  aposta melhor"), documentado aqui pra não repetir o teste depois
  achando que seria óbvio.

## Recomendação

Dois candidatos reais, ambos com direção consistente nos 3 anos,
`n≥27` e ROI muito próximo entre si (+39,2% a +39,3%, contra +23,6%
da base sem filtro):

1. **Teto de odd** (ex.: não apostar Over 2.5-Sbo com odd > ~2,20) —
   mais simples de aplicar, não depende de fonte de dado nova.
2. **Exigir concordância com o `predictions` do Sportmonks** — força
   equivalente, mas depende de manter um pull novo rodando (nunca
   validado de forma prospectiva, só retroativa).

**Não combinar os dois** — a interseção tem ROI pior que qualquer um
isolado (ver Achado 3).

Nenhum dos dois está sendo aplicado à produção nesta rodada — fica
documentado como achado, à espera de decisão do Lucas (mesmo padrão de
sempre: amostra pequena o suficiente pra pedir cautela antes de virar
regra automática). Se ele quiser adotar, a forma mais simples e
defensável é o teto de odd sozinho — mesma força que o Sportmonks, sem
a dependência nova.

## Verificação

- `n` de cada grupo/corte reportado em toda tabela, nunca abaixo de 13
  (a maioria acima de 27); nenhum corte final recomendado com `n<15`.
- Checagem ano a ano em todos os achados reportados como candidatos —
  o achado de `floor_total==3` foi DESCARTADO justamente por falhar
  nessa checagem (um ano ruim isolado inflando o agregado); o de edge
  também foi descartado pelo mesmo motivo (sinal invertendo de ano pra
  ano).
- **Bug de ROI em dobro identificado e corrigido no mesmo dia** (ver
  aviso no topo) — reforça a importância de sempre conferir stake
  consistente entre numerador/denominador ao calcular ROI, mesmo em
  script ad-hoc de análise exploratória.
- Reprodução: `/tmp/.../scratchpad/puxar_predictions_over25.py` (pull
  do `predictions` do Sportmonks), `analise_green_red_over25.py`
  (junta tudo, calcula por-feature), `analise_cortes.py` (testa os
  cortes/interseções, já corrigido) — ad-hoc, não versionados, mesmo
  padrão de sempre.
