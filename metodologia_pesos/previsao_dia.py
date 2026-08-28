"""Gera as sugestões de aposta do dia — BTTS (Série A, stake normal),
Over 2.5 recalibrado (Série A, stake reduzido) e Cartões+Árbitro (Série
B, stake reduzido). Ver `docs/protocolo.md` pra evidência/parâmetros de
cada critério.

BTTS e Cartões+Árbitro usam odd do bet365 (bookmaker_id=2); Over 2.5
recalibrado usa odd da Sbo/Sbobet (bookmaker_id=34) — é a única casa,
entre 12 testadas, que passa acima de z≈2 SEM nenhum ano negativo (ver
`docs/retrospectiva_over25_sbo_betfair_2026-08-27.md`). Execução real:
Lucas tenta a Betfair Exchange primeiro (odd normalmente melhor pra
esse mercado, segundo a experiência dele — não validável com o dado do
Sportmonks, que só tem a Betfair Sportsbook cadastrada, cobertura rala
e margem pior que o bet365), caindo pra Sbo como preço já validado
quando a linha não existir/não compensar lá.

Reaproveita o motor de walk-forward já testado
(`retrospectiva.prever_jogo`) pra jogos FUTUROS, usando uma linha
sintética (placar placeholder, nunca lido de verdade) — ver
`sportmonks_adapter.py` pro porquê disso funcionar sem duplicar nem
arriscar a lógica de previsão em lugar nenhum.

Uso: `python3 previsao_dia.py` — imprime as sugestões do dia em JSON.
Assume que `data/sportmonks_{seriea,serieb}/fixtures.jsonl` já foram
atualizados (rodar `sportmonks_atualizar_dado.py` antes, ou deixar a
rotina diária fazer isso automaticamente).
"""
from __future__ import annotations

import json
import os

import pandas as pd

from cartoes_arbitro import (
    decidir_lado_linha,
    linha_mais_liquida,
    media_arbitro_atual,
    odd_media_na_linha,
    prever_cartoes_combinado,
)
from retrospectiva import _MERCADOS_SIMULAVEIS, prever_jogo
from sportmonks_adapter import BOOKMAKER_BET365, BOOKMAKER_SBO, carregar_liga_sportmonks, flat_para_linha
from sportmonks_client import LEAGUE_IDS, puxar_fixtures_futuros, token

CAMINHO_HIST = {
    "seriea": "data/sportmonks_seriea/fixtures.jsonl",
    "serieb": "data/sportmonks_serieb/fixtures.jsonl",
}
MARKET_NUMBER_OF_CARDS = 255
DIAS_A_FRENTE_PADRAO = 3

# Over 2.5 recalibrado tinha sido removido em 27/08/2026 (com odds do
# bet365, 2025 vira negativo — docs/retrospectiva_bookmaker_bet365_2026-08-27.md).
# Readicionado no mesmo dia usando odd da Sbo (bookmaker_id=34) em vez de
# bet365 — único bookmaker, entre 12 testados, acima de z≈2 sem ano
# negativo (docs/retrospectiva_over25_sbo_betfair_2026-08-27.md).
# odd_maxima=2.20 adicionado no mesmo dia: análise green/red das 80
# apostas do backtest achou que odd baixa prevê acerto melhor de forma
# monotônica em todo limiar testado — acima de 2,20 o ROI cai perto de
# zero (docs/retrospectiva_filtro_over25_green_red_2026-08-27.md).
#
# limiar_favoritismo=0.7484 adicionado no mesmo dia (regra "União"):
# uma segunda análise achou que jogos EQUILIBRADOS pela odd 1x2
# (prob_mercado_favorito_dc ≤ mediana) também preveem acerto melhor no
# Over 2.5, sinal parcialmente independente do teto de odd
# (docs/retrospectiva_filtro_favoritismo_over25_2026-08-27.md). Cruzando
# os dois sinais nos mesmos 80 jogos: só o quadrante "odd alta E
# favorito claro" (n=10) é ruim (ROI−32,3%) — os outros 3 quadrantes
# (n=70 no total) são todos positivos. `avaliar_criterio_gols` por isso
# só PULA a sugestão quando os DOIS sinais forem desfavoráveis ao mesmo
# tempo (odd>2,20 E favorito claro) — não quando só um dos dois for. Essa
# regra "União" gera mais volume E mais lucro absoluto que o teto de odd
# sozinho (n=70 ROI+31,6%/+22,11u vs n=46 ROI+39,3%/+18,07u, stake=1),
# com os 3 anos bem representados (n=18/29/23) — Lucas decidiu adotar.
CRITERIOS_GOLS = [
    dict(nome="BTTS", liga="seriea", mercado="btts", stake="normal", limiar_edge=0.05, n_historico=10,
         bookmaker_id=BOOKMAKER_BET365, casa_ref="bet365",
         params=dict(k_mando=0.7, usar_estilo=True, filtro_estilo=0.8, filtro_favoritismo=0.65,
                     multiplicador_dp=1.5, limite_unilateral=2)),
    dict(nome="Over 2.5", liga="seriea", mercado="over25", stake="reduzido", limiar_edge=0.08, n_historico=15,
         bookmaker_id=BOOKMAKER_SBO, casa_ref="Sbo", odd_maxima=2.20, limiar_favoritismo=0.7484,
         params=dict(k_mando=0.35, usar_estilo=False, filtro_aderencia=0.65,
                     multiplicador_dp=1.5, limite_unilateral=4)),
]

