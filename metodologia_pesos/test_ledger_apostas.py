import pytest

from ledger_apostas import (
    calcular_resumo,
    recalcular_pendentes,
    registrar_novas_sugestoes,
    resolver_pendentes,
)


def _sugestao(**overrides):
    base = dict(
        fixture_id=1, criterio="BTTS", stake="normal", liga="Série A", liga_chave="seriea",
        jogo="Time A x Time B", data="2026-08-30 21:30:00", lado="btts",
        odd=1.8, edge=0.07, linha_aposta=None,
    )
    base.update(overrides)
    return base


def _row(home_gols=1, away_gols=1, home_ya=2, home_ra=0, away_ya=2, away_ra=0):
    return dict(
        home_team_goal_count=home_gols, away_team_goal_count=away_gols,
        home_team_yellow_cards=home_ya, home_team_red_cards=home_ra,
        away_team_yellow_cards=away_ya, away_team_red_cards=away_ra,
    )


def test_registrar_novas_sugestoes_adiciona_como_pendente():
    ledger = registrar_novas_sugestoes([], [_sugestao()], data_registro="2026-08-27")
    assert len(ledger) == 1
    assert ledger[0]["resultado"] == "pendente"
    assert ledger[0]["lucro"] is None
    assert ledger[0]["fixture_id"] == 1


def test_registrar_novas_sugestoes_nao_duplica_mesma_fixture_e_criterio():
    ledger = registrar_novas_sugestoes([], [_sugestao()], data_registro="2026-08-27")
    ledger = registrar_novas_sugestoes(ledger, [_sugestao()], data_registro="2026-08-28")
    assert len(ledger) == 1


def test_registrar_novas_sugestoes_criterios_diferentes_mesmo_jogo_sao_entradas_separadas():
    ledger = registrar_novas_sugestoes([], [_sugestao(criterio="BTTS"), _sugestao(criterio="Over 2.5", lado="over25")], data_registro="2026-08-27")
    assert len(ledger) == 2


def test_registrar_novas_sugestoes_ignora_sem_fixture_id():
    ledger = registrar_novas_sugestoes([], [_sugestao(fixture_id=None)], data_registro="2026-08-27")
    assert ledger == []


def test_recalcular_pendentes_corrige_entrada_com_valor_errado():
    ledger = registrar_novas_sugestoes(
        [], [_sugestao(criterio="Cartões+Árbitro", lado="Under 4.5 cartões", linha_aposta=4.5, odd=1.8, edge=0.199)],
        data_registro="2026-08-27",
    )
    sugestoes_frescas = [_sugestao(criterio="Cartões+Árbitro", lado="Under 3.5 cartões", linha_aposta=3.5, odd=1.83, edge=0.031)]
    ledger, alteracoes = recalcular_pendentes(ledger, sugestoes_frescas)

    assert ledger[0]["lado"] == "Under 3.5 cartões"
    assert ledger[0]["linha_aposta"] == 3.5
    assert ledger[0]["odd"] == 1.83
    assert ledger[0]["edge"] == 0.031
    assert len(alteracoes) == 1
    assert alteracoes[0]["antes"]["lado"] == "Under 4.5 cartões"
    assert alteracoes[0]["depois"]["lado"] == "Under 3.5 cartões"


def test_recalcular_pendentes_nao_mexe_no_que_nao_mudou():
    ledger = registrar_novas_sugestoes([], [_sugestao()], data_registro="2026-08-27")
    ledger, alteracoes = recalcular_pendentes(ledger, [_sugestao()])
    assert alteracoes == []
    assert ledger[0]["odd"] == 1.8


def test_recalcular_pendentes_ignora_entrada_ja_resolvida():
    ledger = registrar_novas_sugestoes([], [_sugestao()], data_registro="2026-08-27")
    ledger[0]["resultado"] = "green"
    ledger[0]["lucro"] = 0.8
    sugestoes_frescas = [_sugestao(odd=2.5, edge=0.5)]
    ledger, alteracoes = recalcular_pendentes(ledger, sugestoes_frescas)
    assert alteracoes == []
    assert ledger[0]["odd"] == 1.8  # não mudou - já resolvida, imutável


def test_recalcular_pendentes_sem_sugestao_fresca_correspondente_mantem_entrada():
    # jogo já começou (não aparece mais em puxar_fixtures_futuros) - fica como estava
    ledger = registrar_novas_sugestoes([], [_sugestao()], data_registro="2026-08-27")
    ledger, alteracoes = recalcular_pendentes(ledger, [])
    assert alteracoes == []
    assert ledger[0]["odd"] == 1.8


def test_resolver_pendentes_btts_green():
    import pandas as pd
    ledger = registrar_novas_sugestoes([], [_sugestao(odd=1.8)], data_registro="2026-08-27")
    df = pd.DataFrame([{"_fixture_id": 1, **_row(home_gols=2, away_gols=1)}])
    ledger = resolver_pendentes(ledger, {"seriea": df})
    assert ledger[0]["resultado"] == "green"
    assert ledger[0]["lucro"] == pytest.approx(0.8)  # stake 1.0 * (1.8-1)


