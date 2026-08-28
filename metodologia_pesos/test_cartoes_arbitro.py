import pytest

from cartoes_arbitro import (
    decidir_lado_linha,
    linha_mais_liquida,
    media_arbitro_atual,
    media_arbitro_walk_forward,
    odd_media_na_linha,
    prever_cartoes_combinado,
    simular_aposta_linha,
)


def test_media_arbitro_walk_forward_exige_minimo_de_jogos_antes_de_prever():
    # árbitro X aparece em 3 jogos; min_jogos_arbitro=2 -> só o 3º jogo tem média
    jogos = [
        {"referee_id": "X", "total_cartoes": 4},
        {"referee_id": "X", "total_cartoes": 6},
        {"referee_id": "X", "total_cartoes": 8},
    ]
    medias = media_arbitro_walk_forward(jogos, min_jogos_arbitro=2)
    assert medias == [None, None, pytest.approx((4 + 6) / 2)]


def test_media_arbitro_walk_forward_nao_olha_o_futuro():
    # se o 3º jogo (cartoes=100, um outlier) viesse ANTES, a média do 4º
    # jogo mudaria muito - confirmando que a ordem de entrada é o que importa
    jogos = [
        {"referee_id": "X", "total_cartoes": 4},
        {"referee_id": "X", "total_cartoes": 6},
        {"referee_id": "X", "total_cartoes": 100},
        {"referee_id": "X", "total_cartoes": 5},
    ]
    medias = media_arbitro_walk_forward(jogos, min_jogos_arbitro=2)
    # a média do 4º jogo (índice 3) só pode usar os 3 primeiros - inclui o outlier
    assert medias[3] == pytest.approx((4 + 6 + 100) / 3)
    # a média do 3º jogo (índice 2) só usa os 2 primeiros - NÃO inclui o próprio outlier
    assert medias[2] == pytest.approx((4 + 6) / 2)


def test_media_arbitro_walk_forward_arbitros_diferentes_tem_historicos_separados():
    jogos = [
        {"referee_id": "X", "total_cartoes": 4},
        {"referee_id": "Y", "total_cartoes": 10},
        {"referee_id": "X", "total_cartoes": 6},
        {"referee_id": "Y", "total_cartoes": 12},
        {"referee_id": "X", "total_cartoes": 8},
    ]
    medias = media_arbitro_walk_forward(jogos, min_jogos_arbitro=2)
    assert medias[4] == pytest.approx((4 + 6) / 2)  # só jogos do árbitro X


def test_media_arbitro_walk_forward_referee_id_ausente_retorna_none():
    jogos = [{"referee_id": None, "total_cartoes": 4}]
    assert media_arbitro_walk_forward(jogos, min_jogos_arbitro=1) == [None]


def test_media_arbitro_walk_forward_total_cartoes_ausente_nao_entra_no_historico():
    jogos = [
        {"referee_id": "X", "total_cartoes": None},
        {"referee_id": "X", "total_cartoes": 4},
        {"referee_id": "X", "total_cartoes": 6},
        {"referee_id": "X", "total_cartoes": 8},
    ]
    medias = media_arbitro_walk_forward(jogos, min_jogos_arbitro=2)
    # o 1º jogo (sem total_cartoes) não entra no histórico - só o 4º jogo
    # (quando o histórico já acumulou os 2 valores dos jogos 2 e 3) tem média
    assert medias == [None, None, None, pytest.approx((4 + 6) / 2)]


def test_media_arbitro_atual_usa_todo_o_historico_sem_ordem():
    jogos = [
        {"referee_id": "X", "total_cartoes": 4},
        {"referee_id": "Y", "total_cartoes": 10},
        {"referee_id": "X", "total_cartoes": 6},
        {"referee_id": "X", "total_cartoes": 8},
    ]
    medias = media_arbitro_atual(jogos, min_jogos_arbitro=3)
    assert medias == {"X": pytest.approx((4 + 6 + 8) / 3)}  # Y só tem 1 jogo, abaixo do minimo


def test_media_arbitro_atual_ignora_jogos_sem_referee_ou_total():
    jogos = [
        {"referee_id": None, "total_cartoes": 4},
        {"referee_id": "X", "total_cartoes": None},
        {"referee_id": "X", "total_cartoes": 6},
        {"referee_id": "X", "total_cartoes": 8},
    ]
    medias = media_arbitro_atual(jogos, min_jogos_arbitro=2)
    assert medias == {"X": pytest.approx((6 + 8) / 2)}


def test_prever_cartoes_combinado_media_ponderada():
    assert prever_cartoes_combinado(pred_time=4.0, media_arbitro=6.0, peso_arbitro=0.25) == pytest.approx(
        4.0 * 0.75 + 6.0 * 0.25
    )


def test_prever_cartoes_combinado_sem_media_arbitro_retorna_none():
    assert prever_cartoes_combinado(pred_time=4.0, media_arbitro=None, peso_arbitro=0.3) is None


def test_prever_cartoes_combinado_peso_invalido_levanta_erro():
    with pytest.raises(ValueError):
        prever_cartoes_combinado(pred_time=4.0, media_arbitro=6.0, peso_arbitro=1.5)


def test_linha_mais_liquida_escolhe_a_linha_com_mais_bookmakers():
    jogo = {"odds": {"255": [
        {"bookmaker_id": 1, "label": "Over", "total": "9.5", "value": 1.9},
        {"bookmaker_id": 1, "label": "Under", "total": "9.5", "value": 1.9},
        {"bookmaker_id": 2, "label": "Over", "total": "9.5", "value": 1.85},
        {"bookmaker_id": 3, "label": "Over", "total": "10.5", "value": 1.95},
    ]}}
    assert linha_mais_liquida(jogo, 255) == 9.5


