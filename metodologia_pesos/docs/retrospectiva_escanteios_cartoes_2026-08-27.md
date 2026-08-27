# Escanteios/Cartões via odds reais do Sportmonks — testado, NÃO USAR (ainda)

## Contexto

Depois de validar que o Sportmonks tem odds reais de escanteios (100%
de cobertura, ~8 bookmakers) e cartões (100% Série A, 92,8% Série B,
~3 bookmakers) para 2024-2026, testamos se o motor de pesos atual
(reaproveitando a mesma lógica usada pra gols — walk-forward,
`indicador_pro_contra`, conversão Poisson via `probabilidade_over`)
consegue vantagem real contra essas odds.

## Abordagem

Reaproveitamos 100% do motor já testado (`rodar_retrospectiva`, params
neutros/padrão — sem calibração específica pra esses mercados ainda) e
extraímos, pra cada jogo já avaliado, a previsão do modelo pra total de
escanteios (`escanteios_pro`+`escanteios_contra`) e cartões
(`cartoes_pro`+`cartoes_contra`). Casamos cada jogo com a odd real do
Sportmonks (linha mais líquida — maior número de bookmakers cotando),
convertendo a previsão em probabilidade via Poisson
(`pesos.probabilidade_over`) e comparando com a probabilidade implícita
de mercado (`probabilidade_implicita_2vias`, odds Over/Under da linha
escolhida).

## Resultado — escanteios negativo consistente, cartões é ruído

**Escanteios** (negativo em TODOS os anos, nas DUAS ligas, em todos os
limiares de edge):

| Liga | edge≥0% | 2024 | 2025 | 2026 |
|---|---|---|---|---|
| Série A | n=907, ROI-7,4%, z=-2,38 | -2,6% | -8,5% | -13,1% |
| Série B | n=862, ROI-8,9%, z=-2,80 | -10,5% | -10,1% | -4,9% |

**Cartões** (agregado perto de zero, mas ano a ano inconsistente —
2025 negativo, 2026 positivo, nas duas ligas):

| Liga | edge≥0% | 2024 | 2025 | 2026 |
|---|---|---|---|---|
| Série A | n=909, ROI-0,6%, z=-0,20 | -3,1% | -6,0% | +13,4% |
| Série B | n=830, ROI+3,0%, z=+0,94 | +3,7% | -1,2% | +8,1% |

Em cartões, o z CAI conforme o limiar de edge exigido sobe (ex.: Série
B edge≥0% z=+0,94 → edge≥8% z=+0,02) — assinatura clássica de ruído,
não de edge real calibrado (se fosse edge de verdade, exigir mais edge
deveria filtrar pro melhor, não pro pior).

## Confirmação com os parâmetros já calibrados (Over 2.5 e BTTS)

Lucas perguntou se o teste acima usou só parâmetros neutros ou também
os combos já validados — resposta: só neutros na primeira rodada.
Refeito com os dois combos campeões (`k=0.5,sem estilo,filtro=0.8,
apertado,n_hist=15` do Over 2.5; `k=0.7,com estilo,filtros
0.8/0.65,apertado,n_hist=10` do BTTS), mesma metodologia:

| Mercado | Config | Série A (z) | Série B (z) |
|---|---|---|---|
| Escanteios | Neutro | -2,38 | -2,80 |
| Escanteios | Over 2.5-campeão | -0,93 | **-3,14** |
| Escanteios | BTTS-campeão | -2,13 | -2,32 |
| Cartões | Neutro | -0,20 | +0,94 |
| Cartões | Over 2.5-campeão | -0,51 | +0,42 |
| Cartões | BTTS-campeão | +0,59 | -0,00 |

**Escanteios continua negativo nas 6 combinações** (2 ligas × 3
configs) — confirma que não é questão de calibração, nenhum parâmetro
testado reverte o sinal.

**Cartões continua perto de zero e inconsistente em todas as 6
combinações** — o caso mais chamativo (Série A, parâmetros do BTTS,
agregado z=+0,59) tem 2026 isolado em z=+2,77, mas 2024 z=+0,17 e 2025
**z=-1,22** nos MESMOS parâmetros — um ano bom cercado de anos
fracos/negativos, o padrão clássico de ruído (mesma lição do "casa" da
Série B), não sinal calibrado.

## Hipótese testada: `limite_unilateral` mal escalado pro tamanho de escanteios/cartões

Lucas perguntou se algum parâmetro podia estar prejudicando a análise.
Identificamos que `corte_outlier` (`pesos.py`) decide corte
unilateral/bilateral comparando `media <= limite_unilateral` — esse
`limite_unilateral` (2 ou 4 nos combos testados) foi calibrado pensando
na escala de GOLS (~1,4/time). Escanteios (~5,0-5,2/time, ~3,6x) e
cartões (~2,6-2,7/time, ~1,9x) têm escalas bem diferentes — pra
escanteios, `media` está sempre acima de qualquer `limite_unilateral`
testado, então o corte roda SEMPRE no modo bilateral (mais agressivo),
nunca no modo unilateral pensado originalmente.

