"""Cliente HTTP fino pra API do Sportmonks — busca fixtures FINALIZADOS
(pra montar o histórico usado pelo motor de walk-forward,
`retrospectiva.py`) e fixtures FUTUROS (pra prever os jogos do dia,
`previsao_dia.py`). Token via variável de ambiente `SPORTMONKS_TOKEN`,
nunca hardcoded.

Mercados pulados: 1 (Fulltime Result/1x2 — usado pro favoritismo do
próprio jogo), 80 (Goals Over/Under), 14 (BTTS), 255 (Number of Cards).
Estatísticas: corners, cartões (amarelo/vermelho), chutes, chutes no
alvo, posse, faltas — tudo que `planilha_lib.get_historico` espera,
menos xG (não existe pra Série A/B no Sportmonks, ver
`sportmonks_adapter.py`).
"""
from __future__ import annotations

import os
import time

import requests

BASE = "https://api.sportmonks.com/v3/football"
LEAGUE_IDS = {"seriea": 648, "serieb": 651}
MARKETS = "1,80,14,255"

STAT_TYPE_MAP = {
    34: "corners", 84: "yellowcards", 83: "redcards",
    42: "shots", 86: "shots_on_target", 45: "possession", 56: "fouls",
}
REFEREE_TYPE_PRINCIPAL = 6


def token():
    t = os.environ.get("SPORTMONKS_TOKEN")
    if not t:
        raise RuntimeError(
            "SPORTMONKS_TOKEN não está definido no ambiente — exporte o token "
            "antes de rodar (nunca hardcodear no código)."
        )
    return t


def descobrir_temporadas(tok, league_id):
    r = requests.get(f"{BASE}/leagues/{league_id}", params={"api_token": tok, "include": "seasons"}, timeout=30)
    r.raise_for_status()
    return {s["name"]: s["id"] for s in r.json()["data"]["seasons"]}


def flatten_fixture(f):
    """Extrai os campos que interessam de um fixture bruto do Sportmonks.
    Funciona tanto pra fixture FINALIZADO (tem `scores`) quanto FUTURO
    (sem `scores` ainda) — `home_goals`/`away_goals` ficam `None` nesse
    caso, e o chamador decide o que fazer (ver `sportmonks_adapter.py`)."""
    participants = f.get("participants") or []
    home = next((p for p in participants if p.get("meta", {}).get("location") == "home"), None)
    away = next((p for p in participants if p.get("meta", {}).get("location") == "away"), None)
    if not home or not away:
        return None

    scores = {}
    for s in f.get("scores") or []:
        pid = s.get("participant_id")
        goals = (s.get("score") or {}).get("goals")
        scores.setdefault(s.get("description"), {})[pid] = goals
    ft = scores.get("CURRENT", {})
    ht = scores.get("1ST_HALF", {})

    stats = {}
    for s in f.get("statistics") or []:
        tipo = STAT_TYPE_MAP.get(s.get("type_id"))
        if not tipo:
            continue
        pid = s.get("participant_id")
        val = (s.get("data") or {}).get("value")
        loc = "home" if pid == home["id"] else ("away" if pid == away["id"] else None)
        if loc:
            stats[f"{tipo}_{loc}"] = val

    referee_id = None
    for ref in f.get("referees") or []:
        if ref.get("type_id") == REFEREE_TYPE_PRINCIPAL:
            referee_id = ref.get("referee_id")
            break

    odds = {}
    for o in f.get("odds") or []:
        mid = o.get("market_id")
        odds.setdefault(str(mid), []).append(dict(
            bookmaker_id=o.get("bookmaker_id"), label=o.get("label"),
            total=o.get("total"), value=o.get("value"),
        ))

    return dict(
        fixture_id=f["id"], date=f["starting_at"], home_team=home["name"], away_team=away["name"],
        home_goals=ft.get(home["id"]), away_goals=ft.get(away["id"]),
        home_goals_ht=ht.get(home["id"]), away_goals_ht=ht.get(away["id"]),
        referee_id=referee_id, odds=odds, **stats,
    )


def puxar_fixtures_finalizados(tok, league_id, out_path):
    """Grava um JSONL (um fixture finalizado por linha) com todas as
    temporadas disponíveis no plano (3 grátis + a atual). Sobrescreve
    `out_path` a cada chamada — rodar de novo pra atualizar o dado."""
    temporadas = descobrir_temporadas(tok, league_id)
    total = 0
    with open(out_path, "w") as fh:
        for nome_temp, season_id in temporadas.items():
            page = 1
            while True:
                params = {
                    "api_token": tok,
                    "filters": f"fixtureLeagues:{league_id};fixtureSeasons:{season_id};markets:{MARKETS}",
                    "include": "scores;participants;statistics;referees;odds",
                    "per_page": 50, "sort": "starting_at", "page": page,
                }
                r = requests.get(f"{BASE}/fixtures", params=params, timeout=60)
                r.raise_for_status()
                d = r.json()
                for f in d.get("data", []):
                    flat = flatten_fixture(f)
                    if flat and flat["home_goals"] is not None and flat["away_goals"] is not None:
                        flat["season"] = nome_temp
                        fh.write(__import__("json").dumps(flat) + "\n")
                        total += 1
                fh.flush()
                pag = d.get("pagination", {})
                if not pag.get("has_more"):
                    break
                page += 1
                time.sleep(0.2)
    return total


def puxar_fixtures_futuros(tok, league_id, dias_a_frente=10):
    """Retorna (não grava em arquivo — é sempre "fresco") a lista de
    fixtures ainda não jogados nos próximos `dias_a_frente` dias, já
    achatados (`flatten_fixture`), com as odds pré-jogo disponíveis."""
    import datetime
    import json as json_mod

    hoje = datetime.date.today()
    ate = hoje + datetime.timedelta(days=dias_a_frente)
    resultado = []
    page = 1
    while True:
        params = {
            "api_token": tok,
            "filters": f"fixtureLeagues:{league_id};markets:{MARKETS}",
            "include": "scores;participants;referees;odds",
            "per_page": 50, "page": page,
        }
        r = requests.get(f"{BASE}/fixtures/between/{hoje.isoformat()}/{ate.isoformat()}", params=params, timeout=60)
        r.raise_for_status()
        d = r.json()
        for f in d.get("data", []):
            flat = flatten_fixture(f)
            if flat and flat["home_goals"] is None:  # ainda não jogado
                resultado.append(flat)
        pag = d.get("pagination", {})
        if not pag.get("has_more"):
            break
        page += 1
        time.sleep(0.2)
    return resultado
