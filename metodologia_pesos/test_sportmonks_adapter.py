import pytest

from sportmonks_adapter import flat_para_linha


def _flat_base(**overrides):
    base = dict(
        fixture_id=1, date="2026-08-29 21:30:00", home_team="Time A", away_team="Time B",
        home_goals=2, away_goals=1, home_goals_ht=1, away_goals_ht=0,
        corners_home=6, corners_away=4, shots_home=12, shots_away=9,
        shots_on_target_home=5, shots_on_target_away=3,
        possession_home=55, possession_away=45, fouls_home=10, fouls_away=12,
        yellowcards_home=2, yellowcards_away=3, redcards_home=0, redcards_away=0,
        referee_id=999, season="2026",
        odds={
            "1": [{"bookmaker_id": 1, "label": "Home", "total": None, "value": "1.80"},
                  {"bookmaker_id": 1, "label": "Draw", "total": None, "value": "3.50"},
                  {"bookmaker_id": 1, "label": "Away", "total": None, "value": "4.50"}],
            "80": [{"bookmaker_id": 1, "label": "Over", "total": "2.5", "value": "2.10"},
                   {"bookmaker_id": 1, "label": "Under", "total": "2.5", "value": "1.70"}],
            "14": [{"bookmaker_id": 1, "label": "Yes", "total": None, "value": "1.95"},
                   {"bookmaker_id": 1, "label": "No", "total": None, "value": "1.85"}],
            "255": [{"bookmaker_id": 1, "label": "Over", "total": "9.5", "value": "1.90"}],
        },
    )
    base.update(overrides)
    return base


def test_flat_para_linha_jogo_finalizado_usa_dado_real():
    linha = flat_para_linha(_flat_base())
    assert linha["home_team_name"] == "Time A"
    assert linha["away_team_name"] == "Time B"
    assert linha["home_team_goal_count"] == 2
    assert linha["away_team_goal_count"] == 1
    assert linha["home_team_corner_count"] == 6
    assert linha["away_team_corner_count"] == 4
    assert linha["home_team_yellow_cards"] == 2
    assert linha["home_team_possession"] == 55
    assert linha["status"] == "complete"


def test_flat_para_linha_usa_gols_reais_como_proxy_de_xg():
    linha = flat_para_linha(_flat_base(home_goals=3, away_goals=0))
    assert linha["team_a_xg"] == 3.0
    assert linha["team_b_xg"] == 0.0


def test_flat_para_linha_odds_1x2_e_gols_e_btts():
    linha = flat_para_linha(_flat_base())
    assert linha["odds_ft_home_team_win"] == pytest.approx(1.80)
    assert linha["odds_ft_draw"] == pytest.approx(3.50)
    assert linha["odds_ft_away_team_win"] == pytest.approx(4.50)
    assert linha["odds_ft_over25"] == pytest.approx(2.10)
    assert linha["odds_btts_yes"] == pytest.approx(1.95)
    assert linha["odds_btts_no"] == pytest.approx(1.85)


def test_flat_para_linha_stats_faltando_aciona_sentinela_de_dado_ausente():
    linha = flat_para_linha(_flat_base(shots_home=None))
    # falta 1 campo de detalhe -> TODO o jogo vira "stats ausentes"
    assert linha["home_team_corner_count"] == -1
    assert linha["away_team_corner_count"] == -1


def test_flat_para_linha_jogo_futuro_usa_placeholder_0x0_e_sentinela():
    flat_futuro = _flat_base(home_goals=None, away_goals=None, home_goals_ht=None, away_goals_ht=None)
    linha = flat_para_linha(flat_futuro)
    assert linha["home_team_goal_count"] == 0
    assert linha["away_team_goal_count"] == 0
    assert linha["home_team_corner_count"] == -1  # jogo futuro sempre aciona o sentinela
    assert linha["away_team_corner_count"] == -1
    # mas a odd e os times continuam reais - é isso que prever_jogo usa de verdade
    assert linha["home_team_name"] == "Time A"
    assert linha["odds_ft_over25"] == pytest.approx(2.10)


def test_flat_para_linha_sem_odd_retorna_none_na_coluna():
    linha = flat_para_linha(_flat_base(odds={}))
    assert linha["odds_ft_home_team_win"] is None
    assert linha["odds_btts_yes"] is None