def test_resolver_pendentes_btts_red():
    import pandas as pd
    ledger = registrar_novas_sugestoes([], [_sugestao(odd=1.8)], data_registro="2026-08-27")
    df = pd.DataFrame([{"_fixture_id": 1, **_row(home_gols=0, away_gols=2)}])
    ledger = resolver_pendentes(ledger, {"seriea": df})
    assert ledger[0]["resultado"] == "red"
    assert ledger[0]["lucro"] == pytest.approx(-1.0)


def test_resolver_pendentes_over25():
    import pandas as pd
    ledger = registrar_novas_sugestoes([], [_sugestao(criterio="Over 2.5", lado="over25", odd=2.0)], data_registro="2026-08-27")
    df_venceu = pd.DataFrame([{"_fixture_id": 1, **_row(home_gols=2, away_gols=1)}])  # 3 gols
    ledger_v = resolver_pendentes([dict(ledger[0])], {"seriea": df_venceu})
    assert ledger_v[0]["resultado"] == "green"
    assert ledger_v[0]["lucro"] == pytest.approx(0.5)  # stake 0.5 * (2.0-1)

    df_perdeu = pd.DataFrame([{"_fixture_id": 1, **_row(home_gols=1, away_gols=1)}])  # 2 gols
    ledger_p = resolver_pendentes([dict(ledger[0])], {"seriea": df_perdeu})
    assert ledger_p[0]["resultado"] == "red"
    assert ledger_p[0]["lucro"] == pytest.approx(-0.5)


def test_resolver_pendentes_cartoes_over_e_under():
    import pandas as pd
    sug_over = _sugestao(criterio="Cartões+Árbitro", liga_chave="serieb", lado="Over 4.5 cartões", linha_aposta=4.5, odd=1.9)
    ledger = registrar_novas_sugestoes([], [sug_over], data_registro="2026-08-27")
    df_5_cartoes = pd.DataFrame([{"_fixture_id": 1, **_row(home_ya=3, away_ya=2)}])  # total=5 > 4.5
    ledger = resolver_pendentes(ledger, {"serieb": df_5_cartoes})
    assert ledger[0]["resultado"] == "green"

    sug_under = _sugestao(criterio="Cartões+Árbitro", liga_chave="serieb", lado="Under 4.5 cartões", linha_aposta=4.5, odd=1.9)
    ledger2 = registrar_novas_sugestoes([], [sug_under], data_registro="2026-08-27")
    ledger2 = resolver_pendentes(ledger2, {"serieb": df_5_cartoes})
    assert ledger2[0]["resultado"] == "red"  # 5 > 4.5, Under perde


def test_resolver_pendentes_jogo_nao_encontrado_continua_pendente():
    import pandas as pd
    ledger = registrar_novas_sugestoes([], [_sugestao()], data_registro="2026-08-27")
    df_vazio = pd.DataFrame([{"_fixture_id": 999, **_row()}])
    ledger = resolver_pendentes(ledger, {"seriea": df_vazio})
    assert ledger[0]["resultado"] == "pendente"
    assert ledger[0]["lucro"] is None


def test_calcular_resumo_ignora_pendentes():
    ledger = [
        dict(criterio="BTTS", resultado="pendente", lucro=None),
        dict(criterio="BTTS", resultado="green", lucro=0.8),
        dict(criterio="Over 2.5", resultado="red", lucro=-0.5),
    ]
    resumo = calcular_resumo(ledger)
    assert resumo["n"] == 2
    assert resumo["n_green"] == 1
    assert resumo["n_red"] == 1
    assert resumo["lucro_total"] == pytest.approx(0.3)
    assert resumo["roi"] == pytest.approx(0.3 / 1.5)  # stake total = 1.0 (BTTS) + 0.5 (Over 2.5)


def test_calcular_resumo_por_criterio():
    ledger = [
        dict(criterio="BTTS", resultado="green", lucro=0.8),
        dict(criterio="BTTS", resultado="red", lucro=-1.0),
        dict(criterio="Cartões+Árbitro", resultado="green", lucro=0.45),
    ]
    resumo = calcular_resumo(ledger)
    assert resumo["por_criterio"]["BTTS"]["n"] == 2
    assert resumo["por_criterio"]["BTTS"]["n_green"] == 1
    assert resumo["por_criterio"]["BTTS"]["roi"] == pytest.approx((0.8 - 1.0) / 2.0)
    assert resumo["por_criterio"]["Cartões+Árbitro"]["n"] == 1
    assert resumo["por_criterio"]["Cartões+Árbitro"]["roi"] == pytest.approx(0.45 / 0.5)


def test_calcular_resumo_sem_dado_resolvido_retorna_none_no_roi():
    resumo = calcular_resumo([dict(criterio="BTTS", resultado="pendente", lucro=None)])
    assert resumo["n"] == 0
    assert resumo["roi"] is None
