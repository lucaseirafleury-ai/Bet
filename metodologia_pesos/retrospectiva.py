"""Validação retrospectiva (walk-forward) do motor de pesos contra os
placares reais já presentes nos CSVs do FootyStats — substitui a
necessidade de `Tips_telegram.xlsx` (inacessível nesta sessão) como fonte
de verdade para calibrar os parâmetros livres do modelo.

Para cada jogo do histórico, finge que a data desse jogo é "hoje": monta o
histórico de cada time só com jogos ANTERIORES a essa data (sem
look-ahead bias), calcula o estilo dos adversários pelos últimos 5 jogos
deles (mesma função de `estilo.py`), roda o motor de pesos (`pesos.py`)
para estimar Gols Pró/Contra do mandante, e compara com o placar real.

Simplificação assumida (documentada, consistente com o fluxo de produção):
o estilo de cada adversário histórico é calculado "como está hoje" (últimos
5 jogos antes da data do jogo sendo avaliado), não recalculado
separadamente para a data de cada jogo histórico individual — é
exatamente como `attach_estilo`/o banco JSON já funcionam em produção (uma
nota por time, não uma nota por data).
"""
from __future__ import annotations

import itertools
from datetime import datetime

from estilo import N_JOGOS_PADRAO, calcular_notas_estilo
from pesos import ajuste_mando, calcular_pesos_historico, indicador_pro_contra
from planilha_lib import get_historico

# mapeia campo esperado por pesos.indicador_pro_contra -> chave do dict de
# get_historico (perspectiva do time da linha)
STAT_KEY_MAP = {
    "gols_pro": "gf", "gols_contra": "ga",
    "cartoes_pro": "yf", "cartoes_contra": "ya",
    "escanteios_pro": "cf", "escanteios_contra": "ca",
    "chutes_pro": "sf", "chutes_contra": "sa",
    "chutes_gol_pro": "sotf", "chutes_gol_contra": "sota",
    "gols_1t_pro": "htf", "gols_1t_contra": "hta",
}

PARAMS_PADRAO = dict(k_mando=None, filtro_aderencia=0.65, limite_unilateral=4, multiplicador_dp=2.5, usar_estilo=True)


def _favoritismo_row(row, is_home):
    """Favoritismo normalizado (mesma fórmula de `get_historico`), a partir
    das odds 3-vias do próprio jogo sendo avaliado."""
    try:
        oh, od_, oa = row["odds_ft_home_team_win"], row["odds_ft_draw"], row["odds_ft_away_team_win"]
        ph, pd_, pa = 1 / oh, 1 / od_, 1 / oa
        s = ph + pd_ + pa
        return (ph / s) if is_home else (pa / s)
    except Exception:
        return None


def _data_partida(row):
    return datetime.strptime(row["date_GMT"].split(" - ")[0], "%b %d %Y")


def _estilo_vetor(notas):
    return [notas["bb"], notas["pa"], notas["tr"], notas["pos"], notas["bp"]]


def _adaptar_historico(hist, df_antes, estilo_cache, n_jogos_estilo):
    """Converte a saída de `get_historico` (chaves gf/ga/cf/...) no formato
    que `pesos.calcular_pesos_historico` espera (data, mando,
    notas_estilo_adv, favoritismo, + campos de estatística renomeados).

    Descarta jogos cujo adversário ainda não tem `n_jogos_estilo` partidas
    anteriores suficientes para calcular estilo (não inventa dado).
    """
    adaptado = []
    for rec in hist:
        adv = rec["adv"]
        if adv not in estilo_cache:
            hist_adv = get_historico(adv, df_antes, n=n_jogos_estilo)
            estilo_cache[adv] = calcular_notas_estilo(hist_adv) if len(hist_adv) >= n_jogos_estilo else None
        notas_adv = estilo_cache[adv]
        if notas_adv is None or rec.get("fav") is None:
            continue
        item = dict(
            data=datetime.strptime(rec["data"], "%d/%m/%Y").date(),
            mando=rec["mando"],
            notas_estilo_adv=_estilo_vetor(notas_adv),
            favoritismo=rec["fav"],
        )
        for campo_pesos, chave_hist in STAT_KEY_MAP.items():
            item[campo_pesos] = rec[chave_hist]
        adaptado.append(item)
    return adaptado