# Cartões + Árbitro (Série B) — mesmos parâmetros de checar_decaimento.py
PARAMS_CARTOES_TIME = dict(
    k_mando=0.7, usar_estilo=True, filtro_estilo=0.8, filtro_favoritismo=0.65,
    multiplicador_dp=1.5, limite_unilateral=2,
    limite_unilateral_por_campo={"cartoes_pro": 3.8, "cartoes_contra": 3.8},
)
N_HISTORICO_CARTOES = 10
MIN_JOGOS_ARBITRO = 10
PESO_ARBITRO = 0.3
LIMIAR_EDGE_CARTOES = 0.0


def _carregar_referees_cartoes(path):
    """Lê o JSONL bruto (não o DataFrame adaptado) só pra reconstruir a
    média histórica de cartões por árbitro — precisa do `total_cartoes`
    por jogo, que o adaptador não expõe num campo único."""
    jogos = []
    with open(path) as f:
        for l in f:
            d = json.loads(l)
            cf, ca = d.get("yellowcards_home") or 0, d.get("yellowcards_away") or 0
            rf, ra = d.get("redcards_home") or 0, d.get("redcards_away") or 0
            jogos.append(dict(referee_id=d.get("referee_id"), total_cartoes=cf + ca + rf + ra))
    return jogos


def avaliar_criterio_gols(criterio, linha, df_historico):
    df_com_futuro = pd.concat([df_historico, pd.DataFrame([linha])], ignore_index=True)
    resultado = prever_jogo(
        df_com_futuro.iloc[-1], df_com_futuro, params=criterio["params"],
        min_jogos_historico=8, min_jogos_estilo=5, n_historico=criterio["n_historico"],
    )
    if resultado is None:
        return None
    campos = _MERCADOS_SIMULAVEIS[criterio["mercado"]]
    prob_modelo, prob_mercado, odd = (resultado.get(campos[k]) for k in ("prob_modelo", "prob_mercado", "odd"))
    if prob_modelo is None or prob_mercado is None or odd is None:
        return None
    edge = prob_modelo - prob_mercado
    if edge < criterio["limiar_edge"]:
        return None
    odd_maxima = criterio.get("odd_maxima")
    limiar_favoritismo = criterio.get("limiar_favoritismo")
    if odd_maxima is not None and odd > odd_maxima:
        # "União": só pula quando os DOIS sinais forem desfavoráveis (odd
        # alta E jogo com favorito claro pela odd 1x2) — se o jogo for
        # equilibrado, a sugestão passa mesmo com odd acima do teto. Sem
        # limiar_favoritismo configurado, ou sem odd 1x2 disponível pro
        # jogo, cai pro comportamento antigo (só o teto de odd decide).
        favoritismo = resultado.get("prob_mercado_favorito_dc")
        equilibrado = (
            limiar_favoritismo is not None and favoritismo is not None and favoritismo <= limiar_favoritismo
        )
        if not equilibrado:
            return None
    return dict(
        criterio=criterio["nome"], stake=criterio["stake"], lado=criterio["mercado"],
        odd=odd, prob_modelo=prob_modelo, prob_mercado=prob_mercado, edge=edge,
        fixture_id=linha.get("_fixture_id"), linha_aposta=None, casa_ref=criterio["casa_ref"],
    )


