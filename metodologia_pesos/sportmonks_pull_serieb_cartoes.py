"""Atualiza `data/sportmonks_serieb_cartoes/fixtures.jsonl` — dado de
árbitro (`referee_id`) e odds do mercado "Number of Cards" (market_id=255)
pra Série B, usado pelo 3º critério (stake reduzido) descrito em
`docs/protocolo.md` (seção "Terceiro critério") e checado semanalmente
por `checar_decaimento.py`.

Mesmo espírito de como os CSVs do FootyStats são atualizados: Lucas
roda este script de novo (com `SPORTMONKS_TOKEN` no ambiente) quando
quiser atualizar o dado — não é uma chamada de API a cada checagem.

Uso: `SPORTMONKS_TOKEN=... python3 sportmonks_pull_serieb_cartoes.py`

Plano gratuito do Sportmonks só retém as últimas 3 temporadas fechadas
mais a corrente — rodar de novo periodicamente vai naturalmente trazer
temporadas novas e (quando o plano permitir) substituir as mais antigas.
"""
from __future__ import annotations

import json
import os
import time

import requests

BASE = "https://api.sportmonks.com/v3/football"
LEAGUE_ID_SERIE_B = 651
MARKET_NUMBER_OF_CARDS = 255
STAT_TYPE_YELLOWCARDS = 84
STAT_TYPE_REDCARDS = 83
REFEREE_TYPE_PRINCIPAL = 6

CAMINHO_SAIDA = "data/sportmonks_serieb_cartoes/fixtures.jsonl"


def _token():
    token = os.environ.get("SPORTMONKS_TOKEN")
    if not token:
        raise RuntimeError(
            "SPORTMONKS_TOKEN não está definido no ambiente — exporte o token "
            "antes de rodar este script (nunca hardcodear no código)."
        )
    return token


def descobrir_temporadas(token, league_id):
    r = requests.get(f"{BASE}/leagues/{league_id}", params={"api_token": token, "include": "seasons"}, timeout=30)
    r.raise_for_status()
    return {s["name"]: s["id"] for s in r.json()["data"]["seasons"]}


def _flatten_fixture(f):
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
    if home["id"] not in scores.get("CURRENT", {}) or away["id"] not in scores.get("CURRENT", {}):
        return None  # jogo não finalizado

    cartoes = {home["id"]: 0, away["id"]: 0}
    for s in f.get("statistics") or []:
        if s.get("type_id") not in (STAT_TYPE_YELLOWCARDS, STAT_TYPE_REDCARDS):
            continue
        pid = s.get("participant_id")
        val = (s.get("data") or {}).get("value")
        if pid in cartoes and val is not None:
            cartoes[pid] += val

    referee_id = None
    for ref in f.get("referees") or []:
        if ref.get("type_id") == REFEREE_TYPE_PRINCIPAL:
            referee_id = ref.get("referee_id")
            break

    odds = {}
    for o in f.get("odds") or []:
        if o.get("market_id") != MARKET_NUMBER_OF_CARDS:
            continue
        odds.setdefault(str(MARKET_NUMBER_OF_CARDS), []).append(dict(
            bookmaker_id=o.get("bookmaker_id"), label=o.get("label"),
            total=o.get("total"), value=o.get("value"),
        ))

    return dict(
        fixture_id=f["id"], date=f["starting_at"],
        home_team=home["name"], away_team=away["name"],
        cartoes_casa=cartoes[home["id"]], cartoes_fora=cartoes[away["id"]],
        referee_id=referee_id, odds=odds,
    )


def pull(out_path=CAMINHO_SAIDA):
    token = _token()
    temporadas = descobrir_temporadas(token, LEAGUE_ID_SERIE_B)
    print(f"Série B: temporadas disponíveis {temporadas}", flush=True)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    total = 0
    with open(out_path, "w") as fh:
        for nome_temp, season_id in temporadas.items():
            page = 1
            while True:
                params = {
                    "api_token": token,
                    "filters": f"fixtureLeagues:{LEAGUE_ID_SERIE_B};fixtureSeasons:{season_id};markets:{MARKET_NUMBER_OF_CARDS}",
                    "include": "scores;participants;statistics;referees;odds",
                    "per_page": 50,
                    "sort": "starting_at",
                    "page": page,
                }
                r = requests.get(f"{BASE}/fixtures", params=params, timeout=60)
                r.raise_for_status()
                d = r.json()
                batch = d.get("data", [])
                for f in batch:
                    flat = _flatten_fixture(f)
                    if flat:
                        fh.write(json.dumps(flat) + "\n")
                        total += 1
                fh.flush()
                pag = d.get("pagination", {})
                print(f"  {nome_temp}: página {page}, {len(batch)} fixtures brutos, total_salvo={total}", flush=True)
                if not pag.get("has_more"):
                    break
                page += 1
                time.sleep(0.3)
    return total


if __name__ == "__main__":
    total = pull()
    print(f"SALVO {total} fixtures em {CAMINHO_SAIDA}", flush=True)
