"""
Versão de escala das duas análises anteriores (analise_btts_prelive.py +
analise_btts_odds_bet365.py), agora para as ÚLTIMAS 3 TEMPORADAS (2024,
2025, 2026-parcial) das 5 ligas monitoradas — ~3.978 jogos, em vez dos 298
da janela de 45 dias.

Cobre BTTS **e** Over/Under 2.5 gols na mesma rodagem: o perfil pré-live de
cada time (a parte cara, 2 chamadas de API por jogo) já alimenta
probabilidades_ao_vivo(), que devolve os dois mercados de graça na mesma
chamada — rodar separado pra cada mercado seria refazer o trabalho caro
duas vezes à toa. Busca também a odd bet365 pré-live dos dois mercados
(BTTS market_id=14, Goals Over/Under market_id=80, total=2.5).

Faz tudo por jogo numa passada só, com CHECKPOINT incremental (salva a
cada N jogos em data/.checkpoint_prelive_3temporadas.json, fora do git) —
se o processo cair no meio (proxy, rede, timeout de sessão — já aconteceu
antes neste projeto), rodar de novo CONTINUA de onde parou em vez de
recomeçar do zero.

Rodar: python3 analise_btts_3temporadas.py
"""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

import config
import sportmonks_client as sm
import poisson_model as poisson
from prelive_analysis import montar_perfil_time
from live_poisson import probabilidades_ao_vivo

MARKET_ID_BTTS = 14
MARKET_ID_OVER_UNDER_GOLS = 80  # "Goals Over/Under" — confirmado label Over/Under, total=2.5
BOOKMAKER_ID_BET365 = 2
CAMINHO_CHECKPOINT = os.path.join(config.DATA_DIR, ".checkpoint_prelive_3temporadas.json")
SALVAR_A_CADA = 10
# Cada jogo faz 3 chamadas de API (2 perfil + 1 odds), sequenciais entre si mas
# independentes de jogo pra jogo — gargalo é rede/latência, não CPU, então
# paralelizar entre jogos acelera bastante. Número conservador (não testamos
# o teto real de rate limit da conta) — sportmonks_client._get agora tem
# retry/backoff em 429, então um estouro ocasional não derruba o processo,
# só desacelera aquela chamada específica.
N_WORKERS = 20


def _listar_fixtures_periodo(inicio, fim):
    """Fixtures finalizadas das 5 ligas entre duas datas, em janelas de <=95
    dias (limite da API pra /fixtures/between) — mesma técnica usada pra
    contar o total antes de rodar isto."""
    todas = []
    cursor = date.fromisoformat(inicio)
    fim_total = date.fromisoformat(fim)
    while cursor < fim_total:
        fim_chunk = min(cursor + timedelta(days=95), fim_total)
        fixtures = sm.fixtures_between(cursor.isoformat(), fim_chunk.isoformat(), include="league;participants;scores")
        todas.extend(
            f for f in fixtures
            if f.get("state_id") == 5 and f.get("league", {}).get("id") in config.LIGAS_MONITORADAS
        )
        cursor = fim_chunk + timedelta(days=1)
    return todas


def _carregar_checkpoint():
    if os.path.exists(CAMINHO_CHECKPOINT):
        with open(CAMINHO_CHECKPOINT, encoding="utf-8") as fp:
            return json.load(fp)
    return {"processados_ids": [], "registros": []}


def _salvar_checkpoint(estado):
    tmp = CAMINHO_CHECKPOINT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fp:
        json.dump(estado, fp, ensure_ascii=False)
    os.replace(tmp, CAMINHO_CHECKPOINT)