def avaliar_cartoes_arbitro(linha, df_historico_serieb, medias_arbitro):
    df_com_futuro = pd.concat([df_historico_serieb, pd.DataFrame([linha])], ignore_index=True)
    resultado = prever_jogo(
        df_com_futuro.iloc[-1], df_com_futuro, params=PARAMS_CARTOES_TIME,
        min_jogos_historico=8, min_jogos_estilo=5, n_historico=N_HISTORICO_CARTOES,
    )
    if resultado is None:
        return None
    m_pro = resultado["mercados"].get("cartoes_pro")
    m_contra = resultado["mercados"].get("cartoes_contra")
    if not m_pro or not m_contra:
        return None
    pred_time = m_pro["pred"] + m_contra["pred"]

    referee_id = linha.get("_referee_id")
    media_arb = medias_arbitro.get(referee_id) if referee_id is not None else None
    pred_combinado = prever_cartoes_combinado(pred_time, media_arb, peso_arbitro=PESO_ARBITRO)
    if pred_combinado is None:
        return None  # árbitro ainda não definido, ou sem histórico suficiente

    jogo_odds = dict(odds={str(MARKET_NUMBER_OF_CARDS): linha.get("_odds_cartoes") or []})
    linha_mercado = linha_mais_liquida(jogo_odds, MARKET_NUMBER_OF_CARDS)
    if linha_mercado is None:
        return None
    odd_over = odd_media_na_linha(jogo_odds, MARKET_NUMBER_OF_CARDS, linha_mercado, "Over")
    odd_under = odd_media_na_linha(jogo_odds, MARKET_NUMBER_OF_CARDS, linha_mercado, "Under")
    if odd_over is None or odd_under is None:
        return None
    decisao = decidir_lado_linha(pred_combinado, linha_mercado, odd_over, odd_under, limiar_edge=LIMIAR_EDGE_CARTOES)
    if decisao is None:
        return None
    return dict(
        criterio="Cartões+Árbitro", stake="reduzido", lado=f"{decisao['lado']} {linha_mercado} cartões",
        odd=decisao["odd"], prob_modelo=decisao["prob_modelo"], prob_mercado=decisao["prob_mercado"],
        edge=decisao["edge"], fixture_id=linha.get("_fixture_id"), linha_aposta=linha_mercado,
        casa_ref="bet365",
    )


def gerar_sugestoes_do_dia(dias_a_frente=DIAS_A_FRENTE_PADRAO):
    tok = token()
    # Cada critério de gols pode ter sua própria casa de referência (BTTS:
    # bet365, Over 2.5: Sbo) — carrega um DataFrame de histórico por
    # bookmaker distinto usado em CRITERIOS_GOLS, em vez de assumir bet365
    # pra todos.
    bookmakers_seriea = {c["bookmaker_id"] for c in CRITERIOS_GOLS}
    dfs_seriea = {bid: carregar_liga_sportmonks(CAMINHO_HIST["seriea"], bookmaker_id=bid) for bid in bookmakers_seriea}
    df_serieb = carregar_liga_sportmonks(CAMINHO_HIST["serieb"])

    sugestoes = []

    for f in puxar_fixtures_futuros(tok, LEAGUE_IDS["seriea"], dias_a_frente):
        for criterio in CRITERIOS_GOLS:
            linha = flat_para_linha(f, bookmaker_id=criterio["bookmaker_id"])
            r = avaliar_criterio_gols(criterio, linha, dfs_seriea[criterio["bookmaker_id"]])
            if r:
                sugestoes.append({**r, "liga": "Série A", "liga_chave": "seriea", "jogo": f"{f['home_team']} x {f['away_team']}", "data": f["date"]})

    medias_arbitro = media_arbitro_atual(_carregar_referees_cartoes(CAMINHO_HIST["serieb"]), min_jogos_arbitro=MIN_JOGOS_ARBITRO)
    for f in puxar_fixtures_futuros(tok, LEAGUE_IDS["serieb"], dias_a_frente):
        linha = flat_para_linha(f)
        r = avaliar_cartoes_arbitro(linha, df_serieb, medias_arbitro)
        if r:
            sugestoes.append({**r, "liga": "Série B", "liga_chave": "serieb", "jogo": f"{f['home_team']} x {f['away_team']}", "data": f["date"]})

    return sugestoes


if __name__ == "__main__":
    sugestoes = gerar_sugestoes_do_dia()
    print(json.dumps(sugestoes, indent=2, ensure_ascii=False, default=str))
