"""Gera as sugestões de aposta do dia — BTTS (Série A, stake normal),
Over 2.5 recalibrado (Série A, stake reduzido) e Cartões+Árbitro (Série
B, stake reduzido). Ver `docs/protocolo.md` pra evidência/parâmetros de
cada critério.

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
from sportmonks_adapter import carregar_liga_sportmonks, flat_para_linha
from sportmonks_client import LEAGUE_IDS, puxar_fixtures_futuros, token

CAMINHO_HIST = {
    "seriea": "data/sportmonks_seriea/fixtures.jsonl",
    "serieb": "data/sportmonks_serieb/fixtures.jsonl",
}
MARKET_NUMBER_OF_CARDS = 255
DIAS_A_FRENTE_PADRAO = 3

# Over 2.5 recalibrado foi REMOVIDO daqui em 27/08/2026 — só se sustentava
# com a média de todas as casas do Sportmonks; com odds só do bet365 (a
# casa real que o Lucas usa), 2025 vira negativo (z=-0,72) e o agregado
# cai de z=+2,28 pra z=+1,31. Ver docs/retrospectiva_bookmaker_bet365_2026-08-27.md.
CRITERIOS_GOLS = [
    dict(nome="BTTS", liga="seriea", mercado="btts", stake="normal", limiar_edge=0.05, n_historico=10,
         params=dict(k_mando=0.7, usar_estilo=True, filtro_estilo=0.8, filtro_favoritismo=0.65,
                     multiplicador_dp=1.5, limite_unilateral=2)),
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
    return dict(
        criterio=criterio["nome"], stake=criterio["stake"], lado=criterio["mercado"],
        odd=odd, prob_modelo=prob_modelo, prob_mercado=prob_mercado, edge=edge,
        fixture_id=linha.get("_fixture_id"), linha_aposta=None,
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
    )


def gerar_sugestoes_do_dia(dias_a_frente=DIAS_A_FRENTE_PADRAO):
    tok = token()
    df_seriea = carregar_liga_sportmonks(CAMINHO_HIST["seriea"])
    df_serieb = carregar_liga_sportmonks(CAMINHO_HIST["serieb"])

    sugestoes = []

    for f in puxar_fixtures_futuros(tok, LEAGUE_IDS["seriea"], dias_a_frente):
        linha = flat_para_linha(f)
        for criterio in CRITERIOS_GOLS:
            r = avaliar_criterio_gols(criterio, linha, df_seriea)
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
