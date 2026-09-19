"""Calibração móvel (rolling-origin) — testa a hipótese "o jogo mudou, então
só os anos recentes importam" sem cair na circularidade de validar em cima
do período de calibração.

Desenho:
    dobra 1: escolhe parâmetros em 2023        -> testa em 2024
    dobra 2: escolhe parâmetros em 2023-2024   -> testa em 2025
    dobra 3: escolhe parâmetros em 2023-2025   -> testa em 2026

Cada ano-alvo é intocado pela escolha, e tudo acontece no regime recente.
Se o método funciona hoje, os anos-alvo somam positivo; se o que temos é
ajuste ao período, eles somam zero — e nesse caso o resultado de
2024-2026 do relatório anterior era o próprio ajuste se olhando no espelho.

O agregado das dobras é a estimativa honesta do que esperar operando:
recalibrar com o que se sabe e apostar no que vem depois — que é
exatamente o que fazemos na prática.

Eficiência: cada combinação do grid roda UMA vez sobre o histórico todo
(parte cara, paralelizada); as dobras são recortes por ano do resultado
já calculado.

Uso: `python3 calibracao_movel.py`
Saída: `docs/retrospectiva_calibracao_movel_<data>.md`
"""
import itertools
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
    LIMIAR_EDGE_CARTOES,
    MARKET_NUMBER_OF_CARDS,
    MIN_JOGOS_ARBITRO,
    N_HISTORICO_CARTOES,
    passa_filtros_gols,
)
from retrospectiva import rodar_retrospectiva, simular_apostas
from sportmonks_adapter import BOOKMAKER_BET365, BOOKMAKER_SBO, carregar_liga_sportmonks

N_PROCESSOS = os.cpu_count() or 1
ANO_INICIAL = 2023  # primeira temporada usada como calibração
ANOS_ALVO = [2024, 2025, 2026]
N_MINIMO = 15

GRADE = dict(
    k_mando=[None, 0.2, 0.35, 0.5, 0.7, 1.0],
    usar_estilo=[True, False],
    filtro_aderencia=[0.0, 0.5, 0.65, 0.8],
    multiplicador_dp=[1.5, 2.5],
    limite_unilateral=[2, 4],
)
MERCADOS = [
    dict(nome="BTTS", liga="seriea", mercado="btts", bookmaker_id=BOOKMAKER_BET365,
         limiar_edge=0.05, n_historico=10, odd_maxima=None, limiar_favoritismo=None),
    dict(nome="Over 2.5", liga="seriea", mercado="over25", bookmaker_id=BOOKMAKER_SBO,
         limiar_edge=0.08, n_historico=15, odd_maxima=2.20, limiar_favoritismo=0.7484),
]
GRADE_CARTOES = dict(
    k_mando=[None, 0.35, 0.7],
    peso_arbitro=[0.0, 0.3, 0.5],
    limite_cartoes=[2, 3.8],
)


def _init_gols(liga, bookmaker_id):
    global _DF
    _DF = carregar_liga_sportmonks(CAMINHO_HIST[liga], bookmaker_id=bookmaker_id)


def _rodar_combo_gols(args):
    combo, chaves, cfg = args
    params = dict(zip(chaves, combo))
    try:
        rel = rodar_retrospectiva(_DF, params=params, min_jogos_historico=8,
                                  min_jogos_estilo=5, n_historico=cfg["n_historico"])
        r = simular_apostas(rel["jogos"], mercado=cfg["mercado"], limiar_edge=cfg["limiar_edge"])
    except Exception:
        return None
    por_chave = {(j["jogo"], j["data"]): j for j in rel["jogos"]}
    apostas = []
    for a in r["apostas"]:
        completo = por_chave.get((a["jogo"], a["data"]))
        fav = completo.get("prob_mercado_favorito_dc") if completo else None
        if passa_filtros_gols(cfg, a["odd"], fav):
            apostas.append(dict(data=a["data"], lucro=a["lucro"], venceu=a["venceu"]))
    return (params, apostas)


