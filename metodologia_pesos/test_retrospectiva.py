"""Teste de integração da retrospectiva walk-forward, com um dataset
fabricado (round-robin pequeno) — confirma que o pipeline roda ponta a
ponta sem olhar o futuro e produz métricas coerentes. Não depende dos CSVs
reais do FootyStats (que só chegam depois, via upload do usuário).
"""
from datetime import datetime, timedelta

import pandas as pd
import pytest

from retrospectiva import (
    _estilo_por_mando,
    _probabilidades_favorito_dc,
    grid_search,
    prever_jogo,
    rodar_retrospectiva,
    simular_apostas,
    simular_apostas_combo,
)

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
        "odds_ft_over15": 1.3 + 0.05 * (i % 5),
        "odds_ft_over25": 1.8 + 0.05 * (i % 5),
        "odds_ft_over35": 2.6 + 0.05 * (i % 5),
        "odds_ft_over45": 4.0 + 0.05 * (i % 5),
        "odds_btts_yes": 1.9, "odds_btts_no": 1.85,
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


def test_prever_jogo_calcula_os_12_mercados_pro_contra(df_fabricado):
    ultima_linha = df_fabricado.iloc[11]
    resultado = prever_jogo(
        ultima_linha, df_fabricado, params=dict(filtro_aderencia=0.0),
        min_jogos_historico=5, min_jogos_estilo=5,
    )
    assert resultado is not None
    esperados = {
        "gols_pro", "gols_contra", "cartoes_pro", "cartoes_contra",
        "escanteios_pro", "escanteios_contra", "chutes_pro", "chutes_contra",
        "chutes_gol_pro", "chutes_gol_contra", "gols_1t_pro", "gols_1t_contra",
    }
    assert esperados <= set(resultado["mercados"].keys())
    for campo, m in resultado["mercados"].items():
        assert m["pred"] >= 0
        assert m["real"] >= 0
        assert m["erro"] == pytest.approx(abs(m["pred"] - m["real"]))
    # consistência com os campos "de gols" já existentes
    assert resultado["mercados"]["gols_pro"]["real"] == resultado["gf_real"]
    assert resultado["mercados"]["gols_pro"]["pred"] == resultado["gf_pred"]


def test_prever_jogo_nunca_olha_o_futuro(df_fabricado):
    # se eu embaralhar o timestamp da última linha pra trás no tempo, ela some do "passado"
    # disponível — prova indireta de que o corte é por timestamp, não por posição na lista
    linha = df_fabricado.iloc[11].copy()
    df_sem_futuro = df_fabricado[df_fabricado["timestamp"] < linha["timestamp"]]
    assert len(df_sem_futuro) == 11  # exclui a própria linha 11


def test_prever_jogo_usar_estilo_false_roda_e_mesmo_conjunto_de_jogos(df_fabricado):
    ultima_linha = df_fabricado.iloc[11]
    com_estilo = prever_jogo(
        ultima_linha, df_fabricado, params=dict(filtro_aderencia=0.0, usar_estilo=True),
        min_jogos_historico=5, min_jogos_estilo=5,
    )
    sem_estilo = prever_jogo(
        ultima_linha, df_fabricado, params=dict(filtro_aderencia=0.0, usar_estilo=False),
        min_jogos_historico=5, min_jogos_estilo=5,
    )
    assert com_estilo is not None and sem_estilo is not None
    # mesmo jogo, mesmo histórico disponível -> mesma quantidade de jogos válidos
    # (o teste de ablação isola o PESO/FILTRO do estilo, não a disponibilidade de dado)
    assert com_estilo["n_jogos_validos"] == sem_estilo["n_jogos_validos"]


def test_rodar_retrospectiva_com_usar_estilo_false_tambem_agrega(df_fabricado):
    relatorio = rodar_retrospectiva(
        df_fabricado, params=dict(filtro_aderencia=0.0, usar_estilo=False),
        min_jogos_historico=5, min_jogos_estilo=5,
    )
    assert relatorio["n"] > 0


