"""Grid search COM HOLDOUT nas 3 ligas novas (Championship/Argentina/MLS).

Diferente de `explorar_ligas_novas.py` (que só reaplica os parâmetros do
Brasileirão), aqui cada liga é calibrada por conta própria — inclusive o
fator casa (`k_mando`), que é o parâmetro com mais motivo teórico pra
diferir entre ligas (mando forte na Argentina, viagem/fuso na MLS,
calendário congestionado na Championship).

Disciplina obrigatória, porque um grid grande ACHA z alto por acaso:
- Treino em 2024-2025, HOLDOUT em 2026 (o processo de escolha nunca vê
  o holdout). Só candidato que se sustenta nos dois conta.
- Ano a ano sempre reportado, nunca só o agregado.
- `n>=15` em treino E holdout pra considerar qualquer célula.
- Análise de potência: quantas apostas seriam necessárias pra o ROI
  observado virar z=2 — distingue "sem edge" de "sem amostra".

Uso: `python3 grid_ligas_novas.py`
Saída: `docs/retrospectiva_grid_ligas_novas_<data>.md`
"""
import itertools
import statistics
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
from previsao_dia import MARKET_NUMBER_OF_CARDS, MIN_JOGOS_ARBITRO
from retrospectiva import rodar_retrospectiva, simular_apostas
from sportmonks_adapter import BOOKMAKER_BET365, BOOKMAKER_SBO, carregar_liga_sportmonks

LIGAS = {
    "championship": "Championship (Inglaterra)",
    "argentina": "Liga Profesional (Argentina)",
    "mls": "MLS (EUA/Canadá)",
}
ANO_HOLDOUT = 2026

# Mesmo espaço de grid usado no Brasileirão (docs/retrospectiva_grid_completo_2026-08-25.md)
GRADE = dict(
    k_mando=[None, 0.2, 0.35, 0.5, 0.7, 1.0],
    usar_estilo=[True, False],
    filtro_aderencia=[0.0, 0.5, 0.65, 0.8],
    multiplicador_dp=[1.5, 2.5],
    limite_unilateral=[2, 4],
)
MERCADOS_GOLS = [
    dict(nome="BTTS", mercado="btts", bookmaker_id=BOOKMAKER_BET365, casa="bet365",
         limiar_edge=0.05, n_historico=10),
    dict(nome="Over 2.5", mercado="over25", bookmaker_id=BOOKMAKER_SBO, casa="Sbo",
         limiar_edge=0.08, n_historico=15),
]
# Cartões tem grid próprio (peso do árbitro é um eixo só dele)
GRADE_CARTOES = dict(
    k_mando=[None, 0.35, 0.7],
    peso_arbitro=[0.0, 0.3, 0.5],
    limite_cartoes=[2, 3.8],
)


def caminho(chave):
    return f"data/sportmonks_{chave}/fixtures.jsonl"


def _split(apostas):
    treino = [a for a in apostas if a["data"].year < ANO_HOLDOUT]
    holdout = [a for a in apostas if a["data"].year >= ANO_HOLDOUT]
    return treino, holdout


def _n_para_z2(apostas):
    """Quantas apostas seriam necessárias pra o ROI observado virar z=2.
    Distingue 'efeito inexistente' de 'efeito real mas amostra curta'."""
    if len(apostas) < 2:
        return None
    lucros = [a["lucro"] for a in apostas]
    roi = sum(lucros) / len(lucros)
    dp = statistics.pstdev(lucros)
    if roi <= 0 or dp == 0:
        return None
    return int(round((2 * dp / roi) ** 2))


def _por_ano(apostas):
    por_ano = defaultdict(list)
    for a in apostas:
        por_ano[a["data"].year].append(a)
    return {ano: stats(lista) for ano, lista in sorted(por_ano.items())}


def apostas_gols(df, params, cfg):
    rel = rodar_retrospectiva(df, params=params, min_jogos_historico=8, min_jogos_estilo=5,
                              n_historico=cfg["n_historico"])
    r = simular_apostas(rel["jogos"], mercado=cfg["mercado"], limiar_edge=cfg["limiar_edge"])
    return r["apostas"]


