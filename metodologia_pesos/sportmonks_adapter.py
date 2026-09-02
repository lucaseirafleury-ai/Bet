"""Converte fixtures do Sportmonks (formato de `sportmonks_client.py`) pro
formato de linha que o motor (`retrospectiva.py`/`planilha_lib.get_historico`)
já espera (mesmas colunas que o CSV do FootyStats usa) — permite
reaproveitar o motor inteiro sem tocar em
`pesos.py`/`retrospectiva.py`/`estilo.py`.

Duas situações:
- **Fixture finalizado** (`home_goals`/`away_goals` presentes): vira uma
  linha de histórico de verdade, usada por `retrospectiva.rodar_retrospectiva`
  (backtesting) e como HISTÓRICO real dos times pra previsão ao vivo.
- **Fixture futuro** (ainda não jogado): vira uma linha SINTÉTICA — só
  serve como "o jogo de hoje" que `retrospectiva.prever_jogo` avalia
  (usa a data/odds/times reais, mas o placar é um placeholder 0-0 nunca
  lido de verdade). Ver `previsao_dia.py` — é assim que conseguimos
  reaproveitar `prever_jogo` (feito pra backtesting) pra prever jogos que
  ainda não aconteceram, sem duplicar a lógica de previsão em lugar
  nenhum.

xG NÃO existe no Sportmonks pra Série A/B (confirmado por inspeção da
API, type_id 5304 nunca aparece nos jogos das duas ligas).
`planilha_lib.get_historico` sempre exige um número real em
`team_a_xg`/`team_b_xg` (faz `float()` antes de qualquer checagem de
dado ausente) — não dá pra passar `None`. Usamos os GOLS REAIS do jogo
como proxy (mais informativo que uma constante fixa, mesmo sendo mais
ruidoso que xG de verdade).

**Odds restritas ao bet365 (bookmaker_id=2)**: o Sportmonks agrega
dezenas de casas internacionais (Unibet, Pinnacle, 10Bet...) que o
Lucas não usa/não tem acesso — usar "a odd com mais casas cotando"
podia sugerir um preço que não existe em nenhuma casa real acessível
(caso real: Goiás x São Bernardo, cartões só tinha 1 casa cotando,
nenhuma delas bet365/Betano). bet365 é a única casa do Lucas que o
Sportmonks cobre de forma confiável (999/999 jogos Série A, 998/1000
Série B têm alguma odd do bet365) — Betano não existe no catálogo pro
Brasil. Quando bet365 não cotar um mercado/jogo específico, a odd fica
`None` e o critério é pulado (nunca cai pra outra casa).
"""
from __future__ import annotations

import json
from datetime import datetime

import pandas as pd

CAMPOS_DETALHE = [
    "corners_home", "corners_away", "shots_home", "shots_away",
    "shots_on_target_home", "shots_on_target_away",
    "possession_home", "possession_away", "fouls_home", "fouls_away",
    "yellowcards_home", "yellowcards_away",
]

BOOKMAKER_BET365 = 2
BOOKMAKER_SBO = 34  # Sbobet — usado só como base do Over 2.5 recalibrado (ver previsao_dia.py)


def _media_odd(entradas, label, total_alvo=None, bookmaker_id=None):
    vals = [
        float(e["value"]) for e in entradas
        if e.get("label") == label and e.get("value") is not None
        and (total_alvo is None or (e.get("total") is not None and float(e["total"]) == total_alvo))
        and (bookmaker_id is None or e.get("bookmaker_id") == bookmaker_id)
    ]
    return sum(vals) / len(vals) if vals else None