def _rodar_combo_cartoes(args):
    params = args
    try:
        apostas = _apostas_cartoes(**params)
    except Exception:
        return None
    return (params, apostas)


def _apostas_cartoes(k_mando, peso_arbitro, limite_cartoes):
    caminho = CAMINHO_HIST["serieb"]
    jogos_ref = carregar_referees_cartoes(caminho)
    medias = media_arbitro_walk_forward(jogos_ref, min_jogos_arbitro=MIN_JOGOS_ARBITRO)
    media_por_fixture = {j["fixture_id"]: m for j, m in zip(jogos_ref, medias)}
    df = carregar_liga_sportmonks(caminho, bookmaker_id=BOOKMAKER_BET365)
    row_por_chave = {
        (f"{r['home_team_name']} x {r['away_team_name']}",
         datetime.fromtimestamp(r["timestamp"]).date()): r for _, r in df.iterrows()
    }
    params = dict(k_mando=k_mando, usar_estilo=True, filtro_estilo=0.8, filtro_favoritismo=0.65,
                  multiplicador_dp=1.5, limite_unilateral=2,
                  limite_unilateral_por_campo={"cartoes_pro": limite_cartoes,
                                               "cartoes_contra": limite_cartoes})
    rel = rodar_retrospectiva(df, params=params, min_jogos_historico=8, min_jogos_estilo=5,
                              n_historico=N_HISTORICO_CARTOES)
    apostas = []
    for jogo in rel["jogos"]:
        m_pro = jogo["mercados"].get("cartoes_pro")
        m_contra = jogo["mercados"].get("cartoes_contra")
        if not m_pro or not m_contra or m_pro["real"] is None or m_contra["real"] is None:
            continue
        row = row_por_chave.get((jogo["jogo"], jogo["data"]))
        if row is None:
            continue
        if peso_arbitro == 0.0:
            pred = m_pro["pred"] + m_contra["pred"]
        else:
            pred = prever_cartoes_combinado(m_pro["pred"] + m_contra["pred"],
                                            media_por_fixture.get(row["_fixture_id"]),
                                            peso_arbitro=peso_arbitro)
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
            apostas.append(dict(data=jogo["data"], lucro=ap["lucro"], venceu=ap["venceu"]))
    return apostas


def _por_ano(apostas):
    d = defaultdict(list)
    for a in apostas:
        d[a["data"].year].append(a)
    return d


def _dobras(resultados, rotulo_params):
    """Para cada ano-alvo: escolhe a melhor config nos anos anteriores e
    aplica no ano-alvo. Devolve linhas da tabela + apostas do conjunto de
    teste agregado."""
    linhas = ["| Ano-alvo | Calibração | Config escolhida | Teste (ano-alvo) |",
              "|---|---|---|---|"]
    teste_agregado = []
    for alvo in ANOS_ALVO:
        anos_cal = list(range(ANO_INICIAL, alvo))
        melhor = None
        for params, apostas in resultados:
            cal = [a for a in apostas if a["data"].year in anos_cal]
            if len(cal) < N_MINIMO:
                continue
            s = stats(cal)
            if melhor is None or s["z"] > melhor[0]:
                melhor = (s["z"], params, s)
        if melhor is None:
            linhas.append(f"| {alvo} | {anos_cal[0]}-{anos_cal[-1]} | — | sem config com n>={N_MINIMO} |")
            continue
        _, params, s_cal = melhor
        apostas_escolhida = next(a for p, a in resultados if p == params)
        teste = [a for a in apostas_escolhida if a["data"].year == alvo]
        teste_agregado += teste
        s_t = stats(teste)
        cal_txt = f"{anos_cal[0]}-{anos_cal[-1]}" if len(anos_cal) > 1 else str(anos_cal[0])
        teste_txt = (f"n={s_t['n']} ROI={s_t['roi']*100:+.1f}% z={s_t['z']:+.2f}"
                     if s_t["n"] else "n=0")
        linhas.append(f"| {alvo} | {cal_txt} (n={s_cal['n']}, ROI={s_cal['roi']*100:+.1f}%) "
                      f"| {rotulo_params(params)} | {teste_txt} |")
    return linhas, teste_agregado


