"""
Wrapper fino sobre a API da Sportmonks.
Centraliza autenticação, includes e tratamento de erro/paginação.
"""
import requests
import config


def _get(path, params=None):
    params = dict(params or {})
    params["api_token"] = config.SPORTMONKS_TOKEN
    url = f"{config.BASE_URL}{path}"
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def fixtures_between(date_from, date_to, include="participants;league;scores"):
    """Todas as fixtures (das ligas assinadas) entre duas datas ISO (YYYY-MM-DD)."""
    data = _get(f"/fixtures/between/{date_from}/{date_to}", {"include": include})
    return data.get("data", [])


def fixture_by_id(fixture_id, include=""):
    data = _get(f"/fixtures/{fixture_id}", {"include": include})
    return data.get("data")


def team_recent_fixtures(team_id, n, include="statistics.type;participants;scores", dias_para_tras=180, ate_data=None):
    """
    Últimos N jogos finalizados de um time, com estatísticas.
    Usado para montar o perfil (médias) do time.

    ate_data: se informado (string YYYY-MM-DD), limita a busca a jogos ATÉ essa data —
    essencial para backtest, evitando usar informação futura (lookahead bias) ao montar
    o perfil de um time para uma partida do passado.

    A Sportmonks v3 não tem um filtro direto de "fixtures por time" no endpoint
    genérico /fixtures — o caminho correto é o endpoint dedicado
    /fixtures/between/{data_inicio}/{data_fim}/{team_id}.
    """
    from datetime import date, timedelta

    fim_ref = date.fromisoformat(ate_data) if ate_data else date.today()
    inicio = (fim_ref - timedelta(days=dias_para_tras)).isoformat()
    fim = fim_ref.isoformat()

    data = _get(
        f"/fixtures/between/{inicio}/{fim}/{team_id}",
        {"include": include},
    )
    fixtures = data.get("data", [])

    finalizados = [f for f in fixtures if f.get("state_id") == 5]
    finalizados.sort(key=lambda f: f.get("starting_at", ""), reverse=True)

    return finalizados[:n]


def all_types():
    """Lista completa de tipos (usada para mapear nome de estatística -> type_id, para trends)."""
    data = _get("/types", {"per_page": 1000})
    return data.get("data", [])


def fixture_com_trends(fixture_id, include="trends;statistics.type;participants;scores;league;events"):
    data = _get(f"/fixtures/{fixture_id}", {"include": include})
    return data.get("data")


def fixtures_finalizadas_ligas(dias_para_tras=30):
    """Jogos já finalizados das ligas monitoradas, dentro da janela de dias informada."""
    from datetime import date, timedelta

    hoje = date.today()
    inicio = (hoje - timedelta(days=dias_para_tras)).isoformat()
    fim = hoje.isoformat()

    fixtures = fixtures_between(inicio, fim, include="league;participants")
    return [
        f for f in fixtures
        if f.get("state_id") == 5 and f.get("league", {}).get("id") in config.LIGAS_MONITORADAS
    ]


def live_fixtures(include="statistics.type;participants;league;scores;periods"):
    """Fixtures atualmente ao vivo (dentro das ligas assinadas)."""
    data = _get("/livescores/inplay", {"include": include})
    return data.get("data", [])
