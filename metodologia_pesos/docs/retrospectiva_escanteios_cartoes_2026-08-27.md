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
   não é problema de calibração.
2. **Não usar cartões com o motor atual** — sem edge, mas aberto a
   reavaliação SE incorporarmos dado de árbitro (Sportmonks expõe
   `referee_id` por jogo; falta calcular a média histórica de cartões
   de cada árbitro e incorporar como fator novo no modelo — trabalho
   de arquitetura, não feito nesta rodada).
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