def prever_jogo(row, df, params=None, min_jogos_historico=10, min_jogos_estilo=N_JOGOS_PADRAO, n_historico=15):
    """Prevê Gols Pró/Contra do time da CASA em `row`, usando só jogos
    anteriores à data de `row` (walk-forward). Retorna None quando não há
    dado suficiente (nunca inventa/preenche com placeholder).

    `params["usar_estilo"]` (default `True`, ver `PARAMS_PADRAO`): quando
    `False`, roda o teste de ablação — calcula estilo normalmente (pra
    manter EXATAMENTE o mesmo conjunto de jogos avaliados entre as duas
    condições, condição justa de comparação), mas ignora o resultado no
    peso/filtro (`pesos.calcular_pesos_historico(usar_estilo=False)`).
    """
    params = {**PARAMS_PADRAO, **(params or {})}
    ts_corte = row["timestamp"]
    df_antes = df[df["timestamp"] < ts_corte]

    home, away = row["home_team_name"], row["away_team_name"]
    hist_home = get_historico(home, df_antes, n=n_historico)
    if len(hist_home) < min_jogos_historico:
        return None

    hist_estilo_away = get_historico(away, df_antes, n=min_jogos_estilo)
    if len(hist_estilo_away) < min_jogos_estilo:
        return None
    estilo_alvo = _estilo_vetor(calcular_notas_estilo(hist_estilo_away))

    favoritismo_alvo = _favoritismo_row(row, is_home=True)
    if favoritismo_alvo is None:
        return None

    estilo_cache = {}
    historico_adaptado = _adaptar_historico(hist_home, df_antes, estilo_cache, min_jogos_estilo)
    if not historico_adaptado:
        return None

    data_jogo = _data_partida(row).date()
    com_pesos = calcular_pesos_historico(
        historico_adaptado, estilo_alvo, favoritismo_alvo, data_jogo, usar_estilo=params["usar_estilo"]
    )
    if params["k_mando"] is not None:
        com_pesos = ajuste_mando(com_pesos, mando_alvo="Casa", k=params["k_mando"])

    validos = [
        j for j in com_pesos
        if j["aderencia_estilo"] >= params["filtro_aderencia"] and j["aderencia_favoritismo"] >= params["filtro_aderencia"]
    ]
    if not validos:
        return None
    pesos_lista = [j["peso_final"] for j in validos]

    ind_pro = indicador_pro_contra(
        [j["gols_pro"] for j in validos], pesos_lista, params["limite_unilateral"], params["multiplicador_dp"]
    )
    ind_contra = indicador_pro_contra(
        [j["gols_contra"] for j in validos], pesos_lista, params["limite_unilateral"], params["multiplicador_dp"]
    )
    if ind_pro["media_final"] is None or ind_contra["media_final"] is None:
        return None

    gf_real, ga_real = float(row["home_team_goal_count"]), float(row["away_team_goal_count"])
    gf_pred, ga_pred = ind_pro["media_final"], ind_contra["media_final"]
    return dict(
        jogo=f"{home} x {away}", data=data_jogo,
        gf_real=gf_real, ga_real=ga_real, gf_pred=gf_pred, ga_pred=ga_pred,
        erro_gf=abs(gf_pred - gf_real), erro_ga=abs(ga_pred - ga_real),
        total_real=gf_real + ga_real, total_pred=gf_pred + ga_pred,
        over25_real=(gf_real + ga_real) > 2.5, over25_pred=(gf_pred + ga_pred) > 2.5,
        btts_real=(gf_real > 0 and ga_real > 0), btts_pred=(gf_pred > 0.5 and ga_pred > 0.5),
        n_jogos_validos=len(validos),
    )


def rodar_retrospectiva(df, params=None, min_jogos_historico=10, min_jogos_estilo=N_JOGOS_PADRAO,
                         n_historico=15, max_jogos_avaliados=None):
    """Roda `prever_jogo` para cada partida do histórico (em ordem
    cronológica) e agrega as métricas. Partidas sem dado suficiente são
    puladas silenciosamente (contam em `n_pulados`, não em `n`).
    """
    df_ordenado = df.sort_values("timestamp")
    avaliados = []
    n_pulados = 0
    for _, row in df_ordenado.iterrows():
        if max_jogos_avaliados and len(avaliados) >= max_jogos_avaliados:
            break
        resultado = prever_jogo(row, df, params, min_jogos_historico, min_jogos_estilo, n_historico)
        if resultado is None:
            n_pulados += 1
        else:
            avaliados.append(resultado)

    if not avaliados:
        return dict(n=0, n_pulados=n_pulados, mae_gols_total=None, acerto_over25=None, acerto_btts=None, jogos=[])

    n = len(avaliados)
    mae_gols_total = sum(j["erro_gf"] + j["erro_ga"] for j in avaliados) / n
    acerto_over25 = sum(1 for j in avaliados if j["over25_pred"] == j["over25_real"]) / n
    acerto_btts = sum(1 for j in avaliados if j["btts_pred"] == j["btts_real"]) / n
    return dict(
        n=n, n_pulados=n_pulados,
        mae_gols_total=mae_gols_total, acerto_over25=acerto_over25, acerto_btts=acerto_btts,
        jogos=avaliados,
    )


def grid_search(df, grade_parametros, **kwargs):
    """Roda `rodar_retrospectiva` para cada combinação de
    `grade_parametros` (dict {nome: [valores]}) e retorna
    `[(params, relatorio), ...]` ordenado do menor pro maior
    `mae_gols_total` (combinações sem jogos avaliados ficam no fim).

    Custo: uma passada completa de `rodar_retrospectiva` por combinação —
    use `max_jogos_avaliados` (via kwargs) para limitar o custo em
    datasets grandes.
    """
    nomes = list(grade_parametros.keys())
    resultados = []
    for combo in itertools.product(*grade_parametros.values()):
        params = dict(zip(nomes, combo))
        relatorio = rodar_retrospectiva(df, params=params, **kwargs)
        resultados.append((params, relatorio))
    resultados.sort(key=lambda par: (par[1]["mae_gols_total"] is None, par[1]["mae_gols_total"]))
    return resultados
