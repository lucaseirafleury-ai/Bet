"""Exploração das 3 ligas novas do Sportmonks (Championship/Argentina/MLS)
com os 3 critérios JÁ VALIDADOS no Brasileirão — roda tudo sozinho e grava
um relatório compacto em markdown, pra gastar o mínimo de interação.

Uso: `python3 explorar_ligas_novas.py [--pular-pull]`
Saída: `docs/retrospectiva_ligas_novas_<data>.md`

Disciplina de sempre: reporta TODAS as células (positivas, negativas e
inconclusivas), com n/acerto/ROI/z agregado E ano a ano — nunca aceitar
z bom sem consistência ano a ano, nunca aceitar n<15 como conclusivo.
"""
import sys
from collections import defaultdict
from datetime import date, datetime

import pandas as pd

from cartoes_arbitro import (
    carregar_referees_cartoes,
    linha_mais_liquida,
    media_arbitro_walk_forward,
    odd_media_na_linha,
    prever_cartoes_combinado,
    simular_aposta_linha,
)
from checar_decaimento import stats
from previsao_dia import (
    CRITERIOS_GOLS,
    LIMIAR_EDGE_CARTOES,
    MARKET_NUMBER_OF_CARDS,
    MIN_JOGOS_ARBITRO,
    N_HISTORICO_CARTOES,
    PARAMS_CARTOES_TIME,
    PESO_ARBITRO,
    passa_filtros_gols,
)
from retrospectiva import rodar_retrospectiva, simular_apostas
from sportmonks_adapter import BOOKMAKER_BET365, carregar_liga_sportmonks
from sportmonks_client import puxar_fixtures_finalizados, token

LIGAS_NOVAS = {
    "championship": dict(league_id=9, nome="Championship (Inglaterra)"),
    "argentina": dict(league_id=636, nome="Liga Profesional (Argentina)"),
    "mls": dict(league_id=779, nome="MLS (EUA/Canadá)"),
}


def caminho(chave):
    return f"data/sportmonks_{chave}/fixtures.jsonl"


def puxar_tudo(tok):
    import os

    for chave, info in LIGAS_NOVAS.items():
        os.makedirs(f"data/sportmonks_{chave}", exist_ok=True)
        n = puxar_fixtures_finalizados(tok, info["league_id"], caminho(chave))
        print(f"  {info['nome']}: {n} fixtures salvos", flush=True)


def _por_ano(apostas):
    """Agrupa lucros por ano -> {ano: stats}. Ano a ano é obrigatório na
    disciplina do projeto: agregado bom com um ano negativo é candidato
    fraco, não achado."""
    por_ano = defaultdict(list)
    for a in apostas:
        por_ano[a["data"].year].append(a)
    return {ano: stats(lista) for ano, lista in sorted(por_ano.items())}


def avaliar_gols(chave, criterio):
    df = carregar_liga_sportmonks(caminho(chave), bookmaker_id=criterio["bookmaker_id"])
    rel = rodar_retrospectiva(
        df, params=criterio["params"], min_jogos_historico=8, min_jogos_estilo=5,
        n_historico=criterio["n_historico"],
    )
    r = simular_apostas(rel["jogos"], mercado=criterio["mercado"], limiar_edge=criterio["limiar_edge"])
    por_chave = {(j["jogo"], j["data"]): j for j in rel["jogos"]}
    apostas = []
    for a in r["apostas"]:
        completo = por_chave.get((a["jogo"], a["data"]))
        favoritismo = completo.get("prob_mercado_favorito_dc") if completo else None
        if passa_filtros_gols(criterio, a["odd"], favoritismo):
            apostas.append(a)
    return apostas