def test_linha_mais_liquida_mercado_ausente_retorna_none():
    assert linha_mais_liquida({"odds": {}}, 255) is None


def test_linha_mais_liquida_empate_de_um_bookmaker_desempata_por_paridade():
    # caso real pós-restrição a bet365: um único bookmaker cota várias
    # linhas alternativas, todas empatadas em "1 bookmaker" - a linha
    # 4.5 vem DEPOIS na ordem de inserção (então a lógica antiga, que
    # devolvia a primeira chave do dict em caso de empate, escolheria
    # 3.5 aqui só por coincidência de ordem) - o desempate correto deve
    # escolher pela paridade (odd Over/Under mais próxima), não pela
    # ordem: 4.5 tem odds bem desequilibradas (1.20/4.50), 5.5 tem odds
    # quase 50/50 (1.95/1.95) - 5.5 deve vencer mesmo aparecendo por
    # último na lista.
    jogo = {"odds": {"255": [
        {"bookmaker_id": 2, "label": "Over", "total": "4.5", "value": 1.20},
        {"bookmaker_id": 2, "label": "Under", "total": "4.5", "value": 4.50},
        {"bookmaker_id": 2, "label": "Over", "total": "5.5", "value": 1.95},
        {"bookmaker_id": 2, "label": "Under", "total": "5.5", "value": 1.95},
    ]}}
    assert linha_mais_liquida(jogo, 255) == 5.5


def test_linha_mais_liquida_empate_prefere_linha_com_os_dois_lados_cotados():
    # 3.5 só tem o lado Over cotado (sem Under pra medir paridade) -
    # mesmo empatada em bookmakers, não deve vencer uma linha com os
    # dois lados presentes e paridade mensurável.
    jogo = {"odds": {"255": [
        {"bookmaker_id": 2, "label": "Over", "total": "3.5", "value": 1.10},
        {"bookmaker_id": 2, "label": "Over", "total": "4.5", "value": 2.10},
        {"bookmaker_id": 2, "label": "Under", "total": "4.5", "value": 1.75},
    ]}}
    assert linha_mais_liquida(jogo, 255) == 4.5


def test_odd_media_na_linha_calcula_media_correta():
    jogo = {"odds": {"255": [
        {"bookmaker_id": 1, "label": "Over", "total": "9.5", "value": 1.9},
        {"bookmaker_id": 2, "label": "Over", "total": "9.5", "value": 1.8},
        {"bookmaker_id": 3, "label": "Under", "total": "9.5", "value": 2.0},
    ]}}
    assert odd_media_na_linha(jogo, 255, 9.5, "Over") == pytest.approx((1.9 + 1.8) / 2)
    assert odd_media_na_linha(jogo, 255, 9.5, "Under") == pytest.approx(2.0)


def test_odd_media_na_linha_sem_cotacao_retorna_none():
    jogo = {"odds": {"255": [{"bookmaker_id": 1, "label": "Over", "total": "9.5", "value": 1.9}]}}
    assert odd_media_na_linha(jogo, 255, 8.5, "Over") is None


def test_simular_aposta_linha_aposta_no_lado_com_edge_positivo():
    # pred_total bem acima da linha -> modelo acha mais provável que o
    # mercado (odds equilibradas em 1.9/1.9 -> mercado acha ~50/50)
    resultado = simular_aposta_linha(pred_total=6.0, linha=2.5, odd_over=1.9, odd_under=1.9, real_total=4)
    assert resultado is not None
    assert resultado["lado"] == "Over"
    assert resultado["venceu"] is True
    assert resultado["lucro"] == pytest.approx(0.9)


def test_simular_aposta_linha_com_limiar_de_edge_pula_jogo_sem_vantagem_minima():
    # odds equilibradas (mercado ~50/50) e pred_total só um pouco acima da
    # linha -> edge pequeno, positivo mas abaixo de um limiar exigente
    resultado = simular_aposta_linha(
        pred_total=2.6, linha=2.5, odd_over=2.0, odd_under=2.0, real_total=3, limiar_edge=0.5,
    )
    assert resultado is None


def test_simular_aposta_linha_limiar_zero_sempre_aposta_no_lado_favorecido():
    # com limiar_edge=0.0 (padrão, o que foi usado na validação empírica),
    # edge_under é sempre o negativo de edge_over - um dos dois lados
    # sempre bate o limiar, a função nunca pula o jogo
    resultado = simular_aposta_linha(pred_total=2.5, linha=2.5, odd_over=2.0, odd_under=2.0, real_total=3)
    assert resultado is not None


def test_decidir_lado_linha_nao_precisa_de_resultado_real():
    # mesmo cenario do teste de simular_aposta_linha, mas sem informar
    # real_total - usado pra jogos futuros (previsao_dia.py)
    decisao = decidir_lado_linha(pred_total=6.0, linha=2.5, odd_over=1.9, odd_under=1.9)
    assert decisao["lado"] == "Over"
    assert decisao["odd"] == pytest.approx(1.9)
    assert decisao["edge"] > 0


def test_decidir_lado_linha_com_limiar_pula_sem_edge_minimo():
    decisao = decidir_lado_linha(pred_total=2.6, linha=2.5, odd_over=2.0, odd_under=2.0, limiar_edge=0.5)
    assert decisao is None


def test_simular_aposta_linha_aposta_perdedora_tem_lucro_negativo():
    resultado = simular_aposta_linha(pred_total=6.0, linha=2.5, odd_over=1.9, odd_under=1.9, real_total=1)
    assert resultado["lado"] == "Over"
    assert resultado["venceu"] is False
    assert resultado["lucro"] == -1.0
