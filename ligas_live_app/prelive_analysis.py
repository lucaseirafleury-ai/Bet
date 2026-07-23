"""
FASE 1 — Análise pré-live.

Para cada jogo futuro das ligas monitoradas:
  1. Monta o perfil de cada time (médias dos últimos N jogos)
  2. Estima o placar modal (Poisson)
  3. Define o favorito de posse / pressão / xG_proxy
  4. Salva tudo em data/prelive_reports.json para o dashboard consumir
"""
import json
import os
from datetime import date, timedelta

import config
import sportmonks_client as sm
import poisson_model as poisson
from xg_pressure import (
    extrair_stat, calcular_xg_proxy, calcular_cartoes, calcular_escanteios,
    CAMPO_POSSE, CAMPO_DANGEROUS,
)


def montar_perfil_time(team_id, ate_data=None):
    """
    Perfil médio de um time com base nos últimos jogos finalizados.

    ate_data: usado pelo backtest.py para montar o perfil só com jogos ANTERIORES
    a uma data de referência, evitando viés retrospectivo (lookahead bias).
    """
    fixtures = sm.team_recent_fixtures(team_id, config.JOGOS_HISTORICO_PERFIL, ate_data=ate_data)

    gols_marcados, gols_sofridos = [], []
    posses, pressoes_dangerous, xg_proxies = [], [], []
    escanteios_lista, cartoes_lista = [], []

    for f in fixtures:
        participants = f.get("participants", [])
        this_team = next((p for p in participants if p["id"] == team_id), None)
        opponent = next((p for p in participants if p["id"] != team_id), None)
        if not this_team or not opponent:
            continue

        location = this_team.get("meta", {}).get("location")
        scores = f.get("scores", [])
        gf = next((s["score"]["goals"] for s in scores
                   if s.get("description") == "CURRENT" and s.get("participant_id") == team_id), None)
        ga = next((s["score"]["goals"] for s in scores
                   if s.get("description") == "CURRENT" and s.get("participant_id") == opponent["id"]), None)
        if gf is not None and ga is not None:
            gols_marcados.append(gf)
            gols_sofridos.append(ga)

        stats_all = f.get("statistics", [])
        stats_time = [s for s in stats_all if s.get("participant_id") == team_id]
        if stats_time:
            posses.append(extrair_stat(stats_time, CAMPO_POSSE))
            pressoes_dangerous.append(extrair_stat(stats_time, CAMPO_DANGEROUS))
            xg_proxies.append(calcular_xg_proxy(stats_time))
            escanteios_lista.append(calcular_escanteios(stats_time))
            cartoes_lista.append(calcular_cartoes(stats_time))

    def media(lst, default=0.0):
        return round(sum(lst) / len(lst), 2) if lst else default

    return {
        "team_id": team_id,
        "jogos_considerados": len(fixtures),
        "gols_marcados_media": media(gols_marcados, 1.2),
        "gols_sofridos_media": media(gols_sofridos, 1.2),
        "posse_media": media(posses, 50.0),
        "dangerous_attacks_media": media(pressoes_dangerous, 30.0),
        "xg_proxy_media": media(xg_proxies, 1.0),
        "escanteios_media": media(escanteios_lista, 4.5),
        "cartoes_media": media(cartoes_lista, 2.0),
    }


def analisar_jogo(fixture):
    participants = fixture.get("participants", [])
    home = next((p for p in participants if p["meta"]["location"] == "home"), None)
    away = next((p for p in participants if p["meta"]["location"] == "away"), None)
    if not home or not away:
        return None

    perfil_casa = montar_perfil_time(home["id"])
    perfil_fora = montar_perfil_time(away["id"])

    lambda_h, lambda_a = poisson.expected_goals(perfil_casa, perfil_fora)
    placar, prob = poisson.placar_modal(lambda_h, lambda_a)

    favorito_posse = home["name"] if perfil_casa["posse_media"] >= perfil_fora["posse_media"] else away["name"]
    favorito_pressao = (
        home["name"] if perfil_casa["dangerous_attacks_media"] >= perfil_fora["dangerous_attacks_media"] else away["name"]
    )
    favorito_xg = home["name"] if perfil_casa["xg_proxy_media"] >= perfil_fora["xg_proxy_media"] else away["name"]

    return {
        "fixture_id": fixture["id"],
        "liga": fixture.get("league", {}).get("name", "?"),
        "data_hora_utc": fixture.get("starting_at"),
        "home": home["name"],
        "away": away["name"],
        "perfil_casa": perfil_casa,
        "perfil_fora": perfil_fora,
        "lambda_home": lambda_h,
        "lambda_away": lambda_a,
        "placar_modal": f"{placar[0]}-{placar[1]}",
        "placar_modal_prob_pct": prob,
        "favorito_posse": favorito_posse,
        "favorito_pressao": favorito_pressao,
        "favorito_xg": favorito_xg,
    }


def rodar():
    hoje = date.today()
    ate = hoje + timedelta(days=config.DIAS_A_FRENTE)

    fixtures = sm.fixtures_between(hoje.isoformat(), ate.isoformat())
    fixtures_monitoradas = [f for f in fixtures if f.get("league", {}).get("id") in config.LIGAS_MONITORADAS]

    relatorios = []
    for f in fixtures_monitoradas:
        try:
            r = analisar_jogo(f)
            if r:
                relatorios.append(r)
                print(f"[OK] {r['liga']}: {r['home']} x {r['away']} -> modal {r['placar_modal']}")
        except Exception as e:
            print(f"[ERRO] fixture {f.get('id')}: {e}")

    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(config.PRELIVE_FILE, "w", encoding="utf-8") as fp:
        json.dump(
            {"gerado_em": hoje.isoformat(), "relatorios": relatorios},
            fp, ensure_ascii=False, indent=2
        )
    print(f"\n{len(relatorios)} relatórios salvos em {config.PRELIVE_FILE}")


if __name__ == "__main__":
    rodar()