def avaliar_cartoes(chave):
    caminho_liga = caminho(chave)
    jogos_ref = carregar_referees_cartoes(caminho_liga)
    medias_wf = media_arbitro_walk_forward(jogos_ref, min_jogos_arbitro=MIN_JOGOS_ARBITRO)
    media_por_fixture = {j["fixture_id"]: m for j, m in zip(jogos_ref, medias_wf)}

    df = carregar_liga_sportmonks(caminho_liga, bookmaker_id=BOOKMAKER_BET365)
    row_por_chave = {}
    for _, row in df.iterrows():
        chave_jogo = (f"{row['home_team_name']} x {row['away_team_name']}",
                      datetime.fromtimestamp(row["timestamp"]).date())
        row_por_chave[chave_jogo] = row

    rel = rodar_retrospectiva(
        df, params=PARAMS_CARTOES_TIME, min_jogos_historico=8, min_jogos_estilo=5,
        n_historico=N_HISTORICO_CARTOES,
    )

    apostas = []
    sem_arbitro = sem_mercado = 0
    for jogo in rel["jogos"]:
        m_pro = jogo["mercados"].get("cartoes_pro")
        m_contra = jogo["mercados"].get("cartoes_contra")
        if not m_pro or not m_contra or m_pro["real"] is None or m_contra["real"] is None:
            continue
        row = row_por_chave.get((jogo["jogo"], jogo["data"]))
        if row is None:
            continue
        pred = prever_cartoes_combinado(
            m_pro["pred"] + m_contra["pred"],
            media_por_fixture.get(row["_fixture_id"]),
            peso_arbitro=PESO_ARBITRO,
        )
        if pred is None:
            sem_arbitro += 1
            continue
        jogo_odds = dict(odds={str(MARKET_NUMBER_OF_CARDS): row.get("_odds_cartoes") or []})
        linha = linha_mais_liquida(jogo_odds, MARKET_NUMBER_OF_CARDS)
        if linha is None:
            sem_mercado += 1
            continue
        odd_over = odd_media_na_linha(jogo_odds, MARKET_NUMBER_OF_CARDS, linha, "Over")
        odd_under = odd_media_na_linha(jogo_odds, MARKET_NUMBER_OF_CARDS, linha, "Under")
        if odd_over is None or odd_under is None:
            sem_mercado += 1
            continue
        aposta = simular_aposta_linha(
            pred, linha, odd_over, odd_under, m_pro["real"] + m_contra["real"],
            limiar_edge=LIMIAR_EDGE_CARTOES,
        )
        if aposta is not None:
            aposta["data"] = jogo["data"]
            apostas.append(aposta)
    return apostas, sem_arbitro, sem_mercado


def _linha_tabela(rotulo, s):
    if s["n"] == 0:
        return f"| {rotulo} | 0 | — | — | — |"
    return (f"| {rotulo} | {s['n']} | {s['acerto']*100:.0f}% | {s['roi']*100:+.1f}% | "
            f"{s['z']:+.2f} |")


def main():
    if "--pular-pull" not in sys.argv:
        print("Puxando histórico das 3 ligas (pode levar alguns minutos)...", flush=True)
        puxar_tudo(token())

    linhas = [
        f"# Ligas novas do Sportmonks — teste dos 3 critérios validados ({date.today()})",
        "",
        "Championship (Inglaterra), Liga Profesional (Argentina) e MLS entraram no",
        "plano no lugar das 3 ligas nórdicas. Este relatório roda os MESMOS 3",
        "critérios já validados no Brasileirão (parâmetros idênticos, sem",
        "recalibração nenhuma) em cada liga — primeiro passo de sempre:",
        "reconfirmar com o que já funciona antes de cogitar grid novo.",
        "",
        "Barra do projeto: `z≈2` agregado **e** consistência ano a ano, `n>=15`.",
        "Resultado negativo também é resultado — todas as células estão aqui.",
        "",
    ]

    for chave, info in LIGAS_NOVAS.items():
        linhas += [f"## {info['nome']}", ""]
        for criterio in CRITERIOS_GOLS:
            try:
                apostas = avaliar_gols(chave, criterio)
            except Exception as e:  # liga sem cobertura do mercado/casa, etc.
                linhas += [f"### {criterio['nome']}", "", f"Não avaliável: `{e}`", ""]
                continue
            s = stats(apostas)
            linhas += [
                f"### {criterio['nome']} (casa {criterio['casa_ref']}, edge>={criterio['limiar_edge']*100:.0f}%)",
                "",
                "| Período | n | acerto | ROI | z |",
                "|---|---|---|---|---|",
                _linha_tabela("**Total**", s),
            ]
            for ano, s_ano in _por_ano(apostas).items():
                linhas.append(_linha_tabela(str(ano), s_ano))
            linhas.append("")

        try:
            apostas, sem_arb, sem_merc = avaliar_cartoes(chave)
        except Exception as e:
            linhas += ["### Cartões+Árbitro", "", f"Não avaliável: `{e}`", ""]
        else:
            s = stats(apostas)
            linhas += [
                f"### Cartões+Árbitro (bet365, edge>=10%, peso árbitro {PESO_ARBITRO})",
                "",
                f"Jogos pulados: {sem_arb} sem árbitro com {MIN_JOGOS_ARBITRO}+ jogos, "
                f"{sem_merc} sem mercado de cartões cotado.",
                "",
                "| Período | n | acerto | ROI | z |",
                "|---|---|---|---|---|",
                _linha_tabela("**Total**", s),
            ]
            for ano, s_ano in _por_ano(apostas).items():
                linhas.append(_linha_tabela(str(ano), s_ano))
            linhas.append("")

    saida = f"docs/retrospectiva_ligas_novas_{date.today()}.md"
    with open(saida, "w") as fh:
        fh.write("\n".join(linhas) + "\n")
    print(f"\nRelatório salvo em {saida}")
    print("\n".join(linhas))


if __name__ == "__main__":
    main()
