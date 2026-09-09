"""
Mesmo backtest de backtest_odds_reais.py, mas quebrando o resultado por
(liga, ano da temporada) em vez de (regiao, confirmacoes) — pedido depois
de aprovar o candidato de 105 regras (confirmacoes>=3 pro Brasil): o ROI
agregado (+5.6%, 159 apostas) esconde se o edge é uniforme entre ligas e
ao longo do tempo, ou concentrado num pedaço só.

Só testa as regras que estão HOJE em ligas_live_app/regras_sinais.json —
se isso já é o candidato de 105, o resultado reflete só ele. Reaproveita
o cache de dados/cache_odds_historico/{fixture_id}.json construído pelas
rodadas anteriores (204 regras e 78 regras), então roda sem custo de API
pra quase todos os jogos.

Uso: python3 backtest_odds_reais_liga_ano.py
"""
import json
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta

import requests

TOKEN = os.environ["SPORTMONKS_TOKEN"]
BASE_URL = "https://api.sportmonks.com/v3/football"
DADOS_DIR = os.path.join(os.path.dirname(__file__), "dados")
REGRAS_PATH = os.path.join(os.path.dirname(__file__), "..", "ligas_live_app", "regras_sinais.json")
CAMINHO_PROGRESSO = os.path.join(DADOS_DIR, ".checkpoint_backtest_liga_ano.json")
CACHE_ODDS_DIR = os.path.join(DADOS_DIR, "cache_odds_historico")

FREQ_SALVAMENTO = 25
MAX_TENTATIVAS = 4

LIGAS_NOME = {573: "Allsvenskan", 579: "Superettan", 447: "1. Division", 648: "Série A", 651: "Série B"}
LIGAS_ID = list(LIGAS_NOME)
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
    print(f"{len(regras)} regras de escanteios/cartões (de {payload['total_regras']} totais) entram no teste\n")

    dados_por_liga = {}
    for lid in LIGAS_ID:
        dados_por_liga[lid] = json.load(open(os.path.join(DADOS_DIR, f".checkpoint_{lid}.json"), encoding="utf-8"))

    candidatos = []
    for lid, d in dados_por_liga.items():
        for fid_str, jogo in d["jogos"].items():
            fid = int(fid_str)
            if not jogo.get("finalizado") or fid_str not in d["resultados_alvo"]:
                continue
            ano = jogo["data_hora"][:4]
            candidatos.append((fid, lid, ano, jogo["data_hora"], d))

    print(f"Total de jogos finalizados nas 5 ligas: {len(candidatos)}\n")

    estado = _carregar_progresso()
    buckets = estado["buckets"]
    processados = estado["processados"]
    erros_api = estado["erros_api"]

    pendentes = [c for c in candidatos if c[0] not in processados]
    print(f"Pendentes nesta execução: {len(pendentes)}\n")

    for i, (fid, lid, ano, data_hora_str, dados_liga) in enumerate(pendentes):
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
        time.sleep(0.05)

        for regra in regras:
            if not _liga_aceita_regra(regra["regiao"], lid):
                continue
            snap = snaps.get(regra["minuto"])
            if not snap or snap.get("gols_momento") != regra["gols_momento"]:
                continue
            if not _condicao_bate(regra["condicoes"], snap):
                continue

            chave_bucket = f"{LIGAS_NOME[lid]}_{ano}"
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

    print(f"\n{'='*78}\nResumo por liga x ano ({len(processados)}/{len(candidatos)} jogos, {erros_api} erros de API)\n{'='*78}")
    print(f"{'bucket':22s} {'disparos':>9s} {'odd_real':>9s} {'ev+':>6s} {'green':>6s} {'red':>5s} {'taxa%':>7s} {'roi%':>7s}")
    for chave in sorted(buckets):
        b = buckets[chave]
        n = b["green"] + b["red"]
        taxa = 100 * b["green"] / n if n else 0.0
        roi = 100 * b["soma_retorno"] / n if n else 0.0
        print(f"{chave:22s} {b['disparos']:9d} {b['odd_encontrada']:9d} {b['ev_positivo']:6d} "
              f"{b['green']:6d} {b['red']:5d} {taxa:7.1f} {roi:7.1f}")

    print(f"\n{'-'*78}\nAgregado só por liga (todas as temporadas somadas)\n{'-'*78}")
    por_liga = defaultdict(_bucket_vazio)
    for chave, b in buckets.items():
        liga = chave.rsplit("_", 1)[0]
        agg = por_liga[liga]
        for k in agg:
            agg[k] += b[k]
    for liga in sorted(por_liga):
        b = por_liga[liga]
        n = b["green"] + b["red"]
        taxa = 100 * b["green"] / n if n else 0.0
        roi = 100 * b["soma_retorno"] / n if n else 0.0
        print(f"{liga:15s} {b['disparos']:9d} {b['odd_encontrada']:9d} {b['ev_positivo']:6d} "
              f"{b['green']:6d} {b['red']:5d} {taxa:7.1f} {roi:7.1f}")

    print(f"\n{'-'*78}\nAgregado só por ano (todas as ligas somadas)\n{'-'*78}")
    por_ano = defaultdict(_bucket_vazio)
    for chave, b in buckets.items():
        ano = chave.rsplit("_", 1)[1]
        agg = por_ano[ano]
        for k in agg:
            agg[k] += b[k]
    for ano in sorted(por_ano):
        b = por_ano[ano]
        n = b["green"] + b["red"]
        taxa = 100 * b["green"] / n if n else 0.0
        roi = 100 * b["soma_retorno"] / n if n else 0.0
        print(f"{ano:15s} {b['disparos']:9d} {b['odd_encontrada']:9d} {b['ev_positivo']:6d} "
              f"{b['green']:6d} {b['red']:5d} {taxa:7.1f} {roi:7.1f}")


if __name__ == "__main__":
    rodar()
