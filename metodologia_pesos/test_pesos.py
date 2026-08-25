"""Testes do motor de pesos — trava a reimplementação Python contra os
casos conhecidos das fórmulas Excel (Times!AG:AK) e da fórmula Pró/Contra
robusta descrita no protocolo (SKILL.md serie-b-planilha-dia, seção 7b).
"""
from datetime import date

import pytest

from pesos import (
    aderencia_estilo,
    aderencia_favoritismo,
    ajuste_mando,
    calcular_pesos_historico,
    corte_outlier,
    desvio_padrao_ponderado,
    indicador_pro_contra,
    media_ponderada,
    peso_final,
    peso_recencia,
    probabilidade_btts,
    probabilidade_implicita,
    probabilidade_implicita_2vias,
    probabilidade_over,
    probabilidade_resultado,
)


def test_aderencia_estilo_identica_e_1():
    assert aderencia_estilo([3, 3, 3, 3, 3], [3, 3, 3, 3, 3]) == 1.0


def test_aderencia_estilo_maxima_diferenca_e_0():
    # cada nota é 1-5, diferença máxima por dimensão é 4; 5 dimensões * 4 = 20
    assert aderencia_estilo([1, 1, 1, 1, 1], [5, 5, 5, 5, 5]) == 0.0


def test_aderencia_estilo_parcial():
    # soma das diferenças = 1+0+2+0+1 = 4 -> 1 - 4/20 = 0.8
    assert aderencia_estilo([4, 3, 5, 2, 4], [3, 3, 3, 2, 3]) == pytest.approx(0.8)


def test_aderencia_estilo_exige_5_notas():
    with pytest.raises(ValueError):
        aderencia_estilo([3, 3, 3], [3, 3, 3, 3, 3])


def test_aderencia_favoritismo():
    assert aderencia_favoritismo(0.60, 0.60) == 1.0
    assert aderencia_favoritismo(0.70, 0.55) == pytest.approx(0.85)


@pytest.mark.parametrize(
    "dias,peso_esperado",
    [
        (0, 1.00),
        (10, 1.00),
        (11, 0.85),
        (20, 0.85),
        (21, 0.70),
        (30, 0.70),
        (31, 0.50),
        (45, 0.50),
        (46, 0.30),
        (90, 0.30),
        (91, 0.15),
        (180, 0.15),
        (181, 0.0),
        (365, 0.0),
    ],
)
def test_peso_recencia_degraus(dias, peso_esperado):
    assert peso_recencia(dias) == pytest.approx(peso_esperado)


def test_peso_recencia_rejeita_negativo():
    with pytest.raises(ValueError):
        peso_recencia(-1)


def test_peso_final_e_produto_dos_tres():
    assert peso_final(0.8, 0.9, 0.5) == pytest.approx(0.8 * 0.9 * 0.5)


def test_peso_final_zero_se_qualquer_fator_zero():
    assert peso_final(0.0, 0.9, 0.5) == 0.0
    assert peso_final(0.8, 0.9, 0.0) == 0.0


def test_calcular_pesos_historico_pipeline_completo():
    historico = [
        dict(data=date(2026, 8, 1), notas_estilo_adv=[3, 3, 3, 3, 3], favoritismo=0.60, mando="Casa"),
        dict(data=date(2026, 1, 1), notas_estilo_adv=[1, 1, 1, 1, 1], favoritismo=0.20, mando="Fora"),
    ]
    resultado = calcular_pesos_historico(
        historico, estilo_alvo=[3, 3, 3, 3, 3], favoritismo_alvo=0.60, data_jogo=date(2026, 8, 10)
    )
    assert len(resultado) == 2
    # jogo 1: estilo idêntico, favoritismo idêntico, 9 dias -> peso 1.0
    j1 = resultado[0]
    assert j1["aderencia_estilo"] == pytest.approx(1.0)
    assert j1["aderencia_favoritismo"] == pytest.approx(1.0)
    assert j1["peso_recencia"] == pytest.approx(1.0)
    assert j1["peso_final"] == pytest.approx(1.0)
    # jogo 2: estilo bem diferente, favoritismo bem diferente, jogo antigo -> peso baixo
    j2 = resultado[1]
    assert j2["peso_final"] < 0.05
    # não modifica os dicts originais
    assert "peso_final" not in historico[0]


