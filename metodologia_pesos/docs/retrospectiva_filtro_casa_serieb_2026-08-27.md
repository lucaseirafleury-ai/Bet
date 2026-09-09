# Filtro no 1x2 "casa" Série B: confirmado morto, não resgatável

## Contexto

Segunda rodada da varredura pedida pelo Lucas: revisitar análises
antigas com amostra grande que não ficaram positivas (ou ficaram só
fracamente positivas), pra ver se a mesma técnica de separar green/red
e procurar um filtro (que funcionou bem pro Over 2.5-Sbo) resgata
algum sinal.

Candidato: **1x2 "casa" (mandante vence), Série B** — o maior z já
achado na Série B em toda a sessão (z=+2,71, n=354, FootyStats,
`docs/retrospectiva_1x2_dc_2026-08-25.md`), mas já identificado como
"sinal morto": decaimento progressivo e consistente ano a ano (2023
ROI+35,8% → 2024 +38,6% → 2025 +2,3% → 2026 −9,9%) — o padrão clássico
de mercado que foi arbitrado, não ruído de amostra pequena.

## Revalidação com dado atual (Sportmonks, bet365)

Rodei de novo com os mesmos parâmetros (`k_mando=0.5, usar_estilo=True,
filtro_aderencia=0, multiplicador_dp=1.5, limite_unilateral=2,
limiar_edge=0%`) sobre o dado 100% Sportmonks (só 3 temporadas
disponíveis, não os 4 anos do FootyStats):

| Ano | n | Acerto | ROI |
|---|---|---|---|
| 2024 | 82 | 53,7% | +31,0% |
| 2025 | 99 | 47,5% | +4,1% |
| 2026 | 61 | 37,7% | −18,3% |

**Mesmo padrão de decaimento, confirmado numa fonte de dado
diferente** — não é artefato do FootyStats. 2026 (o ano que importa pra
apostar hoje) segue negativo.

## Filtro-mineração: nenhuma característica resgata o sinal

Testei 7 features (odd, edge, probabilidade do modelo, probabilidade
de mercado, `gf_pred`/`ga_pred`/diferença) com corte pela mediana, três
formas:

1. **Amostra completa (2024-2026, n=242)**: alguns cortes mostram
   diferença de ROI (ex.: `prob_mercado` ≤ mediana ROI+15,3% vs >
   mediana ROI−0,3%) — mas isso é dominado pelos anos bons (2024/2025),
   não prova nada sobre se ainda funciona hoje.
2. **Só 2025+2026 (n=160, o período já "morto")**: nenhum dos 7 cortes
   produz um subgrupo com os DOIS anos positivos. Em todo corte
   testado, **2026 fica negativo dos dois lados** (de −4,6% a −38,2%)
   — às vezes 2025 sozinho parece ok (+16 a +19% em alguns cortes), mas
   sempre puxado pra baixo por 2026.
3. Nenhuma combinação de filtro chega perto de reverter a tendência no
   ano mais recente.

## Interpretação

Isso confirma a hipótese que eu tinha levantado antes de rodar: esse é
um caso de **eficiência de mercado genuína**, não de "sinal escondido
numa amostra ruidosa". A queda de ROI é uniforme na população — não
existe um subconjunto de jogos (por odd, edge, confiança do modelo ou
gols esperados) que ainda carregue vantagem em 2025/2026. Filtrar um
sinal estruturalmente morto não ressuscita ele; só ajuda a refinar um
sinal que já está vivo (como fizemos com o Over 2.5-Sbo).

## Recomendação

**Não usar 1x2 "casa" Série B, com ou sem filtro.** Confirma a decisão
já registrada em `docs/retrospectiva_1x2_dc_2026-08-25.md`, agora com
dado mais recente e um filtro-mineração dedicado que não achou nada.
Fechado — não vale reabrir de novo sem uma mudança estrutural no motor
(não um novo corte de característica).

## Verificação

- `n` de cada corte reportado (mínimo 61, a maioria ≥69); nenhum corte
  "promissor" reportado como tal — nenhum passou na checagem ano a ano.
- Reprodução: script ad-hoc rodado diretamente nesta sessão
  (`retrospectiva.rodar_retrospectiva`/`simular_apostas`, mercado
  `"casa"`, dado `data/sportmonks_serieb/fixtures.jsonl` via
  `sportmonks_adapter.carregar_liga_sportmonks` bet365) — não
  versionado (ad-hoc), mesmo padrão de sempre.
