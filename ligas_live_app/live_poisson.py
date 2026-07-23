"""
Extensão do modelo de Poisson para uso AO VIVO.

Ideia: dado o placar atual e o minuto do jogo, reduz o "tempo restante" (90 - minuto)
e recalcula a distribuição de gols futuros a partir dos lambdas originais (pré-live).
Soma isso ao placar atual para obter as probabilidades de:
  - vitória casa / empate / vitória fora
  - Over/Under 2.5 gols (no total final da partida)
  - Ambas marcam (BTTS)
"""
from poisson_model import poisson_pmf
import math

GRADE_GOLS_RESTANTES = 6  # gols adicionais possíveis por time, a partir de agora

# ── Limites de segurança do ajuste dinâmico (evita que ruído distorça demais o modelo) ──
FATOR_MINIMO = 0.5   # lambda nunca cai abaixo de 50% do esperado pré-live
FATOR_MAXIMO = 1.8   # lambda nunca sobe acima de 180% do esperado pré-live
PESO_XG = 0.5
PESO_PRESSAO = 0.3

# ── Modelo calibrado de gols TOTAIS restantes (Over/Under), POR LIGA ────────
# Poisson GLM validado fora da amostra, cronologicamente (569 jogos, 2.845
# snapshots, 5 ligas — treino/teste sem vazamento entre snapshots do mesmo jogo).
#
# IMPORTANTE: nem toda liga tem uma métrica incremental que ajuda de verdade.
# A Lyga e Superettan não tiveram nenhuma métrica testada que melhorasse o
# modelo de forma consistente — pra essas duas, o mais seguro é usar "somente
# minuto" (coeficiente de ritmo = 0). Aplicar o coeficiente de uma liga em
# outra reduziria a precisão, por isso os valores são mantidos separados.
#
# xG_restante_total = EXP(intercepto_do_minuto[liga] + coef[liga] × ritmo_da_métrica_da_liga)
MODELOS_CALIBRADOS_POR_LIGA = {
    579: {  # Superettan
        "liga": "Superettan", "metrica": None, "coef": 0.0,
        "interceptos": {15: 0.9902, 30: 0.8183, 45: 0.5644, 60: 0.1754, 75: -0.3101},
    },
    573: {  # Allsvenskan
        "liga": "Allsvenskan", "metrica": "shots_total_rate15", "coef": 0.094703,
        "interceptos": {15: 0.654329, 30: 0.463077, 45: 0.164337, 60: -0.244564, 75: -0.883578},
    },
    405: {  # A Lyga
        "liga": "A Lyga", "metrica": None, "coef": 0.0,
        "interceptos": {15: 0.8255, 30: 0.6596, 45: 0.3405, 60: 0.0279, 75: -0.5203},
    },
    408: {  # 1. Lyga
        "liga": "1. Lyga", "metrica": "shots_off_target_rate15", "coef": 0.10081,
        "interceptos": {15: 0.7161, 30: 0.5324, 45: 0.3192, 60: -0.0695, 75: -0.6755},
    },
    447: {  # 1. Division (Noruega)
        "liga": "1. Division", "metrica": "attacks_rate15", "coef": 0.012355,
        "interceptos": {15: 0.7954, 30: 0.6461, 45: 0.3954, 60: 0.0034, 75: -0.5198},
    },
}


def _intercepto_interpolado(minuto, interceptos_liga):
    """Interpola/extrapola o intercepto calibrado para minutos fora dos checkpoints 15/30/45/60/75."""
    checkpoints = sorted(interceptos_liga.keys())
    if minuto <= checkpoints[0]:
        return interceptos_liga[checkpoints[0]]
    if minuto >= checkpoints[-1]:
        m1, m2 = checkpoints[-2], checkpoints[-1]
        v1, v2 = interceptos_liga[m1], interceptos_liga[m2]
        inclinacao = (v2 - v1) / (m2 - m1)
        return v2 + inclinacao * (minuto - m2)
    for i in range(len(checkpoints) - 1):
        m1, m2 = checkpoints[i], checkpoints[i + 1]
        if m1 <= minuto <= m2:
            v1, v2 = interceptos_liga[m1], interceptos_liga[m2]
            fracao = (minuto - m1) / (m2 - m1)
            return v1 + fracao * (v2 - v1)
    return interceptos_liga[checkpoints[-1]]


def xg_restante_total_calibrado(valor_metrica_acumulada, minuto, league_id):
    """
    Gols totais (dos dois times somados) esperados no RESTO da partida,
    usando o modelo calibrado específico da liga (ver MODELOS_CALIBRADOS_POR_LIGA).
    Ligas sem métrica incremental validada (coef=0) usam só o intercepto por minuto —
    equivalente ao modelo "somente minuto", que foi o mais seguro pra elas nos testes.
    """
    modelo = MODELOS_CALIBRADOS_POR_LIGA.get(league_id)
    if modelo is None:
        return None  # liga sem calibração — quem chama deve cair no fallback heurístico

    if minuto <= 0:
        minuto = 1
    ritmo_15min = (valor_metrica_acumulada / minuto) * 15
    intercepto = _intercepto_interpolado(minuto, modelo["interceptos"])
    return math.exp(intercepto + modelo["coef"] * ritmo_15min)


