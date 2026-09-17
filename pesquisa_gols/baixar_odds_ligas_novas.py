"""
Baixa o histórico de odds ao vivo (bet365) das três ligas novas — MLS (779),
Liga Profesional Argentina (636) e Championship (9) — pro cache local, que
hoje só cobre o Brasil.

Sem isso não dá pra medir ROI real nessas ligas, e medir ROI real é justamente
o método que vai decidir o piso de confirmação (ver descobrir_ligas_novas.py):
o teste estatístico sozinho já se mostrou insuficiente — as regras nórdicas
passavam nele e renderam -47,1% contra odds de verdade.

NÃO paralelizado de propósito, ao contrário da descoberta: aqui o gargalo é o
rate limit da API (2.000 chamadas/hora), não CPU. Mais processos só
competiriam pelo mesmo teto e multiplicariam os 429.

Seguro rodar junto com a descoberta: aquela é CPU-bound e já não faz chamada
de API (lê tudo de checkpoint), esta é rede-bound. Também não há risco de
corrupção por concorrência — cada fixture vira um arquivo próprio
({fixture_id}.json), diferente do checkpoint único que a busca de dados grava.

Uso: python3 baixar_odds_ligas_novas.py
"""
import json
import os
import time

import requests

import config

TOKEN = os.environ["SPORTMONKS_TOKEN"]
BASE_URL = "https://api.sportmonks.com/v3/football"
CACHE_ODDS_DIR = os.path.join(config.DIR_DADOS, "cache_odds_historico")
MAX_TENTATIVAS = 5
INTERVALO = 0.2

LIGAS = {779: "MLS", 636: "Liga Profesional Argentina", 9: "Championship"}


def _baixar(fixture_id):
    """Devolve True se baixou agora, False se já estava em cache."""
    caminho = os.path.join(CACHE_ODDS_DIR, f"{fixture_id}.json")
    if os.path.exists(caminho):
        return False

    for tentativa in range(MAX_TENTATIVAS):
        try:
            r = requests.get(f"{BASE_URL}/odds/inplay/fixtures/{fixture_id}",
                             params={"api_token": TOKEN}, timeout=30)
            if r.status_code == 429:
                espera = 10 * (tentativa + 1)
                print(f"    [rate limit] esperando {espera}s...", flush=True)
                time.sleep(espera)
                continue
            r.raise_for_status()
            dados = r.json().get("data") or []
            os.makedirs(CACHE_ODDS_DIR, exist_ok=True)
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump(dados, f)
            return True
        except requests.exceptions.RequestException as e:
            if tentativa == MAX_TENTATIVAS - 1:
                print(f"    [ERRO] fixture {fixture_id}: {e} — segue sem ela", flush=True)
                return False
            espera = 5 * (tentativa + 1)
            print(f"    [erro de conexão: {e}] esperando {espera}s...", flush=True)
            time.sleep(espera)
    return False


def rodar():
    for league_id, nome in LIGAS.items():
        caminho_ckpt = os.path.join(config.DIR_DADOS, f".checkpoint_{league_id}.json")
        d = json.load(open(caminho_ckpt, encoding="utf-8"))
        fixtures = sorted(int(k) for k in d["resultados_alvo"])
        ja = sum(1 for f in fixtures if os.path.exists(os.path.join(CACHE_ODDS_DIR, f"{f}.json")))
        print(f"\n{'='*60}\n{nome} ({league_id}): {len(fixtures)} fixtures, {ja} já em cache\n{'='*60}", flush=True)

        baixadas = 0
        for i, fid in enumerate(fixtures, 1):
            if _baixar(fid):
                baixadas += 1
                time.sleep(INTERVALO)
            if i % 100 == 0:
                print(f"  [{nome} {i}/{len(fixtures)}] {baixadas} baixadas nesta execução", flush=True)
        print(f"  {nome}: {baixadas} baixadas, {len(fixtures) - baixadas} já estavam em cache", flush=True)


if __name__ == "__main__":
    rodar()
