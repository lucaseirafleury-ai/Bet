"""
ROI real (contra odds da bet365) das candidatas confirmadas no piloto de
diferença de gols (experimento_diferenca_gols.py completo) — só escanteios e
chutes_totais têm confirmadas (cartões e chutes_no_alvo: 0).

Reaproveita 100% de dados já baixados, zero custo de API:
- snapshots: dados/diffgols_full/.checkpoint_{573,579,447}.json (têm o campo
  diferenca_gols, ao contrário dos checkpoints reais)
- odds reais: dados/cache_odds_historico/ (populado no backtest de
  confirmações=1, cobre as mesmas 5 ligas incluindo as 3 nórdicas)
- resultado final de cada jogo: mesmos checkpoints acima (resultados_alvo)

Replica a MESMA lógica de matching de mercado corrigida de
backtest_odds_reais_v2.py (linha inteira 3-vias da bet365 pra escanteios via
market_id 68, não só a linha .5 direta) — sem essa correção, o resultado
"zera" artificialmente pra escanteios, como já aconteceu antes nesta sessão.

Regras candidatas são só um conjunto TEMPORÁRIO de teste — não escreve nem
modifica ligas_live_app/regras_sinais.json nem nenhum arquivo real.

Uso: python3 calcular_roi_diferenca_gols.py
"""
import csv
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta

DADOS_DIR = os.path.join(os.path.dirname(__file__), "dados")
RESULTADOS_DIR = os.path.join(os.path.dirname(__file__), "resultados", "diffgols")
CACHE_ODDS_DIR = os.path.join(DADOS_DIR, "cache_odds_historico")
CHECKPOINTS_DIFFGOLS_DIR = os.path.join(DADOS_DIR, "diffgols_full")

LIGAS_NOME = {573: "Allsvenskan", 579: "Superettan", 447: "1. Division"}
LIGAS_ID = list(LIGAS_NOME)

MARKET_ID_POR_ALVO = {"escanteios": 67, "chutes_totais": 292}
MARKET_ID_FALLBACK_ESCANTEIOS = 68


def _tentativas_mercado(alvo, direcao, linha):
    """Réplica exata de odds_ao_vivo._tentativas_mercado / backtest_odds_reais_v2."""
    market_id = MARKET_ID_POR_ALVO.get(alvo)
    if market_id is None:
        return []
    label = "Over" if direcao == "mais_de" else "Under"
    tentativas = [(market_id, label, linha)]
    if alvo == "escanteios":
        total_inteiro = int(linha - 0.5) if direcao == "mais_de" else int(linha + 0.5)
        tentativas.append((market_id, label, total_inteiro))
        tentativas.append((MARKET_ID_FALLBACK_ESCANTEIOS, label, total_inteiro))
    return tentativas


def _parse_mercado(mercado_str):
    """'+7.5' -> ('mais_de', 7.5); '-10.5' -> ('menos_de', 10.5)."""
    sinal, valor = mercado_str[0], float(mercado_str[1:])
    return ("mais_de" if sinal == "+" else "menos_de"), valor


