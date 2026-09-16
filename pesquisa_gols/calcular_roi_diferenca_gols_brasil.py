"""
ROI real (contra odds da bet365) das candidatas de diferença de gols no
Brasil que confirmam nas 3 fontes independentes (herdado, nativo Série
A->B, nativo Série B->A) -- mesmo piso (confirmacoes>=3) usado em produção
pra region=brasil.

Simplificação assumida (documentada, não é a réplica exata de
gerar_regras_sinais.py::_selecionar_brasil_por_confianca): aqui a interseção
das 3 fontes é feita por chave exata (alvo, minuto, diferenca_gols, mercado,
condições) -- sem o agrupamento por "família" que escolhe a melhor variação
de linha vizinha dentro do mesmo grupo. Suficiente pra medir ROI real
(responde "vale a pena?"), não pra gerar o conjunto definitivo de regras.

Reaproveita 100% de dados já baixados, zero custo de API:
- candidatas confirmadas: resultados/diffgols_brasil/*_confirmacao_*.csv
- snapshots: dados/diffgols_brasil/.checkpoint_{648,651}.json (diferenca_gols)
- odds reais: dados/cache_odds_historico/ (já cobre Série A/B)

Réplica a mesma lógica de matching de mercado corrigida de
backtest_odds_reais_v2.py (linha inteira 3-vias da bet365 pra escanteios).

Uso: python3 calcular_roi_diferenca_gols_brasil.py
"""
import csv
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta

DADOS_DIR = os.path.join(os.path.dirname(__file__), "dados", "diffgols_brasil")
RESULTADOS_DIR = os.path.join(os.path.dirname(__file__), "resultados", "diffgols_brasil")
CACHE_ODDS_DIR = os.path.join(os.path.dirname(__file__), "dados", "cache_odds_historico")

LIGAS_NOME = {648: "Série A", 651: "Série B"}
LIGAS_ID = list(LIGAS_NOME)
ALVOS_NATIVOS = ["escanteios", "chutes_totais", "chutes_no_alvo", "cartoes"]

MARKET_ID_POR_ALVO = {"escanteios": 67, "cartoes": 255, "chutes_totais": 292, "chutes_no_alvo": 291}
MARKET_ID_FALLBACK_ESCANTEIOS = 68


def _tentativas_mercado(alvo, direcao, linha):
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
    sinal, valor = mercado_str[0], float(mercado_str[1:])
    return ("mais_de" if sinal == "+" else "menos_de"), valor


def _chave(alvo, minuto, diferenca, mercado_str, condset):
    return (alvo, minuto, diferenca, mercado_str, condset)


IMPACTO_MINIMO_PP = 5.0  # mesmo piso de gerar_regras_sinais.py -- sem isso, confirmado_bh=True
# sozinho deixa passar efeito estatisticamente real mas economicamente trivial (achado real:
# primeira tentativa sem este filtro deu probabilidade média == 0.5 exato, min 0 max 1 --
# assinatura de threshold sem filtro de tamanho de efeito, não um edge de verdade).


def _carregar_fonte(alvo, sufixo):
    """sufixo: 'brasil' (herdado), 'serieB' (nativo A->B), 'serieA' (nativo B->A).
    Devolve {chave: linha_dict} só das confirmadas (confirmado_bh=True) E com
    impacto >= IMPACTO_MINIMO_PP (mesmo piso usado pra "sinal forte" em produção)."""
    achadas = {}
    caminho_1 = os.path.join(RESULTADOS_DIR, f"{alvo}_confirmacao_{sufixo}_1stat.csv")
    if os.path.exists(caminho_1):
        with open(caminho_1, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["confirmado_bh"] != "True":
                    continue
                if abs(float(r["impacto_outras_ligas_pp"])) < IMPACTO_MINIMO_PP:
                    continue
                condset = frozenset({(r["stat"], r["operador"], float(r["limite"]))})
                chave = _chave(alvo, int(r["minuto"]), int(r["gols_momento"]), r["mercado"], condset)
                achadas[chave] = {"tipo": "1stat", "condicoes": [dict(stat=r["stat"], operador=r["operador"], limite=float(r["limite"]))],
                                   "prob_condicao": float(r["p_final_outras_ligas"])}
    caminho_2 = os.path.join(RESULTADOS_DIR, f"{alvo}_confirmacao_{sufixo}_2stats.csv")
    if os.path.exists(caminho_2):
        with open(caminho_2, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["confirmado_bh"] != "True":
                    continue
                impacto_pp = (float(r["p_conjunta_outras_ligas"]) - float(r["p_base_outras_ligas"])) * 100
                if abs(impacto_pp) < IMPACTO_MINIMO_PP:
                    continue
                condset = frozenset({(r["stat1"], r["operador1"], float(r["limite1"])), (r["stat2"], r["operador2"], float(r["limite2"]))})
                chave = _chave(alvo, int(r["minuto"]), int(r["gols_momento"]), r["mercado"], condset)
                achadas[chave] = {"tipo": "2stats",
                                   "condicoes": [dict(stat=r["stat1"], operador=r["operador1"], limite=float(r["limite1"])),
                                                 dict(stat=r["stat2"], operador=r["operador2"], limite=float(r["limite2"]))],
                                   "prob_condicao": float(r["p_conjunta_outras_ligas"])}
    return achadas


def _montar_regras_confirmacoes_3():
    regras = []
    for alvo in ALVOS_NATIVOS:
        herdado = _carregar_fonte(alvo, "brasil")
        nativo_ab = _carregar_fonte(alvo, "serieB")  # descobre Série A, confirma Série B
        nativo_ba = _carregar_fonte(alvo, "serieA")  # descobre Série B, confirma Série A
        chaves_comuns = set(herdado) & set(nativo_ab) & set(nativo_ba)
        for chave in chaves_comuns:
            _, minuto, diferenca, mercado_str, _condset = chave
            direcao, linha = _parse_mercado(mercado_str)
            # usa a probabilidade média das 3 fontes como estimativa de EV
            probs = [herdado[chave]["prob_condicao"], nativo_ab[chave]["prob_condicao"], nativo_ba[chave]["prob_condicao"]]
            regras.append({
                "alvo": alvo, "minuto": minuto, "diferenca_gols": diferenca,
                "mercado": {"direcao": direcao, "linha": linha},
                "condicoes": herdado[chave]["condicoes"],
                "prob_condicao": sum(probs) / len(probs),
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
    regras = _montar_regras_confirmacoes_3()
    print(f"{len(regras)} candidatas com confirmacoes>=3 (diferença de gols, Brasil) entram no teste")
    for alvo in ALVOS_NATIVOS:
        n = sum(1 for r in regras if r["alvo"] == alvo)
        print(f"  {alvo}: {n}")
    print()
    if not regras:
        print("Nenhuma candidata com confirmação tripla — nada a testar.")
        return

    dados_por_liga = {}
    for lid in LIGAS_ID:
        caminho = os.path.join(DADOS_DIR, f".checkpoint_{lid}.json")
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
    print(f"{'diferenca_gols (brasil, conf>=3)':30s} {bucket['disparos']:9d} {bucket['odd_encontrada']:9d} "
          f"{bucket['ev_positivo']:6d} {bucket['green']:6d} {bucket['red']:5d} {taxa:7.1f} {roi:7.1f}")


if __name__ == "__main__":
    rodar()
