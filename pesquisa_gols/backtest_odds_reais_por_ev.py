"""
Mesmo backtest de backtest_odds_reais.py, mas quebrando o resultado por
FAIXA DE EV% (ev_pct = (p_condicao * odd_real - 1) * 100) em vez de
(regiao, confirmacoes) ou (liga, ano) — pergunta do usuário: dentro das
apostas com EV positivo que o painel já filtra, um EV% mais alto
realmente prevê ROI real melhor? É um teste de calibração do próprio
número de EV.

Roda só sobre as regras hoje em ligas_live_app/regras_sinais.json (o
candidato de 105, confirmacoes>=3 pro Brasil) — mantém a coorte limpa
(mistura de confirmacoes diferentes confundiria "EV alto" com "fonte mais
confirmada"). Reaproveita 100% do cache de dados/cache_odds_historico/.

Uso: python3 backtest_odds_reais_por_ev.py
"""
import json
import os
from datetime import datetime, timedelta

DADOS_DIR = os.path.join(os.path.dirname(__file__), "dados")
REGRAS_PATH = os.path.join(os.path.dirname(__file__), "..", "ligas_live_app", "regras_sinais.json")
CACHE_ODDS_DIR = os.path.join(DADOS_DIR, "cache_odds_historico")

LIGAS_ID = [573, 579, 447, 648, 651]
LIGAS_BRASIL = {648, 651}
LIGAS_NORDICAS = {573, 579, 447}

MARKETS_POR_ALVO = {
    "escanteios": {"principal": 67, "fallback": 68},
    "cartoes": {"principal": 255, "fallback": None},
}

# Faixas pedidas pelo usuário (>=7 como um dos cortes) + granularidade extra
# pra enxergar onde a curva quebra.
FAIXAS_EV = [(0, 3), (3, 7), (7, 15), (15, 30), (30, float("inf"))]


def _get_odds_historico_cache(fixture_id):
    caminho_cache = os.path.join(CACHE_ODDS_DIR, f"{fixture_id}.json")
    if not os.path.exists(caminho_cache):
        return None
    return json.load(open(caminho_cache, encoding="utf-8"))


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


def _faixa_de(ev_pct):
    for lo, hi in FAIXAS_EV:
        if lo <= ev_pct < hi:
            return f"{lo:g}-{hi:g}" if hi != float("inf") else f">={lo:g}"
    return "?"


def rodar():
    payload = json.load(open(REGRAS_PATH, encoding="utf-8"))
    regras = [r for r in payload["regras"] if r["alvo"] in MARKETS_POR_ALVO]
    print(f"{len(regras)} regras de escanteios/cartões (de {payload['total_regras']} totais) entram no teste\n")

    dados_por_liga = {}
    for lid in LIGAS_ID:
        dados_por_liga[lid] = json.load(open(os.path.join(DADOS_DIR, f".checkpoint_{lid}.json"), encoding="utf-8"))

    apostas = []  # (ev_pct, green_bool, odd)
    sem_cache = 0

    for lid, d in dados_por_liga.items():
        for fid_str, jogo in d["jogos"].items():
            fid = int(fid_str)
            if not jogo.get("finalizado") or fid_str not in d["resultados_alvo"]:
                continue
            odds_historico = _get_odds_historico_cache(fid)
            if odds_historico is None:
                sem_cache += 1
                continue
            kickoff = datetime.strptime(jogo["data_hora"], "%Y-%m-%d %H:%M:%S")
            snaps = {}
            for snap in d["snapshots"]:
                if snap["fixture_id"] == fid:
                    snaps[snap["minuto"]] = snap
            resultado_final = d["resultados_alvo"][fid_str]

            for regra in regras:
                if not _liga_aceita_regra(regra["regiao"], lid):
                    continue
                snap = snaps.get(regra["minuto"])
                if not snap or snap.get("gols_momento") != regra["gols_momento"]:
                    continue
                if not _condicao_bate(regra["condicoes"], snap):
                    continue

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

                p_condicao = regra["prob_condicao_confirmacao"]
                ev_pct = (p_condicao * odd - 1) * 100
                if ev_pct < 0:
                    continue

                valor_final = resultado_final.get(alvo)
                if valor_final is None:
                    continue
                bateu = (valor_final > linha) if direcao == "mais_de" else (valor_final < linha)
                apostas.append((ev_pct, bateu, odd))

    print(f"({sem_cache} jogos sem cache de odds — pulados; rode backtest_odds_reais_liga_ano.py de novo pra completar o cache se quiser incluí-los)\n")
    print(f"Total de apostas EV+ com odd real e resultado: {len(apostas)}\n")

    buckets = {}
    for ev_pct, bateu, odd in apostas:
        chave = _faixa_de(ev_pct)
        b = buckets.setdefault(chave, {"n": 0, "green": 0, "red": 0, "soma_retorno": 0.0, "soma_ev": 0.0})
        b["n"] += 1
        b["soma_ev"] += ev_pct
        if bateu:
            b["green"] += 1
            b["soma_retorno"] += (odd - 1)
        else:
            b["red"] += 1
            b["soma_retorno"] += -1

    ordem = [f"{lo:g}-{hi:g}" if hi != float("inf") else f">={lo:g}" for lo, hi in FAIXAS_EV]
    print(f"{'faixa EV%':12s} {'n':>5s} {'ev% médio':>10s} {'green':>6s} {'red':>5s} {'taxa%':>7s} {'roi%':>7s}")
    for chave in ordem:
        b = buckets.get(chave)
        if not b:
            print(f"{chave:12s} {'(sem apostas nessa faixa)':>0s}")
            continue
        taxa = 100 * b["green"] / b["n"]
        roi = 100 * b["soma_retorno"] / b["n"]
        ev_medio = b["soma_ev"] / b["n"]
        print(f"{chave:12s} {b['n']:5d} {ev_medio:10.1f} {b['green']:6d} {b['red']:5d} {taxa:7.1f} {roi:7.1f}")

    print(f"\n{'-'*50}\nCorte específico pedido: EV < 7 vs EV >= 7\n{'-'*50}")
    for nome, filtro in [("EV < 7%", lambda e: e < 7), ("EV >= 7%", lambda e: e >= 7)]:
        subset = [(ev, bateu, odd) for ev, bateu, odd in apostas if filtro(ev)]
        n = len(subset)
        if n == 0:
            print(f"{nome}: sem apostas")
            continue
        green = sum(1 for _, b, _ in subset if b)
        soma = sum((odd - 1) if bateu else -1 for _, bateu, odd in subset)
        print(f"{nome:10s} n={n:4d}  taxa={100*green/n:5.1f}%  roi={100*soma/n:6.1f}%")


if __name__ == "__main__":
    rodar()
