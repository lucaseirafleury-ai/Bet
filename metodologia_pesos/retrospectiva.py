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
from pesos import (
    ajuste_mando,
    calcular_pesos_historico,
    indicador_pro_contra,
    probabilidade_btts,
    probabilidade_implicita,
    probabilidade_implicita_2vias,
    probabilidade_over,
)
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

PARAMS_PADRAO = dict(
    k_mando=None, filtro_aderencia=0.65, limite_unilateral=4, multiplicador_dp=2.5,
    usar_estilo=True, estilo_por_mando=False,
)

_MANDO_OPOSTO = {"Casa": "Fora", "Fora": "Casa"}

# mapeia campo -> colunas do CSV que dão o valor REAL do mercado no jogo
# sendo avaliado (perspectiva do time da CASA, que é quem prever_jogo prevê)
_COLUNAS_VALOR_REAL = {
    "gols_pro": ("home_team_goal_count",), "gols_contra": ("away_team_goal_count",),
    "cartoes_pro": ("home_team_yellow_cards", "home_team_red_cards"),
    "cartoes_contra": ("away_team_yellow_cards", "away_team_red_cards"),
    "escanteios_pro": ("home_team_corner_count",), "escanteios_contra": ("away_team_corner_count",),
    "chutes_pro": ("home_team_shots",), "chutes_contra": ("away_team_shots",),
    "chutes_gol_pro": ("home_team_shots_on_target",), "chutes_gol_contra": ("away_team_shots_on_target",),
    "gols_1t_pro": ("home_team_goal_count_half_time",), "gols_1t_contra": ("away_team_goal_count_half_time",),
}


def _valor_real(row, campo):
    """Valor real (placar/estatística) de `campo` no jogo `row`. Soma as
    colunas quando o mercado precisa de mais de uma (ex.: cartões =
    amarelos + vermelhos). Retorna None se a coluna não existir/for NaN
    (não inventa dado)."""
    try:
        valor = sum(float(row[c]) for c in _COLUNAS_VALOR_REAL[campo])
        return valor if valor == valor else None  # descarta NaN (NaN != NaN)
    except (KeyError, ValueError, TypeError):
        return None


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


def _estilo_por_mando(team, df_antes, mando, n_jogos_estilo):
    """Estilo do time calculado SÓ com os últimos `n_jogos_estilo` jogos no
    mesmo mando (só jogos em casa, ou só jogos fora) — hipótese: muitos
    times jogam diferente em casa vs fora, misturar os dois (como
    `calcular_notas_estilo` normal faz) pode diluir esse sinal.

    Retorna None se o time não tem jogos suficientes NAQUELE mando
    específico antes do corte (não inventa dado — é uma exigência mais
    forte que a versão sem split, então espera-se mais jogos pulados).
    """
    if mando == "Casa":
        sub_df = df_antes[df_antes["home_team_name"] == team]
    elif mando == "Fora":
        sub_df = df_antes[df_antes["away_team_name"] == team]
    else:
        return None
    jogos = get_historico(team, sub_df, n=n_jogos_estilo)
    if len(jogos) < n_jogos_estilo:
        return None
    return calcular_notas_estilo(jogos)


