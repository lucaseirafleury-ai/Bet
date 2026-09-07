"""
Complementa analise_btts_prelive.py: busca a odd PRÉ-LIVE de BTTS (mercado
Sportmonks market_id=14 "Both Teams To Score", bookmaker_id=2 "bet365") de
cada um dos jogos já processados, e calcula o ROI que o modelo pré-live
teria dado apostando nela.

Confirmado numa amostra (ver conversa): a bet365 suspende esse mercado
uns 7-10min antes do apito inicial e a Sportmonks mantém esse último valor
("latest_bookmaker_update") — ou seja, o valor retido É a linha de
fechamento pré-live, não uma atualização ao vivo tardia. Não precisa do
filtro de idade máxima que odds_ao_vivo.py usa pro AO VIVO (ali o problema
é odd desatualizada DURANTE o jogo; aqui é exatamente o oposto, queremos
o congelamento pré-jogo).

Rodar depois de analise_btts_prelive.py (usa /tmp/btts_prelive_registros.json).
"""
import json
import time

import sportmonks_client as sm

MARKET_ID_BTTS = 14
BOOKMAKER_ID_BET365 = 2


def buscar_odds_btts_bet365(fixture_id):
    try:
        linhas = sm.odds_inplay_fixture(fixture_id)
    except Exception as e:
        return None, str(e)
    btts = [o for o in linhas if o.get("market_id") == MARKET_ID_BTTS and o.get("bookmaker_id") == BOOKMAKER_ID_BET365]
    if not btts:
        return None, "sem odd bet365 nesse mercado"
    odd_sim = next((float(o["value"]) for o in btts if o["label"] == "Yes"), None)
    odd_nao = next((float(o["value"]) for o in btts if o["label"] == "No"), None)
    if odd_sim is None or odd_nao is None:
        return None, "faltou um dos dois lados (Yes/No)"
    return {"odd_sim": odd_sim, "odd_nao": odd_nao}, None


def rodar():
    registros = json.load(open("/tmp/btts_prelive_registros.json", encoding="utf-8"))
    print(f"{len(registros)} jogos a processar\n")

    enriquecidos = []
    sem_odd = 0
    for i, d in enumerate(registros, 1):
        odds, motivo = buscar_odds_btts_bet365(d["fixture_id"])
        if odds is None:
            sem_odd += 1
        else:
            d = dict(d, **odds)
        enriquecidos.append(d)
        if i % 25 == 0:
            print(f"  [{i}/{len(registros)}] processados... ({sem_odd} sem odd até agora)")
        time.sleep(0.05)

    print(f"\nTotal: {len(enriquecidos)} | com odd bet365: {len(enriquecidos)-sem_odd} | sem odd: {sem_odd}")
    with open("/tmp/btts_com_odds.json", "w", encoding="utf-8") as fp:
        json.dump(enriquecidos, fp, ensure_ascii=False, indent=2)
    print("Salvo em /tmp/btts_com_odds.json")


if __name__ == "__main__":
    rodar()