def test_calcular_pesos_historico_usar_estilo_false_forca_aderencia_1():
    historico = [
        dict(data=date(2026, 8, 1), notas_estilo_adv=[1, 1, 1, 1, 1], favoritismo=0.60, mando="Casa"),
    ]
    resultado = calcular_pesos_historico(
        historico, estilo_alvo=[5, 5, 5, 5, 5], favoritismo_alvo=0.60,
        data_jogo=date(2026, 8, 10), usar_estilo=False,
    )
    j1 = resultado[0]
    # estilos completamente opostos (diferença máxima) -> normalmente daria aderencia 0,
    # mas usar_estilo=False força 1.0 e ignora a diferença
    assert j1["aderencia_estilo"] == 1.0
    assert j1["aderencia_favoritismo"] == pytest.approx(1.0)
    assert j1["peso_final"] == pytest.approx(j1["aderencia_favoritismo"] * j1["peso_recencia"])


def test_calcular_pesos_historico_usar_estilo_true_e_o_padrao():
    historico = [dict(data=date(2026, 8, 1), notas_estilo_adv=[1, 1, 1, 1, 1], favoritismo=0.60, mando="Casa")]
    com_flag = calcular_pesos_historico(
        historico, estilo_alvo=[5, 5, 5, 5, 5], favoritismo_alvo=0.60, data_jogo=date(2026, 8, 10), usar_estilo=True
    )
    sem_flag = calcular_pesos_historico(
        historico, estilo_alvo=[5, 5, 5, 5, 5], favoritismo_alvo=0.60, data_jogo=date(2026, 8, 10)
    )
    assert com_flag[0]["aderencia_estilo"] == sem_flag[0]["aderencia_estilo"] == 0.0


def test_ajuste_mando_mantem_peso_do_mando_alvo_e_encolhe_o_oposto():
    historico = [
        dict(mando="Casa", peso_final=0.8),
        dict(mando="Fora", peso_final=0.8),
    ]
    ajustado = ajuste_mando(historico, mando_alvo="Casa", k=0.35)
    assert ajustado[0]["peso_final"] == pytest.approx(0.8)  # mesmo mando -> 1x
    assert ajustado[1]["peso_final"] == pytest.approx(0.8 * 0.35)  # mando oposto -> k x
    # não modifica os dicts originais
    assert historico[1]["peso_final"] == 0.8


def test_ajuste_mando_k_1_e_neutro():
    historico = [dict(mando="Fora", peso_final=0.6)]
    ajustado = ajuste_mando(historico, mando_alvo="Casa", k=1.0)
    assert ajustado[0]["peso_final"] == pytest.approx(0.6)


def test_ajuste_mando_rejeita_mando_invalido():
    with pytest.raises(ValueError):
        ajuste_mando([], mando_alvo="Neutro")


def test_media_ponderada_simples():
    assert media_ponderada([1, 2, 3], [1, 1, 1]) == pytest.approx(2.0)
    assert media_ponderada([1, 3], [1, 3]) == pytest.approx((1 * 1 + 3 * 3) / 4)


def test_media_ponderada_ignora_none_e_peso_zero():
    assert media_ponderada([1, None, 3], [1, 1, 0]) == pytest.approx(1.0)


def test_media_ponderada_sem_pontos_validos_retorna_none():
    assert media_ponderada([1, 2], [0, 0]) is None


def test_desvio_padrao_ponderado_zero_quando_todos_iguais():
    assert desvio_padrao_ponderado([2, 2, 2], [1, 1, 1], media=2) == pytest.approx(0.0)


def test_desvio_padrao_ponderado_positivo_com_variancia():
    sd = desvio_padrao_ponderado([1, 2, 3], [1, 1, 1], media=2)
    assert sd > 0


def test_corte_outlier_unilateral_quando_media_baixa():
    # média de gols é baixa (<=4) -> corte unilateral: só remove acima de média+limite
    valores = [1, 1, 1, 1, 8]  # média ~2.4, o "8" é o pico anômalo
    pesos = [1, 1, 1, 1, 1]
    media = media_ponderada(valores, pesos)
    sd = desvio_padrao_ponderado(valores, pesos, media)
    filtrados, _ = corte_outlier(valores, pesos, media, sd, limite_unilateral=4, multiplicador_dp=1.0)
    assert 8 not in filtrados
    assert 1 in filtrados  # valores baixos nunca são cortados no modo unilateral