def _adaptar_historico(hist, df_antes, estilo_cache, n_jogos_estilo, estilo_por_mando=False):
    """Converte a saída de `get_historico` (chaves gf/ga/cf/...) no formato
    que `pesos.calcular_pesos_historico` espera (data, mando,
    notas_estilo_adv, favoritismo, + campos de estatística renomeados).

    Descarta jogos cujo adversário ainda não tem `n_jogos_estilo` partidas
    anteriores suficientes para calcular estilo (não inventa dado).

    `estilo_por_mando`: quando `True`, a nota do adversário é calculada só
    com os jogos dele no mando OPOSTO ao de `rec["mando"]` — porque se o
    time da linha jogou em casa naquele jogo histórico (`rec["mando"] ==
    "Casa"`), o adversário jogou fora, então usamos o estilo do adversário
    JOGANDO FORA (mais fiel ao que ele realmente fez naquele confronto).
    """
    adaptado = []
    for rec in hist:
        adv = rec["adv"]
        if estilo_por_mando:
            mando_adv = _MANDO_OPOSTO.get(rec["mando"])
            cache_key = (adv, mando_adv)
            if cache_key not in estilo_cache:
                estilo_cache[cache_key] = _estilo_por_mando(adv, df_antes, mando_adv, n_jogos_estilo) if mando_adv else None
            notas_adv = estilo_cache[cache_key]
        else:
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

    `params["estilo_por_mando"]` (default `False`): quando `True`, o
    estilo de cada time (o alvo de hoje E cada adversário histórico) é
    calculado só com os jogos NO MESMO MANDO que ele jogou/vai jogar
    naquele confronto específico — ver `_estilo_por_mando`.
    """
    params = {**PARAMS_PADRAO, **(params or {})}
    ts_corte = row["timestamp"]
    df_antes = df[df["timestamp"] < ts_corte]

    home, away = row["home_team_name"], row["away_team_name"]
    hist_home = get_historico(home, df_antes, n=n_historico)
    if len(hist_home) < min_jogos_historico:
        return None

    if params["estilo_por_mando"]:
        # o time visitante joga FORA hoje -> usar o estilo dele jogando fora
        notas_alvo = _estilo_por_mando(away, df_antes, "Fora", min_jogos_estilo)
        if notas_alvo is None:
            return None
        estilo_alvo = _estilo_vetor(notas_alvo)
    else:
        hist_estilo_away = get_historico(away, df_antes, n=min_jogos_estilo)
        if len(hist_estilo_away) < min_jogos_estilo:
            return None
        estilo_alvo = _estilo_vetor(calcular_notas_estilo(hist_estilo_away))

    favoritismo_alvo = _favoritismo_row(row, is_home=True)
    if favoritismo_alvo is None:
        return None

    estilo_cache = {}
    historico_adaptado = _adaptar_historico(
        hist_home, df_antes, estilo_cache, min_jogos_estilo, estilo_por_mando=params["estilo_por_mando"]
    )
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

    mercados = {}
    for campo in STAT_KEY_MAP:
        ind = indicador_pro_contra(
            [j[campo] for j in validos], pesos_lista, params["limite_unilateral"], params["multiplicador_dp"]
        )
        real = _valor_real(row, campo)
        if ind["media_final"] is None or real is None:
            continue
        mercados[campo] = dict(pred=ind["media_final"], real=real, erro=abs(ind["media_final"] - real))

    if "gols_pro" not in mercados or "gols_contra" not in mercados:
        return None  # gols é o mercado obrigatório (mantém compatibilidade com os relatórios anteriores)

    gf_real, ga_real = mercados["gols_pro"]["real"], mercados["gols_contra"]["real"]
    gf_pred, ga_pred = mercados["gols_pro"]["pred"], mercados["gols_contra"]["pred"]
    return dict(
        jogo=f"{home} x {away}", data=data_jogo,
        gf_real=gf_real, ga_real=ga_real, gf_pred=gf_pred, ga_pred=ga_pred,
        erro_gf=abs(gf_pred - gf_real), erro_ga=abs(ga_pred - ga_real),
        total_real=gf_real + ga_real, total_pred=gf_pred + ga_pred,
        over25_real=(gf_real + ga_real) > 2.5, over25_pred=(gf_pred + ga_pred) > 2.5,
        btts_real=(gf_real > 0 and ga_real > 0), btts_pred=(gf_pred > 0.5 and ga_pred > 0.5),
        n_jogos_validos=len(validos),
        mercados=mercados,
        **_probabilidades_e_odds(row, gf_pred, ga_pred),
    )


def _valor_odd(row, coluna):
    """Lê uma coluna de odd do CSV; retorna None se ausente/NaN/inválida
    (odd decimal tem que ser > 1) — nunca inventa odd."""
    try:
        odd = float(row[coluna])
        return odd if odd > 1 and odd == odd else None  # odd==odd descarta NaN
    except (KeyError, ValueError, TypeError):
        return None


def _probabilidades_e_odds(row, gf_pred, ga_pred):
    """Probabilidade que o MODELO dá pros mercados Over 2.5 e BTTS, e a
    probabilidade IMPLÍCITA nas odds reais do jogo (quando disponíveis no
    CSV) — a comparação entre as duas é o que mede vantagem real (não só
    acerto), usada por `simular_apostas`.

    Over 2.5: o CSV só traz a odd do lado "over" (`odds_ft_over25`), não a
    do "under" — a probabilidade implícita fica sem remover a margem da
    casa (`probabilidade_implicita`, superestima um pouco).
    BTTS: o CSV traz os dois lados (`odds_btts_yes`/`odds_btts_no`), dá pra
    normalizar de verdade com `probabilidade_implicita_2vias`.
    """
    prob_modelo_over25 = probabilidade_over(gf_pred + ga_pred, linha=2.5)
    prob_modelo_btts = probabilidade_btts(gf_pred, ga_pred)

    odd_over25 = _valor_odd(row, "odds_ft_over25")
    prob_mercado_over25 = probabilidade_implicita(odd_over25) if odd_over25 else None

    odd_btts_sim = _valor_odd(row, "odds_btts_yes")
    odd_btts_nao = _valor_odd(row, "odds_btts_no")
    prob_mercado_btts = (
        probabilidade_implicita_2vias(odd_btts_sim, odd_btts_nao)
        if odd_btts_sim and odd_btts_nao else None
    )

    return dict(
        prob_modelo_over25=prob_modelo_over25, odd_over25=odd_over25, prob_mercado_over25=prob_mercado_over25,
        prob_modelo_btts=prob_modelo_btts, odd_btts_sim=odd_btts_sim, odd_btts_nao=odd_btts_nao,
        prob_mercado_btts=prob_mercado_btts,
    )


def rodar_retrospectiva(df, params=None, min_jogos_historico=10, min_jogos_estilo=N_JOGOS_PADRAO,
                         n_historico=15, max_jogos_avaliados=None, timestamp_minimo=None):
    """Roda `prever_jogo` para cada partida do histórico (em ordem
    cronológica) e agrega as métricas. Partidas sem dado suficiente são
    puladas silenciosamente (contam em `n_pulados`, não em `n`).

    `timestamp_minimo`: quando informado, só AVALIA jogos com
    `timestamp >= timestamp_minimo` — mas o histórico usado pra prever
    cada um continua vindo de `df` inteiro (jogos antes do corte, mesmo
    que anteriores a `timestamp_minimo`). Serve pra fazer validação
    fora-da-amostra: escolher parâmetros olhando só pra uma temporada
    (ex.: 2025) e depois medir a performance real numa temporada que o
    processo de escolha nunca viu (ex.: 2026) — sem isso, escolher o
    "melhor" de um grid grande na mesma amostra onde ele foi medido é
    viés de comparação múltipla, não validação de verdade.
    """
    df_ordenado = df.sort_values("timestamp")
    if timestamp_minimo is not None:
        df_ordenado = df_ordenado[df_ordenado["timestamp"] >= timestamp_minimo]
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
        return dict(n=0, n_pulados=n_pulados, mae_gols_total=None, acerto_over25=None, acerto_btts=None,
                     mercados={}, jogos=[])

    n = len(avaliados)
    mae_gols_total = sum(j["erro_gf"] + j["erro_ga"] for j in avaliados) / n
    acerto_over25 = sum(1 for j in avaliados if j["over25_pred"] == j["over25_real"]) / n
    acerto_btts = sum(1 for j in avaliados if j["btts_pred"] == j["btts_real"]) / n

    mercados_agg = {}
    for campo in STAT_KEY_MAP:
        pontos = [j["mercados"][campo] for j in avaliados if campo in j["mercados"]]
        if not pontos:
            continue
        mae = sum(p["erro"] for p in pontos) / len(pontos)
        media_real = sum(p["real"] for p in pontos) / len(pontos)
        mercados_agg[campo] = dict(
            n=len(pontos), mae=mae, media_real=media_real,
            mae_relativo=(mae / media_real) if media_real else None,
        )

    return dict(
        n=n, n_pulados=n_pulados,
        mae_gols_total=mae_gols_total, acerto_over25=acerto_over25, acerto_btts=acerto_btts,
        mercados=mercados_agg,
        jogos=avaliados,
    )


def grid_search(df, grade_parametros, ordenar_por="mae_gols_total", **kwargs):
    """Roda `rodar_retrospectiva` para cada combinação de
    `grade_parametros` (dict {nome: [valores]}) e retorna
    `[(params, relatorio), ...]` ordenado do MELHOR pro PIOR segundo
    `ordenar_por` (combinações sem jogos avaliados ficam no fim).

    `ordenar_por`: `"mae_gols_total"` (menor é melhor, default) ou
    `"acerto_over25"`/`"acerto_btts"` (maior é melhor) — use o segundo
    quando o que importa é acertar a linha de aposta, não o placar exato
    (MAE e acerto de Over/Under podem apontar em direções opostas — ver
    `docs/retrospectiva_2025_2026_recalibracao.md`).

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

    if ordenar_por == "mae_gols_total":
        resultados.sort(key=lambda par: (par[1]["mae_gols_total"] is None, par[1]["mae_gols_total"]))
    elif ordenar_por in ("acerto_over25", "acerto_btts"):
        resultados.sort(key=lambda par: (par[1][ordenar_por] is None, -(par[1][ordenar_por] or 0)))
    else:
        raise ValueError(f"ordenar_por inválido: {ordenar_por!r}")
    return resultados


