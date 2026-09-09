"""Testes do cálculo automático de estilo (últimos N jogos -> notas 1-5)."""
import json

import pytest

from estilo import (
    atualizar_banco_estilo,
    calcular_notas_estilo,
    nota_bloco_baixo,
    nota_bola_parada,
    nota_posse,
    nota_pressao_alta,
    nota_transicao,
)


def _jogo(posf=50, xgf=1.3, xga=1.3, sf=12, cf=5, yf=2, ff=11):
    return dict(posf=posf, xgf=xgf, xga=xga, sf=sf, cf=cf, yf=yf, ff=ff)


def test_nota_posse_faixas():
    assert nota_posse(30) == 1
    assert nota_posse(40) == 2
    assert nota_posse(50) == 3
    assert nota_posse(60) == 4
    assert nota_posse(70) == 5


def test_nota_bloco_baixo_espelha_posse():
    # posse baixa (time cede a bola) -> bloco baixo alto, sem ajuste de xGA extremo
    assert nota_bloco_baixo(media_posse=30, media_xga=1.3) == 5
    # posse alta -> bloco baixo baixo
    assert nota_bloco_baixo(media_posse=70, media_xga=1.3) == 1


def test_nota_bloco_baixo_ajuste_defesa_organizada():
    base = nota_bloco_baixo(media_posse=30, media_xga=1.3)
    organizada = nota_bloco_baixo(media_posse=30, media_xga=0.5)
    assert organizada == min(5, base + 1)


def test_nota_bloco_baixo_ajuste_time_dominado():
    base = nota_bloco_baixo(media_posse=30, media_xga=1.3)
    dominado = nota_bloco_baixo(media_posse=30, media_xga=2.5)
    assert dominado == max(1, base - 1)


def test_nota_bloco_baixo_nunca_sai_do_intervalo():
    # posse mínima já dá nota-base 5; ajuste positivo não pode passar de 5
    assert nota_bloco_baixo(media_posse=10, media_xga=0.2) == 5
    # posse máxima já dá nota-base 1; ajuste negativo não pode passar de 1
    assert nota_bloco_baixo(media_posse=90, media_xga=3.0) == 1


def test_nota_pressao_alta_cresce_com_posse_e_producao_ofensiva():
    baixa = nota_pressao_alta(media_posse=30, media_escanteios_pro=2, media_chutes_pro=6)
    alta = nota_pressao_alta(media_posse=68, media_escanteios_pro=8, media_chutes_pro=18)
    assert 1 <= baixa < alta <= 5


def test_nota_transicao_neutra_sem_dado():
    assert nota_transicao(media_posse=None, media_xgf=1.5) == 3
    assert nota_transicao(media_posse=50, media_xgf=None) == 3


def test_nota_transicao_cresce_com_eficiencia_e_pouca_posse():
    # times de contra-ataque: pouca posse, xG alto -> razão alta -> nota alta
    contra_ataque = nota_transicao(media_posse=35, media_xgf=1.8)
    posse_sem_eficiencia = nota_transicao(media_posse=65, media_xgf=1.0)
    assert contra_ataque > posse_sem_eficiencia


def test_nota_bola_parada_sem_dado_e_neutra():
    assert nota_bola_parada(None, None) == 3


def test_nota_bola_parada_cresce_com_fisico_e_escanteios():
    fraco = nota_bola_parada(media_cartoes=0.5, media_escanteios_pro=2)
    forte = nota_bola_parada(media_cartoes=3.5, media_escanteios_pro=9)
    assert fraco < forte


@pytest.mark.parametrize("funcao,kwargs", [
    (nota_posse, dict(media_posse=50)),
    (nota_bloco_baixo, dict(media_posse=50, media_xga=1.5)),
    (nota_pressao_alta, dict(media_posse=50, media_escanteios_pro=5, media_chutes_pro=12)),
    (nota_transicao, dict(media_posse=50, media_xgf=1.3)),
    (nota_bola_parada, dict(media_cartoes=2, media_escanteios_pro=5)),
])
def test_notas_sempre_no_intervalo_1_5(funcao, kwargs):
    nota = funcao(**kwargs)
    assert 1 <= nota <= 5


def test_calcular_notas_estilo_retorna_as_5_dimensoes_e_n_jogos():
    jogos = [_jogo(posf=p) for p in (55, 60, 50, 58, 62)]
    notas = calcular_notas_estilo(jogos)
    assert set(notas.keys()) == {"bb", "pa", "tr", "pos", "bp", "n_jogos"}
    assert notas["n_jogos"] == 5
    for chave in ("bb", "pa", "tr", "pos", "bp"):
        assert 1 <= notas[chave] <= 5


def test_calcular_notas_estilo_rejeita_lista_vazia():
    with pytest.raises(ValueError):
        calcular_notas_estilo([])


def test_calcular_notas_estilo_rejeita_sem_dado_de_posse():
    with pytest.raises(ValueError):
        calcular_notas_estilo([dict(posf=None)])


def test_atualizar_banco_estilo_sobrescreve_e_persiste(tmp_path):
    db_path = tmp_path / "estilos.json"
    db_path.write_text(json.dumps({
        "TimeVelho": {"estilo_text": "nota antiga escrita à mão", "bb": 1, "pa": 1, "tr": 1, "pos": 1, "bp": 1}
    }), encoding="utf-8")

    jogos_time_a = [_jogo(posf=p) for p in (60, 62, 58, 61, 59)]
    resultado = atualizar_banco_estilo({"TimeVelho": jogos_time_a}, str(db_path), n=5)

    assert "TimeVelho" in resultado
    banco = json.loads(db_path.read_text(encoding="utf-8"))
    # sobrescreveu as notas, mas manteve o texto descritivo já existente
    assert banco["TimeVelho"]["estilo_text"] == "nota antiga escrita à mão"
    assert banco["TimeVelho"]["bb"] == resultado["TimeVelho"]["bb"]
    assert banco["TimeVelho"]["pos"] == resultado["TimeVelho"]["pos"]
    assert banco["TimeVelho"]["bb"] != 1 or banco["TimeVelho"]["pos"] != 1  # não é mais o valor manual antigo


def test_atualizar_banco_estilo_cria_arquivo_novo(tmp_path):
    db_path = tmp_path / "novo.json"
    jogos = [_jogo(posf=p) for p in (45, 47, 44, 46, 48)]
    atualizar_banco_estilo({"TimeNovo": jogos}, str(db_path), n=5)
    assert db_path.exists()
    banco = json.loads(db_path.read_text(encoding="utf-8"))
    assert "TimeNovo" in banco


def test_atualizar_banco_estilo_usa_so_os_ultimos_n_jogos(tmp_path):
    db_path = tmp_path / "estilos.json"
    # 5 primeiros jogos com posse baixa, resto (que deve ser ignorado) com posse altíssima
    jogos = [_jogo(posf=p) for p in (30, 31, 29, 32, 28)] + [_jogo(posf=90)] * 10
    resultado = atualizar_banco_estilo({"TimeX": jogos}, str(db_path), n=5)
    assert resultado["TimeX"]["pos"] == nota_posse(30)  # média dos 5 primeiros, não dos 15