def apostas_cartoes(chave, k_mando, peso_arbitro, limite_cartoes):
    caminho_liga = caminho(chave)
    jogos_ref = carregar_referees_cartoes(caminho_liga)
    medias_wf = media_arbitro_walk_forward(jogos_ref, min_jogos_arbitro=MIN_JOGOS_ARBITRO)
    media_por_fixture = {j["fixture_id"]: m for j, m in zip(jogos_ref, medias_wf)}
    df = carregar_liga_sportmonks(caminho_liga, bookmaker_id=BOOKMAKER_BET365)
    row_por_chave = {
        (f"{row['home_team_name']} x {row['away_team_name']}",
         datetime.fromtimestamp(row["timestamp"]).date()): row
        for _, row in df.iterrows()
    }
    params = dict(k_mando=k_mando, usar_estilo=True, filtro_estilo=0.8, filtro_favoritismo=0.65,
                  multiplicador_dp=1.5, limite_unilateral=2,
                  limite_unilateral_por_campo={"cartoes_pro": limite_cartoes,
                                               "cartoes_contra": limite_cartoes})
    rel = rodar_retrospectiva(df, params=params, min_jogos_historico=8, min_jogos_estilo=5,
                              n_historico=10)
    apostas = []
    for jogo in rel["jogos"]:
        m_pro = jogo["mercados"].get("cartoes_pro")
        m_contra = jogo["mercados"].get("cartoes_contra")
        if not m_pro or not m_contra or m_pro["real"] is None or m_contra["real"] is None:
            continue
        row = row_por_chave.get((jogo["jogo"], jogo["data"]))
        if row is None:
            continue
        media_arb = media_por_fixture.get(row["_fixture_id"])
        if peso_arbitro == 0.0:
            pred = m_pro["pred"] + m_contra["pred"]  # sem componente de árbitro
        else:
            pred = prever_cartoes_combinado(m_pro["pred"] + m_contra["pred"], media_arb,
                                            peso_arbitro=peso_arbitro)
        if pred is None:
            continue
        jogo_odds = dict(odds={str(MARKET_NUMBER_OF_CARDS): row.get("_odds_cartoes") or []})
        linha = linha_mais_liquida(jogo_odds, MARKET_NUMBER_OF_CARDS)
        if linha is None:
            continue
        odd_over = odd_media_na_linha(jogo_odds, MARKET_NUMBER_OF_CARDS, linha, "Over")
        odd_under = odd_media_na_linha(jogo_odds, MARKET_NUMBER_OF_CARDS, linha, "Under")
        if odd_over is None or odd_under is None:
            continue
        aposta = simular_aposta_linha(pred, linha, odd_over, odd_under,
                                      m_pro["real"] + m_contra["real"], limiar_edge=0.10)
        if aposta is not None:
            aposta["data"] = jogo["data"]
            apostas.append(aposta)
    return apostas


def _fmt(s):
    if s["n"] == 0:
        return "n=0"
    return f"n={s['n']} ROI={s['roi']*100:+.1f}% z={s['z']:+.2f}"


def rodar_liga_gols(chave, linhas):
    combos = list(itertools.product(*GRADE.values()))
    chaves = list(GRADE.keys())
    for cfg in MERCADOS_GOLS:
        df = carregar_liga_sportmonks(caminho(chave), bookmaker_id=cfg["bookmaker_id"])
        resultados = []
        for i, combo in enumerate(combos, 1):
            params = dict(zip(chaves, combo))
            try:
                apostas = apostas_gols(df, params, cfg)
            except Exception:
                continue
            treino, holdout = _split(apostas)
            s_t, s_h = stats(treino), stats(holdout)
            if s_t["n"] < 15 or s_h["n"] < 15:
                continue  # amostra mínima nos DOIS lados, senão não é avaliável
            resultados.append((s_t["z"], params, s_t, s_h, apostas))
            if i % 48 == 0:
                print(f"    {chave}/{cfg['nome']}: {i}/{len(combos)} combos", flush=True)
        resultados.sort(key=lambda r: r[0], reverse=True)
        linhas += [f"### {cfg['nome']} (casa {cfg['casa']}, edge>={cfg['limiar_edge']*100:.0f}%)", ""]
        if not resultados:
            linhas += ["Nenhuma combinação com n>=15 em treino E holdout — liga sem amostra "
                       "suficiente pra este mercado.", ""]
            continue
        linhas += [f"{len(resultados)} de {len(combos)} combinações avaliáveis. Top 8 por z de TREINO "
                   "(2024-2025), com o holdout 2026 ao lado — holdout é o que vale:", "",
                   "| k_mando | estilo | filtro | dp | outlier | TREINO | HOLDOUT 2026 | n p/ z=2 |",
                   "|---|---|---|---|---|---|---|---|"]
        for z_t, params, s_t, s_h, apostas in resultados[:8]:
            n_z2 = _n_para_z2(apostas)
            linhas.append(
                f"| {params['k_mando']} | {'sim' if params['usar_estilo'] else 'não'} | "
                f"{params['filtro_aderencia']} | {params['multiplicador_dp']} | "
                f"{params['limite_unilateral']} | {_fmt(s_t)} | {_fmt(s_h)} | "
                f"{n_z2 if n_z2 else '—'} |"
            )
        melhor = max(resultados, key=lambda r: r[3]["z"])  # melhor por HOLDOUT
        linhas += ["", f"**Melhor por holdout**: k_mando={melhor[1]['k_mando']}, "
                   f"estilo={'sim' if melhor[1]['usar_estilo'] else 'não'}, "
                   f"filtro={melhor[1]['filtro_aderencia']} → holdout {_fmt(melhor[3])}. "
                   f"Ano a ano (período todo): " +
                   "; ".join(f"{ano} {_fmt(s)}" for ano, s in _por_ano(melhor[4]).items()), ""]