def probabilidades_over_under_calibrado(valor_metrica_acumulada, minuto, gols_atuais_total, league_id, linha=2.5):
    """
    Probabilidade de Over/Under usando o modelo calibrado específico da liga.
    Retorna None se a liga não tiver modelo calibrado (quem chama cai no fallback).
    """
    xg_rest = xg_restante_total_calibrado(valor_metrica_acumulada, minuto, league_id)
    if xg_rest is None:
        return None

    p_over = p_under = 0.0
    grade = 10

    for n in range(grade + 1):
        p = poisson_pmf(n, xg_rest)
        total_final = gols_atuais_total + n
        if total_final > linha:
            p_over += p
        else:
            p_under += p

    modelo = MODELOS_CALIBRADOS_POR_LIGA[league_id]
    return {
        "prob_over25_calibrado": round(p_over, 4),
        "prob_under25_calibrado": round(p_under, 4),
        "xg_restante_total_calibrado": round(xg_rest, 3),
        "metrica_usada": modelo["metrica"] or "somente_minuto",
    }


def delta_fracional(valor_atual, valor_esperado_90min, minuto):
    """
    Quanto o valor observado até agora desvia (em fração) do que era esperado
    para este ponto do jogo, prorrateando a média pré-live pelo tempo já jogado.
    """
    if valor_esperado_90min <= 0 or minuto <= 0:
        return 0.0
    esperado_prorrateado = valor_esperado_90min * (minuto / 90)
    if esperado_prorrateado <= 0:
        return 0.0
    return (valor_atual - esperado_prorrateado) / esperado_prorrateado


def fator_ajuste_lambda(delta_xg, delta_pressao):
    """
    Combina o desvio de xG_proxy e de pressão num único multiplicador para o
    lambda de gols restantes do time. 1.0 = sem ajuste (comportamento igual ao
    esperado pré-live). Acima de 1.0 = time performando acima do esperado.
    """
    bruto = 1 + (PESO_XG * delta_xg) + (PESO_PRESSAO * delta_pressao)
    return max(FATOR_MINIMO, min(FATOR_MAXIMO, bruto))


def probabilidades_ao_vivo(lambda_home_original, lambda_away_original, minuto, gols_home, gols_away,
                            ajuste_home=1.0, ajuste_away=1.0):
    minutos_restantes = max(90 - minuto, 1)
    fator_tempo = minutos_restantes / 90

    lam_h_rest = lambda_home_original * fator_tempo * ajuste_home
    lam_a_rest = lambda_away_original * fator_tempo * ajuste_away

    p_casa = p_empate = p_fora = 0.0
    p_over25 = p_under25 = 0.0
    p_btts_sim = p_btts_nao = 0.0

    for dh in range(GRADE_GOLS_RESTANTES + 1):
        for da in range(GRADE_GOLS_RESTANTES + 1):
            p = poisson_pmf(dh, lam_h_rest) * poisson_pmf(da, lam_a_rest)
            final_h = gols_home + dh
            final_a = gols_away + da

            if final_h > final_a:
                p_casa += p
            elif final_h == final_a:
                p_empate += p
            else:
                p_fora += p

            total = final_h + final_a
            if total > 2.5:
                p_over25 += p
            else:
                p_under25 += p

            if final_h >= 1 and final_a >= 1:
                p_btts_sim += p
            else:
                p_btts_nao += p

    return {
        "prob_casa": round(p_casa, 4),
        "prob_empate": round(p_empate, 4),
        "prob_fora": round(p_fora, 4),
        "prob_over25": round(p_over25, 4),
        "prob_under25": round(p_under25, 4),
        "prob_btts_sim": round(p_btts_sim, 4),
        "prob_btts_nao": round(p_btts_nao, 4),
    }


def valor_esperado(probabilidade, odd):
    """
    probabilidade: 0-1 (nossa estimativa)
    odd: decimal (ex: 2.35)
    Retorna o EV em fração (0.08 = 8% de valor esperado positivo).
    """
    if odd is None or odd <= 1:
        return None
    return round((probabilidade * odd) - 1, 4)


def probabilidade_escanteios(lambda_corners_home, lambda_corners_away, minuto,
                              escanteios_atuais_home, escanteios_atuais_away, linha):
    """
    Mesmo mecanismo do modelo de gols, aplicado a escanteios.

    ATENÇÃO — confiança menor que o modelo de gols: escanteios reagem muito ao
    estado do placar (time perdendo ataca mais tarde no jogo), efeito que este
    modelo NÃO captura. Tratar como Referência Analítica até calibrar com jogos
    reais, não como Edge Real.
    """
    minutos_restantes = max(90 - minuto, 1)
    fator = minutos_restantes / 90

    lam_h_rest = lambda_corners_home * fator
    lam_a_rest = lambda_corners_away * fator

    p_over = p_under = 0.0
    grade = 12  # escanteios adicionais possíveis por time, a partir de agora

    for dh in range(grade + 1):
        for da in range(grade + 1):
            p = poisson_pmf(dh, lam_h_rest) * poisson_pmf(da, lam_a_rest)
            total = escanteios_atuais_home + escanteios_atuais_away + dh + da
            if total > linha:
                p_over += p
            else:
                p_under += p

    return {"prob_over_escanteios": round(p_over, 4), "prob_under_escanteios": round(p_under, 4)}
