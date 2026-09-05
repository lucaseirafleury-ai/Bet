"""Cliente HTTP fino pra API do Sportmonks — busca fixtures FINALIZADOS
(pra montar o histórico usado pelo motor de walk-forward,
`retrospectiva.py`) e fixtures FUTUROS (pra prever os jogos do dia,
`previsao_dia.py`). Token via variável de ambiente `SPORTMONKS_TOKEN`,
nunca hardcoded.

Mercados pedidos: 1 (Fulltime Result/1x2 — usado pro favoritismo do
próprio jogo), 80 (Goals Over/Under), 14 (BTTS), 60 (2-Way Corners —
não é critério de produção hoje, mas mantido pra qualquer investigação
futura não precisar de pull ad-hoc; ver
docs/retrospectiva_contra_ataque_bloco_baixo_2026-09-02.md, onde a
ausência desse mercado no filtro atrasou um teste real), 255 (Number
of Cards).
Estatísticas: corners, cartões (amarelo/vermelho), chutes, chutes no
alvo, posse, faltas — tudo que `planilha_lib.get_historico` espera,
menos xG (não existe pra Série A/B no Sportmonks, ver
`sportmonks_adapter.py`).
"""
from __future__ import annotations

import datetime
import json
import os
import time

import requests

BASE = "https://api.sportmonks.com/v3/football"
LEAGUE_IDS = {"seriea": 648, "serieb": 651}
MARKETS = "1,80,14,60,255"

# `state_id` (sempre presente no fixture, não depende de nenhum `include`)
# — únicas fontes confiáveis de "ainda não começou"/"terminou de verdade".
# NUNCA usar `home_goals is None`/`is not None` pra isso: o Sportmonks às
# vezes já publica um placeholder "CURRENT" 0-0 pouco antes do jogo
# começar (confirmado em produção, jogo Goiás x São Bernardo 28/08/2026
# — `state_id` continuava 1/NS, mas `scores` já tinha entrada CURRENT com
# `goals: 0` pros dois lados), o que faz `home_goals`/`away_goals` virarem
# 0 (não None) mesmo pro jogo ainda não ter começado. Ver
# `docs/retrospectiva_estado_fixture_bug_2026-08-28.md`.
ESTADO_NAO_INICIADO = 1  # NS
ESTADOS_FINALIZADOS = {5, 7, 8}  # FT, AET, FT_PEN — resultado final de verdade

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
        referee_id=referee_id, odds=odds, state_id=f.get("state_id"), **stats,
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
                    if flat and flat.get("state_id") in ESTADOS_FINALIZADOS:
                        flat["season"] = nome_temp
                        fh.write(json.dumps(flat) + "\n")
                        total += 1
                fh.flush()
                pag = d.get("pagination", {})
                if not pag.get("has_more"):
                    break
                page += 1
                time.sleep(0.2)
    return total


def atualizar_fixtures_finalizados(tok, league_id, out_path, margem_dias=3):
    """Atualiza `out_path` de forma incremental: se o arquivo já existir,
    busca só os fixtures dos últimos dias via `/fixtures/between` (mesmo
    endpoint usado pra jogos futuros) em vez de rebaixar as ~1000
    fixtures históricas da liga inteira a cada rodada — é isso que fazia
    a rotina diária demorar minutos só pra atualizar o dado. `margem_dias`
    é uma folga de segurança pra recapturar jogos cuja odd/estatística
    ainda não estava completa na última passada. Sem arquivo prévio (1ª
    vez), faz o pull completo de sempre (`puxar_fixtures_finalizados`)."""
    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        return puxar_fixtures_finalizados(tok, league_id, out_path)

    existentes = []
    ids_existentes = set()
    with open(out_path) as fh:
        for l in fh:
            d = json.loads(l)
            existentes.append(d)
            ids_existentes.add(d["fixture_id"])

    data_mais_recente = max(d["date"] for d in existentes)[:10]
    inicio = datetime.date.fromisoformat(data_mais_recente) - datetime.timedelta(days=margem_dias)
    hoje = datetime.date.today()

    novos = 0
    page = 1
    while True:
        params = {
            "api_token": tok,
            "filters": f"fixtureLeagues:{league_id};markets:{MARKETS}",
            "include": "scores;participants;statistics;referees;odds",
            "per_page": 50, "page": page,
        }
        r = requests.get(f"{BASE}/fixtures/between/{inicio.isoformat()}/{hoje.isoformat()}", params=params, timeout=60)
        r.raise_for_status()
        d = r.json()
        for f in d.get("data", []):
            flat = flatten_fixture(f)
            if (
                flat and flat.get("state_id") in ESTADOS_FINALIZADOS
                and flat["fixture_id"] not in ids_existentes
            ):
                flat["season"] = ""  # desconhecida pro pull incremental — só usada pra rótulo cosmético (__src)
                existentes.append(flat)
                ids_existentes.add(flat["fixture_id"])
                novos += 1
        pag = d.get("pagination", {})
        if not pag.get("has_more"):
            break
        page += 1
        time.sleep(0.2)

    with open(out_path, "w") as fh:
        for d in existentes:
            fh.write(json.dumps(d) + "\n")
    return novos


def puxar_fixtures_futuros(tok, league_id, dias_a_frente=10):
    """Retorna (não grava em arquivo — é sempre "fresco") a lista de
    fixtures ainda não jogados nos próximos `dias_a_frente` dias, já
    achatados (`flatten_fixture`), com as odds pré-jogo disponíveis."""
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
            if flat and flat.get("state_id") == ESTADO_NAO_INICIADO:
                resultado.append(flat)
        pag = d.get("pagination", {})
        if not pag.get("has_more"):
            break
        page += 1
        time.sleep(0.2)
    return resultado
