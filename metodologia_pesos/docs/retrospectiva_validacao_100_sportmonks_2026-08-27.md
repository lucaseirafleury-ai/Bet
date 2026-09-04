# Validação 100% Sportmonks (stats + odds, sem FootyStats) — BTTS confirma, Over 2.5 enfraquece

## Contexto

Lucas decidiu cancelar o FootyStats e ir 100% Sportmonks, automatizando
tudo numa rotina diária com painel (sem planilha manual). Diferente do
teste de troca de odds feito antes (`docs/retrospectiva_...` do
Estágio A, que só trocava a ODD mantendo os stats do FootyStats), este
teste roda o motor inteiro (histórico, estilo, predição, aposta) só com
dado do Sportmonks — stats E odds.

## Dois problemas técnicos resolvidos

1. **xG não existe no Sportmonks pra Série A/B** (confirmado via API —
   o type_id 5304 "Expected Goals (xG)" existe no catálogo geral do
   Sportmonks, mas nunca aparece nas estatísticas de nenhum jogo das
   duas ligas, em nenhum dos planos). Isso afeta só os critérios com
   `usar_estilo=True` (BTTS e Cartões+Árbitro) — Over 2.5 usa
   `usar_estilo=False`, não é afetado. Solução: usar os GOLS REAIS do
   jogo como proxy de xG (mantém variação real entre times, mais
   informativo que zerar essa parte do modelo).
2. **`planilha_lib.get_historico` exige todo campo como número real**,
   mesmo antes de checar o sentinela de dado ausente (`cf == -1`) — não
   dá pra passar `None`/`NaN`. Cerca de 5-16% dos jogos do Sportmonks
   têm algum campo de detalhe faltando (corners/chutes/posse/faltas).
   Solução: tratar esses jogos com o mesmo sentinela `-1` que o
   FootyStats já usa pra "stats ausentes além do placar" — aciona o
   placeholder conservador por margem de gol já validado no projeto.

Adaptador: `sportmonks_adapter.py` (ad-hoc, scratchpad) — converte
fixture do Sportmonks pro formato de linha que `retrospectiva.py`/
`planilha_lib.py` já esperam, sem tocar em nenhum código de produção.

## Resultado

| Liga | Critério | z (100% Sportmonks) | z (original, FootyStats) |
|---|---|---|---|
| Série A | **BTTS** | **+2,33** (n=175) | +2,65 |
| Série A | Over 2.5 | +0,49 (n=169) | +2,23 |
| Série B | Over 2.5 | −3,11 | (nunca funcionou) |
| Série B | BTTS | −0,72 | (nunca funcionou) |

Ano a ano, Série A/BTTS: 2024 z=+2,44, 2025 z=−0,10 (ruído, não
prejuízo), 2026 z=+2,04 — consistente, sem ano realmente negativo.

## Conclusão

**BTTS (Série A) se sustenta muito bem 100% em cima do Sportmonks** —
pode entrar no painel automatizado com confiança equivalente à que já
tínhamos. **Over 2.5 (Série A) não se sustenta** com os parâmetros
calibrados no FootyStats — confirma que parte do edge original vinha
especificamente da odd/dado dessa fonte. Recalibração dedicada rodada
em seguida (ver `docs/retrospectiva_over25_sportmonks_2026-08-27.md`):
não achou candidato defensável — não incluir Over 2.5 no painel por
enquanto. Série B (ambos mercados) confirma o que já sabíamos —
continua sem edge defensável.

Reprodução: `/tmp/.../scratchpad/sportmonks_adapter.py`,
`sportmonks_pull_full.py`, `teste_validacao_100_sportmonks.py` (ad-hoc,
não versionados nesta rodada).