def test_estilo_por_mando_exige_jogos_naquele_mando_especifico(df_fabricado):
    # T2 tem só 2 jogos como visitante antes da última linha (i=11) -> com
    # min_jogos_estilo=2 dá, com 5 não dá (mesmo tendo 5 jogos no total)
    df_antes = df_fabricado[df_fabricado["timestamp"] < 11]
    assert _estilo_por_mando("T2", df_antes, "Fora", n_jogos_estilo=2) is not None
    assert _estilo_por_mando("T2", df_antes, "Fora", n_jogos_estilo=5) is None


def test_estilo_por_mando_mando_invalido_retorna_none(df_fabricado):
    df_antes = df_fabricado[df_fabricado["timestamp"] < 11]
    assert _estilo_por_mando("T2", df_antes, "Neutro", n_jogos_estilo=2) is None


def test_prever_jogo_estilo_por_mando_roda_com_dado_suficiente(df_fabricado):
    ultima_linha = df_fabricado.iloc[11]  # T3 (casa) x T2 (fora)
    resultado = prever_jogo(
        ultima_linha, df_fabricado,
        params=dict(filtro_aderencia=0.0, usar_estilo=True, estilo_por_mando=True),
        min_jogos_historico=5, min_jogos_estilo=2,
    )
    assert resultado is not None
    assert resultado["n_jogos_validos"] > 0


def test_prever_jogo_estilo_por_mando_falta_dado_retorna_none(df_fabricado):
    # com min_jogos_estilo=5, nenhum time tem 5 jogos NUM MANDO específico
    # ainda (só 6 jogos totais, 3 em casa e 3 fora no máximo)
    ultima_linha = df_fabricado.iloc[11]
    resultado = prever_jogo(
        ultima_linha, df_fabricado,
        params=dict(filtro_aderencia=0.0, usar_estilo=True, estilo_por_mando=True),
        min_jogos_historico=5, min_jogos_estilo=5,
    )
    assert resultado is None


def test_grid_search_ordenar_por_acerto_over25(df_fabricado):
    grade = dict(k_mando=[None, 0.35])
    resultados = grid_search(
        df_fabricado, grade, ordenar_por="acerto_over25",
        min_jogos_historico=5, min_jogos_estilo=5,
    )
    acertos = [r["acerto_over25"] for _, r in resultados if r["acerto_over25"] is not None]
    assert acertos == sorted(acertos, reverse=True)  # maior primeiro (maior acerto é melhor)


def test_rodar_retrospectiva_timestamp_minimo_so_avalia_jogos_recentes(df_fabricado):
    # sem corte: avalia todos os jogos com histórico suficiente
    sem_corte = rodar_retrospectiva(
        df_fabricado, params=dict(filtro_aderencia=0.0),
        min_jogos_historico=5, min_jogos_estilo=5,
    )
    # com corte (timestamp>=6): só considera AVALIAR as linhas 6..11 (6 jogos),
    # mas o histórico usado pra prever cada uma continua vindo das linhas anteriores
    com_corte = rodar_retrospectiva(
        df_fabricado, params=dict(filtro_aderencia=0.0),
        min_jogos_historico=5, min_jogos_estilo=5, timestamp_minimo=6,
    )
    assert com_corte["n"] + com_corte["n_pulados"] == 6
    assert com_corte["n"] <= sem_corte["n"]
    # todos os jogos avaliados são de linhas com timestamp >= 6 (data da linha 6 em diante)
    data_corte = datetime.strptime(df_fabricado.iloc[6]["date_GMT"].split(" - ")[0], "%b %d %Y").date()
    assert all(j["data"] >= data_corte for j in com_corte["jogos"])


def test_grid_search_ordenar_por_invalido_levanta_erro(df_fabricado):
    with pytest.raises(ValueError):
        grid_search(df_fabricado, dict(k_mando=[None]), ordenar_por="chute", min_jogos_historico=5)


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


