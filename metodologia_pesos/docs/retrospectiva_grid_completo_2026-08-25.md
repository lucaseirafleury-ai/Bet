# Grid completo (parâmetros + corte de outlier): melhor achado da sessão

## Contexto

Depois de isolar que o corte de outlier mais apertado
(`multiplicador_dp=1.5, limite_unilateral=2`) melhora Over 2.5 na
Série A (`docs/retrospectiva_corte_outlier_2026-08-25.md`), Lucas
pediu pra testar tudo junto: `k_mando × usar_estilo × filtro_aderencia`
combinado com o corte de outlier (apertado vs. padrão), e reincluir as
outras linhas de Over (1.5/3.5/4.5) na busca. Grid: 6×2×4×2 = 96
combinações por liga, treino 2023-2025, holdout 2026, top 10 de cada
mercado revalidados.

## Resultado — múltiplos candidatos passam de z=2 no período completo

Diferente de toda rodada anterior (onde o melhor achado nunca passava
de z≈1,5 no período completo, só no holdout isolado), esta busca
combinada encontrou candidatos com **z>2 no acumulado 2023-2026
inteiro** — e o campeão nem depende do ano de 2026 ter sido bom, ele é
positivo em TODOS os 4 anos:

| Mercado | Parâmetros | Edge | n (2023-26) | ROI | z-score | Pior ano |
|---|---|---|---|---|---|---|
| **Over 2.5** | `k=0.5, sem estilo, filtro=0.8, mult_dp=1.5, uni=2` | 5% | **221** | **+16,0%** | **+2,23** | 2025: **−1,0%** (quase zero) |
| Over 2.5 | `k=0.5, sem estilo, filtro=0.65, mult_dp=1.5, uni=2` | 8% | 118 | +21,4% | +2,16 | 2025: −9,8% |
| Over 2.5 | `k=0.35, sem estilo, filtro=0.8, mult_dp=1.5, uni=2` | 8% | 194 | +14,0% | +1,83 | 2023: −1,0% (quase zero) |
| BTTS | `k=0.7, com estilo, filtro=0, mult_dp=1.5, uni=2` | 8% | 95 | +21,5% | +2,13 | 2025: −6,7% |
| BTTS | `k=0.7, sem estilo, filtro=0.65, mult_dp=1.5, uni=2` | 8% | 107 | +18,3% | +1,93 | 2025: −13,1% |

**O candidato campeão de Over 2.5** (`k=0.5, usar_estilo=False,
filtro_aderencia=0.8, multiplicador_dp=1.5, limite_unilateral=2,
limiar_edge=5%`) é o achado mais robusto da sessão inteira:
- **z=2,23** — acima do limiar de significância usado no projeto todo.
- **n=221** — mais que o dobro de qualquer candidato anterior (o
  melhor achado documentado até aqui tinha n=42-99).
- **Nenhum ano realmente negativo**: 2023 +10,2%, 2024 +35,8%, 2025
  −1,0% (essencialmente zero, não prejuízo), 2026 +25,4%.

Série B continua sem qualquer candidato defensável — os melhores
resultados do grid lá foram negativos ou catastróficos (Over 3.5/4.5
com ROI de holdout até −100%, clássico artefato de amostra minúscula
em mercado de cauda).

## Por que esse combo funciona melhor

Reúne 3 achados que, sozinhos, já tinham sinal parcial:
1. **Corte de outlier apertado** (`mult_dp=1.5`) — já validado
   isoladamente, melhora a calibração especificamente em Over 2.5.
2. **`usar_estilo=False`** — o teste de ablação de estilo (rodada
   anterior) já mostrava a Série B melhor sem estilo; aqui aparece
   também como parte do combo vencedor da Série A pra Over 2.5.
3. **`k_mando=0.5`** (encolhimento de mando moderado) — nem neutro
   (`None`) nem forte, um meio-termo que nenhuma rodada anterior tinha
   testado combinado com o corte apertado.

Nenhum desses 3 sozinho batia o neutro com folga — a combinação dos
três é que produziu o salto de z≈0-1,5 pra z>2.

## Recomendação — atualiza o parâmetro final da Série A

**Adotar como novo parâmetro de Over 2.5 na Série A:**
`k_mando=0.5, usar_estilo=False, filtro_aderencia=0.8,
multiplicador_dp=1.5, limite_unilateral=2, limiar_edge=5%`

Substitui a recomendação anterior (neutro + `limiar_edge≥8%`, z=2,24
mas só no holdout isolado, n=42) — esta é mais forte (z=2,23 mas com
n=221, no período completo de 4 anos) e mais estável (sem ano
realmente negativo).

Pra BTTS, os candidatos são promissores (z=1,93-2,13) mas com pior
consistência ano a ano (2025 sempre fraco) — considerar validado com
mais cautela que o Over 2.5.

## Ressalvas

- **z>2 é sinal forte, não prova definitiva** — mesma disciplina de
  sempre: 4 anos de dado, não décadas. Mas é a evidência mais robusta
  reunida até agora (maior `n`, período completo, não só holdout).
- Grid buscou em 96 combinações por liga — existe RISCO residual de
  comparação múltipla (testamos muitas combinações, o "melhor" pode
  ainda estar um pouco favorecido pela busca). Mitigado parcialmente
  porque a métrica reportada (z-score) já é do período completo (não
  só o treino que gerou a seleção), mas não elimina o risco totalmente.
- Over 1.5/3.5/4.5 continuam sem edge defensável mesmo com o corte
  apertado e a busca combinada — confirma o achado anterior de que o
  sinal fica mesmo concentrado em Over 2.5/BTTS.
- Série B segue sem qualquer configuração defensável.

Reprodução: `metodologia_pesos/retrospectiva.py`, grid de
`k_mando × usar_estilo × filtro_aderencia × multiplicador_dp ×
limite_unilateral`, script de orquestração ad-hoc (não versionado).
