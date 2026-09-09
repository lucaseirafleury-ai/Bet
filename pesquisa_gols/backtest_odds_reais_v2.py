"""
Correção de um bug real encontrado nos backtests anteriores
(backtest_odds_reais.py, backtest_odds_reais_detalhado.py,
backtest_odds_reais_liga_ano.py, backtest_odds_reais_por_ev.py): nenhum
deles replicava a conversão de linha que ligas_live_app/odds_ao_vivo.py
já faz pro fallback de escanteios (market_id 68, "Match Corners" — linha
INTEIRA, 3 vias Over/Exactly/Under) nem pro formato "bet365 sob o próprio
market_id 67 com total inteiro". Os backtests comparavam a linha .5 crua
contra o campo "total" da API, então NUNCA batiam com esses formatos —
só com o formato "linha .5 direta" (que é o único que Série A/B do
Brasil parece oferecer nesse endpoint; as ligas nórdicas usam SÓ o
formato de linha inteira pra escanteios, conforme documentado em
odds_ao_vivo.py). Isso fez o backtest concluir "0% cobertura real nas
nórdicas" quando na verdade era um bug de matching, não ausência de
mercado — confirmado inspecionando o cache: o jogo 19635919
(Allsvenskan) tem 0 entradas em market 67/255 mas 30 em market 68.

Este script reaproveita 100% do cache já baixado (nenhuma chamada de API
nova) e replica _tentativas_mercado()/_candidatas_no_mercado() de
odds_ao_vivo.py fielmente, pra recalcular os números corretos.

Uso: python3 backtest_odds_reais_v2.py
"""
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta

DADOS_DIR = os.path.join(os.path.dirname(__file__), "dados")
REGRAS_PATH = os.path.join(os.path.dirname(__file__), "..", "ligas_live_app", "regras_sinais.json")
CACHE_ODDS_DIR = os.path.join(DADOS_DIR, "cache_odds_historico")

LIGAS_NOME = {573: "Allsvenskan", 579: "Superettan", 447: "1. Division", 648: "Série A", 651: "Série B"}
LIGAS_ID = list(LIGAS_NOME)
LIGAS_BRASIL = {648, 651}
LIGAS_NORDICAS = {573, 579, 447}

# Réplica fiel de odds_ao_vivo.MARKET_ID_POR_ALVO / MARKET_ID_FALLBACK_ESCANTEIOS
MARKET_ID_POR_ALVO = {
    "escanteios": 67,
    "chutes_totais": 292,
    "chutes_no_alvo": 291,
    "cartoes": 255,
}
MARKET_ID_FALLBACK_ESCANTEIOS = 68


def _tentativas_mercado(alvo, direcao, linha):
    """Réplica exata de odds_ao_vivo._tentativas_mercado."""
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


def _achar_odd_real(odds_historico, tentativas, timestamp_checkpoint):
    """Mesma lógica de tolerância retroativa dos backtests anteriores (odd mais
    recente conhecida até checkpoint+5min), mas testando TODAS as tentativas de
    mercado/linha (formato .5 direto + os dois formatos de linha inteira),
    igual _candidatas_no_mercado faz na produção — combina tudo, não para na
    primeira tentativa que achar."""
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
    payload = json.load(open(REGRAS_PATH, encoding="utf-8"))
    regras = payload["regras"]
    print(f"{len(regras)} regras totais entram no teste (agora TODOS os alvos, não só escanteios/cartões)\n")

    dados_por_liga = {}
    for lid in LIGAS_ID:
        dados_por_liga[lid] = json.load(open(os.path.join(DADOS_DIR, f".checkpoint_{lid}.json"), encoding="utf-8"))

    buckets_regiao_conf = defaultdict(_bucket_vazio)
    buckets_liga = defaultdict(_bucket_vazio)
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
                tentativas = _tentativas_mercado(alvo, direcao, linha)
                if not tentativas:
                    continue

                chave_rc = f"{regra['regiao']}_{regra.get('confirmacoes', 1)}"
                chave_liga = LIGAS_NOME[lid]
                b_rc = buckets_regiao_conf[chave_rc]
                b_liga = buckets_liga[chave_liga]
                b_rc["disparos"] += 1
                b_liga["disparos"] += 1

                timestamp_checkpoint = kickoff + timedelta(minutes=regra["minuto"])
                odd = _achar_odd_real(odds_historico, tentativas, timestamp_checkpoint)
                if odd is None:
                    continue
                b_rc["odd_encontrada"] += 1
                b_liga["odd_encontrada"] += 1

                p_condicao = regra["prob_condicao_confirmacao"]
                ev_pct = (p_condicao * odd - 1) * 100
                if ev_pct < 0:
                    continue
                b_rc["ev_positivo"] += 1
                b_liga["ev_positivo"] += 1

                valor_final = resultado_final.get(alvo)
                if valor_final is None:
                    continue
                bateu = (valor_final > linha) if direcao == "mais_de" else (valor_final < linha)
                if bateu:
                    b_rc["green"] += 1
                    b_liga["green"] += 1
                    b_rc["soma_retorno"] += (odd - 1)
                    b_liga["soma_retorno"] += (odd - 1)
                else:
                    b_rc["red"] += 1
                    b_liga["red"] += 1
                    b_rc["soma_retorno"] += -1
                    b_liga["soma_retorno"] += -1

    print(f"Jogos processados: {total_jogos} ({sem_cache} sem cache, pulados)\n")

    def _imprime(buckets, titulo):
        print(f"{'='*78}\n{titulo}\n{'='*78}")
        print(f"{'bucket':22s} {'disparos':>9s} {'odd_real':>9s} {'ev+':>6s} {'green':>6s} {'red':>5s} {'taxa%':>7s} {'roi%':>7s}")
        for chave in sorted(buckets):
            b = buckets[chave]
            n = b["green"] + b["red"]
            taxa = 100 * b["green"] / n if n else 0.0
            roi = 100 * b["soma_retorno"] / n if n else 0.0
            print(f"{chave:22s} {b['disparos']:9d} {b['odd_encontrada']:9d} {b['ev_positivo']:6d} "
                  f"{b['green']:6d} {b['red']:5d} {taxa:7.1f} {roi:7.1f}")
        print()

    _imprime(buckets_regiao_conf, "Por (regiao, confirmacoes)")
    _imprime(buckets_liga, "Por liga")


if __name__ == "__main__":
    rodar()