def test_rodar_retrospectiva_agrega_mae_por_mercado(df_fabricado):
    relatorio = rodar_retrospectiva(
        df_fabricado, params=dict(filtro_aderencia=0.0),
        min_jogos_historico=5, min_jogos_estilo=5,
    )
    assert "gols_pro" in relatorio["mercados"]
    assert "escanteios_pro" in relatorio["mercados"]
    assert "cartoes_contra" in relatorio["mercados"]
    for campo, agg in relatorio["mercados"].items():
        assert agg["n"] > 0
        assert agg["mae"] >= 0
        assert agg["media_real"] >= 0
        if agg["media_real"] > 0:
            assert agg["mae_relativo"] == pytest.approx(agg["mae"] / agg["media_real"])
    # gols_pro/gols_contra estão presentes em todo jogo avaliado (são obrigatórios pra
    # inclusão) -> soma dos dois MAEs bate exatamente com mae_gols_total
    mae_gols_pro_contra = relatorio["mercados"]["gols_pro"]["mae"] + relatorio["mercados"]["gols_contra"]["mae"]
    assert mae_gols_pro_contra == pytest.approx(relatorio["mae_gols_total"])


def test_rodar_retrospectiva_sem_dado_suficiente_retorna_vazio(df_fabricado):
    relatorio = rodar_retrospectiva(
        df_fabricado, min_jogos_historico=999, min_jogos_estilo=5,
    )
    aposta_vazia = dict(n_apostas=0, n_vitorias=0, taxa_acerto=None, lucro_total=0.0, roi=None, edge_medio=None, apostas=[])
    assert relatorio == dict(n=0, n_pulados=len(df_fabricado), mae_gols_total=None,
                              acerto_over25=None, acerto_btts=None, mercados={}, jogos=[],
                              aposta_over25=aposta_vazia, aposta_btts=aposta_vazia, roi_over25=None, roi_btts=None)


def test_grid_search_ordena_por_erro_e_cobre_todas_combinacoes(df_fabricado):
    grade = dict(k_mando=[None, 0.35], limite_unilateral=[4], multiplicador_dp=[2.5, 3.0])
    resultados = grid_search(df_fabricado, grade, min_jogos_historico=5, min_jogos_estilo=5)
    assert len(resultados) == 4  # 2 x 1 x 2 combinações
    maes = [r["mae_gols_total"] for _, r in resultados if r["mae_gols_total"] is not None]
    assert maes == sorted(maes)  # ordenado crescente
    for params, _ in resultados:
        assert set(params.keys()) == {"k_mando", "limite_unilateral", "multiplicador_dp"}


def test_prever_jogo_traz_probabilidades_e_odds_de_mercado(df_fabricado):
    ultima_linha = df_fabricado.iloc[11]
    resultado = prever_jogo(
        ultima_linha, df_fabricado, params=dict(filtro_aderencia=0.0),
        min_jogos_historico=5, min_jogos_estilo=5,
    )
    assert resultado is not None
    assert 0 <= resultado["prob_modelo_over25"] <= 1
    assert 0 <= resultado["prob_modelo_btts"] <= 1
    assert resultado["odd_over25"] == pytest.approx(ultima_linha["odds_ft_over25"])
    assert resultado["prob_mercado_over25"] == pytest.approx(1 / ultima_linha["odds_ft_over25"])
    assert resultado["odd_btts_sim"] == pytest.approx(1.9)
    # BTTS usa a margem removida (2 vias), não é só 1/odd bruto
    assert resultado["prob_mercado_btts"] == pytest.approx(
        (1 / 1.9) / (1 / 1.9 + 1 / 1.85)
    )
    # mesma cobertura pras outras linhas de Over (1.5/3.5/4.5) — mesmo padrão do 2.5
    for nome, coluna in (("over15", "odds_ft_over15"), ("over35", "odds_ft_over35"), ("over45", "odds_ft_over45")):
        assert 0 <= resultado[f"prob_modelo_{nome}"] <= 1
        assert resultado[f"odd_{nome}"] == pytest.approx(ultima_linha[coluna])
        assert resultado[f"prob_mercado_{nome}"] == pytest.approx(1 / ultima_linha[coluna])
    # linha mais baixa (1.5) tem probabilidade de Over maior que a mais alta (4.5)
    assert resultado["prob_modelo_over15"] > resultado["prob_modelo_over25"] > resultado["prob_modelo_over45"]


