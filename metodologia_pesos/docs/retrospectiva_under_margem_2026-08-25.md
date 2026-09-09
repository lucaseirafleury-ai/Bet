# Under com margem de casa assumida (~7-8%) — viés corrigido, mas ainda sem edge

## Contexto

O teste anterior de Under (margem assumida = 0%,
`docs/retrospectiva_under_aproximado_2026-08-25.md`) deu ROI positivo
em 24/24 combinações — sinal claro de viés sistemático da fórmula, não
de edge real. Lucas perguntou se dava pra assumir uma margem de casa
(~7%) em vez de zero, pra corrigir isso.

Antes de rodar, medimos a margem REAL desta fonte de dado (FootyStats)
nos mercados que já trazem os dois lados (1x2 e BTTS sempre têm):

| Liga | Margem 1x2 (média/mediana) | Margem BTTS (média/mediana) |
|---|---|---|
| Série A | 7,04% / 6,25% | 7,14% / 7,14% |
| Série B | 8,71% / 8,21% | 7,70% / 7,50% |

Usamos **7% pra Série A e 8% pra Série B** (arredondando as médias
medidas) como `margem_under` em `pesos.odd_e_prob_under_aproximada`
(implementado nesta sessão, commit `a044e43`): em vez de
`prob_under = 1 - prob_over_bruta` (margem zero, o viés otimista),
passa a ser `prob_under = (1 + margem) - prob_over_bruta`.

## Resultado — o viés sistemático desaparece

| Liga | Mercado | edge=0% | edge=5% | edge=8% |
|---|---|---|---|---|
| Série A | Under 1.5 | n=749, −14,9%, z=−2,98 | n=580, −13,5%, z=−2,36 | n=480, −11,9%, z=−1,90 |
| Série A | Under 2.5 | n=740, −10,3%, z=−3,35 | n=591, −7,8%, z=−2,27 | n=489, −7,4%, z=−1,93 |
| Série A | Under 3.5 | n=715, +0,5%, z=+0,20 | n=500, +1,5%, z=+0,48 | n=345, +2,4%, z=+0,60 |
| Série A | Under 4.5 | n=580, −0,8%, z=−0,37 | n=136, +9,8%, z=+1,23 | n=39, +33,5%, z=+1,27 |
| Série B | Under 1.5 | n=759, −9,5%, z=−2,15 | n=620, −11,5%, z=−2,36 | n=545, −12,6%, z=−2,45 |
| Série B | Under 2.5 | n=765, −6,0%, z=−2,27 | n=620, −5,6%, z=−1,90 | n=524, −4,2%, z=−1,32 |
| Série B | Under 3.5 | n=694, −2,2%, z=−1,35 | n=422, −3,3%, z=−1,52 | n=265, −5,3%, z=−1,83 |
| Série B | Under 4.5 | n=441, −3,4%, z=−2,70 | n=18, −8,0%, z=−0,78 | n=3, −13,7%, z=−0,31 |

**Só 5 de 24 combinações dão ROI positivo agora** (contra 24/24 com
margem zero), e nenhuma delas passa de z=1,3 — nenhuma se aproxima do
limiar de significância (~2) do resto do projeto. As combinações com
`n` maior e mais confiável (Under 1.5/2.5, `n` na casa de 500-760) são
**consistentemente negativas** nas duas ligas, com z-scores fortemente
negativos (até z=−3,35). As poucas "positivas" (Under 4.5 com edge
alto) têm `n` pequeno demais (18-39) pra significar qualquer coisa.

## Interpretação

1. **A correção de margem funcionou como esperado** — o padrão
   "positivo em tudo, sempre" (assinatura clássica de viés sistemático,
   não de edge) desapareceu completamente. Isso é evidência de que
   assumir uma margem realista (em vez de zero) é a correção certa a
   fazer nesta aproximação.
2. **Mesmo corrigido, não aparece edge real em Under** — pelo
   contrário, os mercados com amostra confiável (Under 1.5/2.5) mostram
   desvantagem estatisticamente relevante (z<−1,9 na maioria dos casos).
   Isso é coerente com o próprio critério campeão de Over 2.5 (o modelo
   tende a favorecer Over com edge real) — o espelho disso é que apostar
   no lado oposto (Under) tende a ser pior que o mercado, não melhor.
3. Continua sendo uma ODD APROXIMADA, não real — mesmo com a correção
   de margem, o valor de `margem_under` (7%/8%) é uma média da liga
   toda, não a margem exata de cada jogo/casa específica. O resultado
   negativo não deve ser lido como "Under é ruim, prova estatística
   definitiva" — é "não há evidência de edge, e ainda existe sinal de
   desvantagem", o que já é suficiente pra não recomendar.

## Recomendação — mantém a decisão anterior, por um motivo mais forte

**Não usar nenhum critério de Under pra apostar dinheiro real** —
continua valendo, mas agora por um motivo mais sólido: não é só "o
teste tinha viés" (ponto anterior), é "mesmo corrigindo o viés
conhecido, não aparece edge nenhum, e boa parte dos mercados mostra
desvantagem". Duas conclusões independentes apontando na mesma direção.

O critério vigente continua sendo só Over 2.5 na Série A (odd REAL de
mercado, z=+2,23, ROI+16,0%, n=221).

## Limitações

- `margem_under` é uma média por liga, não a margem real jogo a jogo —
  ainda uma aproximação, não substitui ter a odd real de Under.
- Mesma ressalva de sempre: período de 4 anos, `n` variável entre
  mercados/edges.
- Não testamos outros valores de margem além de 7%/8% (poderia haver
  um valor de margem que "zera" o viés perfeitamente sem revelar nem
  edge nem desvantagem — não foi o objetivo aqui, o objetivo era
  verificar se a correção elimina o artefato óbvio, o que aconteceu).

Reprodução: `metodologia_pesos/pesos.py::odd_e_prob_under_aproximada`
(parâmetro `margem_total`), `retrospectiva.py` (`PARAMS_PADRAO["margem_under"]`),
script de orquestração ad-hoc (não versionado).