def _carregar_confirmadas(alvo):
    regras = []
    caminho_1 = os.path.join(RESULTADOS_DIR, f"{alvo}_confirmacao_1stat.csv")
    if os.path.exists(caminho_1):
        with open(caminho_1, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["confirmado_bh"] != "True":
                    continue
                direcao, linha = _parse_mercado(r["mercado"])
                regras.append({
                    "alvo": alvo, "minuto": int(r["minuto"]), "diferenca_gols": int(r["gols_momento"]),
                    "mercado": {"direcao": direcao, "linha": linha},
                    "condicoes": [{"stat": r["stat"], "operador": r["operador"], "limite": float(r["limite"])}],
                    "prob_condicao": float(r["p_final_outras_ligas"]),
                })
    caminho_2 = os.path.join(RESULTADOS_DIR, f"{alvo}_confirmacao_2stats.csv")
    if os.path.exists(caminho_2):
        with open(caminho_2, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["confirmado_bh"] != "True":
                    continue
                direcao, linha = _parse_mercado(r["mercado"])
                regras.append({
                    "alvo": alvo, "minuto": int(r["minuto"]), "diferenca_gols": int(r["gols_momento"]),
                    "mercado": {"direcao": direcao, "linha": linha},
                    "condicoes": [
                        {"stat": r["stat1"], "operador": r["operador1"], "limite": float(r["limite1"])},
                        {"stat": r["stat2"], "operador": r["operador2"], "limite": float(r["limite2"])},
                    ],
                    "prob_condicao": float(r["p_conjunta_outras_ligas"]),
                })
    return regras


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


def _achar_odd_real(odds_historico, tentativas, timestamp_checkpoint):
    candidatas = []
    for market_id, label, total_alvo in tentativas:
        for d in odds_historico:
            if d.get("stopped"):
                continue
            if d["market_id"] != market_id or d["label"] != label:
                continue
            total = d.get("total")
            if total is None:
                continue
            try:
                if float(total) != float(total_alvo):
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


def rodar():
    regras = _carregar_confirmadas("escanteios") + _carregar_confirmadas("chutes_totais")
    print(f"{len(regras)} candidatas confirmadas (diferença de gols) entram no teste "
          f"({sum(1 for r in regras if r['alvo']=='escanteios')} escanteios, "
          f"{sum(1 for r in regras if r['alvo']=='chutes_totais')} chutes totais)\n")
    if not regras:
        print("Nenhuma candidata confirmada — nada a testar.")
        return

    dados_por_liga = {}
    for lid in LIGAS_ID:
        caminho = os.path.join(CHECKPOINTS_DIFFGOLS_DIR, f".checkpoint_{lid}.json")
        dados_por_liga[lid] = json.load(open(caminho, encoding="utf-8"))

    bucket = _bucket_vazio()
    sem_cache = 0
    total_jogos = 0

    for lid, d in dados_por_liga.items():
        snaps_por_fixture = defaultdict(dict)
        for snap in d["snapshots"]:
            snaps_por_fixture[snap["fixture_id"]][snap["minuto"]] = snap

        for fid_str, jogo in d["jogos"].items():
            fid = int(fid_str)
            if not jogo.get("finalizado") or fid_str not in d["resultados_alvo"]:
                continue
            total_jogos += 1
            caminho_cache = os.path.join(CACHE_ODDS_DIR, f"{fid}.json")
            if not os.path.exists(caminho_cache):
                sem_cache += 1
                continue
            odds_historico = json.load(open(caminho_cache, encoding="utf-8"))
            kickoff = datetime.strptime(jogo["data_hora"], "%Y-%m-%d %H:%M:%S")
            snaps = snaps_por_fixture.get(fid, {})
            resultado_final = d["resultados_alvo"][fid_str]

            for regra in regras:
                snap = snaps.get(regra["minuto"])
                if not snap or snap.get("diferenca_gols") != regra["diferenca_gols"]:
                    continue
                if not _condicao_bate(regra["condicoes"], snap):
                    continue

                bucket["disparos"] += 1
                alvo = regra["alvo"]
                direcao = regra["mercado"]["direcao"]
                linha = regra["mercado"]["linha"]
                tentativas = _tentativas_mercado(alvo, direcao, linha)

                timestamp_checkpoint = kickoff + timedelta(minutes=regra["minuto"])
                odd = _achar_odd_real(odds_historico, tentativas, timestamp_checkpoint)
                if odd is None:
                    continue
                bucket["odd_encontrada"] += 1

                ev_pct = (regra["prob_condicao"] * odd - 1) * 100
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

    print(f"Jogos processados: {total_jogos} ({sem_cache} sem cache, pulados)\n")
    n = bucket["green"] + bucket["red"]
    taxa = 100 * bucket["green"] / n if n else 0.0
    roi = 100 * bucket["soma_retorno"] / n if n else 0.0
    print(f"{'bucket':30s} {'disparos':>9s} {'odd_real':>9s} {'ev+':>6s} {'green':>6s} {'red':>5s} {'taxa%':>7s} {'roi%':>7s}")
    print(f"{'diferenca_gols (nordicas)':30s} {bucket['disparos']:9d} {bucket['odd_encontrada']:9d} "
          f"{bucket['ev_positivo']:6d} {bucket['green']:6d} {bucket['red']:5d} {taxa:7.1f} {roi:7.1f}")


if __name__ == "__main__":
    rodar()
