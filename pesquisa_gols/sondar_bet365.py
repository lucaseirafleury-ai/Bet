"""
Sonda se a bet365 realmente publica odds AO VIVO de escanteios, cartões e
chutes (totais/no alvo) para uma liga — usar assim que uma liga nova for
assinada na Sportmonks, ANTES de investir tempo rodando o pesquisa_gols nela.

Por que isso não dá pra saber de antemão: a Sportmonks não publica um
catálogo de "quais mercados a bet365 cobre em qual liga" (testado nesta
sessão: /odds/bookmakers e /odds/markets sob a base football 404; a única
forma de confirmar é consultar fixtures reais já cobertas pela assinatura
atual). Por isso este script pega fixtures FINALIZADAS recentes da liga (já
precisa estar assinada) e olha o histórico de odds ao vivo pra ver se a
bet365 realmente publicou linha pra cada mercado em algum minuto do jogo —
"a Sportmonks tem odds pra essa liga" (coluna genérica de qualquer planilha
de plano) não implica "a bet365 tem odds AO VIVO de X mercado" (achado real
desta sessão: nas nórdicas a bet365 só publica escanteios, nem cartões nem
chutes; no Brasil publica escanteios+cartões, mas nunca chutes, em nenhuma
das 5 ligas monitoradas).

Uso:
    export SPORTMONKS_TOKEN=...
    python3 sondar_bet365.py <league_id> [n_fixtures]

Ex.: python3 sondar_bet365.py 271 15   # liga 271 = Superliga (Dinamarca)
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

TOKEN = os.environ["SPORTMONKS_TOKEN"]
BASE_URL = "https://api.sportmonks.com/v3/football"
ODDS_BASE_URL = "https://api.sportmonks.com/v3/odds"

BET365_ID = 2  # confirmado nesta sessão via /odds/bookmakers -> nome "bet365"

MERCADOS = {
    # market_id 67 (escanteios) só tem dado pré-jogo no endpoint de inplay;
    # ao vivo de verdade é sempre 68 (ver sportmonks_client.odds_inplay_fixture) —
    # mantido no set por segurança, mas 68 é o que realmente aparece.
    "escanteios": {67, 68},
    "cartoes": {255},
    "chutes_totais": {292},
    "chutes_no_alvo": {291},
}


def _get(path, params=None, base_url=None):
    r = requests.get(
        f"{base_url or BASE_URL}{path}", params={**(params or {}), "api_token": TOKEN}, timeout=20,
    )
    r.raise_for_status()
    return r.json()


ESTADO_FINALIZADO = 5  # state_id 5 = FT (confirmado nos dados já capturados nesta sessão)


def fixtures_finalizadas_recentes(league_id, n):
    """/fixtures/between devolve em ordem CRESCENTE de data e pagina 25 por vez
    (ignora per_page maior) — para pegar as mais RECENTES sem paginar a janela
    inteira do começo, busca em janelas de 15 dias, da mais recente pra trás,
    até juntar fixtures suficientes."""
    hoje = datetime.now(timezone.utc).date()
    encontradas = []
    fim_janela = hoje
    for _ in range(6):  # 6 janelas de 15 dias = até 90 dias pro passado
        inicio_janela = fim_janela - timedelta(days=15)
        pagina = 1
        while True:
            d = _get(f"/fixtures/between/{inicio_janela}/{fim_janela}", {"page": pagina})
            dados = d.get("data", [])
            encontradas.extend(
                f for f in dados
                if f.get("league_id") == league_id and f.get("state_id") == ESTADO_FINALIZADO
            )
            if not d.get("pagination", {}).get("has_more"):
                break
            pagina += 1
        if len(encontradas) >= n:
            break
        fim_janela = inicio_janela - timedelta(days=1)
    encontradas.sort(key=lambda f: f.get("starting_at") or "", reverse=True)
    return encontradas[:n]


def sondar(league_id, n_fixtures=15):
    print(f"Buscando {n_fixtures} fixtures recentes da liga {league_id}...")
    try:
        fixtures = fixtures_finalizadas_recentes(league_id, n_fixtures)
    except requests.exceptions.HTTPError as e:
        corpo = e.response.text[:300] if e.response is not None else str(e)
        print(f"[erro] não consegui buscar fixtures dessa liga — provavelmente não está na assinatura atual:\n  {corpo}")
        return
    if not fixtures:
        print("Nenhuma fixture finalizada encontrada nos últimos 90 dias — liga sem jogos recentes ou fora de temporada.")
        return

    print(f"{len(fixtures)} fixtures encontradas. Consultando odds ao vivo de cada uma...\n")
    presente = {alvo: 0 for alvo in MERCADOS}
    erros = 0

    for f in fixtures:
        fid = f["id"]
        try:
            # Base football (não a base /v3/odds — o path já começa com
            # "/odds/...", duplicar a base dá 404, ver sportmonks_client.py).
            d = _get(f"/odds/inplay/fixtures/{fid}")
        except requests.exceptions.HTTPError:
            erros += 1
            continue
        odds = d.get("data") or []
        odds_bet365 = [o for o in odds if o.get("bookmaker_id") == BET365_ID]
        for alvo, market_ids in MERCADOS.items():
            if any(o.get("market_id") in market_ids for o in odds_bet365):
                presente[alvo] += 1

    n = len(fixtures)
    print(f"{'='*60}\nCobertura bet365 — liga {league_id} ({n} fixtures, {erros} erros de API)\n{'='*60}")
    for alvo, count in presente.items():
        print(f"  {alvo:16s}: {count}/{n}")

    print(
        "\nLeitura: X/N significa 'a bet365 publicou pelo menos uma odd ao vivo "
        "desse mercado em X das N fixtures testadas'. 0/N = mercado não coberto "
        "por essa casa nessa liga (mesmo que a Sportmonks tenha o dado)."
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    liga_id = int(sys.argv[1])
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 15
    sondar(liga_id, n)