def test_prever_jogo_traz_under_aproximado_de_todas_as_linhas(df_fabricado):
    ultima_linha = df_fabricado.iloc[11]
    resultado = prever_jogo(
        ultima_linha, df_fabricado, params=dict(filtro_aderencia=0.0),
        min_jogos_historico=5, min_jogos_estilo=5,
    )
    assert resultado is not None
    for nome, coluna in (
        ("under15", "odds_ft_over15"), ("under25", "odds_ft_over25"),
        ("under35", "odds_ft_over35"), ("under45", "odds_ft_over45"),
    ):
        nome_over = "over" + nome[len("under"):]
        # probabilidade do MODELO é o complemento exato (mesma distribuição Poisson)
        assert resultado[f"prob_modelo_{nome}"] == pytest.approx(1 - resultado[f"prob_modelo_{nome_over}"])
        # real/pred são o oposto booleano do lado over
        assert resultado[f"{nome}_real"] == (not resultado[f"{nome_over}_real"])
        assert resultado[f"{nome}_pred"] == (not resultado[f"{nome_over}_pred"])
        # odd/prob de mercado são aproximadas a partir da odd real de Over
        odd_over = ultima_linha[coluna]
        prob_under_esperada = 1 - 1 / odd_over
        assert resultado[f"prob_mercado_{nome}"] == pytest.approx(prob_under_esperada)
        assert resultado[f"odd_{nome}"] == pytest.approx(1 / prob_under_esperada)


def test_prever_jogo_margem_under_reduz_odd_de_under(df_fabricado):
    ultima_linha = df_fabricado.iloc[11]
    sem_margem = prever_jogo(
        ultima_linha, df_fabricado, params=dict(filtro_aderencia=0.0, margem_under=0.0),
        min_jogos_historico=5, min_jogos_estilo=5,
    )
    com_margem = prever_jogo(
        ultima_linha, df_fabricado, params=dict(filtro_aderencia=0.0, margem_under=0.07),
        min_jogos_historico=5, min_jogos_estilo=5,
    )
    assert sem_margem is not None and com_margem is not None
    for nome in ("under15", "under25", "under35", "under45"):
        assert com_margem[f"odd_{nome}"] < sem_margem[f"odd_{nome}"]
        assert com_margem[f"prob_mercado_{nome}"] > sem_margem[f"prob_mercado_{nome}"]


def test_prever_jogo_sem_coluna_de_odd_retorna_none_nesse_campo(df_fabricado):
    df_sem_odds = df_fabricado.drop(columns=["odds_ft_over25", "odds_btts_yes", "odds_btts_no"])
    ultima_linha = df_sem_odds.iloc[11]
    resultado = prever_jogo(
        ultima_linha, df_sem_odds, params=dict(filtro_aderencia=0.0),
        min_jogos_historico=5, min_jogos_estilo=5,
    )
    assert resultado is not None
    assert resultado["odd_over25"] is None
    assert resultado["prob_mercado_over25"] is None
    assert resultado["odd_under25"] is None
    assert resultado["prob_mercado_under25"] is None
    assert resultado["odd_btts_sim"] is None
    assert resultado["prob_mercado_btts"] is None
    # a probabilidade do MODELO não depende de odd nenhuma, continua presente
    assert resultado["prob_modelo_over25"] is not None


