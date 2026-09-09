"""
Mesmo backtest de backtest_odds_reais.py, mas quebrando o resultado por
(regiao, confirmacoes) em vez de só um número agregado — pedido depois de
achar que o conjunto de 204 regras tem ROI real pior que o de 78 (-6.3% vs
+2.2%, ver conversa): que fatia específica está puxando isso pra baixo?
universal? nórdicas? Brasil de 1/2/3 fontes?

Também CACHEIA o histórico de odds de cada fixture em
dados/cache_odds_historico/{fixture_id}.json — qualquer reanálise futura
(outro corte de regras, outro critério) reaproveita esse cache em vez de
gastar API de novo. Os dois backtests já rodados (204 e 78 regras) não
tinham esse cache ainda, por isso esta rodada volta a gastar API uma vez —
dali em diante, fica de graça.

Uso: python3 backtest_odds_reais_detalhado.py
"""
import json
import os
import time
from datetime import datetime, timedelta

import requests

TOKEN = os.environ["SPORTMONKS_TOKEN"]
BASE_URL = "https://api.sportmonks.com/v3/football"
DADOS_DIR = os.path.join(os.path.dirname(__file__), "dados")
REGRAS_PATH = os.path.join(os.path.dirname(__file__), "..", "ligas_live_app", "regras_sinais.json")
CAMINHO_PROGRESSO = os.path.join(DADOS_DIR, ".checkpoint_backtest_detalhado.json")
CACHE_ODDS_DIR = os.path.join(DADOS_DIR, "cache_odds_historico")

FREQ_SALVAMENTO = 25
MAX_TENTATIVAS = 4

LIGAS_ID = [573, 579, 447, 648, 651]
LIGAS_BRASIL = {648, 651}
LIGAS_NORDICAS = {573, 579, 447}

MARKETS_POR_ALVO = {
    "escanteios": {"principal": 67, "fallback": 68},
    "cartoes": {"principal": 255, "fallback": None},
}


def _get_odds_historico(fixture_id):
    caminho_cache = os.path.join(CACHE_ODDS_DIR, f"{fixture_id}.json")
    if os.path.exists(caminho_cache):
        return json.load(open(caminho_cache, encoding="utf-8"))

    for tentativa in range(MAX_TENTATIVAS):
        try:
            r = requests.get(f"{BASE_URL}/odds/inplay/fixtures/{fixture_id}", params={"api_token": TOKEN}, timeout=30)
            if r.status_code == 429:
                espera = 5 * (tentativa + 1)
                print(f"    [rate limit] esperando {espera}s...")
                time.sleep(espera)
                continue
            r.raise_for_status()
            dados = r.json().get("data") or []
            os.makedirs(CACHE_ODDS_DIR, exist_ok=True)
            with open(caminho_cache, "w", encoding="utf-8") as f:
                json.dump(dados, f)
            return dados
        except requests.exceptions.RequestException as e:
            if tentativa == MAX_TENTATIVAS - 1:
                raise
            espera = 5 * (tentativa + 1)
            print(f"    [erro de conexão: {e}] esperando {espera}s...")
            time.sleep(espera)
    return []


def _condicao_bate(condicoes, snap):
    for c in condicoes:
        v = snap.get(c["stat"])
        if v is None:
            return False
        if c["operador"] == ">=" and v < c["limite"]:
            return False
        if c["operador"] == "<=" and v > c["limite"]:
            return False
    return True


def _liga_aceita_regra(regiao, league_id):
    if regiao == "brasil":
        return league_id in LIGAS_BRASIL
    if regiao == "nordicas":
        return league_id in LIGAS_NORDICAS
    return True


