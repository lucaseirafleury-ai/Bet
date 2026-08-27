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
import math
from datetime import datetime

from estilo import N_JOGOS_PADRAO, calcular_notas_estilo
from pesos import (
    ajuste_mando,
    calcular_pesos_historico,
    indicador_pro_contra,
    odd_e_prob_under_aproximada,
    probabilidade_btts,
    probabilidade_implicita,
    probabilidade_implicita_2vias,
    probabilidade_over,
    probabilidade_resultado,
    probabilidades_implicitas_nvias,
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
    limiar_edge=0.0,  # edge mínimo (prob_modelo - prob_mercado) pra simular_apostas contar como aposta
    margem_under=0.0,  # margem de casa assumida ao aproximar odd/prob de Under a partir da odd de Over
                        # (ver pesos.odd_e_prob_under_aproximada) — 0.0 preserva o comportamento antigo
                        # (comprovadamente otimista); usar ~0.07 (margem real medida nesta fonte de
                        # dado, docs/retrospectiva_under_margem_2026-08-25.md) corrige a maior parte do viés.
    filtro_estilo=None,        # corte mínimo de aderencia_estilo, independente de aderencia_favoritismo.
    filtro_favoritismo=None,   # corte mínimo de aderencia_favoritismo, independente de aderencia_estilo.
                               # None em qualquer um dos dois usa filtro_aderencia (comportamento antigo,
                               # retrocompatível) — só divergem quando explicitamente setados nos params.
    limite_unilateral_por_campo=None,  # dict opcional {campo: limite}, sobrepõe limite_unilateral só
                                        # nesses campos de STAT_KEY_MAP — o corte de outlier foi calibrado
                                        # pra escala de gols (~1,4/time) e não escala sozinho pra campos com
                                        # média muito maior (escanteios ~5/time, cartões ~2,6/time); None
                                        # (default) preserva o comportamento antigo em todos os campos.
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

    corte_estilo = params["filtro_estilo"] if params["filtro_estilo"] is not None else params["filtro_aderencia"]
    corte_favoritismo = (
        params["filtro_favoritismo"] if params["filtro_favoritismo"] is not None else params["filtro_aderencia"]
    )
    validos = [
        j for j in com_pesos
        if j["aderencia_estilo"] >= corte_estilo and j["aderencia_favoritismo"] >= corte_favoritismo
    ]
    if not validos:
        return None
    pesos_lista = [j["peso_final"] for j in validos]

    limites_por_campo = params["limite_unilateral_por_campo"] or {}
    mercados = {}
    for campo in STAT_KEY_MAP:
        limite_campo = limites_por_campo.get(campo, params["limite_unilateral"])
        ind = indicador_pro_contra(
            [j[campo] for j in validos], pesos_lista, limite_campo, params["multiplicador_dp"]
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
        over15_real=(gf_real + ga_real) > 1.5, over15_pred=(gf_pred + ga_pred) > 1.5,
        over25_real=(gf_real + ga_real) > 2.5, over25_pred=(gf_pred + ga_pred) > 2.5,
        over35_real=(gf_real + ga_real) > 3.5, over35_pred=(gf_pred + ga_pred) > 3.5,
        over45_real=(gf_real + ga_real) > 4.5, over45_pred=(gf_pred + ga_pred) > 4.5,
        under15_real=(gf_real + ga_real) < 1.5, under15_pred=(gf_pred + ga_pred) < 1.5,
        under25_real=(gf_real + ga_real) < 2.5, under25_pred=(gf_pred + ga_pred) < 2.5,
        under35_real=(gf_real + ga_real) < 3.5, under35_pred=(gf_pred + ga_pred) < 3.5,
        under45_real=(gf_real + ga_real) < 4.5, under45_pred=(gf_pred + ga_pred) < 4.5,
        btts_real=(gf_real > 0 and ga_real > 0), btts_pred=(gf_pred > 0.5 and ga_pred > 0.5),
        n_jogos_validos=len(validos),
        mercados=mercados,
        **_probabilidades_e_odds(row, gf_pred, ga_pred, gf_real, ga_real, margem_under=params["margem_under"]),
    )


def _valor_odd(row, coluna):
    """Lê uma coluna de odd do CSV; retorna None se ausente/NaN/inválida
    (odd decimal tem que ser > 1) — nunca inventa odd."""
    try:
        odd = float(row[coluna])
        return odd if odd > 1 and odd == odd else None  # odd==odd descarta NaN
    except (KeyError, ValueError, TypeError):
        return None


_LINHAS_OVER = dict(over15=(1.5, "odds_ft_over15"), over25=(2.5, "odds_ft_over25"),
                     over35=(3.5, "odds_ft_over35"), over45=(4.5, "odds_ft_over45"))


def _probabilidades_favorito_dc(row, gf_pred, ga_pred, gf_real, ga_real):
    """Probabilidade de Dupla Chance do FAVORITO (vitória ou empate do lado
    com menor odd 1x2) — modelo vs. mercado, mesma lógica de vantagem real
    das outras funções.

    Favorito é definido pela odd real do jogo (menor odd entre casa/fora),
    não pelo modelo — é o "favorito de mercado" que aparece na odd.

    O CSV não traz uma odd de Dupla Chance de verdade — só as 3 odds do
    1x2. A probabilidade de mercado usa as 3 odds normalizadas (remove a
    margem de verdade, como em `probabilidade_implicita_2vias`); a ODD
    usada pra simular aposta é a combinação bruta das duas pernas
    (`1 / (implícita_favorito + implícita_empate)`, sem remover margem) —
    subestima um pouco a odd real de Dupla Chance (que costuma ter margem
    menor que a soma de duas pernas do 1x2), então o ROI simulado aqui
    tende a ser conservador, não otimista.
    """
    odd_casa = _valor_odd(row, "odds_ft_home_team_win")
    odd_empate = _valor_odd(row, "odds_ft_draw")
    odd_fora = _valor_odd(row, "odds_ft_away_team_win")
    if not (odd_casa and odd_empate and odd_fora):
        return dict(mando_favorito=None, prob_modelo_favorito_dc=None,
                    odd_favorito_dc=None, prob_mercado_favorito_dc=None, favorito_dc_real=None)

    mando_favorito = "Casa" if odd_casa <= odd_fora else "Fora"
    p_casa, p_empate, p_fora = 1 / odd_casa, 1 / odd_empate, 1 / odd_fora
    soma = p_casa + p_empate + p_fora
    if mando_favorito == "Casa":
        prob_mercado = (p_casa + p_empate) / soma
        odd_combinada = 1 / (p_casa + p_empate)
    else:
        prob_mercado = (p_fora + p_empate) / soma
        odd_combinada = 1 / (p_fora + p_empate)

    resultado_modelo = probabilidade_resultado(gf_pred, ga_pred)
    prob_modelo = (
        resultado_modelo["vitoria"] + resultado_modelo["empate"] if mando_favorito == "Casa"
        else resultado_modelo["derrota"] + resultado_modelo["empate"]
    )

    favorito_dc_real = None
    if gf_real is not None and ga_real is not None:
        favorito_dc_real = (gf_real >= ga_real) if mando_favorito == "Casa" else (ga_real >= gf_real)

    return dict(
        mando_favorito=mando_favorito, prob_modelo_favorito_dc=prob_modelo,
        odd_favorito_dc=odd_combinada, prob_mercado_favorito_dc=prob_mercado,
        favorito_dc_real=favorito_dc_real,
    )


def _probabilidades_1x2_e_dc(row, gf_pred, ga_pred, gf_real, ga_real):
    """1x2 (casa/empate/fora) e Dupla Chance de mandante/visitante — modelo
    vs. mercado. Diferente de `_probabilidades_favorito_dc` (que sempre
    olha pro lado favorito na odd), aqui `mandante_dc`/`visitante_dc` são
    sempre o mesmo lado fixo (casa ou fora), independente de quem é
    favorito.

    1x2 tem as 3 odds reais no CSV — a probabilidade de MERCADO de cada
    lado usa `probabilidades_implicitas_nvias` (remove a margem de
    verdade, normalizando os 3 lados), mais precisa que a aproximação
    bruta usada em Over/Under (que só tem 1 lado real disponível). As
    odds de Dupla Chance combinam duas pernas com a probabilidade BRUTA
    (sem remover margem, mesma convenção conservadora de
    `_probabilidades_favorito_dc`) — subestima um pouco a odd real.
    """
    odd_casa = _valor_odd(row, "odds_ft_home_team_win")
    odd_empate = _valor_odd(row, "odds_ft_draw")
    odd_fora = _valor_odd(row, "odds_ft_away_team_win")

    campos = ("casa", "empate", "fora", "mandante_dc", "visitante_dc")
    if not (odd_casa and odd_empate and odd_fora):
        vazio = {}
        for campo in campos:
            vazio[f"prob_modelo_{campo}"] = None
            vazio[f"odd_{campo}"] = None
            vazio[f"prob_mercado_{campo}"] = None
            vazio[f"{campo}_real"] = None
        return vazio

    p_casa_mercado, p_empate_mercado, p_fora_mercado = probabilidades_implicitas_nvias(odd_casa, odd_empate, odd_fora)
    p_casa_bruta = probabilidade_implicita(odd_casa)
    p_empate_bruta = probabilidade_implicita(odd_empate)
    p_fora_bruta = probabilidade_implicita(odd_fora)

    resultado_modelo = probabilidade_resultado(gf_pred, ga_pred)

    resultado = dict(
        prob_modelo_casa=resultado_modelo["vitoria"], odd_casa=odd_casa, prob_mercado_casa=p_casa_mercado,
        prob_modelo_empate=resultado_modelo["empate"], odd_empate=odd_empate, prob_mercado_empate=p_empate_mercado,
        prob_modelo_fora=resultado_modelo["derrota"], odd_fora=odd_fora, prob_mercado_fora=p_fora_mercado,
        prob_modelo_mandante_dc=resultado_modelo["vitoria"] + resultado_modelo["empate"],
        odd_mandante_dc=1 / (p_casa_bruta + p_empate_bruta),
        prob_mercado_mandante_dc=p_casa_mercado + p_empate_mercado,
        prob_modelo_visitante_dc=resultado_modelo["derrota"] + resultado_modelo["empate"],
        odd_visitante_dc=1 / (p_fora_bruta + p_empate_bruta),
        prob_mercado_visitante_dc=p_fora_mercado + p_empate_mercado,
    )

    if gf_real is not None and ga_real is not None:
        resultado["casa_real"] = gf_real > ga_real
        resultado["empate_real"] = gf_real == ga_real
        resultado["fora_real"] = ga_real > gf_real
        resultado["mandante_dc_real"] = gf_real >= ga_real
        resultado["visitante_dc_real"] = ga_real >= gf_real
    else:
        for campo in ("casa", "empate", "fora", "mandante_dc", "visitante_dc"):
            resultado[f"{campo}_real"] = None

    return resultado


def _probabilidades_e_odds(row, gf_pred, ga_pred, gf_real=None, ga_real=None, margem_under=0.0):
    """Probabilidade que o MODELO dá pros mercados de Over gols (1.5/2.5/
    3.5/4.5), BTTS e Dupla Chance do favorito, e a probabilidade IMPLÍCITA
    nas odds reais do jogo (quando disponíveis no CSV) — a comparação entre
    as duas é o que mede vantagem real (não só acerto), usada por
    `simular_apostas`/`simular_apostas_combo`.

    Over (todas as linhas): o CSV só traz a odd do lado "over", não a do
    "under" — a probabilidade implícita fica sem remover a margem da casa
    (`probabilidade_implicita`, superestima um pouco).
    Under (todas as linhas): odd/probabilidade APROXIMADAS a partir da odd
    de Over, via `odd_e_prob_under_aproximada(odd, margem_under)` — não é
    odd real de mercado. Com `margem_under=0.0` (padrão) tende a ficar
    otimista (comprovado, ver `docs/retrospectiva_under_aproximado_2026-08-25.md`);
    `margem_under` > 0 assume uma margem de casa e corrige a maior parte
    do viés (ver `docs/retrospectiva_under_margem_2026-08-25.md`).
    BTTS: o CSV traz os dois lados (`odds_btts_yes`/`odds_btts_no`), dá pra
    normalizar de verdade com `probabilidade_implicita_2vias`.
    Favorito DC: ver `_probabilidades_favorito_dc`.
    1x2 (casa/empate/fora) e Dupla Chance de mandante/visitante (lado
    fixo, não o favorito): ver `_probabilidades_1x2_e_dc`.
    """
    resultado = {}
    for nome, (linha, coluna_odd) in _LINHAS_OVER.items():
        odd = _valor_odd(row, coluna_odd)
        prob_modelo_over = probabilidade_over(gf_pred + ga_pred, linha=linha)
        resultado[f"prob_modelo_{nome}"] = prob_modelo_over
        resultado[f"odd_{nome}"] = odd
        resultado[f"prob_mercado_{nome}"] = probabilidade_implicita(odd) if odd else None

        nome_under = f"under{nome[len('over'):]}"
        prob_mercado_under, odd_under = odd_e_prob_under_aproximada(odd, margem_under) if odd else (None, None)
        resultado[f"prob_modelo_{nome_under}"] = 1 - prob_modelo_over
        resultado[f"odd_{nome_under}"] = odd_under
        resultado[f"prob_mercado_{nome_under}"] = prob_mercado_under

    prob_modelo_btts = probabilidade_btts(gf_pred, ga_pred)
    odd_btts_sim = _valor_odd(row, "odds_btts_yes")
    odd_btts_nao = _valor_odd(row, "odds_btts_no")
    prob_mercado_btts = (
        probabilidade_implicita_2vias(odd_btts_sim, odd_btts_nao)
        if odd_btts_sim and odd_btts_nao else None
    )
    resultado.update(
        prob_modelo_btts=prob_modelo_btts, odd_btts_sim=odd_btts_sim, odd_btts_nao=odd_btts_nao,
        prob_mercado_btts=prob_mercado_btts,
    )
    resultado.update(_probabilidades_favorito_dc(row, gf_pred, ga_pred, gf_real, ga_real))
    resultado.update(_probabilidades_1x2_e_dc(row, gf_pred, ga_pred, gf_real, ga_real))
    return resultado


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
    params_completos = {**PARAMS_PADRAO, **(params or {})}
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

    aposta_vazia = dict(n_apostas=0, n_vitorias=0, taxa_acerto=None, lucro_total=0.0, roi=None, edge_medio=None, apostas=[])
    if not avaliados:
        return dict(n=0, n_pulados=n_pulados, mae_gols_total=None, acerto_over25=None, acerto_btts=None,
                     mercados={}, jogos=[],
                     aposta_over25=aposta_vazia, aposta_btts=aposta_vazia, roi_over25=None, roi_btts=None)

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

    aposta_over25 = simular_apostas(avaliados, mercado="over25", limiar_edge=params_completos["limiar_edge"])
    aposta_btts = simular_apostas(avaliados, mercado="btts", limiar_edge=params_completos["limiar_edge"])

    return dict(
        n=n, n_pulados=n_pulados,
        mae_gols_total=mae_gols_total, acerto_over25=acerto_over25, acerto_btts=acerto_btts,
        mercados=mercados_agg,
        aposta_over25=aposta_over25, aposta_btts=aposta_btts,
        roi_over25=aposta_over25["roi"], roi_btts=aposta_btts["roi"],
        jogos=avaliados,
    )


def grid_search(df, grade_parametros, ordenar_por="mae_gols_total", min_apostas_roi=15, **kwargs):
    """Roda `rodar_retrospectiva` para cada combinação de
    `grade_parametros` (dict {nome: [valores]}) e retorna
    `[(params, relatorio), ...]` ordenado do MELHOR pro PIOR segundo
    `ordenar_por` (combinações sem jogos avaliados ficam no fim).

    `ordenar_por`:
    - `"mae_gols_total"` (menor é melhor, default) — erro do placar exato.
    - `"acerto_over25"`/`"acerto_btts"` (maior é melhor) — taxa de acerto.
    - `"roi_over25"`/`"roi_btts"` (maior é melhor) — **vantagem real**
      (ROI simulado contra odd de mercado, via `simular_apostas`; inclua
      `limiar_edge` na grade pra também variar o edge mínimo exigido).
      Acerto e ROI podem apontar em direções OPOSTAS — ver
      `docs/retrospectiva_roi_2026-08-24.md`. Combinações com menos de
      `min_apostas_roi` apostas feitas (amostra pequena demais pro ROI
      significar algo) ficam no fim, mesmo com ROI alto — evita que um
      resultado de sorte com poucas apostas vença por acaso.

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
    elif ordenar_por in ("roi_over25", "roi_btts"):
        campo_aposta = "aposta_over25" if ordenar_por == "roi_over25" else "aposta_btts"

        def chave(par):
            roi = par[1][ordenar_por]
            n_apostas = par[1][campo_aposta]["n_apostas"]
            amostra_pequena_demais = roi is None or n_apostas < min_apostas_roi
            return (amostra_pequena_demais, -(roi or 0))

        resultados.sort(key=chave)
    else:
        raise ValueError(f"ordenar_por inválido: {ordenar_por!r}")
    return resultados


_MERCADOS_SIMULAVEIS = {
    **{
        nome: dict(prob_modelo=f"prob_modelo_{nome}", prob_mercado=f"prob_mercado_{nome}",
                   odd=f"odd_{nome}", real=f"{nome}_real")
        for nome in _LINHAS_OVER
    },
    **{
        f"under{nome[len('over'):]}": dict(
            prob_modelo=f"prob_modelo_under{nome[len('over'):]}",
            prob_mercado=f"prob_mercado_under{nome[len('over'):]}",
            odd=f"odd_under{nome[len('over'):]}", real=f"under{nome[len('over'):]}_real",
        )
        for nome in _LINHAS_OVER
    },
    "btts": dict(prob_modelo="prob_modelo_btts", prob_mercado="prob_mercado_btts",
                 odd="odd_btts_sim", real="btts_real"),
    "favorito_dc": dict(prob_modelo="prob_modelo_favorito_dc", prob_mercado="prob_mercado_favorito_dc",
                         odd="odd_favorito_dc", real="favorito_dc_real"),
    **{
        nome: dict(prob_modelo=f"prob_modelo_{nome}", prob_mercado=f"prob_mercado_{nome}",
                   odd=f"odd_{nome}", real=f"{nome}_real")
        for nome in ("casa", "empate", "fora", "mandante_dc", "visitante_dc")
    },
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

    `mercado`: `"over15"`/`"over25"`/`"over35"`/`"over45"` (odd real do
    lado "over", sem remover margem — só temos a odd de um lado no CSV),
    `"under15"`/`"under25"`/`"under35"`/`"under45"` (odd APROXIMADA a
    partir da odd de Over — ver `pesos.odd_e_prob_under_aproximada`, não é
    odd real de mercado, tende a ficar um pouco otimista), ou `"btts"`
    (usa BTTS Sim, com margem removida via odds dos dois lados).

    IMPORTANTE sobre Under: o CSV não traz a odd real desse lado — a odd
    usada aqui é derivada da odd de Over (complemento bruto da
    probabilidade implícita), não uma odd de mercado de verdade. Trate
    qualquer resultado desses mercados com mais cautela ainda do que o
    normal. Jogos sem a odd necessária são pulados (não inventa odd).

    Retorna dict com `n_apostas`, `n_vitorias`, `taxa_acerto` (das apostas
    FEITAS, não de todos os jogos avaliados), `lucro_total`, `roi`
    (lucro/total apostado), `edge_medio` (das apostas feitas).
    """
    if mercado not in _MERCADOS_SIMULAVEIS:
        raise ValueError(f"mercado inválido: {mercado!r} (use {sorted(_MERCADOS_SIMULAVEIS)!r})")
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


def simular_apostas_combo(jogos, pernas, limiar_edge=0.0, stake=1.0):
    """Simula uma aposta MÚLTIPLA (combinada) de 2+ mercados no mesmo jogo —
    ex.: Over 2.5 + Dupla Chance do favorito, do jeito que uma "múltipla" de
    boletim de aposta normal funciona: odd combinada = produto das odds de
    cada perna, e a aposta só ganha se TODAS as pernas baterem.

    `pernas`: lista de nomes de mercado (chaves de `_MERCADOS_SIMULAVEIS`),
    ex. `["over25", "favorito_dc"]`.

    A probabilidade do MODELO pra combinação é o produto das probabilidades
    de cada perna (assume independência entre elas — simplificação: pernas
    do mesmo jogo têm alguma correlação real, ex. jogo aberto favorece Over
    E o favorito ao mesmo tempo; não modelada aqui). A probabilidade de
    MERCADO usa o mesmo produto das probabilidades implícitas de cada
    perna — mesma simplificação dos dois lados, pra manter a comparação de
    edge consistente.

    Jogos sem odd/probabilidade em QUALQUER uma das pernas são pulados (não
    inventa dado faltante).
    """
    if len(pernas) < 2:
        raise ValueError("simular_apostas_combo precisa de pelo menos 2 pernas")
    for perna in pernas:
        if perna not in _MERCADOS_SIMULAVEIS:
            raise ValueError(f"mercado inválido: {perna!r} (use {sorted(_MERCADOS_SIMULAVEIS)!r})")

    apostas = []
    for jogo in jogos:
        valores = []
        for perna in pernas:
            campos = _MERCADOS_SIMULAVEIS[perna]
            prob_modelo = jogo.get(campos["prob_modelo"])
            prob_mercado = jogo.get(campos["prob_mercado"])
            odd = jogo.get(campos["odd"])
            real = jogo.get(campos["real"])
            if prob_modelo is None or prob_mercado is None or odd is None or real is None:
                valores = None
                break
            valores.append((prob_modelo, prob_mercado, odd, bool(real)))
        if valores is None:
            continue

        prob_modelo_combo = math.prod(v[0] for v in valores)
        prob_mercado_combo = math.prod(v[1] for v in valores)
        odd_combo = math.prod(v[2] for v in valores)
        venceu = all(v[3] for v in valores)

        edge = prob_modelo_combo - prob_mercado_combo
        if edge < limiar_edge:
            continue
        lucro = stake * (odd_combo - 1) if venceu else -stake
        apostas.append(dict(jogo=jogo["jogo"], data=jogo["data"], odd=odd_combo, edge=edge,
                             venceu=venceu, lucro=lucro))

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