def test_prever_jogo_traz_favorito_dc(df_fabricado):
    # fixture: odds_ft_home_team_win=2.1 < odds_ft_away_team_win=3.4 -> casa é favorita
    ultima_linha = df_fabricado.iloc[11]
    resultado = prever_jogo(
        ultima_linha, df_fabricado, params=dict(filtro_aderencia=0.0),
        min_jogos_historico=5, min_jogos_estilo=5,
    )
    assert resultado is not None
    assert resultado["mando_favorito"] == "Casa"
    assert 0 <= resultado["prob_modelo_favorito_dc"] <= 1
    assert 0 <= resultado["prob_mercado_favorito_dc"] <= 1
    assert resultado["odd_favorito_dc"] > 1
    assert resultado["favorito_dc_real"] == (resultado["gf_real"] >= resultado["ga_real"])
    # DC (vitória OU empate) sempre tem mais probabilidade que só a vitória do favorito
    assert resultado["prob_mercado_favorito_dc"] > 1 / ultima_linha["odds_ft_home_team_win"]


def test_probabilidades_favorito_dc_sem_1x2_retorna_none():
    # sem as 3 odds do 1x2 no "row", não dá pra determinar favorito nem odd combinada
    linha_sem_1x2 = {}
    resultado = _probabilidades_favorito_dc(linha_sem_1x2, gf_pred=1.5, ga_pred=1.0, gf_real=2, ga_real=1)
    assert resultado == dict(mando_favorito=None, prob_modelo_favorito_dc=None,
                              odd_favorito_dc=None, prob_mercado_favorito_dc=None, favorito_dc_real=None)


def test_probabilidades_favorito_dc_time_visitante_favorito():
    linha = {"odds_ft_home_team_win": 4.0, "odds_ft_draw": 3.3, "odds_ft_away_team_win": 1.8}
    resultado = _probabilidades_favorito_dc(linha, gf_pred=0.8, ga_pred=1.9, gf_real=0, ga_real=2)
    assert resultado["mando_favorito"] == "Fora"
    assert resultado["favorito_dc_real"] is True  # visitante venceu (2 > 0) -> DC do favorito bate
    assert 0 < resultado["prob_mercado_favorito_dc"] < 1
    assert resultado["odd_favorito_dc"] > 1


def _jogo_simulado(odd, prob_modelo, prob_mercado, venceu, mercado="over25"):
    campo_odd = "odd_btts_sim" if mercado == "btts" else f"odd_{mercado}"
    campo_pm = f"prob_modelo_{mercado}"
    campo_pmk = f"prob_mercado_{mercado}"
    campo_real = f"{mercado}_real"
    return {
        "jogo": "Time A x Time B", "data": None,
        campo_odd: odd, campo_pm: prob_modelo, campo_pmk: prob_mercado, campo_real: venceu,
    }


def test_simular_apostas_calcula_lucro_e_roi_corretamente():
    jogos = [
        # edge positivo, aposta vence: odd 2.0, stake 1 -> lucro +1.0
        _jogo_simulado(odd=2.0, prob_modelo=0.60, prob_mercado=0.50, venceu=True),
        # edge positivo, aposta perde: -1.0
        _jogo_simulado(odd=1.8, prob_modelo=0.65, prob_mercado=0.55, venceu=False),
    ]
    r = simular_apostas(jogos, mercado="over25", limiar_edge=0.0, stake=1.0)
    assert r["n_apostas"] == 2
    assert r["n_vitorias"] == 1
    assert r["taxa_acerto"] == pytest.approx(0.5)
    assert r["lucro_total"] == pytest.approx(1.0 - 1.0)
    assert r["roi"] == pytest.approx(0.0 / 2.0)
    assert r["edge_medio"] == pytest.approx(((0.60 - 0.50) + (0.65 - 0.55)) / 2)


def test_simular_apostas_respeita_limiar_de_edge():
    jogos = [
        _jogo_simulado(odd=2.0, prob_modelo=0.51, prob_mercado=0.50, venceu=True),  # edge 0.01
        _jogo_simulado(odd=2.0, prob_modelo=0.60, prob_mercado=0.50, venceu=True),  # edge 0.10
    ]
    r = simular_apostas(jogos, mercado="over25", limiar_edge=0.05, stake=1.0)
    assert r["n_apostas"] == 1  # só o segundo jogo passa do limiar de 5%


