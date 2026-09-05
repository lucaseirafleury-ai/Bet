import json
from unittest.mock import MagicMock, patch

import sportmonks_client as sm


def _fixture_bruto(fixture_id, home_goals, away_goals, date="2026-08-20 20:00:00", state_id=5):
    return {
        "id": fixture_id,
        "starting_at": date,
        "state_id": state_id,
        "participants": [
            {"id": 1, "name": "Time A", "meta": {"location": "home"}},
            {"id": 2, "name": "Time B", "meta": {"location": "away"}},
        ],
        "scores": [
            {"description": "CURRENT", "participant_id": 1, "score": {"goals": home_goals}},
            {"description": "CURRENT", "participant_id": 2, "score": {"goals": away_goals}},
        ],
        "statistics": [], "referees": [], "odds": [],
    }


def _resposta(fixtures, has_more=False):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"data": fixtures, "pagination": {"has_more": has_more}}
    return resp


def test_atualizar_fixtures_finalizados_sem_arquivo_faz_pull_completo(tmp_path):
    out_path = str(tmp_path / "fixtures.jsonl")
    with patch.object(sm, "puxar_fixtures_finalizados", return_value=42) as mock_full:
        total = sm.atualizar_fixtures_finalizados("tok", 648, out_path)
    mock_full.assert_called_once_with("tok", 648, out_path)
    assert total == 42


def test_atualizar_fixtures_finalizados_incremental_pula_existente_e_adiciona_novo(tmp_path):
    out_path = tmp_path / "fixtures.jsonl"
    existente = dict(fixture_id=1, date="2026-08-20 20:00:00", home_team="Time A", away_team="Time B",
                      home_goals=1, away_goals=1, home_goals_ht=0, away_goals_ht=0,
                      referee_id=None, odds={}, season="2026")
    out_path.write_text(json.dumps(existente) + "\n")

    resposta = _resposta([_fixture_bruto(1, 1, 1), _fixture_bruto(2, 2, 0, date="2026-08-22 20:00:00")])
    with patch.object(sm.requests, "get", return_value=resposta) as mock_get:
        novos = sm.atualizar_fixtures_finalizados("tok", 648, str(out_path), margem_dias=3)

    assert novos == 1
    linhas = [json.loads(l) for l in out_path.read_text().splitlines()]
    assert {l["fixture_id"] for l in linhas} == {1, 2}
    novo = next(l for l in linhas if l["fixture_id"] == 2)
    assert novo["season"] == ""
    # não duplicou nem alterou a fixture já existente
    velho = next(l for l in linhas if l["fixture_id"] == 1)
    assert velho["season"] == "2026"

    url_chamada = mock_get.call_args[0][0]
    assert url_chamada.startswith(f"{sm.BASE}/fixtures/between/2026-08-17/")  # 2026-08-20 - 3 dias


def test_atualizar_fixtures_finalizados_ignora_fixture_ainda_nao_jogado(tmp_path):
    out_path = tmp_path / "fixtures.jsonl"
    existente = dict(fixture_id=1, date="2026-08-20 20:00:00", home_team="Time A", away_team="Time B",
                      home_goals=1, away_goals=1, home_goals_ht=0, away_goals_ht=0,
                      referee_id=None, odds={}, season="2026")
    out_path.write_text(json.dumps(existente) + "\n")

    fixture_futuro = _fixture_bruto(3, None, None, date="2026-08-25 20:00:00", state_id=sm.ESTADO_NAO_INICIADO)
    fixture_futuro["scores"] = []
    resposta = _resposta([fixture_futuro])
    with patch.object(sm.requests, "get", return_value=resposta):
        novos = sm.atualizar_fixtures_finalizados("tok", 648, str(out_path))

    assert novos == 0
    linhas = [json.loads(l) for l in out_path.read_text().splitlines()]
    assert len(linhas) == 1


def test_atualizar_fixtures_finalizados_ignora_placeholder_zero_a_zero_pre_jogo(tmp_path):
    # bug real (28/08/2026, Goiás x São Bernardo): o Sportmonks às vezes
    # já publica uma entrada "CURRENT" 0-0 minutos antes do jogo começar,
    # mesmo com state_id ainda 1 (NS) - usar só "scores tem CURRENT" ou
    # "home_goals is not None" pra decidir "terminou" classificaria esse
    # jogo (que nem começou) como finalizado, com placar fantasma 0-0.
    out_path = tmp_path / "fixtures.jsonl"
    existente = dict(fixture_id=1, date="2026-08-20 20:00:00", home_team="Time A", away_team="Time B",
                      home_goals=1, away_goals=1, home_goals_ht=0, away_goals_ht=0,
                      referee_id=None, odds={}, season="2026")
    out_path.write_text(json.dumps(existente) + "\n")

    fixture_com_placeholder = _fixture_bruto(9, 0, 0, date="2026-08-28 20:00:00", state_id=sm.ESTADO_NAO_INICIADO)
    resposta = _resposta([fixture_com_placeholder])
    with patch.object(sm.requests, "get", return_value=resposta):
        novos = sm.atualizar_fixtures_finalizados("tok", 648, str(out_path), margem_dias=10)

    assert novos == 0
    linhas = [json.loads(l) for l in out_path.read_text().splitlines()]
    assert [l["fixture_id"] for l in linhas] == [1]


def test_puxar_fixtures_futuros_inclui_jogo_com_placeholder_zero_a_zero_pre_jogo():
    # mesmo bug do teste acima, do lado do painel de sugestões: um jogo
    # NS com placeholder 0-0 precisa continuar aparecendo como "ainda não
    # jogado" pro painel conseguir sugerir aposta nele - se cair no ramo
    # "já jogado" ele simplesmente some da lista de sugestões (foi o que
    # aconteceu de verdade: o jogo sumiu de puxar_fixtures_futuros e o
    # painel ficou preso mostrando a última sugestão antiga).
    fixture_com_placeholder = _fixture_bruto(9, 0, 0, date="2026-08-28 22:30:00", state_id=sm.ESTADO_NAO_INICIADO)
    resposta = _resposta([fixture_com_placeholder])
    with patch.object(sm.requests, "get", return_value=resposta):
        futuros = sm.puxar_fixtures_futuros("tok", 648, dias_a_frente=3)

    assert [f["fixture_id"] for f in futuros] == [9]


def test_puxar_fixtures_futuros_exclui_jogo_em_andamento():
    fixture_em_andamento = _fixture_bruto(9, 1, 0, date="2026-08-28 20:00:00", state_id=22)  # INPLAY_2ND_HALF
    resposta = _resposta([fixture_em_andamento])
    with patch.object(sm.requests, "get", return_value=resposta):
        futuros = sm.puxar_fixtures_futuros("tok", 648, dias_a_frente=3)

    assert futuros == []
