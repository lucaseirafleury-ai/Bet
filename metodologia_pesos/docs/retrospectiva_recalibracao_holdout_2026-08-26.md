# Recalibração com treino 2016-2022 / holdout 2023-2026 — nenhum parâmetro é durável

## Contexto

Depois de descobrir que os critérios campeões (calibrados só em
2023-2026) têm z≈0 quando testados no período completo 2016-2026
(`docs/retrospectiva_estabilidade_era_2026-08-26.md`), o próximo passo
natural era **inverter a lógica**: recalibrar do zero usando 2016-2022
como treino e 2023-2026 como holdout de verdade — testar se EXISTE
algum conjunto de parâmetros (não necessariamente os já escolhidos) que
seja durável através das eras, em vez de só aplicar o parâmetro já
otimizado em 2023-2026 a dados que ele nunca viu.

Série B fica de fora desta rodada — só tem dado de 2023 em diante, não
há "época antiga" pra treinar nela.

## Abordagem

Grid de 208 combinações por mercado, rodado inteiramente sobre
2016-2022 (2.659 jogos, ~2.431-2.659 avaliados dependendo de
`n_historico`):

- `k_mando ∈ {None, 0.35, 0.5, 0.7}` (4)
- corte de outlier ∈ {padrão (`mult_dp=2.5, uni=4`), apertado
  (`mult_dp=1.5, uni=2`)} (2)
- `n_historico ∈ {10, 15}` (2)
- variantes de estilo (13): sem estilo com `filtro_aderencia ∈
  {0, 0.5, 0.65, 0.8}` (4) + com estilo com `(filtro_estilo,
  filtro_favoritismo)` em 9 combinações curadas (incluindo os extremos
  e a diagonal 0/0,5/0,65/0,8)

Cada combinação avaliada em Over 2.5 e BTTS, 2 limiares de edge (5%,
8%) — 832 células no total. Rodado em paralelo (4 processos), ~2h45 de
execução. Seleção: só ROI de TREINO (2016-2022), exigindo `n≥15`
apostas — mesmo processo de sempre (nunca aceitar "vencedor" de amostra
minúscula).

## Resultado — nenhuma configuração tem edge real no treino (2016-2022)

**Over 2.5**: das 416 combinações qualificadas (`n≥15`), a MELHOR tem
ROI **negativo** (-2,7%, `z=-0,36`, n=211). Nenhuma configuração no
grid inteiro bate o mercado em 2016-2022.

**BTTS**: a melhor combinação chega a `ROI+2,5%, z=+0,37` (n=245) — tecnicamente
positivo, mas muito abaixo de qualquer limiar de significância usado
neste projeto (z≈2). É ruído, não sinal.

| Mercado | Melhor candidato (treino 2016-2022) | n | ROI | z |
|---|---|---|---|---|
| Over 2.5 | `k=None, apertado, n_hist=15, sem estilo, filtro=0.8, edge=8%` | 211 | **-2,7%** | -0,36 |
| BTTS | `k=0.35, apertado, n_hist=15, com estilo, filtro_estilo=0.8, filtro_favoritismo=0.8, edge=8%` | 245 | +2,5% | +0,37 |

Pra referência, os critérios campeões atuais (calibrados em
2023-2026), avaliados neste mesmo treino 2016-2022, confirmam o que já
tínhamos visto no teste de estabilidade por era:

| Critério campeão (2023-2026) | Treino 2016-2022: n | ROI | z |
|---|---|---|---|
| Over 2.5 (`k=0.5, sem estilo, filtro=0.8, apertado, n_hist=15`) | 300 | -7,0% | -1,12 |
| BTTS (`k=0.7, com estilo, filtro_estilo=0.8, filtro_favoritismo=0.65, padrão, n_hist=10`) | 463 | -4,5% | -0,92 |

## Interpretação — não é problema de calibração, é ausência de edge na época antiga

Isto muda a leitura do achado anterior. Não é só que os parâmetros
campeões (otimizados em 2023-2026) "não generalizam pra trás" — é que
**nenhuma configuração testada, de um grid de 208×2×2=832 avaliações,
encontra qualquer edge defensável em 2016-2022**, nem em Over 2.5 nem
em BTTS. Se o problema fosse simplesmente "ajuste fino errado" ou
"overfitting aleatório ao período de treino", seria esperado que ALGUMA
combinação entre 832 testadas aparecesse com um z alto por puro acaso
(efeito de comparação múltipla) — isso não aconteceu; o máximo absoluto
foi z=0,37.

Isso pesa a favor da explicação nº2 já levantada no relatório anterior:
**mudança real de regime de mercado**, provavelmente ligada à
regulamentação de apostas esportivas no Brasil (Lei 14.790/2023, casas
licenciadas desde 2024) — não uma falha de calibração que um grid mais
esperto resolveria. Em 2016-2022 aparentemente não havia esse tipo de
ineficiência de mercado pro nosso modelo capturar (ou as odds da época
já eram bem mais eficientes/maduras); o que aparece em 2023-2026 tem
cara de janela temporária, não de propriedade permanente do futebol
brasileiro.

## O que isso muda na prática

- **Não existe um "santo graal" de parâmetros durável nas 3 eras** —
  pelo menos não dentro deste grid e deste modelo. Não vale a pena
  insistir em buscar mais fundo por calibração (o problema não é
  calibração).
- **Mantém a recomendação prática atual**: usar os critérios calibrados
  em 2023-2026 pra apostar AGORA, com a confiança já rebaixada pra
  "moderada, específica do período recente" (ver
  `docs/retrospectiva_estabilidade_era_2026-08-26.md`).
- **Reforça a hipótese de regime temporário**: se o edge realmente vier
  da entrada de casas novas ainda calibrando modelos pro mercado
  brasileiro, é esperado que ele se erode com o tempo (as casas ficam
  mais precisas) — vale acompanhar se o ROI de 2026/2027 em diante
  começa a cair, o que confirmaria essa hipótese.

## Limitações

- Grid não é exaustivo — 208 combinações cobrem os eixos já validados
  nesta sessão, mas não é uma busca completa do espaço de parâmetros
  possível.
- Não foi feita uma segunda rodada de holdout formal (aplicar o "melhor
  candidato de treino" de volta em 2023-2026) porque nenhum candidato
  de treino passou perto de um z defensável — não há candidato
  legítimo pra promover a holdout.
- Qualidade/profundidade das odds em 2016-2022 não foi verificada
  (menos casas cotando, mercado menos líquido) — poderia explicar parte
  da ausência de edge além da hipótese de regulamentação.

Reprodução: `metodologia_pesos/retrospectiva.py`
(`rodar_retrospectiva`/`simular_apostas`), script de orquestração
ad-hoc paralelizado (não versionado), treino
`data/footystats_seriea_{2016..2022}`, mesma base de dados do teste de
estabilidade por era.
