"""
Versão de escala das duas análises anteriores (analise_btts_prelive.py +
analise_btts_odds_bet365.py), agora para as ÚLTIMAS 3 TEMPORADAS (2024,
2025, 2026-parcial) das 5 ligas monitoradas — ~3.978 jogos, em vez dos 298
da janela de 45 dias.

Faz as duas coisas por jogo (perfil pré-live + odd bet365) numa passada só,
com CHECKPOINT incremental (salva a cada N jogos em
data/.checkpoint_btts_3temporadas.json, fora do git) — se o processo cair
no meio (proxy, rede, timeout de sessão — já aconteceu antes neste
projeto), rodar de novo CONTINUA de onde parou em vez de recomeçar do zero.

Rodar: python3 analise_btts_3temporadas.py
"""
import json
import os
import time
from datetime import date, timedelta

import config
import sportmonks_client as sm
import poisson_model as poisson
from prelive_analysis import montar_perfil_time
from live_poisson import probabilidades_ao_vivo

MARKET_ID_BTTS = 14
BOOKMAKER_ID_BET365 = 2
CAMINHO_CHECKPOINT = os.path.join(config.DATA_DIR, ".checkpoint_btts_3temporadas.json")
SALVAR_A_CADA = 10


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

    registro = {
        "fixture_id": fixture_id, "liga": liga_nome, "data_jogo": data_jogo,
        "jogo": f"{home['name']} x {away['name']}",
        "placar": f"{gols_home}-{gols_away}",
        "prob_btts_sim": probs["prob_btts_sim"],
        "prob_btts_nao": probs["prob_btts_nao"],
        "btts_real_sim": gols_home >= 1 and gols_away >= 1,
    }

    try:
        linhas_odds = sm.odds_inplay_fixture(fixture_id)
        btts = [o for o in linhas_odds if o.get("market_id") == MARKET_ID_BTTS and o.get("bookmaker_id") == BOOKMAKER_ID_BET365]
        odd_sim = next((float(o["value"]) for o in btts if o["label"] == "Yes"), None)
        odd_nao = next((float(o["value"]) for o in btts if o["label"] == "No"), None)
        if odd_sim is not None and odd_nao is not None:
            registro["odd_sim"] = odd_sim
            registro["odd_nao"] = odd_nao
    except Exception:
        pass  # sem odd bet365 pra esse jogo — registro fica só com a parte de calibração

    return registro


def rodar():
    print("Listando fixtures das 3 temporadas (2024-01-01 até hoje)...")
    fixtures = _listar_fixtures_periodo("2024-01-01", date.today().isoformat())
    print(f"{len(fixtures)} fixtures finalizadas encontradas\n")

    estado = _carregar_checkpoint()
    ja_feitos = set(estado["processados_ids"])
    print(f"Checkpoint existente: {len(ja_feitos)} já processados — continuando dali.\n")

    pendentes = [f for f in fixtures if f["id"] not in ja_feitos]
    total = len(fixtures)
    for i, f in enumerate(pendentes, 1):
        tentativas = 0
        while True:
            try:
                registro = _processar_fixture(f)
                break
            except Exception as e:
                tentativas += 1
                if tentativas > 3:
                    print(f"  [erro definitivo] fixture {f['id']}: {e}")
                    registro = None
                    break
                print(f"  [erro, retry {tentativas}/3] fixture {f['id']}: {e} — esperando 5s...")
                time.sleep(5)

        estado["processados_ids"].append(f["id"])
        if registro is not None:
            estado["registros"].append(registro)

        feitos_agora = len(ja_feitos) + i
        if i % SALVAR_A_CADA == 0 or i == len(pendentes):
            _salvar_checkpoint(estado)
            print(f"  [{feitos_agora}/{total}] processados (checkpoint salvo, {len(estado['registros'])} com dados completos)")
        time.sleep(0.05)

    print(f"\nConcluído: {len(estado['registros'])} registros com dados completos de {total} fixtures.")
    with open("/tmp/btts_3temporadas_final.json", "w", encoding="utf-8") as fp:
        json.dump(estado["registros"], fp, ensure_ascii=False, indent=2)
    print("Salvo em /tmp/btts_3temporadas_final.json")


if __name__ == "__main__":
    rodar()
