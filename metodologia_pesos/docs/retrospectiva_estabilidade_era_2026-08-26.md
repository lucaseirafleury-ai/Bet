# Estabilidade por era (2016-2026) — o critério campeão NÃO é durável em 10 anos

## Contexto

Lucas conseguiu (plano pago FootyStats) 7 temporadas adicionais da
Série A (2016-2022), estendendo a cobertura de 4 pra 11 anos seguidos
(2016-2026). Testamos os dois critérios já adotados (Over 2.5 e BTTS,
com seus parâmetros campeões já validados) divididos em 3 blocos de
era, em vez de uma média só — exatamente pra evitar o problema que já
vimos antes (agregado escondendo decadência, caso do "casa" da Série B).

## Resultado — os dois critérios têm z≈0 no agregado de 11 anos

### Over 2.5 (`k=0.5, sem estilo, filtro=0.8, mult_dp=1.5, uni=2, edge=5%`)

| Período | n | Acerto | ROI | z |
|---|---|---|---|---|
| **2016-2026 (agregado)** | 578 | 47,2% | **+0,5%** | **+0,12** |
| Bloco 2016-2019 | 132 | 42,4% | −10,9% | −1,18 |
| Bloco 2020-2022 | 168 | 43,5% | −4,0% | −0,47 |
| Bloco 2023-2026 | 278 | 51,8% | +8,7% | +1,37 |
| ↳ 2024 (dentro do bloco) | 68 | 60,3% | +29,2% | +2,25 |
| ↳ 2025 (dentro do bloco) | 78 | 46,2% | −4,1% | −0,34 |

### BTTS (`k=0.7, com estilo, filtro_estilo=0.8, filtro_favoritismo=0.65, n_hist=10, edge=5%`)

| Período | n | Acerto | ROI | z |
|---|---|---|---|---|
| **2016-2026 (agregado)** | 540 | 50,4% | **+2,0%** | **+0,46** |
| Bloco 2016-2019 | 133 | 42,1% | −10,3% | −1,11 |
| Bloco 2020-2022 | 151 | 43,0% | −10,7% | −1,27 |
| Bloco 2023-2026 | 256 | 59,0% | +16,0% | +2,62 |

**Os dois critérios são claramente negativos em 2016-2022 (7 dos 11
anos) e só ficam positivos no bloco 2023-2026** — que é justamente o
único período usado pra calibrar TODOS os parâmetros já validados
nesta sessão (grid completo, corte de outlier, n_historico, filtros
separados etc.). Isso muda a leitura de forma importante.

## Por que isso está acontecendo — duas explicações, não excludentes

**1. Os parâmetros foram otimizados só em cima de 2023-2026** — todo
grid search desta sessão (k_mando/usar_estilo/filtro_aderencia/corte de
outlier/n_historico/filtro_estilo/filtro_favoritismo) rodou
exclusivamente nos dados que tínhamos até agora (2023-2026). É
esperado que uma configuração otimizada pra um período específico
performe pior fora dele — isso não prova ausência de qualquer edge,
prova que ESSA calibração específica é (pelo menos em parte) um ajuste
ao período de treino, não uma verdade universal do futebol brasileiro.

**2. Mudança real de regime de mercado** — o Brasil regulamentou
apostas esportivas (Lei 14.790/2023), com as primeiras casas
licenciadas operando a partir de 2024. Isso é uma hipótese concreta e
checável: entrada de várias casas novas, ainda calibrando modelos
específicos pro mercado brasileiro, pode ter criado uma janela de
ineficiência temporária que nosso modelo capturou — coincide bem com
o período em que o "edge" aparece (2023-2026, com destaque pro salto
em 2024). Se for isso, não é garantido que dure (as casas tendem a
ficar mais precisas com o tempo).

## O que isso NÃO significa

- **Não invalida o uso atual do critério** — pro que interessa (apostar
  agora, em 2026), o bloco 2023-2026 continua sendo o período mais
  relevante, e nele os dois critérios continuam positivos (embora Over
  2.5 mais fraco que o z=2,23 documentado antes — ver ressalva abaixo
  sobre a diferença de amostra).
- **Não prova que o futebol/mercado de 2016-2022 é "certo" e o de hoje
  é "errado"** — é perfeitamente possível que o jogo/mercado tenha
  mudado de fato (VAR, regulamentação de apostas, entrada de casas
  novas) e que o comportamento recente seja o que vale pra frente, não
  o antigo.

## O que isso muda na prática

- **Reduz a confiança que devemos depositar no "z=2,23"/"z=2,65"
  isolados do período 2023-2026** — eles não são mais a validação mais
  forte possível, porque não se sustentam quando testados fora da
  janela onde foram calibrados. Não eram falsos, mas eram mais frágeis
  do que pareciam.
- **Reabre a pergunta de fundo**: será que existe algum conjunto de
  parâmetros (não necessariamente os já escolhidos) que seja durável
  nos 3 blocos ao mesmo tempo? Isso exigiria recalibrar o grid usando
  só 2016-2022 como treino e testar em 2023-2026 como holdout de
  verdade (inverso do que fizemos até agora) — ainda não fizemos isso.

## Nota técnica sobre a diferença de `n` no bloco 2023-2026

O bloco 2023-2026 aqui mostra `n=278` (Over 2.5) e `n=256` (BTTS),
maiores que os `n=221`/`n=207` documentados antes. Motivo: com
histórico de 2016-2022 disponível, jogos do INÍCIO de 2023 (que antes
eram pulados por falta de histórico suficiente, já que não tínhamos
nada anterior a 2023) agora entram na avaliação — e o ROI desses jogos
adicionais parece ser pior, puxando o bloco pra baixo (z=1,37 aqui vs.
z=2,23 documentado antes só com 2023-2026 isolado). Isso por si só já é
uma lição: o "z=2,23" anterior também dependia parcialmente de qual
recorte exato de jogos entrava na conta — mais um motivo pra tratar
esse número com mais cautela do que se estava tratando antes.

## Recomendação

1. **Não abandonar os critérios atuais** — mas rebaixar a confiança
   estatística de "forte" pra "moderada, específica do período recente,
   com hipótese plausível de causa (regulamentação de apostas no
   Brasil)".
2. **Próximo passo natural**: recalibrar o grid completo usando
   2016-2022 como treino e 2023-2026 como holdout — inverte a lógica
   atual e testa se ALGUM parâmetro é durável através das eras, em vez
   de só aplicar o parâmetro já escolhido em dado que ele nunca viu.
3. Atualizar `docs/protocolo.md`/`README.md` com essa ressalva
   destacada — é importante demais pra ficar só num relatório à parte.

## Limitações

- Só testamos os parâmetros JÁ escolhidos (otimizados em 2023-2026) —
  não foi feita uma recalibração do zero usando os 11 anos.
- `n` por bloco antigo é relativamente pequeno (132-168), z não é
  conclusivo isoladamente pra nenhum bloco — o que importa aqui é o
  PADRÃO (negativo nos dois blocos antigos, positivo só no recente),
  não o valor exato de cada z.
- Não verificamos se a qualidade/profundidade das odds (quantas casas
  cotam, liquidez) é a mesma nos anos mais antigos — isso poderia
  explicar parte da diferença também.

Reprodução: `metodologia_pesos/retrospectiva.py`
(`rodar_retrospectiva`/`simular_apostas`, mesmos parâmetros já
documentados), script de orquestração ad-hoc (não versionado),
usando `data/footystats_seriea_{2016..2025}` + `data/footystats_seriea`
(2026).