def main():
    linhas = [
        f"# Calibração móvel — teste fora da amostra dentro do regime atual ({date.today()})", "",
        "Responde à hipótese *\"o jogo mudou, então só os anos recentes valem\"*",
        "sem a circularidade de validar no próprio período de calibração.",
        "",
        "Cada ano-alvo é escolhido **só com os anos anteriores** e testado intocado:",
        "calibra em 2023 → testa 2024; calibra em 2023-2024 → testa 2025; calibra em",
        "2023-2025 → testa 2026. Tudo dentro do regime recente.",
        "",
        "O **agregado dos anos-alvo** é a estimativa honesta do que esperar operando:",
        "recalibrar com o que se sabe e apostar no que vem depois.",
        "",
    ]

    rotulo_gols = lambda p: (f"k={p['k_mando']}, estilo={'s' if p['usar_estilo'] else 'n'}, "
                             f"filtro={p['filtro_aderencia']}")
    combos = list(itertools.product(*GRADE.values()))
    chaves = list(GRADE.keys())

    for cfg in MERCADOS:
        print(f"== {cfg['nome']} ({len(combos)} combos) ==", flush=True)
        tarefas = [(c, chaves, cfg) for c in combos]
        with mp.Pool(N_PROCESSOS, initializer=_init_gols,
                      initargs=(cfg["liga"], cfg["bookmaker_id"])) as pool:
            resultados = [r for r in pool.map(_rodar_combo_gols, tarefas) if r]
        tabela, teste = _dobras(resultados, rotulo_gols)
        s = stats(teste)
        linhas += [f"## {cfg['nome']}", ""] + tabela + [
            "", f"**Agregado dos anos-alvo (fora da amostra): n={s['n']}, "
            f"ROI={s['roi']*100:+.1f}%, z={s['z']:+.2f}**" if s["n"] else "**Sem apostas**", ""]
        print(f"  agregado: n={s['n']} ROI={s['roi']*100:+.1f}% z={s['z']:+.2f}", flush=True)

    print("== Cartões+Árbitro ==", flush=True)
    chaves_c = list(GRADE_CARTOES.keys())
    tarefas = [dict(zip(chaves_c, c)) for c in itertools.product(*GRADE_CARTOES.values())]
    with mp.Pool(N_PROCESSOS) as pool:
        resultados = [r for r in pool.map(_rodar_combo_cartoes, tarefas) if r]
    rotulo_c = lambda p: f"k={p['k_mando']}, peso árbitro={p['peso_arbitro']}"
    tabela, teste = _dobras(resultados, rotulo_c)
    s = stats(teste)
    linhas += ["## Cartões+Árbitro", ""] + tabela + [
        "", f"**Agregado dos anos-alvo (fora da amostra): n={s['n']}, "
        f"ROI={s['roi']*100:+.1f}%, z={s['z']:+.2f}**" if s["n"] else "**Sem apostas**", ""]

    linhas += ["## Como ler", "",
               "Se o agregado dos anos-alvo for positivo com `z` decente, o método tem",
               "valor no regime atual e a hipótese da mudança de jogo se sustenta. Se for",
               "perto de zero, o `+22%` de 2024-2026 era o ajuste se olhando no espelho —",
               "e o resultado não depende de anos antigos nem de discussão sobre regime.", ""]

    saida = f"docs/retrospectiva_calibracao_movel_{date.today()}.md"
    with open(saida, "w") as fh:
        fh.write("\n".join(linhas) + "\n")
    print(f"\nRelatório: {saida}")


if __name__ == "__main__":
    main()