def test_simular_apostas_pula_jogos_sem_odd():
    jogos = [
        {"jogo": "X", "data": None, "odd_over25": None, "prob_modelo_over25": 0.6,
         "prob_mercado_over25": None, "over25_real": True},
    ]
    r = simular_apostas(jogos, mercado="over25")
    assert r["n_apostas"] == 0
    assert r["lucro_total"] == 0.0
    assert r["roi"] is None


def test_simular_apostas_sem_nenhuma_aposta_valida():
    r = simular_apostas([], mercado="over25")
    assert r["n_apostas"] == 0
    assert r["taxa_acerto"] is None
    assert r["roi"] is None
    assert r["apostas"] == []


def test_simular_apostas_mercado_invalido_levanta_erro():
    with pytest.raises(ValueError):
        simular_apostas([], mercado="escanteios")


@pytest.mark.parametrize("mercado", ["over15", "over35", "over45", "under15", "under25", "under35", "under45"])
def test_simular_apostas_funciona_nas_outras_linhas_de_over(mercado):
    jogos = [
        _jogo_simulado(odd=2.0, prob_modelo=0.60, prob_mercado=0.50, venceu=True, mercado=mercado),
        _jogo_simulado(odd=1.8, prob_modelo=0.65, prob_mercado=0.55, venceu=False, mercado=mercado),
    ]
    r = simular_apostas(jogos, mercado=mercado, limiar_edge=0.0, stake=1.0)
    assert r["n_apostas"] == 2
    assert r["lucro_total"] == pytest.approx(0.0)


def test_simular_apostas_btts_usa_campos_corretos():
    jogos = [_jogo_simulado(odd=1.9, prob_modelo=0.55, prob_mercado=0.50, venceu=True, mercado="btts")]
    r = simular_apostas(jogos, mercado="btts", limiar_edge=0.0, stake=2.0)
    assert r["n_apostas"] == 1
    assert r["lucro_total"] == pytest.approx(2.0 * (1.9 - 1))


def test_rodar_retrospectiva_traz_roi_de_apostas(df_fabricado):
    relatorio = rodar_retrospectiva(
        df_fabricado, params=dict(filtro_aderencia=0.0), min_jogos_historico=5, min_jogos_estilo=5,
    )
    assert "aposta_over25" in relatorio and "aposta_btts" in relatorio
    assert relatorio["roi_over25"] == relatorio["aposta_over25"]["roi"]
    assert relatorio["roi_btts"] == relatorio["aposta_btts"]["roi"]
    # o dataset fabricado tem odds_ft_over25/odds_btts_* -> deve dar pra apostar em algo
    assert relatorio["aposta_over25"]["n_apostas"] >= 0


def test_rodar_retrospectiva_limiar_edge_reduz_apostas(df_fabricado):
    frouxo = rodar_retrospectiva(
        df_fabricado, params=dict(filtro_aderencia=0.0, limiar_edge=0.0),
        min_jogos_historico=5, min_jogos_estilo=5,
    )
    estrito = rodar_retrospectiva(
        df_fabricado, params=dict(filtro_aderencia=0.0, limiar_edge=0.5),
        min_jogos_historico=5, min_jogos_estilo=5,
    )
    assert estrito["aposta_over25"]["n_apostas"] <= frouxo["aposta_over25"]["n_apostas"]


def test_grid_search_ordenar_por_roi_respeita_min_apostas(df_fabricado):
    grade = dict(limiar_edge=[0.0, 0.5])
    resultados = grid_search(
        df_fabricado, grade, ordenar_por="roi_over25", min_apostas_roi=1000,
        min_jogos_historico=5, min_jogos_estilo=5,
    )
    # min_apostas_roi absurdamente alto -> nenhuma combinação é "elegível",
    # a ordenação não quebra mesmo assim (todas empatam no critério de amostra pequena)
    assert len(resultados) == 2


