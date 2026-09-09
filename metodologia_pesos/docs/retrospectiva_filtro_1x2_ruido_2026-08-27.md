# 1x2 casa Série A e mandante_dc Série B: filtro não ajuda quando não há edge de base

## Contexto

Terceira e quarta rodadas da varredura pedida pelo Lucas — os "dois
mais promissores" restantes que não são correlacionados com o Over
Série A: **1x2 casa Série A** (o melhor caso do grid original, z=+0,27
— `docs/retrospectiva_1x2_dc_2026-08-25.md`) e **mandante_dc Série B**
(z=+0,09 — `docs/retrospectiva_1x2_dc_novos_eixos_2026-08-25.md`).

**Diferença importante em relação às 2 rodadas anteriores**: esses dois
partem de z≈0 (ruído puro), não de um edge real que decaiu (caso do
"casa" Série B, z=+2,71 antes de morrer) nem de um critério já positivo
(caso do Over 2.5-Sbo). Filtrar dentro de uma amostra que nunca teve
edge é minerar ruído — risco de comparação múltipla ainda maior que
nos casos anteriores.

## Revalidação com dado atual (Sportmonks, bet365)

| Critério | n | Acerto | ROI | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| 1x2 casa Série A | 274 | 46,4% | +7,0% | +22,9% | +0,2% | +0,2% |
| mandante_dc Série B | 303 | 74,6% | −3,3% | +0,6% | −4,9% | −6,9% |

Confirma o z≈0 original — casa Série A fica flat em 2025/2026 (só 2024
carrega o agregado); mandante_dc Série B já é levemente negativo,
piorando ano a ano.

## Filtro-mineração: nenhum corte produz subgrupo limpo

Testei as mesmas 7 features de sempre (odd, edge, probabilidade do
modelo, probabilidade de mercado, `gf_pred`/`ga_pred`/diferença), corte
pela mediana, checando ano a ano:

- **1x2 casa Série A**: alguns cortes têm diferença de ROI agregado
  (ex.: `prob_modelo`≤mediana ROI+15,2% vs >mediana ROI−1,2%), mas
  NENHUM lado de NENHUM corte tem os 3 anos positivos — o que parece
  bom em 2024 vira fraco ou negativo em 2025 ou 2026 sempre.
- **mandante_dc Série B**: pior ainda — praticamente todo corte fica
  negativo (ou perto de zero) dos dois lados, nos 3 anos. Não há
  absolutamente nada pra resgatar aqui.

## Interpretação

Confirma a hipótese levantada antes de rodar: mercados que já são
ruído desde o início (nunca passaram perto de z=2 em nenhuma
configuração testada) não têm um subconjunto escondido com edge —
diferente de um sinal que já foi real e decaiu (onde pelo menos existe
uma explicação causal, mercado ficou eficiente), aqui simplesmente
nunca existiu informação que o modelo de Poisson pro resultado (1x2)
capturasse além do que a odd já precifica.

## Recomendação

**Não vale continuar testando 1x2/DC por filtro.** Os 2 casos "menos
ruins" (`casa` Série A e `mandante_dc` Série B) foram os melhores
candidatos disponíveis nessa família de mercado e nenhum rendeu nada.
Os demais (empate, fora, visitante_dc, nas duas ligas) já são
negativos de forma mais clara (`docs/retrospectiva_1x2_dc_2026-08-25.md`)
— não há razão pra esperar resultado melhor deles. Fechar a família
1x2/DC inteira como "sem edge, mesmo com filtro".

## Verificação

- `n` de cada corte reportado (mínimo 136); nenhum corte "promissor"
  passou na checagem ano a ano.
- Reprodução: scripts ad-hoc rodados nesta sessão
  (`retrospectiva.rodar_retrospectiva`/`simular_apostas`, mercados
  `"casa"`/`"mandante_dc"`, dado Sportmonks bet365) — não versionados.