_MERCADOS_SIMULAVEIS = {
    "over25": dict(prob_modelo="prob_modelo_over25", prob_mercado="prob_mercado_over25",
                    odd="odd_over25", real="over25_real"),
    "btts": dict(prob_modelo="prob_modelo_btts", prob_mercado="prob_mercado_btts",
                 odd="odd_btts_sim", real="btts_real"),
}


def simular_apostas(jogos, mercado="over25", limiar_edge=0.0, stake=1.0):
    """Simula apostas de verdade (odd real, banca, ROI) — não só taxa de
    acerto. Só aposta quando a probabilidade do MODELO supera a
    probabilidade IMPLÍCITA na odd de mercado em pelo menos `limiar_edge`
    (vantagem/edge mínima exigida) — é essa comparação que mede vantagem
    competitiva de verdade, não o acerto isolado (uma taxa de acerto alta
    não vale nada se a odd já embutia essa probabilidade ou mais).

    `jogos`: lista vinda de `rodar_retrospectiva(...)["jogos"]` (cada item
    já carrega `prob_modelo_*`/`prob_mercado_*`/`odd_*` calculados por
    `prever_jogo`).

    `mercado`: `"over25"` (usa a odd de Over 2.5, sem remover margem — só
    temos a odd de um lado no CSV) ou `"btts"` (usa BTTS Sim, com margem
    removida via odds dos dois lados).

    IMPORTANTE — só cobre apostar no lado "over"/"sim": o CSV não traz a
    odd do lado oposto (Under 2.5), então não dá pra simular apostar contra
    o modelo nesse mercado. Jogos sem a odd necessária são pulados (não
    inventa odd).

    Retorna dict com `n_apostas`, `n_vitorias`, `taxa_acerto` (das apostas
    FEITAS, não de todos os jogos avaliados), `lucro_total`, `roi`
    (lucro/total apostado), `edge_medio` (das apostas feitas).
    """
    if mercado not in _MERCADOS_SIMULAVEIS:
        raise ValueError(f"mercado inválido: {mercado!r} (use 'over25' ou 'btts')")
    campos = _MERCADOS_SIMULAVEIS[mercado]

    apostas = []
    for jogo in jogos:
        prob_modelo = jogo.get(campos["prob_modelo"])
        prob_mercado = jogo.get(campos["prob_mercado"])
        odd = jogo.get(campos["odd"])
        if prob_modelo is None or prob_mercado is None or odd is None:
            continue
        edge = prob_modelo - prob_mercado
        if edge < limiar_edge:
            continue
        venceu = bool(jogo[campos["real"]])
        lucro = stake * (odd - 1) if venceu else -stake
        apostas.append(dict(jogo=jogo["jogo"], data=jogo["data"], odd=odd, edge=edge, venceu=venceu, lucro=lucro))

    if not apostas:
        return dict(n_apostas=0, n_vitorias=0, taxa_acerto=None, lucro_total=0.0, roi=None, edge_medio=None, apostas=[])

    n_apostas = len(apostas)
    n_vitorias = sum(1 for a in apostas if a["venceu"])
    lucro_total = sum(a["lucro"] for a in apostas)
    total_apostado = stake * n_apostas
    return dict(
        n_apostas=n_apostas,
        n_vitorias=n_vitorias,
        taxa_acerto=n_vitorias / n_apostas,
        lucro_total=lucro_total,
        roi=lucro_total / total_apostado,
        edge_medio=sum(a["edge"] for a in apostas) / n_apostas,
        apostas=apostas,
    )
