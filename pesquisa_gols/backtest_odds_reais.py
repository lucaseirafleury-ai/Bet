"""
Backtest retroativo com odds REAIS de jogos já finalizados — base completa
(ver conversa: validado antes numa amostra de 80 jogos — 4.1% de cobertura
de odd real, ROI de -6.9% em 54 apostas, amostra pequena demais pra
conclusão. Agora roda em todos os jogos finalizados que já temos em cache,
nas 5 ligas monitoradas, pra ter confiança estatística de verdade).

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
checkpoint de dados. Roda ~4.000 chamadas de API (1 por jogo, não por
sinal) — demorado (~1h), por isso salva progresso incremental em
CAMINHO_PROGRESSO a cada FREQ_SALVAMENTO jogos: se cair no meio, rodar de
novo RETOMA dali (mesmo padrão de checkpoint já usado no resto do projeto),
em vez de perder tudo e recomeçar.

Uso: python3 backtest_odds_reais.py
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta

import requests

TOKEN = os.environ["SPORTMONKS_TOKEN"]
BASE_URL = "https://api.sportmonks.com/v3/football"
DADOS_DIR = os.path.join(os.path.dirname(__file__), "dados")

# Uso: python3 backtest_odds_reais.py [caminho_regras.json] [sufixo_progresso]
# Sem argumentos: roda contra o regras_sinais.json atual (204 regras, ver
# conversa). Com argumentos: permite comparar retroativamente um conjunto de
# regras DIFERENTE (ex.: o snapshot de 78 regras de antes de hoje, salvo em
# dados/comparacao_roi/regras_sinais_78_original.json) contra os MESMOS
# jogos — cada conjunto de regras precisa do seu próprio arquivo de
# progresso (sufixo_progresso), senão uma rodada pisaria no checkpoint da
# outra.
REGRAS_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "..", "ligas_live_app", "regras_sinais.json"
)
# Sem sufixo (uso normal, sem argumentos) -> mantém o nome de arquivo
# ORIGINAL (.checkpoint_backtest_odds_reais.json, sem sufixo) — importante
# pra não perder compatibilidade com a rodada das 204 regras já em
# andamento em background quando este arquivo foi editado (ver conversa:
# ela só seria "resumível" se o nome do progresso continuar batendo).
SUFIXO_PROGRESSO = sys.argv[2] if len(sys.argv) > 2 else None
nome_arquivo_progresso = (
    "checkpoint_backtest_odds_reais.json" if SUFIXO_PROGRESSO is None
    else f"checkpoint_backtest_odds_reais_{SUFIXO_PROGRESSO}.json"
)
CAMINHO_PROGRESSO = os.path.join(DADOS_DIR, f".{nome_arquivo_progresso}")

FREQ_SALVAMENTO = 25  # jogos entre cada save do progresso
MAX_TENTATIVAS = 4  # retry pra erro de rede/rate-limit, mesmo padrão de sportmonks.py::_get

LIGAS_ID = [573, 579, 447, 648, 651]  # todas as 5 monitoradas (A Lyga/1.Lyga de fora)
LIGAS_BRASIL = {648, 651}
LIGAS_NORDICAS = {573, 579, 447}

# market_id principal + fallback por alvo — mesmo mapeamento de
# ligas_live_app/odds_ao_vivo.py::MARKET_ID_POR_ALVO, restrito aos 2 alvos
# que têm mercado real negociável (ver docstring acima).
MARKETS_POR_ALVO = {
    "escanteios": {"principal": 67, "fallback": 68},
    "cartoes": {"principal": 255, "fallback": None},
}


def _get_odds_historico(fixture_id):
    for tentativa in range(MAX_TENTATIVAS):
        try:
            r = requests.get(f"{BASE_URL}/odds/inplay/fixtures/{fixture_id}", params={"api_token": TOKEN}, timeout=30)
            if r.status_code == 429:
                espera = 5 * (tentativa + 1)
                print(f"    [rate limit] esperando {espera}s...")
                time.sleep(espera)
                continue
            r.raise_for_status()
            return r.json().get("data") or []
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


def _carregar_progresso():
    if os.path.exists(CAMINHO_PROGRESSO):
        d = json.load(open(CAMINHO_PROGRESSO, encoding="utf-8"))
        d["processados"] = set(d["processados"])
        print(f"Retomando de checkpoint anterior: {len(d['processados'])} jogos já processados")
        return d
    return {
        "processados": set(),
        "stats": {"disparos": 0, "odd_encontrada": 0, "ev_positivo": 0, "green": 0, "red": 0, "soma_retorno": 0.0},
        "erros_api": 0,
    }


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
    stats = estado["stats"]
    processados = estado["processados"]
    erros_api = estado["erros_api"]

    pendentes = [c for c in candidatos if c[0] not in processados]
    print(f"Pendentes nesta execução: {len(pendentes)}\n")

    for i, (fid, lid, data_hora_str, dados_liga) in enumerate(pendentes):
        if (i + 1) % 100 == 0:
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
        time.sleep(0.25)

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

        processados.add(fid)
        if len(processados) % FREQ_SALVAMENTO == 0:
            _salvar_progresso({"processados": processados, "stats": stats, "erros_api": erros_api})

    _salvar_progresso({"processados": processados, "stats": stats, "erros_api": erros_api})

    print(f"\n{'='*70}\nResumo do backtest ({len(processados)}/{len(candidatos)} jogos, {erros_api} erros de API)\n{'='*70}")
    print(f"Disparos de regra (condição bateu, independente de odd): {stats['disparos']}")
    print(f"  ... com odd real encontrada no histórico: {stats['odd_encontrada']} "
          f"({100*stats['odd_encontrada']/stats['disparos']:.1f}%)" if stats['disparos'] else "")
    print(f"  ... com EV positivo contra essa odd real: {stats['ev_positivo']}")
    if stats["ev_positivo"] > 0:
        n_apostas = stats["green"] + stats["red"]
        print(f"\nDas apostas com EV positivo que teriam sido feitas ({n_apostas}):")
        print(f"  green: {stats['green']} | red: {stats['red']} | taxa de acerto: {100*stats['green']/n_apostas:.1f}%")
        print(f"  ROI real (unidades ganhas / apostas, assumindo stake=1): {100*stats['soma_retorno']/n_apostas:.1f}%")
    else:
        print("\nNenhuma aposta com EV positivo encontrada.")


if __name__ == "__main__":
    rodar()
