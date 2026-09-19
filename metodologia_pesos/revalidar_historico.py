"""Revalidação dos 3 critérios em produção sobre o histórico profundo.

Os 3 critérios foram calibrados olhando 2024-2026. Com o add-on de
Historical Data temos odds desde ~2018 — ou seja, **2018-2023 é
fora-da-amostra genuíno**: seis anos que nunca participaram de nenhuma
escolha de parâmetro, bookmaker, limiar ou filtro. É a validação mais
forte que este projeto pode produzir; nenhum grid, holdout ou
reamostragem chega perto de dado que o processo nunca viu.

Rodando os 3 critérios em paralelo (CPU puro, ver CLAUDE.md).

Uso: `python3 revalidar_historico.py`
Saída: `docs/retrospectiva_revalidacao_historica_<data>.md`
"""
import multiprocessing as mp
import os
from collections import defaultdict
from datetime import date, datetime

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
    CAMINHO_HIST,
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

ANO_CALIBRACAO = 2024  # 2024+ é o período que o processo de escolha viu


def _apostas_gols(criterio):
    df = carregar_liga_sportmonks(CAMINHO_HIST[criterio["liga"]], bookmaker_id=criterio["bookmaker_id"])
    rel = rodar_retrospectiva(df, params=criterio["params"], min_jogos_historico=8,
                              min_jogos_estilo=5, n_historico=criterio["n_historico"])
    r = simular_apostas(rel["jogos"], mercado=criterio["mercado"], limiar_edge=criterio["limiar_edge"])
    por_chave = {(j["jogo"], j["data"]): j for j in rel["jogos"]}
    apostas = []
    for a in r["apostas"]:
        completo = por_chave.get((a["jogo"], a["data"]))
        fav = completo.get("prob_mercado_favorito_dc") if completo else None
        if passa_filtros_gols(criterio, a["odd"], fav):
            apostas.append(a)
    return apostas


def _apostas_cartoes():
    caminho = CAMINHO_HIST["serieb"]
    jogos_ref = carregar_referees_cartoes(caminho)
    medias = media_arbitro_walk_forward(jogos_ref, min_jogos_arbitro=MIN_JOGOS_ARBITRO)
    media_por_fixture = {j["fixture_id"]: m for j, m in zip(jogos_ref, medias)}
    df = carregar_liga_sportmonks(caminho, bookmaker_id=BOOKMAKER_BET365)
    row_por_chave = {
        (f"{r['home_team_name']} x {r['away_team_name']}",
         datetime.fromtimestamp(r["timestamp"]).date()): r
        for _, r in df.iterrows()
    }
    rel = rodar_retrospectiva(df, params=PARAMS_CARTOES_TIME, min_jogos_historico=8,
                              min_jogos_estilo=5, n_historico=N_HISTORICO_CARTOES)
    apostas = []
    for jogo in rel["jogos"]:
        m_pro = jogo["mercados"].get("cartoes_pro")
        m_contra = jogo["mercados"].get("cartoes_contra")
        if not m_pro or not m_contra or m_pro["real"] is None or m_contra["real"] is None:
            continue
        row = row_por_chave.get((jogo["jogo"], jogo["data"]))
        if row is None:
            continue
        pred = prever_cartoes_combinado(m_pro["pred"] + m_contra["pred"],
                                        media_por_fixture.get(row["_fixture_id"]),
                                        peso_arbitro=PESO_ARBITRO)
        if pred is None:
            continue
        jogo_odds = dict(odds={str(MARKET_NUMBER_OF_CARDS): row.get("_odds_cartoes") or []})
        linha = linha_mais_liquida(jogo_odds, MARKET_NUMBER_OF_CARDS)
        if linha is None:
            continue
        over = odd_media_na_linha(jogo_odds, MARKET_NUMBER_OF_CARDS, linha, "Over")
        under = odd_media_na_linha(jogo_odds, MARKET_NUMBER_OF_CARDS, linha, "Under")
        if over is None or under is None:
            continue
        ap = simular_aposta_linha(pred, linha, over, under,
                                  m_pro["real"] + m_contra["real"], limiar_edge=LIMIAR_EDGE_CARTOES)
        if ap is not None:
            ap["data"] = jogo["data"]
            apostas.append(ap)
    return apostas


def _tarefa(nome):
    if nome == "Cartões+Árbitro":
        return nome, _apostas_cartoes()
    criterio = next(c for c in CRITERIOS_GOLS if c["nome"] == nome)
    return nome, _apostas_gols(criterio)


def _fmt(s):
    if s["n"] == 0:
        return "| 0 | — | — | — |"
    return f"| {s['n']} | {s['acerto']*100:.0f}% | {s['roi']*100:+.1f}% | {s['z']:+.2f} |"


def main():
    nomes = [c["nome"] for c in CRITERIOS_GOLS] + ["Cartões+Árbitro"]
    print(f"Rodando {len(nomes)} critérios em paralelo...", flush=True)
    with mp.Pool(processes=min(len(nomes), os.cpu_count() or 1)) as pool:
        resultados = dict(pool.map(_tarefa, nomes))

    linhas = [
        f"# Revalidação sobre o histórico profundo ({date.today()})", "",
        "Os 3 critérios em produção foram calibrados olhando **2024-2026**. Com o",
        "add-on de Historical Data temos odds desde ~2018 — então **2018-2023 é",
        "fora-da-amostra genuíno**: seis anos que nunca participaram de nenhuma",
        "escolha de parâmetro, casa de aposta, limiar ou filtro.",
        "",
        "Nenhum holdout ou reamostragem é tão forte quanto dado que o processo",
        "nunca viu. Se o edge sobrevive aqui, é o argumento mais sólido que este",
        "projeto pode ter; se some, o critério era ajuste ao período de calibração.",
        "",
        "**Ressalva honesta**: mercado antigo era menos eficiente. Um edge maior em",
        "2018-2020 pode refletir mercado mais frouxo, não superioridade do modelo —",
        "por isso o ano a ano está completo abaixo, não só o agregado.",
        "",
    ]

    for nome in nomes:
        apostas = resultados[nome]
        fora = [a for a in apostas if a["data"].year < ANO_CALIBRACAO]
        dentro = [a for a in apostas if a["data"].year >= ANO_CALIBRACAO]
        linhas += [f"## {nome}", "", "| Período | n | acerto | ROI | z |", "|---|---|---|---|---|",
                   f"| **Fora da amostra (2018-2023)** {_fmt(stats(fora))}",
                   f"| Calibração (2024-2026) {_fmt(stats(dentro))}",
                   f"| Tudo {_fmt(stats(apostas))}", ""]
        por_ano = defaultdict(list)
        for a in apostas:
            por_ano[a["data"].year].append(a)
        linhas += ["Ano a ano:", "", "| Ano | n | acerto | ROI | z |", "|---|---|---|---|---|"]
        for ano in sorted(por_ano):
            marca = "" if ano >= ANO_CALIBRACAO else " ·"
            linhas.append(f"| {ano}{marca} {_fmt(stats(por_ano[ano]))}")
        linhas += ["", "`·` = fora da amostra", ""]

    saida = f"docs/retrospectiva_revalidacao_historica_{date.today()}.md"
    with open(saida, "w") as fh:
        fh.write("\n".join(linhas) + "\n")
    print(f"Relatório: {saida}")
    print("\n".join(linhas))


if __name__ == "__main__":
    main()