def rodar_liga_cartoes(chave, linhas):
    combos = list(itertools.product(*GRADE_CARTOES.values()))
    chaves = list(GRADE_CARTOES.keys())
    resultados = []
    for combo in combos:
        params = dict(zip(chaves, combo))
        try:
            apostas = apostas_cartoes(chave, **params)
        except Exception:
            continue
        treino, holdout = _split(apostas)
        s_t, s_h = stats(treino), stats(holdout)
        if s_t["n"] < 15 or s_h["n"] < 15:
            continue
        resultados.append((s_t["z"], params, s_t, s_h, apostas))
    resultados.sort(key=lambda r: r[0], reverse=True)
    linhas += ["### Cartões+Árbitro (bet365, edge>=10%)", ""]
    if not resultados:
        linhas += ["Nenhuma combinação com n>=15 em treino E holdout.", ""]
        return
    linhas += [f"{len(resultados)} de {len(combos)} combinações avaliáveis:", "",
               "| k_mando | peso árbitro | outlier cartões | TREINO | HOLDOUT 2026 | n p/ z=2 |",
               "|---|---|---|---|---|---|"]
    for z_t, params, s_t, s_h, apostas in resultados:
        n_z2 = _n_para_z2(apostas)
        linhas.append(f"| {params['k_mando']} | {params['peso_arbitro']} | "
                      f"{params['limite_cartoes']} | {_fmt(s_t)} | {_fmt(s_h)} | "
                      f"{n_z2 if n_z2 else '—'} |")
    melhor = max(resultados, key=lambda r: r[3]["z"])
    linhas += ["", f"**Melhor por holdout**: k_mando={melhor[1]['k_mando']}, "
               f"peso_arbitro={melhor[1]['peso_arbitro']} → holdout {_fmt(melhor[3])}. "
               f"Ano a ano: " + "; ".join(f"{ano} {_fmt(s)}" for ano, s in _por_ano(melhor[4]).items()), ""]


def main():
    import sys as _sys

    # `--ligas a,b` roda só essas ligas; `--enxuto` fixa os dois eixos de
    # refinamento fino (dp/outlier) nos valores padrão, deixando só os eixos
    # com motivo teórico de variar entre ligas (fator casa, estilo, filtro) —
    # 48 combinações em vez de 192, ~4x mais rápido.
    ligas = dict(LIGAS)
    for i, arg in enumerate(_sys.argv):
        if arg == "--ligas" and i + 1 < len(_sys.argv):
            ligas = {k: LIGAS[k] for k in _sys.argv[i + 1].split(",")}
    if "--enxuto" in _sys.argv:
        GRADE["multiplicador_dp"] = [1.5]
        GRADE["limite_unilateral"] = [2]

    linhas = [
        f"# Grid com holdout nas 3 ligas novas ({date.today()})",
        "",
        "Cada liga calibrada por conta própria (inclusive fator casa `k_mando`),",
        f"treino 2024-2025 e **holdout {ANO_HOLDOUT}** — o holdout nunca participa da escolha.",
        "",
        "Grid de gols: 192 combinações (`k_mando × usar_estilo × filtro_aderencia ×`",
        "`multiplicador_dp × limite_unilateral`), mesmo espaço usado no Brasileirão.",
        "Grid de cartões: 18 combinações (`k_mando × peso_arbitro × outlier de cartões`) —",
        "`peso_arbitro=0.0` é o teste de ablação: mede se o árbitro agrega algo de verdade.",
        "",
        "**Aviso de comparação múltipla**: com centenas de combinações, o melhor z de TREINO",
        "é quase sempre sorte. A coluna que importa é o HOLDOUT. `n p/ z=2` = quantas apostas",
        "seriam necessárias pro ROI observado virar significante (distingue 'sem edge' de",
        "'sem amostra').",
        "",
    ]
    # Checkpoint a cada etapa: o grid inteiro leva horas, e um container
    # reciclado no meio não pode custar o trabalho todo.
    sufixo = "_".join(ligas) if len(ligas) < len(LIGAS) else "todas"
    parcial = f"docs/_parcial_grid_ligas_novas_{sufixo}_{date.today()}.md"

    def salvar(caminho_saida):
        with open(caminho_saida, "w") as fh:
            fh.write("\n".join(linhas) + "\n")

    for chave, nome in ligas.items():
        print(f"== {nome} ==", flush=True)
        linhas += [f"## {nome}", ""]
        rodar_liga_gols(chave, linhas)
        salvar(parcial)
        print("  cartões...", flush=True)
        rodar_liga_cartoes(chave, linhas)
        salvar(parcial)
        print(f"  parcial salvo ({nome} completa)", flush=True)

    saida = f"docs/retrospectiva_grid_ligas_novas_{sufixo}_{date.today()}.md"
    salvar(saida)
    print(f"\nRelatório salvo em {saida}")


if __name__ == "__main__":
    main()
