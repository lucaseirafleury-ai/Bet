# Retrospectiva estendida — os 12 mercados Pró/Contra (não só gols)

Até aqui as retrospectivas (mando, estilo) só validavam Gols Pró/Contra.
`retrospectiva.py` agora calcula os 12 indicadores completos (gols,
cartões, escanteios, chutes, chutes no gol, gols 1º tempo) e compara cada
um com o valor real do jogo. Rodado com os parâmetros já validados por
liga (Série A: `k_mando=None`; Série B: `k_mando=0.35`; ambas
`filtro_aderencia=0.65`, `limite_unilateral=4`, `multiplicador_dp=2.5`).

## 1. MAE por mercado (baseline, com estilo ativo)

Como os mercados têm escalas bem diferentes (gols ~1, escanteios ~5,
chutes ~15), o MAE relativo (`MAE / média real`) é o que permite comparar
entre eles — quanto menor, melhor a previsão proporcionalmente.

| Mercado | Série A: MAE rel. | Série B: MAE rel. |
|---|---|---|
| Chutes Pró | **0.294** (melhor) | **0.297** (melhor) |
| Chutes Contra | 0.323 | 0.316 |
| Chutes no Gol Pró | 0.358 | 0.400 |
| Escanteios Pró | 0.391 | 0.425 |
| Chutes no Gol Contra | 0.474 | 0.452 |
| Cartões Contra | 0.450 | 0.484 |
| Escanteios Contra | 0.505 | 0.545 |
| Cartões Pró | 0.587 | 0.601 |
| Gols Pró | 0.582 | 0.689 |
| Gols Contra | 0.760 | 0.788 |
| Gols 1ºT Pró | 1.064 | 1.093 |
| Gols 1ºT Contra | **1.337** (pior) | **1.320** (pior) |

**Leitura**: o modelo prevê proporcionalmente melhor mercados de volume
alto (chutes, escanteios) do que mercados de contagem baixa e mais
aleatória (gols, e principalmente gols no 1º tempo — MAE relativo >100%
significa que o erro médio é maior que a própria média do que está
tentando prever, ou seja, pouco melhor que "chutar a média da liga" nesse
mercado). Isso é esperado estatisticamente (eventos raros têm mais
variância relativa), não indica bug — mas é um sinal de que apostas
baseadas no "Gols 1ºT" desta metodologia merecem MENOS confiança que
apostas de escanteios/chutes, na forma como o modelo está hoje.

## 2. Ablação do estilo — agora em TODOS os 12 mercados

Pergunta: será que o estilo (indiferente pra gols, testado antes) importa
mais em escanteios — onde o protocolo original ("Princípio 5") já ligava
estilo a resultado? Comparação pareada SEM vs COM estilo, MAE relativo,
mesmo desenho de teste (mesmo conjunto de jogos nas duas condições):

| Mercado | Série A: Δ (sem−com) | Série B: Δ (sem−com) |
|---|---|---|
| Gols Pró | +0.0032 | −0.0015 |
| Gols Contra | −0.0026 | +0.0007 |
| Cartões Pró | +0.0035 | −0.0035 |
| Cartões Contra | −0.0005 | +0.0010 |
| **Escanteios Pró** | **−0.0030** | **−0.0022** |
| **Escanteios Contra** | **−0.0038** | **−0.0024** |
| Chutes Pró | −0.0024 | −0.0008 |
| Chutes Contra | +0.0009 | +0.0007 |
| Chutes no Gol Pró | +0.0003 | −0.0010 |
| Chutes no Gol Contra | −0.0029 | +0.0008 |
| Gols 1ºT Pró | −0.0047 | +0.0010 |
| Gols 1ºT Contra | −0.0024 | +0.0006 |

(Δ negativo = tirar o estilo melhorou o MAE relativo; positivo = tirar o
estilo piorou. Valores estão em fração de MAE relativo, ex. −0.0030 =
0.3 pontos percentuais.)

## Conclusão

**A resposta é não** — escanteios não é diferente. Em TODOS os 12
mercados, nas duas ligas, a diferença com/sem estilo fica abaixo de 0.005
(meio ponto percentual) de MAE relativo. Escanteios até tem Δ ligeiramente
negativo (tirar o estilo ajuda um pouquinho), mas na mesma ordem de
grandeza do resto — não há mercado onde o estilo se destaque como
relevante.

Isso reforça a conclusão do teste anterior (só gols): **os proxies atuais
de estilo (`estilo.py`) não estão contribuindo de forma mensurável em
nenhum dos 12 mercados**, com esta amostra e neste desenho de modelo. Não
significa que estilo de jogo seja irrelevante pro futebol — significa que
a forma atual de capturá-lo (posse + xG contra + proxies de escanteios/
cartões/chutes, calculados dos últimos 5 jogos) não está discriminando o
suficiente pra mover a agulha aqui.

## Recomendação

- Manter o estilo ativo no filtro/peso (não atrapalha, como já visto) mas
  não é mais tratado como validado — é um candidato a redesenho, não um
  pilar do modelo.
- Não vale a pena investir em estender esse teste pra outras variações
  (ex.: pesos diferentes por dimensão de estilo) até repensar os proxies
  em si — o problema provável não é o peso que o estilo recebe, é o que
  está sendo medido.
- Os MAEs relativos por mercado (seção 1) são úteis por si — sugerem
  priorizar assertividade em chutes/escanteios/cartões sobre "Gols 1ºT"
  ao decidir onde confiar mais na metodologia.

## Limitações

Mesmas de sempre: amostra de temporada parcial (~155 jogos/liga, rodada
24/38), e o MAE mede erro do ponto-estimado, não taxa de acerto de aposta
(que dependeria de definir limiares Over/Under por mercado, não feito
aqui).

Reprodução: `metodologia_pesos/retrospectiva.py`, `rodar_retrospectiva()`
já retorna `relatorio["mercados"]` com os 12 campos automaticamente — não
precisa mais rodar setup especial, é o comportamento padrão agora.
