"""
Backtest retroativo com odds REAIS de jogos já finalizados — amostra pequena
(ver conversa: antes de gastar a cota inteira de API rodando ~4.000 jogos,
validar o método numa amostra de ~80 primeiro).

Ideia: pra cada jogo já finalizado (temos o resultado final em
resultados_alvo), busca o HISTÓRICO de odds ao vivo
(/odds/inplay/fixtures/{id} — confirmado nesta conversa que a Sportmonks
guarda várias atualizações por jogo, não só a última). Casa os timestamps
desse histórico com os checkpoints (15/30/45/60/75/90') via
kickoff + minuto. Pra cada regra de escanteios/cartões (únicos alvos com
mercado real negociável — chutes_totais/chutes_no_alvo usam market_id
292/291 na Sportmonks mas raramente têm odds ao vivo de verdade, ver
conversa) que dispara naquele checkpoint daquele jogo, acha a odd real mais
próxima (mesmo mercado+linha+direção) e calcula:
  - encontrou odd real? (cobertura)
  - EV positivo com essa odd? (mesmo gate de live_monitor.py)
  - bateu o mercado de verdade? (resultado real do jogo)

Isso dá ROI REAL histórico, não a estimativa teórica de impacto_pp.

CUIDADO: só faz GET em /odds/inplay/fixtures/{id} — não mexe em nenhum
checkpoint, não escreve nada além do relatório final. 1 chamada de API por
jogo da amostra (sem custo por sinal).

Uso: python3 backtest_odds_reais.py
"""
import json
import os
import random
import time
from datetime import datetime, timedelta

import requests

TOKEN = os.environ["SPORTMONKS_TOKEN"]
BASE_URL = "https://api.sportmonks.com/v3/football"
DADOS_DIR = os.path.join(os.path.dirname(__file__), "dados")
REGRAS_PATH = os.path.join(os.path.dirname(__file__), "..", "ligas_live_app", "regras_sinais.json")

TAMANHO_AMOSTRA = 80
CHECKPOINTS = [15, 30, 45, 60, 75, 90]

# market_id principal + fallback por alvo — mesmo mapeamento de
# ligas_live_app/odds_ao_vivo.py::MARKET_ID_POR_ALVO, restrito aos 2 alvos
# que têm mercado real negociável (ver docstring acima).
MARKETS_POR_ALVO = {
    "escanteios": {"principal": 67, "fallback": 68},
    "cartoes": {"principal": 255, "fallback": None},
}

LIGAS_BRASIL = {648, 651}
LIGAS_NORDICAS = {573, 579, 447}


def _get_odds_historico(fixture_id):
    r = requests.get(f"{BASE_URL}/odds/inplay/fixtures/{fixture_id}", params={"api_token": TOKEN}, timeout=30)
    r.raise_for_status()
    return r.json().get("data") or []


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
    """Entre as entradas do(s) market_id(s) dados, acha a odd da linha/direção certas
    com atualização mais próxima (e não muito posterior) ao timestamp do checkpoint —
    evita usar uma odd que só existiu DEPOIS do momento do sinal (vazamento de futuro)."""
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
            continue  # só um pouco de tolerância pra atraso de atualização; nada de futuro
        candidatas.append((ts, valor))
    if not candidatas:
        return None
    candidatas.sort(key=lambda x: x[0])
    return candidatas[-1][1]  # a mais recente ANTES/perto do checkpoint


def rodar():
    payload = json.load(open(REGRAS_PATH, encoding="utf-8"))
    regras = [r for r in payload["regras"] if r["alvo"] in MARKETS_POR_ALVO]
    print(f"{len(regras)} regras de escanteios/cartões (de {payload['total_regras']} totais) entram no teste")

    checkpoints_648 = json.load(open(os.path.join(DADOS_DIR, ".checkpoint_648.json"), encoding="utf-8"))
    checkpoints_651 = json.load(open(os.path.join(DADOS_DIR, ".checkpoint_651.json"), encoding="utf-8"))

    candidatos = []
    for lid, d in [(648, checkpoints_648), (651, checkpoints_651)]:
        for fid_str, jogo in d["jogos"].items():
            fid = int(fid_str)
            if not jogo.get("finalizado") or fid not in d["resultados_alvo"]:
                continue
            candidatos.append((fid, lid, jogo["data_hora"], d))

    random.seed(42)
    amostra = random.sample(candidatos, min(TAMANHO_AMOSTRA, len(candidatos)))
    print(f"Amostra: {len(amostra)} jogos (de {len(candidatos)} finalizados disponíveis)\n")

    stats = {"disparos": 0, "odd_encontrada": 0, "ev_positivo": 0, "green": 0, "red": 0, "soma_retorno": 0.0}
    erros_api = 0

    for i, (fid, lid, data_hora_str, dados_liga) in enumerate(amostra):
        if (i + 1) % 10 == 0:
            print(f"  ... {i+1}/{len(amostra)} jogos processados")
        kickoff = datetime.strptime(data_hora_str, "%Y-%m-%d %H:%M:%S")
        snaps = {}
        for snap in dados_liga["snapshots"]:
            if snap["fixture_id"] == fid:
                snaps[snap["minuto"]] = snap
        resultado_final = dados_liga["resultados_alvo"][str(fid)]

        try:
            odds_historico = _get_odds_historico(fid)
        except Exception as e:
            erros_api += 1
            continue
        time.sleep(0.3)  # gentileza com rate limit

        for regra in regras:
            if not _liga_aceita_regra(regra["regiao"], lid):
                continue
            snap = snaps.get(regra["minuto"])
            if not snap or snap.get("gols_momento") != regra["gols_momento"]:
                continue
            if not _condicao_bate(regra["condicoes"], snap):
                continue

            stats["disparos"] += 1
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
            stats["odd_encontrada"] += 1

            p_condicao = regra["prob_condicao_confirmacao"]
            ev_pct = (p_condicao * odd - 1) * 100
            if ev_pct < 0:
                continue
            stats["ev_positivo"] += 1

            valor_final = resultado_final.get(alvo)
            if valor_final is None:
                continue
            bateu = (valor_final > linha) if direcao == "mais_de" else (valor_final < linha)
            if bateu:
                stats["green"] += 1
                stats["soma_retorno"] += (odd - 1)
            else:
                stats["red"] += 1
                stats["soma_retorno"] += -1

    print(f"\n{'='*70}\nResumo do backtest (amostra de {len(amostra)} jogos, {erros_api} erros de API)\n{'='*70}")
    print(f"Disparos de regra (condição bateu, independente de odd): {stats['disparos']}")
    print(f"  ... com odd real encontrada no histórico: {stats['odd_encontrada']}")
    print(f"  ... com EV positivo contra essa odd real: {stats['ev_positivo']}")
    if stats["ev_positivo"] > 0:
        n_apostas = stats["green"] + stats["red"]
        print(f"\nDas apostas com EV positivo que teriam sido feitas ({n_apostas}):")
        print(f"  green: {stats['green']} | red: {stats['red']} | taxa de acerto: {100*stats['green']/n_apostas:.1f}%")
        print(f"  ROI real (unidades ganhas / apostas, assumindo stake=1): {100*stats['soma_retorno']/n_apostas:.1f}%")
    else:
        print("\nNenhuma aposta com EV positivo encontrada na amostra.")


if __name__ == "__main__":
    rodar()
