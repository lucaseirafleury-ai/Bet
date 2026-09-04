"""Checagem mensal de decaimento dos 3 critérios em produção — BTTS,
Over 2.5 (Sbo + filtro União) e Cartões+Árbitro (Série B) — rodando
100% em cima do Sportmonks, com os MESMOS parâmetros e a MESMA fonte de
odd que `previsao_dia.py` usa de verdade no painel (reaproveita
`previsao_dia.CRITERIOS_GOLS`/`PARAMS_CARTOES_TIME`/
`passa_filtros_gols` diretamente, nunca duplica os números — assim os
dois processos não podem divergir silenciosamente).

Substitui a versão antiga (FootyStats, upload manual de CSV,
`data/sportmonks_serieb_cartoes/` separado) — obsoleta desde a migração
100% Sportmonks de 27/08/2026. Não depende de nenhum passo manual do
Lucas: só precisa que `data/sportmonks_{seriea,serieb}/fixtures.jsonl`
estejam atualizados (rodar `sportmonks_atualizar_dado.py` antes, ou
deixar a rotina mensal fazer isso).

Mede ROI/z/acerto tanto no acumulado (desde que o Sportmonks tem dado,
2024+) quanto numa janela recente de 90 dias, registrando em
`docs/decaimento_mensal.md` pra acompanhar a TENDÊNCIA ao longo de
várias checagens — nunca reagir a uma checagem isolada (amostra de 90
dias é pequena pra critérios seletivos, ruído é esperado; o que importa
é se a tendência se mantém, melhora ou piora ao longo de meses).

Uso: `python3 checar_decaimento.py`.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import date, datetime, timedelta

from cartoes_arbitro import (
    linha_mais_liquida,
    media_arbitro_walk_forward,
    odd_media_na_linha,
    prever_cartoes_combinado,
    simular_aposta_linha,
)
from previsao_dia import (
    CAMINHO_HIST,
    CRITERIOS_GOLS,
    LIMIAR_EDGE_CARTOES,
    MIN_JOGOS_ARBITRO,
    N_HISTORICO_CARTOES,
    PARAMS_CARTOES_TIME,
    PESO_ARBITRO,
    passa_filtros_gols,
)
from retrospectiva import rodar_retrospectiva, simular_apostas
from sportmonks_adapter import BOOKMAKER_BET365, carregar_liga_sportmonks

CAMINHO_LOG = "docs/decaimento_mensal.md"
MARKET_NUMBER_OF_CARDS = 255
JANELA_RECENTE_DIAS = 90


def zscore(lucros):
    n = len(lucros)
    if n == 0:
        return None
    media = sum(lucros) / n
    var = sum((x - media) ** 2 for x in lucros) / (n - 1) if n > 1 else 0
    se = math.sqrt(var / n) if n > 1 else float("nan")
    return media / se if se else float("nan")


def stats(apostas):
    n = len(apostas)
    if n == 0:
        return dict(n=0, roi=None, z=None, acerto=None)
    lucro = sum(a["lucro"] for a in apostas)
    return dict(
        n=n, roi=(lucro / n), z=zscore([a["lucro"] for a in apostas]),
        acerto=sum(1 for a in apostas if a["venceu"]) / n,
    )


def fmt(s):
    if s["n"] == 0:
        return "sem apostas"
    return f"n={s['n']} ROI={s['roi']*100:+.1f}% z={s['z']:+.2f} acerto={s['acerto']*100:.0f}%"


def _checagem_criterio_gols(criterio, corte_recente):
    """BTTS ou Over 2.5 — mesmos parâmetros/bookmaker/filtros de
    `previsao_dia.CRITERIOS_GOLS`, aplicados de ponta a ponta ao
    histórico Sportmonks disponível hoje."""
    caminho = CAMINHO_HIST[criterio["liga"]]
    df = carregar_liga_sportmonks(caminho, bookmaker_id=criterio["bookmaker_id"])
    rel = rodar_retrospectiva(
        df, params=criterio["params"], min_jogos_historico=8, min_jogos_estilo=5,
        n_historico=criterio["n_historico"],
    )
    r = simular_apostas(rel["jogos"], mercado=criterio["mercado"], limiar_edge=criterio["limiar_edge"])
    by_key = {(j["jogo"], j["data"]): j for j in rel["jogos"]}

    apostas = []
    for a in r["apostas"]:
        full = by_key.get((a["jogo"], a["data"]))
        favoritismo = full.get("prob_mercado_favorito_dc") if full else None
        if passa_filtros_gols(criterio, a["odd"], favoritismo):
            apostas.append(a)

    s_total = stats(apostas)
    s_recente = stats([a for a in apostas if a["data"] >= corte_recente])
    return dict(nome=criterio["nome"], total=s_total, recente=s_recente)


def _carregar_referees_serieb_ordenado(caminho):
    """Lê o JSONL principal da Série B (não mais um pull separado) e
    devolve os jogos ordenados cronologicamente com `referee_id`/
    `total_cartoes`/`fixture_id` — insumo do walk-forward de árbitro."""
    jogos = []
    with open(caminho) as f:
        for l in f:
            d = json.loads(l)
            cf, ca = d.get("yellowcards_home") or 0, d.get("yellowcards_away") or 0
            rf, ra = d.get("redcards_home") or 0, d.get("redcards_away") or 0
            data = datetime.strptime(d["date"][:10], "%Y-%m-%d").date()
            jogos.append(dict(
                fixture_id=d["fixture_id"], referee_id=d.get("referee_id"),
                total_cartoes=cf + ca + rf + ra, data=data,
            ))
    return sorted(jogos, key=lambda j: j["data"])


def _checagem_cartoes_arbitro(corte_recente):
    """3º critério (stake reduzido) — Cartões + Árbitro, Série B. Odds
    e estatísticas vêm de `data/sportmonks_serieb/fixtures.jsonl` (o
    mesmo arquivo que o painel usa, bookmaker bet365) — não depende
    mais de nenhum pull separado."""
    caminho = CAMINHO_HIST["serieb"]
    jogos_ref = _carregar_referees_serieb_ordenado(caminho)
    medias_wf = media_arbitro_walk_forward(jogos_ref, min_jogos_arbitro=MIN_JOGOS_ARBITRO)
    media_arbitro_por_fixture = {j["fixture_id"]: m for j, m in zip(jogos_ref, medias_wf)}

    df = carregar_liga_sportmonks(caminho, bookmaker_id=BOOKMAKER_BET365)
    fixture_por_key = {}
    for _, row in df.iterrows():
        jogo_str = f"{row['home_team_name']} x {row['away_team_name']}"
        data = datetime.fromtimestamp(row["timestamp"]).date()
        fixture_por_key[(jogo_str, data)] = row

    rel = rodar_retrospectiva(
        df, params=PARAMS_CARTOES_TIME, min_jogos_historico=8, min_jogos_estilo=5,
        n_historico=N_HISTORICO_CARTOES,
    )

    apostas = []
    for jogo in rel["jogos"]:
        m_pro = jogo["mercados"].get("cartoes_pro")
        m_contra = jogo["mercados"].get("cartoes_contra")
        if not m_pro or not m_contra:
            continue
        pred_time = m_pro["pred"] + m_contra["pred"]
        real_total = m_pro["real"] + m_contra["real"]

        row = fixture_por_key.get((jogo["jogo"], jogo["data"]))
        if row is None:
            continue
        media_arb = media_arbitro_por_fixture.get(row["_fixture_id"])
        pred_combinado = prever_cartoes_combinado(pred_time, media_arb, peso_arbitro=PESO_ARBITRO)
        if pred_combinado is None:
            continue

        jogo_odds = dict(odds={str(MARKET_NUMBER_OF_CARDS): row.get("_odds_cartoes") or []})
        linha = linha_mais_liquida(jogo_odds, MARKET_NUMBER_OF_CARDS)
        if linha is None:
            continue
        odd_over = odd_media_na_linha(jogo_odds, MARKET_NUMBER_OF_CARDS, linha, "Over")
        odd_under = odd_media_na_linha(jogo_odds, MARKET_NUMBER_OF_CARDS, linha, "Under")
        if odd_over is None or odd_under is None:
            continue

        aposta = simular_aposta_linha(pred_combinado, linha, odd_over, odd_under, real_total, limiar_edge=LIMIAR_EDGE_CARTOES)
        if aposta is not None:
            aposta["data"] = jogo["data"]
            apostas.append(aposta)

    s_total = stats(apostas)
    s_recente = stats([a for a in apostas if a["data"] >= corte_recente])
    return dict(nome="Cartões+Árbitro (Série B, stake reduzido)", total=s_total, recente=s_recente)


def rodar_checagem():
    hoje = date.today()
    corte_recente = hoje - timedelta(days=JANELA_RECENTE_DIAS)

    resumo = [_checagem_criterio_gols(c, corte_recente) for c in CRITERIOS_GOLS]
    resumo.append(_checagem_cartoes_arbitro(corte_recente))

    linhas_log = [
        f"| {hoje.isoformat()} | {item['nome']} | {fmt(item['total'])} | {fmt(item['recente'])} |"
        for item in resumo
    ]
    return resumo, linhas_log, hoje


def atualizar_log(linhas_log, hoje):
    try:
        with open(CAMINHO_LOG, "r") as f:
            conteudo = f.read()
    except FileNotFoundError:
        conteudo = (
            "# Decaimento mensal — critérios em produção (100% Sportmonks)\n\n"
            "Checagem recorrente (rotina mensal) do ROI/z/acerto dos 3 "
            "critérios em produção (`docs/protocolo.md`), acumulado desde que "
            "o Sportmonks tem dado (2024+) vs. janela móvel dos últimos "
            f"{JANELA_RECENTE_DIAS} dias — a janela recente é o que importa "
            "pra pegar decaimento cedo, o acumulado se move devagar demais "
            "pra isso. **Nunca reagir a uma checagem isolada** — o que "
            "importa é a tendência ao longo de várias checagens seguidas "
            '(foi assim que o "casa" Série B foi identificado como sinal '
            "morto: 2023/2024 ótimos, 2025 murchando, 2026 negativo — só "
            "visível olhando vários pontos).\n\n"
            f"| Data da checagem | Critério | Acumulado (2024+) | Últimos {JANELA_RECENTE_DIAS} dias |\n"
            "|---|---|---|---|\n"
        )
    conteudo += "\n".join(linhas_log) + "\n"
    with open(CAMINHO_LOG, "w") as f:
        f.write(conteudo)


def main():
    resumo, linhas_log, hoje = rodar_checagem()
    print(f"Checagem de {hoje.isoformat()}:")
    for item in resumo:
        print(f"  {item['nome']}: acumulado -> {fmt(item['total'])} | "
              f"últimos {JANELA_RECENTE_DIAS}d -> {fmt(item['recente'])}")
    atualizar_log(linhas_log, hoje)
    print(f"Log atualizado em {CAMINHO_LOG}")


if __name__ == "__main__":
    main()
