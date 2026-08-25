# Teto de odd máxima por mercado — não altera o campeão, ajuda BTTS

## Contexto

Lucas pediu pra testar um teto de odd máxima na entrada de cada
mercado (evita apostar em odds "longas" demais, mesmo quando o modelo
acha que tem edge):

| Mercado | Teto de odd |
|---|---|
| Over 1.5 | 1,5 |
| Over 2.5 | 3,0 |
| Over 3.5 | 6,0 |
| Over 4.5 | 7,0 |
| BTTS | 2,0 |

Rodado em cima dos parâmetros já adotados como padrão (`k_mando=0.5,
usar_estilo=False, filtro_aderencia=0.8, multiplicador_dp=1.5,
limite_unilateral=2` — o combo campeão de
`docs/retrospectiva_grid_completo_2026-08-25.md`), comparando "com
teto" vs. "sem teto" em 3 limiares de edge (0%, 5%, 8%), nas duas
ligas, período completo 2023-2026.

## Resultado principal — o critério campeão de Over 2.5 não muda

No critério já adotado (Over 2.5, `limiar_edge=5%`), **o teto de 3,0
não filtra nenhuma aposta**: com teto e sem teto dão exatamente os
mesmos números (`n=221, ROI+16,0%, z=+2,23`), inclusive ano a ano
idênticos. Ou seja, nenhuma aposta que passa no filtro de edge desse
critério tem odd de mercado acima de 3,0 — o teto é redundante para
esse caso específico, não uma proteção adicional nem uma restrição
que perde apostas boas.

## BTTS — o teto ajuda de verdade (mas com ressalva importante)

| Config | n | ROI | z |
|---|---|---|---|
| Sem teto, edge=5% | 192 | +4,7% | (menor) |
| **Com teto ≤2,0, edge=5%** | **126** | **+13,1%** | **+1,56** |
| Sem teto, edge=8% | 148 | +7,0% | — |
| Com teto ≤2,0, edge=8% | 98 | +11,1% | +1,16 |

O teto corta as apostas de odd mais alta (mais arriscadas/voláteis) e
o ROI/z sobem de forma consistente nos dois limiares de edge testados.
**Ressalva**: este teste usou os parâmetros de modelo do combo de Over
2.5 (`usar_estilo=False, filtro=0.8`), não os parâmetros específicos de
BTTS já achados antes (`k=0.7, usar_estilo=True, filtro=0`, z=2,13 em
`docs/retrospectiva_grid_completo_2026-08-25.md`). Ainda não testamos
"melhor combo de BTTS + teto de odd" juntos — é a pista mais promissora
que sobra desta rodada, não uma conclusão fechada.

## Outros mercados — sem mudança de diagnóstico

- **Over 4.5**: sem teto o ROI desaba (-10% a -26%, claramente puxado
  por apostas de odd muito alta); com teto vira positivo, mas `n`
  fica pequeno (50-98) — não dá pra tratar como conclusivo, mesma
  disciplina de sempre com amostra pequena.
- **Over 1.5 e Over 3.5**: continuam fracos (z<1,1) com ou sem teto —
  confirma o achado anterior de que o sinal real fica concentrado em
  Over 2.5/BTTS, o teto não resgata esses mercados.
- **Série B**: nenhum mercado fica defensável mesmo com teto — a
  maioria continua com z fortemente negativo (ex.: Over 3.5, edge=0%,
  z=-2,85; Over 2.5, edge=5%, z=-2,60). O teto às vezes até piora
  levemente o ROI, porque corta o pouco volume que já existia sem
  resolver o problema de fundo (falta de edge real nessa liga).

## Recomendação

- **Não é necessário adicionar o teto de odd ao critério campeão de
  Over 2.5** — ele já não pega apostas de odd alta nesse filtro, então
  a mudança seria cosmética (mesmo resultado, código a mais).
- **Considerar testar o teto de BTTS (≤2,0) combinado com os
  parâmetros específicos de BTTS** numa rodada futura, antes de
  adotá-lo oficialmente — o sinal isolado é promissor mas ainda não
  foi testado com o combo certo de parâmetros de modelo.
- Over 1.5/3.5/4.5 e Série B seguem sem recomendação de uso.

## Limitações

- Mesma ressalva de sempre: período de 4 anos (2023-2026), não décadas.
- BTTS aqui usa parâmetros de modelo que não são os ótimos pra esse
  mercado especificamente — o teste isolou só o efeito do teto de odd,
  não é a combinação final recomendada.
- Over 4.5 com teto tem `n` pequeno demais (50-98) pra qualquer
  conclusão forte.

Reprodução: `metodologia_pesos/retrospectiva.py`
(`rodar_retrospectiva`/`simular_apostas`), filtro adicional de odd
máxima aplicado no script de orquestração ad-hoc (não versionado).