Testamos reescalando `limite_unilateral` proporcionalmente (×3,6 pra
escanteios, ×1,9 pra cartões) nos mesmos 3 combos:

| Mercado | Config | Antes → Depois (Série A) | Antes → Depois (Série B) |
|---|---|---|---|
| Escanteios | Neutro | -2,38 → -2,23 | -2,80 → -2,85 |
| Escanteios | Over2.5-corte | -0,93 → **-1,49** | -3,14 → **-4,07** |
| Escanteios | BTTS-corte | -2,13 → -2,10 | -2,32 → -2,53 |
| Cartões | Neutro | -0,20 → -0,20 | +0,94 → +0,94 |
| Cartões | Over2.5-corte | -0,51 → **-0,23** | +0,42 → **+1,27** |
| Cartões | BTTS-corte | +0,59 → **+1,19** | -0,00 → **+1,27** |

**Escanteios: hipótese refutada** — reescalar não ajuda, em 2 dos 6
casos até piora. O viés negativo é mais estrutural, não é explicado
por esse parâmetro específico.

**Cartões: melhora real, mas ainda abaixo do limiar** — Série B com o
corte do BTTS passa a ter os **3 anos positivos** pela primeira vez
(2024 z=+0,38, 2025 z=+0,12, 2026 z=+1,91) — antes sempre tinha algum
ano negativo. Ainda não é z≈2 na maioria dos anos, mas é um padrão mais
consistente do que o observado antes do reescalonamento.

## Interpretação

**Escanteios**: o sinal negativo é forte demais e consistente demais
(mesma direção nos 2 anos × 2 ligas × 3 limiares) pra ser só falta de
calibração fina — é mais provável que o motor de gols reaproveitado
tenha um viés sistemático específico pra escanteios (a suposição de
Poisson pode não caber bem na distribuição real de escanteios, ou o
histórico ponderado por estilo/favoritismo simplesmente não capta o
que determina escanteios tão bem quanto capta gols). Mesmo padrão do
1x2/Dupla Chance da Série B: não vale insistir com grid de parâmetros.

**Cartões**: sem edge defensável, mas por um motivo diferente — parece
ruído puro, não um viés sistemático. Isso bate com a intuição do Lucas:
cartões dependem muito do árbitro (rigor pessoal), um fator que o
modelo atual simplesmente não vê. Sem esse dado, qualquer calibração
fina estaria só ajustando ruído.

## Recomendação

1. **Não usar escanteios com o motor atual** — sinal negativo forte,
   confirmado que não é `limite_unilateral` mal escalado (testado e
   refutado) nem calibração de `k_mando`/`usar_estilo`/filtros
   (testado e refutado antes) — é mais estrutural.
2. **Não usar cartões com o motor atual** — mas o reescalonamento do
   corte de outlier mostrou melhora real de consistência (Série B com
   3 anos positivos pela primeira vez), então vale reavaliar cartões
   COM esse ajuste E o dado de árbitro juntos numa rodada futura, em
   vez de descartar de vez.
3. **Mantém a recomendação de usar só Over 2.5/BTTS** por enquanto —
   a busca por diversificação continua em aberto.

## Limitações

- Params usados foram neutros/padrão (`PARAMS_PADRAO`), sem grid de
  calibração — não fizemos uma busca extensa como fizemos pra gols.
  Decidimos não fazer essa busca dado o padrão do resultado (negativo
  forte e consistente em escanteios não é o tipo de coisa que
  calibração resolve; cartões precisa de dado novo, não de mais
  ajuste fino nos parâmetros já existentes).
- Linha de aposta usada foi "a mais líquida disponível por jogo" (mais
  bookmakers cotando), não uma linha fixa — reflete melhor o que
  aconteceria na prática (apostar na linha que o mercado oferece), mas
  significa que jogos diferentes usaram linhas diferentes.
- `n` por ano é da ordem de 120-370 — grande o suficiente pra
  confiar no padrão observado (negativo consistente em escanteios),
  mas isso é sobre 3 anos apenas (2024-2026, limite do plano gratuito
  do Sportmonks).

Reprodução: `metodologia_pesos/retrospectiva.py`
(`rodar_retrospectiva`), `metodologia_pesos/pesos.py`
(`probabilidade_over`, `probabilidade_implicita_2vias`), script de
orquestração ad-hoc (não versionado) usando os dados do Sportmonks
(`sportmonks_seriea.jsonl`/`sportmonks_serieb.jsonl`, não versionados
— odds reais de mercado, arquivo grande, mesma convenção de manter
dado bruto fora do repo).
