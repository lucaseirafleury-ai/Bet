# Under com odds REAIS do Sportmonks — confirma: não usar (27/08/2026)

## Contexto

Under já tinha sido testado 2x nesta sessão usando uma odd
*aproximada* (o CSV do FootyStats não traz odd real de Under, só de
Over) — ver `docs/retrospectiva_under_aproximado_2026-08-25.md` e
`docs/retrospectiva_under_margem_2026-08-25.md`. Com a margem de casa
corrigida (~7-8%), o viés grosseiro desapareceu, mas o resultado ficou
negativo nos mercados líquidos (Under 1.5/2.5, z até −3,35) — conclusão
registrada foi "não usar Under até termos odd REAL desse lado".

Essa condição mudou: já temos os arquivos brutos do pull do Sportmonks
(Estágio A da investigação de escanteios/cartões) com o mercado 80
(Goals Over/Under) cobrindo todas as linhas usuais com odds reais dos
dois lados. Lucas pediu pra refazer o teste de Under com essa odd real,
usando os dois conjuntos de parâmetros já campeões (Over 2.5 e BTTS),
nas duas ligas.

## Método

Walk-forward normal (`retrospectiva.rodar_retrospectiva`) com cada
conjunto de parâmetros já homologado (Over 2.5: `k=0.5, sem estilo,
filtro=0.8, mult_dp=1.5, uni=2, n_hist=15`; BTTS: `k=0.7, com estilo,
filtro_estilo=0.8, filtro_favoritismo=0.65, mult_dp=1.5, uni=2,
n_hist=10`), sobre o histórico completo do FootyStats disponível
(Série A 2016-2026, Série B 2023-2026). Pra cada jogo casado com o
Sportmonks (por nome+data, ±1 dia), pegamos a odd real média de
Over/Under nas linhas 1.5/2.5/3.5/4.5 (mercado 80), calculamos o edge
do lado Under (`prob_mercado_over − prob_modelo_over`) e só contamos
como aposta quando esse edge ≥ 5% (mesmo limiar dos dois critérios
campeões). Avaliação restrita a 2024-2026, período em que o Sportmonks
tem par (~999-1000 jogos por liga, 3 temporadas grátis).

## Resultado — negativo em TODAS as 16 células, sem exceção ano a ano

| Liga | Params do modelo | Linha | n | ROI | z | Pior ano |
|---|---|---|---|---|---|---|
| Série A | Over 2.5 | Under 1.5 | 459 | −18,9% | **−3,00** | todos negativos |
| Série A | Over 2.5 | Under 2.5 | 508 | −12,2% | **−3,23** | todos negativos |
| Série A | Over 2.5 | Under 3.5 | 520 | −2,7% | −1,20 | todos negativos |
| Série A | Over 2.5 | Under 4.5 | 452 | −3,8% | −2,48 | todos negativos |
| Série A | BTTS | Under 1.5 | 446 | −19,9% | **−3,12** | todos negativos |
| Série A | BTTS | Under 2.5 | 481 | −9,5% | −2,41 | todos negativos |
| Série A | BTTS | Under 3.5 | 486 | −2,4% | −1,01 | 2024 (+1,6%, único positivo) |
| Série A | BTTS | Under 4.5 | 448 | −3,2% | −2,13 | todos negativos |
| Série B | Over 2.5 | Under 1.5 | 484 | −9,4% | −1,66 | todos negativos |
| Série B | Over 2.5 | Under 2.5 | 510 | −7,8% | −2,35 | todos negativos |
| Série B | Over 2.5 | Under 3.5 | 510 | −3,6% | −1,81 | todos negativos |
| Série B | Over 2.5 | Under 4.5 | 483 | −3,6% | **−2,97** | todos negativos |
| Série B | BTTS | Under 1.5 | 483 | −10,3% | −1,83 | todos negativos |
| Série B | BTTS | Under 2.5 | 531 | −5,3% | −1,64 | todos negativos |
| Série B | BTTS | Under 3.5 | 533 | −1,8% | −0,96 | 2025 (−0,3%, quase zero) |
| Série B | BTTS | Under 4.5 | 486 | −3,4% | **−2,83** | todos negativos |

**47 dos 48 recortes ano-a-ano são negativos** (só 1 exceção, Série
A/BTTS/Under 3.5 em 2024, com ROI+1,6% — ruído, não sinal: nem essa
célula agregada é positiva). Não há UMA célula, muito menos uma
consistente ano a ano, que sugira qualquer edge no lado Under, com
odd real, em nenhuma combinação testada.

## Interpretação

Isso fecha a dúvida que ficou aberta nos testes anteriores. Com odd
aproximada, era possível que o resultado negativo fosse um artefato da
aproximação (mesmo depois de corrigir a margem). Com odd REAL de
mercado, o resultado é o mesmo — na verdade mais negativo e mais
consistente ano a ano do que antes. Confirma que o mercado de Over
(gols) está com o overround do lado Over "certo" pro nosso modelo, e o
lado Under, precificado pelo mesmo bookmaker, simplesmente não deixa
edge equivalente pro nosso modelo capturar — não é uma limitação da
nossa fonte de dado, é o mercado mesmo.

## Recomendação

**Não apostar em Under, em nenhuma linha, com nenhum dos dois conjuntos
de parâmetros, em nenhuma das duas ligas.** Diferente do "aguardando
mais dado" do critério de cartões+árbitro, aqui a evidência já é forte
o bastante (n grande, negativo em quase todos os anos, duas fontes de
odd independentes concordando) pra tratar como encerrado, não como algo
a reabrir sem uma mudança de motor de verdade.

Reprodução: `/tmp/.../scratchpad/teste_under_odds_reais.py` (ad-hoc, não
versionado), reaproveitando `retrospectiva.rodar_retrospectiva`,
`pesos.probabilidade_over`/`probabilidade_implicita_2vias`, e
`cartoes_arbitro.odd_media_na_linha` (função genérica, não específica
de cartões).