def _processar_fixture(f):
    fixture_id = f["id"]
    participants = f.get("participants", [])
    home = next((p for p in participants if p["meta"]["location"] == "home"), None)
    away = next((p for p in participants if p["meta"]["location"] == "away"), None)
    if not home or not away:
        return None

    scores = f.get("scores", [])
    gols_home = next((s["score"]["goals"] for s in scores
                       if s.get("description") == "CURRENT" and s.get("participant_id") == home["id"]), None)
    gols_away = next((s["score"]["goals"] for s in scores
                       if s.get("description") == "CURRENT" and s.get("participant_id") == away["id"]), None)
    if gols_home is None or gols_away is None:
        return None

    data_jogo = (f.get("starting_at") or "")[:10]
    liga_nome = f.get("league", {}).get("name", "?")

    perfil_casa = montar_perfil_time(home["id"], ate_data=data_jogo)
    perfil_fora = montar_perfil_time(away["id"], ate_data=data_jogo)
    lambda_h, lambda_a = poisson.expected_goals(perfil_casa, perfil_fora)
    probs = probabilidades_ao_vivo(lambda_h, lambda_a, 0, 0, 0)

    gols_totais = gols_home + gols_away
    registro = {
        "fixture_id": fixture_id, "liga": liga_nome, "data_jogo": data_jogo,
        "jogo": f"{home['name']} x {away['name']}",
        "placar": f"{gols_home}-{gols_away}",
        "gols_totais": gols_totais,
        # BTTS
        "prob_btts_sim": probs["prob_btts_sim"],
        "prob_btts_nao": probs["prob_btts_nao"],
        "btts_real_sim": gols_home >= 1 and gols_away >= 1,
        # Over/Under 2.5 gols — mesma chamada de probabilidades_ao_vivo já devolve
        # isso de graça junto com o BTTS (o caro é o perfil dos times, não esse
        # cálculo), por isso capturamos os dois mercados na mesma rodagem.
        "prob_over25": probs["prob_over25"],
        "prob_under25": probs["prob_under25"],
        "over25_real": gols_totais > 2.5,
    }

    try:
        linhas_odds = sm.odds_inplay_fixture(fixture_id)
        btts = [o for o in linhas_odds if o.get("market_id") == MARKET_ID_BTTS and o.get("bookmaker_id") == BOOKMAKER_ID_BET365]
        odd_sim = next((float(o["value"]) for o in btts if o["label"] == "Yes"), None)
        odd_nao = next((float(o["value"]) for o in btts if o["label"] == "No"), None)
        if odd_sim is not None and odd_nao is not None:
            registro["odd_sim"] = odd_sim
            registro["odd_nao"] = odd_nao

        ou = [
            o for o in linhas_odds
            if o.get("market_id") == MARKET_ID_OVER_UNDER_GOLS and o.get("bookmaker_id") == BOOKMAKER_ID_BET365
        ]
        try:
            odd_over25 = next((float(o["value"]) for o in ou if o["label"] == "Over" and float(o.get("total")) == 2.5), None)
            odd_under25 = next((float(o["value"]) for o in ou if o["label"] == "Under" and float(o.get("total")) == 2.5), None)
        except (TypeError, ValueError):
            odd_over25 = odd_under25 = None
        if odd_over25 is not None and odd_under25 is not None:
            registro["odd_over25"] = odd_over25
            registro["odd_under25"] = odd_under25
    except Exception:
        pass  # sem odd bet365 pra esse jogo — registro fica só com a parte de calibração

    return registro


def _processar_com_retry(f):
    tentativas = 0
    while True:
        try:
            return f["id"], _processar_fixture(f)
        except Exception as e:
            tentativas += 1
            if tentativas > 3:
                print(f"  [erro definitivo] fixture {f['id']}: {e}")
                return f["id"], None
            print(f"  [erro, retry {tentativas}/3] fixture {f['id']}: {e} — esperando 5s...")
            time.sleep(5)


def rodar():
    print("Listando fixtures das 3 temporadas (2024-01-01 até hoje)...")
    fixtures = _listar_fixtures_periodo("2024-01-01", date.today().isoformat())
    print(f"{len(fixtures)} fixtures finalizadas encontradas\n")

    estado = _carregar_checkpoint()
    ja_feitos = set(estado["processados_ids"])
    print(f"Checkpoint existente: {len(ja_feitos)} já processados — continuando dali.\n")

    pendentes = [f for f in fixtures if f["id"] not in ja_feitos]
    total = len(fixtures)
    concluidos = 0
    with ThreadPoolExecutor(max_workers=N_WORKERS) as executor:
        futures = [executor.submit(_processar_com_retry, f) for f in pendentes]
        for future in as_completed(futures):
            fixture_id, registro = future.result()
            estado["processados_ids"].append(fixture_id)
            if registro is not None:
                estado["registros"].append(registro)
            concluidos += 1

            feitos_agora = len(ja_feitos) + concluidos
            if concluidos % SALVAR_A_CADA == 0 or concluidos == len(pendentes):
                _salvar_checkpoint(estado)
                print(f"  [{feitos_agora}/{total}] processados (checkpoint salvo, {len(estado['registros'])} com dados completos)")

    print(f"\nConcluído: {len(estado['registros'])} registros com dados completos de {total} fixtures.")
    with open("/tmp/prelive_3temporadas_final.json", "w", encoding="utf-8") as fp:
        json.dump(estado["registros"], fp, ensure_ascii=False, indent=2)
    print("Salvo em /tmp/prelive_3temporadas_final.json")


if __name__ == "__main__":
    rodar()
