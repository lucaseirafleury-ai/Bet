# Recalibração de Over 2.5 (Série A) 100% Sportmonks — sem candidato defensável

## Contexto

Com a decisão de ir 100% Sportmonks (cancelar FootyStats), validamos os
2 critérios campeões usando stats+odds só do Sportmonks
(`docs/retrospectiva_validacao_100_sportmonks_2026-08-27.md` — ver
seção "Estado atual" em `protocolo.md`). BTTS se sustentou bem
(z=+2,33). Over 2.5 despencou (z=+2,23 → +0,49) — esperado, já que os
parâmetros campeões foram calibrados especificamente pra escala e
margem do FootyStats. Rodamos um grid novo, específico pro Sportmonks,
antes de descartar o mercado de vez.

## Método

Grid `k_mando × usar_estilo × filtro_aderencia × multiplicador_dp ×
limite_unilateral` (192 combinações de modelo) × 3 limiares de edge
(0%/5%/8%) = 576 configurações, sobre a Série A 100% Sportmonks (999
jogos, só 3 temporadas — 2024/2025/2026, mais raso que os 4 anos do
grid original em FootyStats). Ordenado por z-score do período completo
(`n≥15`).

## Resultado — o topo do grid é inflado por 2026 (temporada incompleta), não é achado real

O melhor candidato (`k=0.35, sem estilo, filtro=0.65, mult_dp=1.5,
uni=4, edge=8%`) dá z=+2,28 agregado (n=94) — à primeira vista pareceria
passar do limiar. Mas o padrão ano a ano é revelador:

| Ano | n | ROI | z |
|---|---|---|---|
| 2024 | 27 | +31,0% | +1,44 |
| 2025 | 44 | **+5,4%** | **+0,33** |
| 2026 | 23 | +57,1% | **+2,83** |

**2025 (temporada completa, maior n) fica praticamente zero.** Todo o
z agregado vem de 2026 — temporada AINDA EM ANDAMENTO, com só 23
apostas e um ROI de +57% que é ele mesmo uma bandeira vermelha (ROI
implausivelmente alto vindo de uma amostra pequena, mesmo padrão de
"sorte de amostra pequena" que já vimos com cartões+árbitro em 2024 e
com o achado original de Série B BTTS).

**Isso não é exceção do candidato #1 — é o padrão de TODO o top 15 do
grid**: em todas as 15 melhores configurações, 2025 fica entre −0,72 e
+0,33 (nunca forte), e 2026 é sempre o ano que carrega o z agregado
(z entre +1,83 e +3,07). Recalculando o z combinado só com os anos
completos e maiores (2024+2025, excluindo 2026): para o candidato #1,
`z_combinado ≈ (1,44×√27 + 0,33×√44) / √71 ≈ 1,15` — bem abaixo do
limiar de z≈2, e olhando só o ano mais recente completo (2025) o
resultado é ruído puro.

## Conclusão

**Não há candidato defensável de Over 2.5 na fonte 100% Sportmonks.**
O aparente z≈2+ do topo do grid é um artefato de temporada incompleta
(2026) com amostra pequena, não um achado real — mesma disciplina que
já rejeitou outros casos parecidos nesta sessão (Série B BTTS
reavaliado, Favorito DC). Diferente do Cartões+Árbitro (que também tem
uma inflação de amostra pequena, mas pelo menos os anos completos
isolados já mostram sinal positivo), aqui o ano completo mais recente
(2025) é neutro — não há nem uma pista fraca pra acompanhar.

**Recomendação**: excluir Over 2.5 do painel automatizado por
enquanto. Reavaliar quando a temporada 2026 completar e 2027 começar a
entrar na amostra (mais dado real, menos dependência de uma temporada
parcial). Reprodução:
`/tmp/.../scratchpad/grid_over25_sportmonks.py` +
`sportmonks_adapter.py` (ad-hoc, não versionado).
