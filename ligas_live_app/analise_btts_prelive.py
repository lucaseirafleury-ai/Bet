"""
Backtest de calibração das probabilidades PRÉ-LIVE de BTTS (Ambas Marcam)
— prob_btts_sim/prob_btts_nao, calculadas em live_poisson.probabilidades_ao_vivo
a partir dos lambdas pré-live (poisson_model.expected_goals sobre o perfil
médio dos últimos 8 jogos de cada time, prelive_analysis.montar_perfil_time).

"Pré-live" aqui = a mesma chamada que o painel faz ao vivo, mas com
minuto=0, gols_home=gols_away=0, sem nenhum ajuste dinâmico de xG/pressão
(ajuste_home=ajuste_away=1.0, o default) — ou seja, exatamente a estimativa
que já existe ANTES do jogo começar, antes de qualquer observação ao vivo.

Metodologia igual à de backtest.py (evita lookahead bias): o perfil de cada
time é montado só com jogos ANTERIORES à data da partida analisada.

Rodar: python3 analise_btts_prelive.py [dias_para_tras]
"""
import sys
import time

import config
import sportmonks_client as sm
import poisson_model as poisson
from prelive_analysis import montar_perfil_time
from live_poisson import probabilidades_ao_vivo

DIAS_HISTORICO_PADRAO = 45


def analisar():
    dias = int(sys.argv[1]) if len(sys.argv) > 1 else DIAS_HISTORICO_PADRAO
    fixtures = sm.fixtures_finalizadas_ligas(dias)
    print(f"{len(fixtures)} jogos finalizados encontrados nas 5 ligas (últimos {dias} dias)\n")

    registros = []
    for i, f in enumerate(fixtures, 1):
        fixture_id = f["id"]
        participants = f.get("participants", [])
        home = next((p for p in participants if p["meta"]["location"] == "home"), None)
        away = next((p for p in participants if p["meta"]["location"] == "away"), None)
        if not home or not away:
            continue

        scores = f.get("scores", [])
        gols_home = next((s["score"]["goals"] for s in scores
                           if s.get("description") == "CURRENT" and s.get("participant_id") == home["id"]), None)
        gols_away = next((s["score"]["goals"] for s in scores
                           if s.get("description") == "CURRENT" and s.get("participant_id") == away["id"]), None)
        if gols_home is None or gols_away is None:
            continue

        data_jogo = (f.get("starting_at") or "")[:10]
        liga_nome = f.get("league", {}).get("name", "?")

        try:
            perfil_casa = montar_perfil_time(home["id"], ate_data=data_jogo)
            perfil_fora = montar_perfil_time(away["id"], ate_data=data_jogo)
        except Exception as e:
            print(f"  [{i}/{len(fixtures)}] [ERRO perfil] fixture {fixture_id}: {e}")
            continue

        lambda_h, lambda_a = poisson.expected_goals(perfil_casa, perfil_fora)
        probs = probabilidades_ao_vivo(lambda_h, lambda_a, 0, 0, 0)

        btts_real = gols_home >= 1 and gols_away >= 1
        registros.append({
            "fixture_id": fixture_id, "liga": liga_nome, "data_jogo": data_jogo,
            "jogo": f"{home['name']} x {away['name']}",
            "placar": f"{gols_home}-{gols_away}",
            "prob_btts_sim": probs["prob_btts_sim"],
            "prob_btts_nao": probs["prob_btts_nao"],
            "btts_real_sim": btts_real,
            "jogos_considerados_casa": perfil_casa["jogos_considerados"],
            "jogos_considerados_fora": perfil_fora["jogos_considerados"],
        })
        if i % 25 == 0:
            print(f"  [{i}/{len(fixtures)}] processados...")
        time.sleep(0.05)

    print(f"\nTotal com dados completos: {len(registros)} jogos\n")
    return registros


if __name__ == "__main__":
    import json
    registros = analisar()
    with open("/tmp/btts_prelive_registros.json", "w", encoding="utf-8") as fp:
        json.dump(registros, fp, ensure_ascii=False, indent=2)
    print("Salvo em /tmp/btts_prelive_registros.json")
