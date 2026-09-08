"""
Wrapper fino sobre a API da Sportmonks.
Centraliza autenticação, includes e tratamento de erro/paginação.
"""
import time

import requests
import config

CORE_BASE_URL = "https://api.sportmonks.com/v3/core"  # /types vive aqui, não em /football
ODDS_BASE_URL = "https://api.sportmonks.com/v3/odds"  # odds vivem numa base própria, não em /football nem /core

TENTATIVAS_429 = 3
ESPERA_MAXIMA_429 = 15  # segundos — nunca confiar cegamente no Retry-After da API


class RateLimitError(Exception):
    """
    Levantado quando a API pede uma espera longa (Retry-After > ESPERA_MAXIMA_429)
    — sinal de cota realmente estourada, não um soluço passageiro. Descoberto
    rodando analise_btts_3temporadas.py em paralelo (20 threads): a Sportmonks
    respondeu Retry-After=1281s (~21min), e como _get antes dormia esse valor
    cru, as 20 threads travaram simultaneamente por ~21min — paralelizar sem
    esse teto piora o problema (estoura a cota mais rápido, trava mais threads
    de uma vez). Quem chama decide o que fazer (não insiste sozinho aqui):
    normalmente esperar de verdade fora do _get, ou reduzir a concorrência.
    """
    def __init__(self, retry_after):
        self.retry_after = retry_after
        super().__init__(f"Rate limit: API pediu espera de {retry_after}s")


def _get(path, params=None, base_url=None):
    # Token vai no header, não na query string: se a chamada falhar, a exceção
    # do requests inclui a URL na mensagem — com o token como query param, ele
    # vazaria em texto puro em qualquer log/traceback (já aconteceu antes desta
    # correção). raise_for_status() também é evitado por isso: sua mensagem
    # inclui a URL completa da requisição.
    for tentativa in range(TENTATIVAS_429):
        r = requests.get(
            f"{base_url or config.BASE_URL}{path}", params=params or {}, timeout=20,
            headers={"Authorization": config.SPORTMONKS_TOKEN},
        )
        if r.status_code == 429:
            retry_after = float(r.headers.get("Retry-After", 2 * (tentativa + 1)))
            if retry_after > ESPERA_MAXIMA_429:
                raise RateLimitError(retry_after)  # cota estourada de verdade — não adianta insistir aqui
            if tentativa < TENTATIVAS_429 - 1:
                time.sleep(retry_after)
                continue
        break
    try:
        r.raise_for_status()
    except requests.HTTPError:
        raise requests.HTTPError(f"Sportmonks respondeu {r.status_code} em {path}") from None
    return r.json()


def fixtures_between(date_from, date_to, include="participants;league;scores"):
    """
    Todas as fixtures (das ligas assinadas) entre duas datas ISO (YYYY-MM-DD).
    Pagina até o fim (a API devolve só 25 por página, "has_more"/"next_page"
    em "pagination") — sem isso, qualquer janela com mais de 25 jogos ficava
    silenciosamente truncada na primeira página, sem erro nem aviso (bug
    real encontrado analisando BTTS pré-live: backtest.py/fixtures_finalizadas_ligas
    vinham usando só os 25 jogos mais recentes de cada janela, não a janela
    inteira pedida).
    """
    todas = []
    page = 1
    while True:
        data = _get(f"/fixtures/between/{date_from}/{date_to}", {"include": include, "page": page})
        todas.extend(data.get("data", []))
        if not data.get("pagination", {}).get("has_more"):
            break
        page += 1
    return todas


def fixture_by_id(fixture_id, include=""):
    data = _get(f"/fixtures/{fixture_id}", {"include": include})
    return data.get("data")