def flat_para_linha(flat, bookmaker_id=BOOKMAKER_BET365):
    """Converte um fixture achatado (`sportmonks_client.flatten_fixture`)
    numa linha de DataFrame no formato FootyStats. Funciona tanto pra
    fixture finalizado quanto futuro (`home_goals is None`) — no caso
    futuro, o placar vira um placeholder 0-0 (nunca lido de verdade, ver
    módulo docstring) e as estatísticas de detalhe são forçadas pro
    sentinela de "dado ausente" (`-1`), já que um jogo futuro nunca tem
    stats de jogo.

    `bookmaker_id`: restringe as odds a uma única casa (default bet365,
    ver docstring do módulo) — passe `None` pra reproduzir o
    comportamento antigo (média de todas as casas do Sportmonks), usado
    só pra comparar/revalidar contra os números documentados antes
    dessa mudança."""
    dt = datetime.strptime(flat["date"][:19], "%Y-%m-%d %H:%M:%S")
    odds_1x2 = flat.get("odds", {}).get("1", [])
    odds_gols = flat.get("odds", {}).get("80", [])
    odds_btts = flat.get("odds", {}).get("14", [])

    eh_futuro = flat.get("home_goals") is None
    home_goals = 0 if eh_futuro else flat["home_goals"]
    away_goals = 0 if eh_futuro else flat["away_goals"]

    # `get_historico` (planilha_lib.py) sempre lê os campos de estatística
    # como número real, mesmo antes de checar o sentinela de dado ausente
    # (cf == -1) — nunca podemos passar None. Jogo futuro nunca tem stats
    # de detalhe (força o sentinela); jogo finalizado só força quando
    # falta QUALQUER campo (comum em ~5-16% dos jogos mais antigos) —
    # aciona o mesmo placeholder conservador por margem de gol que o
    # FootyStats já usa pra dado ausente, em vez de inventar defaults
    # por campo individual.
    stats_ausentes = eh_futuro or any(flat.get(c) is None for c in CAMPOS_DETALHE)
    corners_home = -1 if stats_ausentes else flat["corners_home"]
    corners_away = -1 if stats_ausentes else flat["corners_away"]

    return {
        "home_team_name": flat["home_team"], "away_team_name": flat["away_team"],
        "date_GMT": dt.strftime("%b %d %Y") + " - 3:00pm",
        "timestamp": int(dt.timestamp()),
        "status": "complete",
        "__src": f"sm_{flat.get('season', '')}.csv",
        "home_team_goal_count": home_goals, "away_team_goal_count": away_goals,
        "home_team_goal_count_half_time": flat.get("home_goals_ht") or 0,
        "away_team_goal_count_half_time": flat.get("away_goals_ht") or 0,
        "team_a_xg": float(home_goals), "team_b_xg": float(away_goals),
        "home_team_corner_count": corners_home, "away_team_corner_count": corners_away,
        "home_team_yellow_cards": flat.get("yellowcards_home") or 0,
        "home_team_red_cards": flat.get("redcards_home") or 0,
        "away_team_yellow_cards": flat.get("yellowcards_away") or 0,
        "away_team_red_cards": flat.get("redcards_away") or 0,
        "home_team_shots": flat.get("shots_home") or 0, "away_team_shots": flat.get("shots_away") or 0,
        "home_team_shots_on_target": flat.get("shots_on_target_home") or 0,
        "away_team_shots_on_target": flat.get("shots_on_target_away") or 0,
        "home_team_possession": flat.get("possession_home") or 50, "away_team_possession": flat.get("possession_away") or 50,
        "home_team_fouls": flat.get("fouls_home") or 0, "away_team_fouls": flat.get("fouls_away") or 0,
        "odds_ft_home_team_win": _media_odd(odds_1x2, "Home", bookmaker_id=bookmaker_id),
        "odds_ft_draw": _media_odd(odds_1x2, "Draw", bookmaker_id=bookmaker_id),
        "odds_ft_away_team_win": _media_odd(odds_1x2, "Away", bookmaker_id=bookmaker_id),
        "odds_ft_over15": _media_odd(odds_gols, "Over", 1.5, bookmaker_id=bookmaker_id),
        "odds_ft_over25": _media_odd(odds_gols, "Over", 2.5, bookmaker_id=bookmaker_id),
        "odds_ft_over35": _media_odd(odds_gols, "Over", 3.5, bookmaker_id=bookmaker_id),
        "odds_ft_over45": _media_odd(odds_gols, "Over", 4.5, bookmaker_id=bookmaker_id),
        "odds_btts_yes": _media_odd(odds_btts, "Yes", bookmaker_id=bookmaker_id),
        "odds_btts_no": _media_odd(odds_btts, "No", bookmaker_id=bookmaker_id),
        "_fixture_id": flat["fixture_id"], "_referee_id": flat.get("referee_id"),
        "_odds_cartoes": [
            e for e in (flat.get("odds", {}).get("255", []))
            if bookmaker_id is None or e.get("bookmaker_id") == bookmaker_id
        ],
        "_odds_escanteios": [
            e for e in (flat.get("odds", {}).get("60", []))
            if bookmaker_id is None or e.get("bookmaker_id") == bookmaker_id
        ],
    }


def carregar_liga_sportmonks(path, bookmaker_id=BOOKMAKER_BET365):
    """Carrega um JSONL de fixtures FINALIZADOS (gerado por
    `sportmonks_client.puxar_fixtures_finalizados`) num DataFrame no
    formato que `retrospectiva.py` já entende."""
    linhas = []
    with open(path) as f:
        for l in f:
            linhas.append(flat_para_linha(json.loads(l), bookmaker_id=bookmaker_id))
    return pd.DataFrame(linhas)