def test_corte_outlier_bilateral_quando_media_alta():
    # média alta (>4) -> corte bilateral, também corta pontos muito abaixo da média
    valores = [10, 10, 10, 10, 0]
    pesos = [1, 1, 1, 1, 1]
    media = media_ponderada(valores, pesos)
    sd = desvio_padrao_ponderado(valores, pesos, media)
    filtrados, _ = corte_outlier(valores, pesos, media, sd, limite_unilateral=4, multiplicador_dp=1.0)
    assert 0 not in filtrados


def test_indicador_pro_contra_pipeline_e_reporta_removidos():
    valores = [1, 1, 1, 1, 8]
    pesos = [1, 1, 1, 1, 1]
    r = indicador_pro_contra(valores, pesos, limite_unilateral=4, multiplicador_dp=1.0)
    assert r["media_bruta"] == pytest.approx(2.4)
    assert r["n_removidos"] == 1
    assert r["media_final"] == pytest.approx(1.0)  # sem o outlier, sobra só o cluster de 1s


def test_indicador_pro_contra_sem_dados_retorna_none():
    r = indicador_pro_contra([], [])
    assert r == dict(media_bruta=None, sd=None, media_final=None, n_removidos=0)


def test_probabilidade_over_valor_conhecido():
    # Poisson(2.5): P(total > 2.5) calculado à parte, valor de referência
    assert probabilidade_over(2.5, linha=2.5) == pytest.approx(0.4561868841166705)
    assert probabilidade_over(1.0, linha=1.5) == pytest.approx(0.26424111765711533)


def test_probabilidade_over_zero_gols_esperados_e_zero():
    assert probabilidade_over(0, linha=2.5) == 0.0


def test_probabilidade_over_cresce_com_media_esperada():
    baixa = probabilidade_over(1.5, linha=2.5)
    alta = probabilidade_over(4.0, linha=2.5)
    assert 0 <= baixa < alta <= 1


def test_probabilidade_over_rejeita_media_negativa():
    with pytest.raises(ValueError):
        probabilidade_over(-1, linha=2.5)


def test_probabilidade_btts_valor_conhecido():
    assert probabilidade_btts(1.3, 1.1) == pytest.approx(0.4853150765573204)


def test_probabilidade_btts_zero_se_um_lado_nao_marca():
    assert probabilidade_btts(0, 1.5) == 0.0


def test_probabilidade_btts_rejeita_negativo():
    with pytest.raises(ValueError):
        probabilidade_btts(-0.5, 1.0)


def test_probabilidade_implicita_simples():
    assert probabilidade_implicita(2.0) == pytest.approx(0.5)
    assert probabilidade_implicita(1.5) == pytest.approx(2 / 3)


def test_probabilidade_implicita_rejeita_odd_invalida():
    with pytest.raises(ValueError):
        probabilidade_implicita(1.0)
    with pytest.raises(ValueError):
        probabilidade_implicita(0.5)


def test_probabilidade_implicita_2vias_remove_margem():
    # odds com margem: 1/1.90 + 1/2.10 = 0.526+0.476 = 1.003 (>1, margem da casa)
    p_sim = probabilidade_implicita_2vias(1.90, 2.10)
    p_nao = probabilidade_implicita_2vias(2.10, 1.90)
    assert p_sim + p_nao == pytest.approx(1.0)
    assert p_sim > probabilidade_implicita(2.10)  # não é só 1/odd bruto, é normalizado


def test_probabilidade_resultado_soma_um():
    r = probabilidade_resultado(1.5, 1.2)
    assert r["vitoria"] + r["empate"] + r["derrota"] == pytest.approx(1.0)


def test_probabilidade_resultado_mandante_franco_favorito():
    # mandante espera 3 gols, visitante espera 0.3 -> vitória do mandante deve dominar
    r = probabilidade_resultado(3.0, 0.3)
    assert r["vitoria"] > 0.8
    assert r["vitoria"] > r["empate"] > r["derrota"]


def test_probabilidade_resultado_simetrico_quando_gols_esperados_iguais():
    r = probabilidade_resultado(1.4, 1.4)
    assert r["vitoria"] == pytest.approx(r["derrota"], abs=1e-9)


def test_probabilidade_resultado_rejeita_negativo():
    with pytest.raises(ValueError):
        probabilidade_resultado(-1.0, 1.0)
