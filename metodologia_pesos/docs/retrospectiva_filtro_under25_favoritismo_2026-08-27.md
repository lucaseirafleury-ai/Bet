# Testando favoritismo/odd no Under 2.5 (Série A): hipótese não se confirma

## Contexto

Lucas notou que, no Over 2.5-Sbo, jogos com favorito claro e/ou odd
alta de Over tendem a "fechar" mais (menos gols) — e perguntou se esse
mesmo padrão rende um filtro que dê edge pro lado Under 2.5, Série A
(mercado já testado e descartado antes,
`docs/retrospectiva_under_odds_reais_2026-08-27.md`, 47/48 células
ano-a-ano negativas).

**Nuance importante, verificada empiricamente aqui**: "Over foi pior
nesses jogos" não é o mesmo que "existe edge real pra Under nesses
jogos" — a odd de Over já embute a visão do mercado de que esses jogos
tendem a ter menos gols (é parte do motivo dela ser alta). Edge de
verdade em Under exige que o MODELO ache uma probabilidade de Under
maior que a implícita na odd REAL de Under — não basta o Over ter ido
mal.

## Método

Mesmo motor (`retrospectiva.rodar_retrospectiva`) com os parâmetros do
Over 2.5-Sbo em produção (`k_mando=0.35, usar_estilo=False,
filtro_aderencia=0.65, multiplicador_dp=1.5, limite_unilateral=4,
n_historico=15`) sobre a Série A. Odd real de Under 2.5 puxada direto
do JSONL bruto do Sportmonks (mercado 80, `label="Under"`,
bookmaker **bet365**, não Sbo — cobertura de 999/999 fixtures contra
812/999 da Sbo, mais robusto pra esse teste específico). Margem
removida com a odd real de Over 2.5 do mesmo bookmaker
(`pesos.probabilidade_implicita_2vias`). `edge = prob_modelo_under −
prob_mercado_under`, `limiar_edge=5%` (mesmo usado no teste anterior
de Under).

## Resultado — negativo em toda a amostra e em todo corte testado

| Grupo | n | Acerto | ROI | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| Base completa (sem corte) | 497 | 51,3% | −12,6% | −15,2% | −13,2% | −8,4% |
| Equilibrado (favoritismo ≤ mediana) | 249 | 54,2% | −12,5% | −20,3% | −6,9% | −9,4% |
| Favorito claro (> mediana) | 248 | 48,4% | −12,7% | −8,6% | −17,7% | −7,2% |
| Over-odd baixa (mercado acha Over provável) | 198 | 44,4% | −15,3% | −10,8% | −19,7% | −15,4% |
| Over-odd alta (mercado acha Over improvável) | 212 | 53,8% | −12,6% | −22,8% | −9,6% | −2,1% |
| **Favorito claro E Over-odd alta** (hipótese exata do Lucas) | 77 | 51,9% | **−15,1%** | −29,1% | −9,2% | −9,2% |
| União (favorito claro OU Over-odd alta) | 355 | 50,7% | −11,7% | −14,7% | −13,5% | −4,9% |

**Nenhum corte, em nenhuma combinação, fica positivo em nenhum ano.**
O quadrante exato da hipótese do Lucas (favorito claro E odd alta de
Over) fica até PIOR que a base sem filtro (−15,1% vs −12,6%) — o
oposto do que se esperava.

## Interpretação

Confirma a nuance: o mesmo padrão que ajuda a EVITAR apostas ruins de
Over (jogos "fechados" erram menos o Over) não gera, por si só, uma
aposta boa do lado Under — porque a odd real de Under nesses jogos já
está precificada considerando exatamente essa tendência. O mercado já
"sabe" que jogo com favorito claro tende a ter menos gols; não sobra
edge pro nosso modelo capturar do lado Under especificamente.

## Recomendação

**Não hà edge em Under 2.5 Série A, mesmo filtrando por
favoritismo/odd de Over.** Confirma e reforça a conclusão anterior
(`docs/retrospectiva_under_odds_reais_2026-08-27.md`) com um ângulo
novo e específico — fechado, não vale retestar sem uma mudança
estrutural (ex.: um sinal genuinamente novo, não derivado do próprio
Over).

## Verificação

- `n` de cada corte reportado (mínimo 77); nenhum corte "promissor" —
  todos negativos em toda checagem ano a ano.
- Reprodução: script ad-hoc rodado nesta sessão, odds reais extraídas
  direto do JSONL bruto (`data/sportmonks_seriea/fixtures.jsonl`,
  mercado 80, bookmaker bet365) — não versionado.
