"""
Wrapper fino sobre a API da Sportmonks.
Centraliza autenticação, includes e tratamento de erro/paginação.
"""
import requests
import config

CORE_BASE_URL = "https://api.sportmonks.com/v3/core"  # /types vive aqui, não em /football


def _get(path, params=None, base_url=None):
    # Token vai no header, não na query string: se a chamada falhar, a exceção
    # do requests inclui a URL na mensagem — com o token como query param, ele
    # vazaria em texto puro em qualquer log/traceback (já aconteceu antes desta
    # correção). raise_for_status() também é evitado por isso: sua mensagem
    # inclui a URL completa da requisição.
    r = requests.get(
        f"{base_url or config.BASE_URL}{path}", params=params or {}, timeout=20,
        headers={"Authorization": config.SPORTMONKS_TOKEN},
    )
    try:
        r.raise_for_status()
    except requests.HTTPError:
        raise requests.HTTPError(f"Sportmonks respondeu {r.status_code} em {path}") from None
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
    """
    Lista completa de tipos (usada para mapear nome de estatística -> type_id,
    para trends). Vive em /core/types, não em /football — e a API ignora
    per_page grande, paginando sempre de 25 em 25 (confirmado: per_page=1000
    pedido, 25 devolvido) — por isso pagina até has_more virar False.
    """
    tipos = []
    pagina = 1
    while True:
        data = _get("/types", {"page": pagina}, base_url=CORE_BASE_URL)
        tipos.extend(data.get("data", []))
        if not data.get("pagination", {}).get("has_more"):
            break
        pagina += 1
    return tipos


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
