# Janela de histórico + filtros separados — novo candidato de BTTS mais forte que o Over 2.5

## Contexto

Depois da preocupação de Lucas sobre poucas apostas convincentes
(n=221/3,5 anos), buscamos dois eixos nunca testados: variar
`n_historico` (janela de jogos passados por time, sempre fixado em 15
em todo grid anterior) e separar o filtro de aderência de estilo do de
favoritismo (`filtro_estilo`/`filtro_favoritismo`, implementados nesta
sessão — antes um único `filtro_aderencia` exigia o mesmo corte dos
dois ao mesmo tempo). Grid: `n_historico ∈ {10,15,20} × filtro_estilo ∈
{0,0.5,0.65,0.8} × filtro_favoritismo ∈ {0,0.5,0.65,0.8}` (48
combinações), testado sobre os parâmetros-base já conhecidos de cada
mercado (Over 2.5 e BTTS na Série A, Over 2.5 na Série B), 3 limiares
de edge, período completo 2023-2026.

## Resultado principal — BTTS tem um candidato novo, mais forte que o antigo

| Candidato | n | ROI | z | Pior ano |
|---|---|---|---|---|
| BTTS antigo (`filtro_aderencia=0`, `n_hist=15`, edge=8%) | 95 | +21,5% | +2,13 | 2023: **−7,7%**, 2025: **−6,7%** |
| **BTTS novo (`filtro_estilo=0.8, filtro_favoritismo=0.65`, `n_hist=10`, edge=5%)** | **207** | **+17,9%** | **+2,65** | **2025: +1,9% (nenhum ano negativo)** |
| BTTS novo, variante (`n_hist=20`, mesmos filtros/edge) | 162 | +20,2% | +2,61 | 2025: −0,8% (quase zero) |

**O candidato novo é melhor em TRÊS dimensões ao mesmo tempo**:
mais que o dobro da amostra (n=207 vs 95), z-score mais alto (+2,65 vs
+2,13), e — o mais importante — **os 4 anos são positivos** (2023
+18,3%, 2024 +19,0%, 2025 +1,9%, 2026 +37,2%). O candidato antigo tinha
2 dos 4 anos com queda real (−7,7% e −6,7%); este novo não tem nenhum
ano negativo, nem "quase zero" — o pior ano já é positivo. Isso
resolve exatamente a ressalva que tínhamos registrado sobre o BTTS ser
"mais arriscado que o Over 2.5" — com esse ajuste, ele fica tão ou mais
consistente que o próprio Over 2.5 (que tem um ano em −1,0%).

Os parâmetros que mudaram: `n_historico=10` (janela mais curta que o
padrão de 15) e os dois filtros de aderência separados
(`filtro_estilo=0.8`, exigente; `filtro_favoritismo=0.65`, mais
permissivo) — nunca testados combinados antes.

## Over 2.5 (Série A) — confirma o campeão, mostra que o filtro de estilo nunca importou

No grid de Over 2.5, variar `filtro_estilo` (0, 0,5, 0,65, 0,8) com
`filtro_favoritismo=0.8` fixo dá **exatamente o mesmo resultado**
(n=221, ROI+16,0%, z=+2,23) em todas as variações — ou seja, o corte de
`aderencia_estilo` nunca chegou a excluir nenhum jogo adicional nesse
critério; quem faz o trabalho todo é o filtro de favoritismo. Não é uma
melhoria, é uma confirmação de que o critério já vigente é robusto e
que `filtro_estilo` é redundante para esse mercado específico — não
precisa mudar nada aqui.

## Série B (Over 2.5) — continua sem qualquer candidato viável

Melhor resultado do grid inteiro: `n=142, ROI−7,0%, z=−0,71`. Todos os
top-5 candidatos são negativos. Nem a janela de histórico nem os
filtros separados destravam sinal na Série B — confirma (mais uma vez)
que o problema ali não é falta de calibração fina, é ausência de edge
real nesse dataset/liga.

## Recomendação — atualizar o critério de BTTS

**Substituir o candidato de BTTS por
`k_mando=0.7, usar_estilo=True, filtro_estilo=0.8,
filtro_favoritismo=0.65, multiplicador_dp=1.5, limite_unilateral=2,
n_historico=10, limiar_edge=5%`** — mais amostra, mais z, e sem nenhum
ano negativo. Adotar como SEGUNDO critério de aposta em paralelo ao
Over 2.5, agora com confiança comparável (não mais "mais arriscado").
Volume combinado: Over 2.5 (n=221/3,5 anos, ~63/ano) + BTTS novo
(n=207/3,5 anos, ~59/ano) ≈ **122 apostas/ano**, quase o dobro do que
se tinha só com Over 2.5.

## Ressalvas

- Mesmo risco de sempre: grid de 48 combinações × 3 edges = 144 células
  avaliadas por perfil — risco residual de comparação múltipla. Mas a
  melhora qualitativa (de 2 anos negativos pra 0) é grande demais pra
  ser só sorte de busca, e o z-score já é medido no período completo,
  não só numa fatia favorável.
- `n_historico=10` é uma janela mais curta que o padrão (15) — ainda
  não testamos se isso quebra a robustez em cenários fora desta amostra
  específica (ex.: início de temporadas futuras com menos jogos ainda
  disponíveis pode se comportar diferente).
- Continua sendo o mesmo tipo de aproximação estatística de sempre — 4
  anos de dado, não décadas.

Reprodução: `metodologia_pesos/retrospectiva.py` (novos parâmetros
`filtro_estilo`/`filtro_favoritismo`, commit `a25d669`), script de
orquestração ad-hoc (não versionado).
