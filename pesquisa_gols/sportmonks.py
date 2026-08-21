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
import time
from datetime import date, timedelta

import requests

MAX_DIAS_POR_JANELA = 100  # /fixtures/between rejeita (422) períodos acima disso

BASE_URL = "https://api.sportmonks.com/v3/football"
CORE_BASE_URL = "https://api.sportmonks.com/v3/core"  # /types vive aqui, não em /football


def _token():
    token = os.environ.get("SPORTMONKS_TOKEN")
    if not token:
        raise RuntimeError(
            "Defina a variável de ambiente SPORTMONKS_TOKEN antes de rodar "
            "(ex.: export SPORTMONKS_TOKEN=... no terminal, nesta sessão)."
        )
    return token


def _get(path, params=None, base_url=BASE_URL, tentativas=5):
    # token vai no header, não na query string: se a chamada falhar, a exceção
    # do requests inclui a URL na mensagem — com o token como query param, ele
    # vazaria em texto puro em qualquer log/traceback.
    for tentativa in range(1, tentativas + 1):
        r = requests.get(
            f"{base_url}{path}", params=params or {}, timeout=20,
            headers={"Authorization": _token()},
        )
        if r.status_code == 429 and tentativa < tentativas:
            espera = int(r.headers.get("Retry-After", 5 * tentativa))
            print(f"  [rate limit] esperando {espera}s antes de tentar de novo ({path})...")
            time.sleep(espera)
            continue
        try:
            r.raise_for_status()
        except requests.HTTPError:
            raise requests.HTTPError(f"Sportmonks respondeu {r.status_code} em {path}") from None
        return r.json()
    raise requests.HTTPError(f"Sportmonks respondeu 429 repetidamente em {path}, desisti após {tentativas} tentativas")


def _janelas_de_data(date_from, date_to, max_dias=MAX_DIAS_POR_JANELA):
    """Quebra [date_from, date_to] em pedaços de até max_dias dias (/fixtures/between rejeita janelas maiores)."""
    inicio = date.fromisoformat(date_from)
    fim = date.fromisoformat(date_to)
    atual = inicio
    while atual <= fim:
        fim_janela = min(atual + timedelta(days=max_dias - 1), fim)
        yield atual.isoformat(), fim_janela.isoformat()
        atual = fim_janela + timedelta(days=1)


def _fixtures_da_liga_janela(league_id, date_from, date_to):
    fixtures = []
    pagina = 1
    while True:
        data = _get(
            f"/fixtures/between/{date_from}/{date_to}",
            {
                "include": "round;participants;scores",
                "per_page": 50, "page": pagina,
                "filters": f"fixtureLeagues:{league_id}",
            },
        )
        fixtures.extend(data.get("data", []))
        if not data.get("pagination", {}).get("has_more"):
            break
        pagina += 1
    return fixtures


def fixtures_da_liga(league_id, date_from, date_to):
    """
    Fixtures de uma liga entre duas datas ISO (YYYY-MM-DD), com round/participants/scores.

    Usa o filtro `fixtureLeagues` do lado do servidor (sem ele, /fixtures/between
    devolve TODAS as ligas do período, paginado de 50 em 50 — inviável pra um
    período de meses). O período pedido é quebrado em janelas de até
    MAX_DIAS_POR_JANELA dias, porque a API rejeita (422) períodos maiores.
    """
    fixtures = []
    for de, ate in _janelas_de_data(date_from, date_to):
        fixtures.extend(_fixtures_da_liga_janela(league_id, de, ate))
    return fixtures


def fixture_com_trends(fixture_id):
    """Trends (progressão minuto a minuto) + estatísticas + eventos de uma fixture."""
    data = _get(
        f"/fixtures/{fixture_id}",
        {"include": "trends;statistics.type;participants;scores;events;round"},
    )
    return data.get("data")


def mapa_types():
    """
    nome do type -> type_id (usado para ler os trends por estatística).

    A Sportmonks ignora per_page grande e sempre pagina de 25 em 25 nesse
    endpoint (confirmado: per_page=1000 pedido, per_page=25 devolvido) — dá
    pra ter ~1250 types no total, então precisa passear pelas páginas até
    `has_more` virar False.
    """
    tipos = {}
    pagina = 1
    while True:
        data = _get("/types", {"page": pagina}, base_url=CORE_BASE_URL)
        for t in data.get("data", []):
            tipos[t["name"]] = t["id"]
        if not data.get("pagination", {}).get("has_more"):
            break
        pagina += 1
    return tipos
