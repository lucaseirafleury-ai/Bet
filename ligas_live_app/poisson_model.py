"""
Modelo de Poisson simples para estimar o placar mais provável (placar modal).
lambda_home / lambda_away = médias esperadas de gols de cada time no confronto.
"""
import math
import config


def poisson_pmf(k, lam):
    if lam <= 0:
        lam = 0.05  # evita log(0) / divisão por zero em times sem histórico de gols
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def expected_goals(perfil_casa, perfil_fora):
    """
    Combina gols marcados pelo mandante com gols sofridos pelo visitante (e vice-versa)
    para estimar as médias esperadas de gols no confronto.
    """
    lambda_home = (perfil_casa["gols_marcados_media"] + perfil_fora["gols_sofridos_media"]) / 2
    lambda_away = (perfil_fora["gols_marcados_media"] + perfil_casa["gols_sofridos_media"]) / 2
    return round(lambda_home, 2), round(lambda_away, 2)


def placar_modal(lambda_home, lambda_away):
    """Varre a grade de placares e retorna o mais provável + sua probabilidade."""
    melhor_placar = (0, 0)
    melhor_prob = -1
    for h in range(config.MAX_GOLS_GRADE + 1):
        for a in range(config.MAX_GOLS_GRADE + 1):
            p = poisson_pmf(h, lambda_home) * poisson_pmf(a, lambda_away)
            if p > melhor_prob:
                melhor_prob = p
                melhor_placar = (h, a)
    return melhor_placar, round(melhor_prob * 100, 1)
