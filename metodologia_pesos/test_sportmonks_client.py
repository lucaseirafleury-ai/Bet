import json
from unittest.mock import MagicMock, patch

import sportmonks_client as sm


def _fixture_bruto(fixture_id, home_goals, away_goals, date="2026-08-20 20:00:00"):
    return {
        "id": fixture_id,
        "starting_at": date,
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

    fixture_futuro = _fixture_bruto(3, None, None, date="2026-08-25 20:00:00")
    fixture_futuro["scores"] = []
    resposta = _resposta([fixture_futuro])
    with patch.object(sm.requests, "get", return_value=resposta):
        novos = sm.atualizar_fixtures_finalizados("tok", 648, str(out_path))

    assert novos == 0
    linhas = [json.loads(l) for l in out_path.read_text().splitlines()]
    assert len(linhas) == 1
