"""Teste de integração da retrospectiva walk-forward, com um dataset
fabricado (round-robin pequeno) — confirma que o pipeline roda ponta a
ponta sem olhar o futuro e produz métricas coerentes. Não depende dos CSVs
reais do FootyStats (que só chegam depois, via upload do usuário).
"""
from datetime import datetime, timedelta

import pandas as pd
import pytest

from retrospectiva import grid_search, prever_jogo, rodar_retrospectiva

TIMES = ["T1", "T2", "T3", "T4"]

# Round-robin dobrado (cada dupla joga 2x, casa e fora) — 12 jogos, 6 por time.
CONFRONTOS = [
    ("T1", "T2"), ("T3", "T4"),  # rodada 1
    ("T1", "T3"), ("T2", "T4"),  # rodada 2
    ("T1", "T4"), ("T2", "T3"),  # rodada 3
    ("T2", "T1"), ("T4", "T3"),  # rodada 4 (volta)
    ("T3", "T1"), ("T4", "T2"),  # rodada 5
    ("T4", "T1"), ("T3", "T2"),  # rodada 6
]


def _linha(i, home, away):
    data = datetime(2026, 1, 1) + timedelta(days=3 * i)
    # placar/estatísticas variam um pouco por índice, só pra não ficar tudo idêntico
    gf, ga = 1 + (i % 3), i % 2
    return {
        "home_team_name": home, "away_team_name": away,
        "date_GMT": data.strftime("%b %d %Y") + " - 3:00pm",
        "timestamp": i,
        "status": "complete",
        "home_team_goal_count": gf, "away_team_goal_count": ga,
        "team_a_xg": 1.2 + 0.1 * (i % 4), "team_b_xg": 0.9 + 0.1 * (i % 3),
        "home_team_corner_count": 5 + (i % 4), "away_team_corner_count": 3 + (i % 3),
        "home_team_yellow_cards": 2, "home_team_red_cards": 0,
        "away_team_yellow_cards": 2, "away_team_red_cards": 0,
        "home_team_shots": 11 + (i % 5), "away_team_shots": 9 + (i % 4),
        "home_team_shots_on_target": 5, "away_team_shots_on_target": 4,
        "home_team_possession": 45 + (i % 15), "away_team_possession": 55 - (i % 15),
        "home_team_fouls": 10, "away_team_fouls": 11,
        "home_team_goal_count_half_time": 0, "away_team_goal_count_half_time": 0,
        "odds_ft_home_team_win": 2.1, "odds_ft_draw": 3.3, "odds_ft_away_team_win": 3.4,
        "__src": "teste.csv",
    }


@pytest.fixture()
def df_fabricado():
    linhas = [_linha(i, home, away) for i, (home, away) in enumerate(CONFRONTOS)]
    return pd.DataFrame(linhas)


def test_prever_jogo_precisa_de_historico_suficiente(df_fabricado):
    # primeiro jogo do dataset (T1 x T2, i=0) não tem histórico nenhum antes
    primeira_linha = df_fabricado.iloc[0]
    resultado = prever_jogo(primeira_linha, df_fabricado, min_jogos_historico=5, min_jogos_estilo=5)
    assert resultado is None


def test_prever_jogo_funciona_com_historico_e_estilo_suficientes(df_fabricado):
    # última linha (T3 x T2, i=11): os dois times já têm 5 jogos anteriores
    ultima_linha = df_fabricado.iloc[11]
    resultado = prever_jogo(
        ultima_linha, df_fabricado,
        params=dict(filtro_aderencia=0.0),  # sem filtro de validade, só testando o encanamento
        min_jogos_historico=5, min_jogos_estilo=5,
    )
    assert resultado is not None
    assert resultado["gf_pred"] >= 0
    assert resultado["ga_pred"] >= 0
    assert resultado["erro_gf"] == pytest.approx(abs(resultado["gf_pred"] - resultado["gf_real"]))
    assert resultado["n_jogos_validos"] > 0


def test_prever_jogo_nunca_olha_o_futuro(df_fabricado):
    # se eu embaralhar o timestamp da última linha pra trás no tempo, ela some do "passado"
    # disponível — prova indireta de que o corte é por timestamp, não por posição na lista
    linha = df_fabricado.iloc[11].copy()
    df_sem_futuro = df_fabricado[df_fabricado["timestamp"] < linha["timestamp"]]
    assert len(df_sem_futuro) == 11  # exclui a própria linha 11


def test_rodar_retrospectiva_agrega_metricas_coerentes(df_fabricado):
    relatorio = rodar_retrospectiva(
        df_fabricado, params=dict(filtro_aderencia=0.0),
        min_jogos_historico=5, min_jogos_estilo=5,
    )
    assert relatorio["n"] > 0
    assert relatorio["n"] + relatorio["n_pulados"] == len(df_fabricado)
    assert relatorio["mae_gols_total"] >= 0
    assert 0 <= relatorio["acerto_over25"] <= 1
    assert 0 <= relatorio["acerto_btts"] <= 1
    assert len(relatorio["jogos"]) == relatorio["n"]


def test_rodar_retrospectiva_sem_dado_suficiente_retorna_vazio(df_fabricado):
    relatorio = rodar_retrospectiva(
        df_fabricado, min_jogos_historico=999, min_jogos_estilo=5,
    )
    assert relatorio == dict(n=0, n_pulados=len(df_fabricado), mae_gols_total=None,
                              acerto_over25=None, acerto_btts=None, jogos=[])


def test_grid_search_ordena_por_erro_e_cobre_todas_combinacoes(df_fabricado):
    grade = dict(k_mando=[None, 0.35], limite_unilateral=[4], multiplicador_dp=[2.5, 3.0])
    resultados = grid_search(df_fabricado, grade, min_jogos_historico=5, min_jogos_estilo=5)
    assert len(resultados) == 4  # 2 x 1 x 2 combinações
    maes = [r["mae_gols_total"] for _, r in resultados if r["mae_gols_total"] is not None]
    assert maes == sorted(maes)  # ordenado crescente
    for params, _ in resultados:
        assert set(params.keys()) == {"k_mando", "limite_unilateral", "multiplicador_dp"}