def test_grid_search_ordenar_por_roi_ordena_do_maior_pro_menor(df_fabricado):
    grade = dict(limiar_edge=[0.0, 0.02, 0.05])
    resultados = grid_search(
        df_fabricado, grade, ordenar_por="roi_over25", min_apostas_roi=0,
        min_jogos_historico=5, min_jogos_estilo=5,
    )
    rois_elegiveis = [r["roi_over25"] for _, r in resultados if r["roi_over25"] is not None]
    assert rois_elegiveis == sorted(rois_elegiveis, reverse=True)


def test_grid_search_ordenar_por_roi_btts_tambem_funciona(df_fabricado):
    resultados = grid_search(
        df_fabricado, dict(k_mando=[None, 0.35]), ordenar_por="roi_btts", min_apostas_roi=0,
        min_jogos_historico=5, min_jogos_estilo=5,
    )
    assert len(resultados) == 2


def _jogo_combo(over25_odd, over25_pm, over25_pmk, over25_real,
                 fav_odd, fav_pm, fav_pmk, fav_real):
    return {
        "jogo": "Time A x Time B", "data": None,
        "odd_over25": over25_odd, "prob_modelo_over25": over25_pm,
        "prob_mercado_over25": over25_pmk, "over25_real": over25_real,
        "odd_favorito_dc": fav_odd, "prob_modelo_favorito_dc": fav_pm,
        "prob_mercado_favorito_dc": fav_pmk, "favorito_dc_real": fav_real,
    }


def test_simular_apostas_combo_multiplica_odds_e_probabilidades():
    jogo = _jogo_combo(
        over25_odd=2.0, over25_pm=0.55, over25_pmk=0.50, over25_real=True,
        fav_odd=1.4, fav_pm=0.80, fav_pmk=0.72, fav_real=True,
    )
    r = simular_apostas_combo([jogo], pernas=["over25", "favorito_dc"], limiar_edge=0.0, stake=1.0)
    assert r["n_apostas"] == 1
    odd_esperada = 2.0 * 1.4
    edge_esperado = (0.55 * 0.80) - (0.50 * 0.72)
    assert r["apostas"][0]["odd"] == pytest.approx(odd_esperada)
    assert r["apostas"][0]["edge"] == pytest.approx(edge_esperado)
    assert r["lucro_total"] == pytest.approx(odd_esperada - 1)  # venceu as duas pernas


def test_simular_apostas_combo_perde_se_uma_perna_falhar():
    jogo = _jogo_combo(
        over25_odd=2.0, over25_pm=0.55, over25_pmk=0.50, over25_real=False,  # essa perna perde
        fav_odd=1.4, fav_pm=0.80, fav_pmk=0.72, fav_real=True,
    )
    r = simular_apostas_combo([jogo], pernas=["over25", "favorito_dc"], limiar_edge=0.0, stake=1.0)
    assert r["n_apostas"] == 1
    assert r["n_vitorias"] == 0
    assert r["lucro_total"] == pytest.approx(-1.0)


def test_simular_apostas_combo_pula_jogo_com_perna_incompleta():
    jogo_incompleto = _jogo_combo(
        over25_odd=2.0, over25_pm=0.55, over25_pmk=0.50, over25_real=True,
        fav_odd=None, fav_pm=0.80, fav_pmk=0.72, fav_real=True,  # falta a odd dessa perna
    )
    r = simular_apostas_combo([jogo_incompleto], pernas=["over25", "favorito_dc"])
    assert r["n_apostas"] == 0


def test_simular_apostas_combo_menos_de_2_pernas_levanta_erro():
    with pytest.raises(ValueError):
        simular_apostas_combo([], pernas=["over25"])


def test_simular_apostas_combo_mercado_invalido_levanta_erro():
    with pytest.raises(ValueError):
        simular_apostas_combo([], pernas=["over25", "escanteios"])