def _achar_odd_real(odds_historico, market_ids, direcao_label, linha, timestamp_checkpoint):
    candidatas = []
    for d in odds_historico:
        if d["market_id"] not in market_ids:
            continue
        if d["label"] != direcao_label:
            continue
        total = d.get("total")
        if total is None:
            continue
        try:
            if abs(float(total) - linha) > 0.01:
                continue
            valor = float(d["value"])
        except (TypeError, ValueError):
            continue
        try:
            ts = datetime.strptime(d["latest_bookmaker_update"], "%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError):
            continue
        if ts > timestamp_checkpoint + timedelta(minutes=5):
            continue
        candidatas.append((ts, valor))
    if not candidatas:
        return None
    candidatas.sort(key=lambda x: x[0])
    return candidatas[-1][1]


def _bucket_vazio():
    return {"disparos": 0, "odd_encontrada": 0, "ev_positivo": 0, "green": 0, "red": 0, "soma_retorno": 0.0}


def _carregar_progresso():
    if os.path.exists(CAMINHO_PROGRESSO):
        d = json.load(open(CAMINHO_PROGRESSO, encoding="utf-8"))
        d["processados"] = set(d["processados"])
        print(f"Retomando de checkpoint anterior: {len(d['processados'])} jogos já processados")
        return d
    return {"processados": set(), "buckets": {}, "erros_api": 0}


def _salvar_progresso(estado):
    out = dict(estado)
    out["processados"] = sorted(estado["processados"])
    with open(CAMINHO_PROGRESSO, "w", encoding="utf-8") as f:
        json.dump(out, f)


def rodar():
    payload = json.load(open(REGRAS_PATH, encoding="utf-8"))
    regras = [r for r in payload["regras"] if r["alvo"] in MARKETS_POR_ALVO]
    print(f"{len(regras)} regras de escanteios/cartões (de {payload['total_regras']} totais) entram no teste")

    dados_por_liga = {}
    for lid in LIGAS_ID:
        dados_por_liga[lid] = json.load(open(os.path.join(DADOS_DIR, f".checkpoint_{lid}.json"), encoding="utf-8"))

    candidatos = []
    for lid, d in dados_por_liga.items():
        for fid_str, jogo in d["jogos"].items():
            fid = int(fid_str)
            if not jogo.get("finalizado") or fid_str not in d["resultados_alvo"]:
                continue
            candidatos.append((fid, lid, jogo["data_hora"], d))

    print(f"Total de jogos finalizados nas 5 ligas: {len(candidatos)}\n")

    estado = _carregar_progresso()
    buckets = estado["buckets"]
    processados = estado["processados"]
    erros_api = estado["erros_api"]

    pendentes = [c for c in candidatos if c[0] not in processados]
    print(f"Pendentes nesta execução: {len(pendentes)}\n")

    for i, (fid, lid, data_hora_str, dados_liga) in enumerate(pendentes):
        if (i + 1) % 200 == 0:
            print(f"  ... {i+1}/{len(pendentes)} processados nesta execução "
                  f"({len(processados)}/{len(candidatos)} no total)")
        kickoff = datetime.strptime(data_hora_str, "%Y-%m-%d %H:%M:%S")
        snaps = {}
        for snap in dados_liga["snapshots"]:
            if snap["fixture_id"] == fid:
                snaps[snap["minuto"]] = snap
        resultado_final = dados_liga["resultados_alvo"][str(fid)]

        try:
            odds_historico = _get_odds_historico(fid)
        except Exception:
            erros_api += 1
            processados.add(fid)
            continue
        time.sleep(0.1)  # cache reduz muito a necessidade de pausa longa, mas mantém alguma gentileza

        for regra in regras:
            if not _liga_aceita_regra(regra["regiao"], lid):
                continue
            snap = snaps.get(regra["minuto"])
            if not snap or snap.get("gols_momento") != regra["gols_momento"]:
                continue
            if not _condicao_bate(regra["condicoes"], snap):
                continue

            chave_bucket = f"{regra['regiao']}_{regra.get('confirmacoes', 1)}"
            bucket = buckets.setdefault(chave_bucket, _bucket_vazio())
            bucket["disparos"] += 1

            alvo = regra["alvo"]
            direcao = regra["mercado"]["direcao"]
            linha = regra["mercado"]["linha"]
            label = "Over" if direcao == "mais_de" else "Under"
            markets_cfg = MARKETS_POR_ALVO[alvo]
            market_ids = {markets_cfg["principal"]} | ({markets_cfg["fallback"]} if markets_cfg["fallback"] else set())

            timestamp_checkpoint = kickoff + timedelta(minutes=regra["minuto"])
            odd = _achar_odd_real(odds_historico, market_ids, label, linha, timestamp_checkpoint)
            if odd is None:
                continue
            bucket["odd_encontrada"] += 1

            p_condicao = regra["prob_condicao_confirmacao"]
            ev_pct = (p_condicao * odd - 1) * 100
            if ev_pct < 0:
                continue
            bucket["ev_positivo"] += 1

            valor_final = resultado_final.get(alvo)
            if valor_final is None:
                continue
            bateu = (valor_final > linha) if direcao == "mais_de" else (valor_final < linha)
            if bateu:
                bucket["green"] += 1
                bucket["soma_retorno"] += (odd - 1)
            else:
                bucket["red"] += 1
                bucket["soma_retorno"] += -1

        processados.add(fid)
        if len(processados) % FREQ_SALVAMENTO == 0:
            _salvar_progresso({"processados": processados, "buckets": buckets, "erros_api": erros_api})

    _salvar_progresso({"processados": processados, "buckets": buckets, "erros_api": erros_api})

    print(f"\n{'='*70}\nResumo detalhado ({len(processados)}/{len(candidatos)} jogos, {erros_api} erros de API)\n{'='*70}")
    print(f"{'bucket':22s} {'disparos':>9s} {'odd_real':>9s} {'ev+':>6s} {'green':>6s} {'red':>5s} {'taxa%':>7s} {'roi%':>7s}")
    for chave in sorted(buckets):
        b = buckets[chave]
        n = b["green"] + b["red"]
        taxa = 100 * b["green"] / n if n else 0.0
        roi = 100 * b["soma_retorno"] / n if n else 0.0
        print(f"{chave:22s} {b['disparos']:9d} {b['odd_encontrada']:9d} {b['ev_positivo']:6d} "
              f"{b['green']:6d} {b['red']:5d} {taxa:7.1f} {roi:7.1f}")


if __name__ == "__main__":
    rodar()
