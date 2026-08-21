"""
Cliente mínimo para a API da Sportmonks — só o necessário pra buscar_sportmonks.py.

Inspirado em ligas_live_app/sportmonks_client.py (mesmos endpoints e padrões),
mas independente dele: pesquisa_gols/ fica isolado do ligas_live_app por
decisão de fases (ver README.md), então este módulo não importa nada de lá.

O token NUNCA tem valor-padrão hardcoded — precisa vir da variável de
ambiente SPORTMONKS_TOKEN. Isso evita o risco de alguém commitar um token
sem querer (o que aconteceria com um default tipo "COLE_SEU_TOKEN_AQUI").
"""
import os

import requests

BASE_URL = "https://api.sportmonks.com/v3/football"


def _token():
    token = os.environ.get("SPORTMONKS_TOKEN")
    if not token:
        raise RuntimeError(
            "Defina a variável de ambiente SPORTMONKS_TOKEN antes de rodar "
            "(ex.: export SPORTMONKS_TOKEN=... no terminal, nesta sessão)."
        )
    return token


def _get(path, params=None):
    params = dict(params or {})
    params["api_token"] = _token()
    r = requests.get(f"{BASE_URL}{path}", params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def fixtures_da_liga(league_id, date_from, date_to):
    """Fixtures de uma liga entre duas datas ISO (YYYY-MM-DD), com round/participants/scores."""
    data = _get(
        f"/fixtures/between/{date_from}/{date_to}",
        {"include": "round;participants;scores", "per_page": 50},
    )
    fixtures = data.get("data", [])
    return [f for f in fixtures if f.get("league_id") == league_id]


def fixture_com_trends(fixture_id):
    """Trends (progressão minuto a minuto) + estatísticas + eventos de uma fixture."""
    data = _get(
        f"/fixtures/{fixture_id}",
        {"include": "trends;statistics.type;participants;scores;events;round"},
    )
    return data.get("data")


def mapa_types():
    """nome do type -> type_id (usado para ler os trends por estatística)."""
    data = _get("/types", {"per_page": 1000})
    return {t["name"]: t["id"] for t in data.get("data", [])}