def team_recent_fixtures(team_id, n, include="statistics.type;participants;scores", dias_para_tras=180, ate_data=None):
    """
    Últimos N jogos finalizados de um time, com estatísticas.
    Usado para montar o perfil (médias) do time.

    ate_data: se informado (string YYYY-MM-DD), limita a busca a jogos ANTES dessa
    data (exclusive) — essencial para backtest, evitando usar informação futura
    (lookahead bias) ao montar o perfil de um time para uma partida do passado.

    BUG REAL já encontrado com isso (ver conversa, análise BTTS/Over-Under 3
    temporadas): a versão anterior usava `fim = ate_data` (INCLUSIVE) — como
    "ate_data" é sempre a própria data da partida sendo analisada, e essa
    partida já está com state_id=5 (finalizada) no momento em que rodamos o
    backtest, ela mesma entrava na lista de "jogos recentes" do time,
    contaminando o perfil com o PRÓPRIO resultado que estávamos tentando
    prever. Isso inflava artificialmente qualquer backtest que use
    ate_data (aqui e em backtest.py) — ROI/acurácia saíam bons demais pra
    serem reais (chegou a dar +40% de ROI contra a bet365 em todas as 5
    ligas, o que não se sustenta metodologicamente).

    A Sportmonks v3 não tem um filtro direto de "fixtures por time" no endpoint
    genérico /fixtures — o caminho correto é o endpoint dedicado
    /fixtures/between/{data_inicio}/{data_fim}/{team_id}.
    """
    from datetime import date, timedelta

    fim_ref = (date.fromisoformat(ate_data) - timedelta(days=1)) if ate_data else date.today()
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
    """
    Jogos já finalizados das ligas monitoradas, dentro da janela de dias informada.
    Inclui "scores" — sem isso, o campo vem AUSENTE do dict (não None), então
    qualquer leitura direta de placar teria que re-buscar cada fixture de novo
    (como backtest.py já faz via fixture_com_trends); com scores aqui, quem só
    precisa do placar final (não de trends) pode usar o resumo direto.
    """
    from datetime import date, timedelta

    hoje = date.today()
    inicio = (hoje - timedelta(days=dias_para_tras)).isoformat()
    fim = hoje.isoformat()

    fixtures = fixtures_between(inicio, fim, include="league;participants;scores")
    return [
        f for f in fixtures
        if f.get("state_id") == 5 and f.get("league", {}).get("id") in config.LIGAS_MONITORADAS
    ]


def live_fixtures(include="statistics.type;participants;league;scores;periods"):
    """Fixtures atualmente ao vivo (dentro das ligas assinadas)."""
    data = _get("/livescores/inplay", {"include": include})
    return data.get("data", [])


def odds_inplay_fixture(fixture_id):
    """
    Linhas de odds AO VIVO (mercado x casa x label) de uma fixture, via o
    endpoint dedicado /odds/inplay/fixtures/{id}.

    BUG REAL corrigido aqui (ver conversa, investigação sobre "conseguir mais
    odds reais"): a versão anterior deste método concluiu que esse endpoint
    "sempre devolve no access" e caiu para /fixtures/{id}?include=odds como
    workaround — mas o teste original chamava ESSE MESMO path relativo
    ("/odds/inplay/fixtures/{id}") com base_url=ODDS_BASE_URL
    ("https://api.sportmonks.com/v3/odds"), montando
    ".../v3/odds/odds/inplay/fixtures/{id}" — "odds" duplicado na URL, por
    isso o erro. O caminho certo é sob a base normal de football (BASE_URL,
    o padrão desta função): "https://api.sportmonks.com/v3/football/odds/inplay/fixtures/{id}".

    A diferença não é cosmética: /fixtures/{id}?include=odds devolve uma
    mistura de odds pré-jogo e ao vivo com timestamps confusos (na prática,
    quase sempre a última atualização parece travada perto do apito, dando a
    falsa impressão de que a odd "não muda ao vivo"). Este endpoint dedicado
    devolve SÓ as linhas realmente negociadas ao vivo, com "created_at" e
    "latest_bookmaker_update" refletindo o jogo de verdade — testado contra
    jogos reais e confirmado: linha de escanteios (bet365) se movendo de 10
    para 7 ao longo da partida, linha de cartões abrindo/fechando várias
    vezes (3.5→4.5→5.5→6.5→7.5→8.5) conforme o jogo ficou mais truncado.

    NOTA: para escanteios, o mercado ao vivo real do bet365 aparece aqui só
    sob market_id 68 (linha inteira, Over/Exactly/Under) — nunca 67 (que na
    prática só tem dado pré-jogo) — o que já é coberto pelo fallback
    MARKET_ID_FALLBACK_ESCANTEIOS existente em odds_ao_vivo.py.
    """
    data = _get(f"/odds/inplay/fixtures/{fixture_id}")
    return data.get("data") or []


_cache_bookmakers = {}


def bookmakers_mapa():
    """id -> nome da casa de apostas. Cacheado em memória (não muda durante a vida do processo)."""
    if _cache_bookmakers:
        return _cache_bookmakers
    pagina = 1
    while True:
        data = _get("/bookmakers", {"per_page": 100, "page": pagina}, base_url=ODDS_BASE_URL)
        for b in data.get("data", []):
            _cache_bookmakers[b["id"]] = b["name"]
        if not data.get("pagination", {}).get("has_more"):
            break
        pagina += 1
    return _cache_bookmakers
