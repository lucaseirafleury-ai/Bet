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
# Recalibrado (pesquisa_gols/validar_over_under.py) contra os 3.001 jogos já
# cacheados em pesquisa_gols/dados/.checkpoint_*.json — bem mais dado que a
# calibração anterior (569 jogos). Testamos ~19 métricas de ritmo (chutes,
# ataques, cruzamentos, etc.) por liga, com split cronológico 70/30 e teste
# pareado POR JOGO (não por checkpoint, pra não repetir o erro de
# pseudo-replicação achado no backtest.py de xG_proxy). Depois de corrigir
# por Benjamini-Hochberg (5 ligas testadas), NENHUMA métrica sobreviveu em
# NENHUMA liga — inclusive as métricas que estavam calibradas antes
# (shots_total pra Allsvenskan, attacks pra 1. Division) nem eram mais as
# "melhores" nesta base maior, sinal de que a calibração original estava
# ajustando ruído, não um efeito real. Resultado bate com a pesquisa de gols
# (pesquisa_gols/README.md): nenhuma estatística de ritmo prevê gols de forma
# confiável, nem olhando pro jogo todo (Over/Under) nem por time.
#
# Por isso as 5 ligas usam "somente minuto" agora (coeficiente de ritmo = 0,
# só o intercepto por minuto) — mais simples e sem a falsa precisão de um
# coeficiente que não se sustentou fora da amostra.
#
# xG_restante_total = EXP(intercepto_do_minuto[liga] + coef[liga] × ritmo_da_métrica_da_liga)
MODELOS_CALIBRADOS_POR_LIGA = {
    573: {  # Allsvenskan — recalibrado em 616 jogos
        "liga": "Allsvenskan", "metrica": None, "coef": 0.0,
        "interceptos": {15: 0.937915, 30: 0.767022, 45: 0.531492, 60: 0.196361, 75: -0.23628},
    },
    579: {  # Superettan — recalibrado em 631 jogos
        "liga": "Superettan", "metrica": None, "coef": 0.0,
        "interceptos": {15: 0.891998, 30: 0.739267, 45: 0.514021, 60: 0.204735, 75: -0.166763},
    },
    405: {  # A Lyga — recalibrado em 481 jogos
        "liga": "A Lyga", "metrica": None, "coef": 0.0,
        "interceptos": {15: 0.814448, 30: 0.671779, 45: 0.435318, 60: 0.152639, 75: -0.229506},
    },
    408: {  # 1. Lyga — recalibrado em 644 jogos
        "liga": "1. Lyga", "metrica": None, "coef": 0.0,
        "interceptos": {15: 0.946364, 30: 0.78959, 45: 0.57068, 60: 0.298141, 75: -0.089563},
    },
    447: {  # 1. Division (Noruega) — recalibrado em 629 jogos
        "liga": "1. Division", "metrica": None, "coef": 0.0,
        "interceptos": {15: 1.08137, 30: 0.927129, 45: 0.702717, 60: 0.402255, 75: -0.04591},
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
