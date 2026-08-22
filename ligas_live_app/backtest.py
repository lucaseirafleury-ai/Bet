"""
BACKTEST — valida o modelo (xG_proxy, pressão, lambda ajustado ao vivo) contra
jogos JÁ FINALIZADOS das 5 ligas monitoradas, usando o include=trends da
Sportmonks (progressão minuto a minuto das estatísticas, disponível também
para partidas passadas).

Não depende de esperar rodadas futuras — roda em cima do histórico que a
Sportmonks já tem catalogado.

Cuidado metodológico: o perfil de cada time (usado para calcular o lambda)
é montado só com jogos ANTERIORES à data da partida analisada, para não usar
informação que na hora real do jogo ainda não existia (lookahead bias).

Saída: data/backtest_resultados.csv — uma linha por (jogo, checkpoint de minuto),
comparando a probabilidade que o modelo dava naquele momento (com e sem o
ajuste dinâmico de xG/pressão) com o resultado final real da partida.
"""
import csv
import os
import time

import config
import sportmonks_client as sm
import poisson_model as poisson
from prelive_analysis import montar_perfil_time
from xg_pressure import (
    calcular_xg_proxy, calcular_pressao,
    CAMPO_SHOTS_ON, CAMPO_SHOTS_OFF, CAMPO_SHOTS_IN, CAMPO_SHOTS_OUT,
    CAMPO_BLOCKED, CAMPO_DANGEROUS, CAMPO_POSSE, CAMPO_SHOTS_TOTAL, CAMPO_CORNERS,
)
from live_poisson import probabilidades_ao_vivo, delta_fracional, fator_ajuste_lambda

CHECKPOINTS = [15, 30, 45, 60, 75]
DIAS_HISTORICO = 45  # janela de jogos já finalizados a analisar
CAMPOS_NECESSARIOS = [
    CAMPO_SHOTS_ON, CAMPO_SHOTS_OFF, CAMPO_SHOTS_IN, CAMPO_SHOTS_OUT,
    CAMPO_BLOCKED, CAMPO_DANGEROUS, CAMPO_POSSE, CAMPO_SHOTS_TOTAL, CAMPO_CORNERS,
]

_types_cache = None


def carregar_mapa_types():
    global _types_cache
    if _types_cache is None:
        print("Carregando mapa de tipos de estatística (uma vez só)...")
        todos = sm.all_types()
        _types_cache = {t["name"]: t["id"] for t in todos}
    return _types_cache


def identificar_type_id_gol(mapa_types):
    """
    Tenta achar o type_id de 'Goal' nos types da Sportmonks. Nomes candidatos,
    porque a grafia exata não foi confirmada em teste real ainda — se nenhum bater,
    a reconstrução de placar parcial cai no fallback (ver gols_ate_minuto).
    """
    for candidato in ["Goal", "GOAL", "Goals", "Normal Goal"]:
        if candidato in mapa_types:
            return mapa_types[candidato]
    return None


def gols_ate_minuto(events, participant_id, minuto, goal_type_id, gols_finais_fallback):
    """
    Conta gols do time até o minuto, usando os eventos da partida.
    Se o type_id de gol não foi identificado, cai no fallback: assume o placar
    final inteiro (aviso: menos preciso, mas mais realista que sempre 0-0).
    """
    if goal_type_id is None:
        return gols_finais_fallback
    return sum(
        1 for e in events
        if e.get("type_id") == goal_type_id
        and e.get("participant_id") == participant_id
        and (e.get("minute") or 0) <= minuto
    )


def valor_acumulado_no_minuto(trends, type_id, participant_id, minuto):
    """Pega o último valor do trend registrado até aquele minuto (trend é cumulativo)."""
    candidatos = [
        t for t in trends
        if t.get("type_id") == type_id and t.get("participant_id") == participant_id
        and (t.get("minute") or 0) <= minuto
    ]
    if not candidatos:
        return 0.0
    candidatos.sort(key=lambda t: t.get("minute") or 0)
    valor = candidatos[-1].get("value")
    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


def montar_stats_simuladas(trends, participant_id, minuto, mapa_types):
    lista = []
    for nome in CAMPOS_NECESSARIOS:
        tid = mapa_types.get(nome)
        if tid is None:
            continue
        valor = valor_acumulado_no_minuto(trends, tid, participant_id, minuto)
        lista.append({"type": {"name": nome}, "data": {"value": valor}})
    return lista


def resultado_real(gols_home_final, gols_away_final):
    if gols_home_final > gols_away_final:
        return "casa"
    if gols_home_final < gols_away_final:
        return "fora"
    return "empate"


def analisar_fixture(fixture_resumo, mapa_types, linhas_saida):
    fixture_id = fixture_resumo["id"]
    fixture = sm.fixture_com_trends(fixture_id)
    if not fixture:
        return

    trends = fixture.get("trends", [])
    if not trends:
        print(f"  [sem trends] fixture {fixture_id} — pulando (liga provavelmente sem cobertura de trends)")
        return

    participants = fixture.get("participants", [])
    home = next((p for p in participants if p["meta"]["location"] == "home"), None)
    away = next((p for p in participants if p["meta"]["location"] == "away"), None)
    if not home or not away:
        return

    scores = fixture.get("scores", [])
    gols_home_final = next((s["score"]["goals"] for s in scores
                             if s.get("description") == "CURRENT" and s.get("participant_id") == home["id"]), None)
    gols_away_final = next((s["score"]["goals"] for s in scores
                             if s.get("description") == "CURRENT" and s.get("participant_id") == away["id"]), None)
    if gols_home_final is None or gols_away_final is None:
        return

    resultado = resultado_real(gols_home_final, gols_away_final)
    data_jogo = fixture.get("starting_at", "")[:10]
    events = fixture.get("events", [])
    goal_type_id = identificar_type_id_gol(mapa_types)
    if goal_type_id is None:
        print(f"  [aviso] type_id de gol não identificado — placar parcial usará o placar final como aproximação")

    # perfil dos times, montado só com jogos ANTERIORES a esta data (evita lookahead bias)
    perfil_casa = montar_perfil_time(home["id"], ate_data=data_jogo)
    perfil_fora = montar_perfil_time(away["id"], ate_data=data_jogo)
    lambda_home, lambda_away = poisson.expected_goals(perfil_casa, perfil_fora)

    for minuto in CHECKPOINTS:
        stats_home_sim = montar_stats_simuladas(trends, home["id"], minuto, mapa_types)
        stats_away_sim = montar_stats_simuladas(trends, away["id"], minuto, mapa_types)

        xg_home = calcular_xg_proxy(stats_home_sim)
        xg_away = calcular_xg_proxy(stats_away_sim)
        pressao_home = calcular_pressao(stats_home_sim, minuto)
        pressao_away = calcular_pressao(stats_away_sim, minuto)

        gols_home_parcial = gols_ate_minuto(events, home["id"], minuto, goal_type_id, gols_home_final)
        gols_away_parcial = gols_ate_minuto(events, away["id"], minuto, goal_type_id, gols_away_final)

        delta_xg_home = delta_fracional(xg_home, perfil_casa["xg_proxy_media"], minuto)
        delta_xg_away = delta_fracional(xg_away, perfil_fora["xg_proxy_media"], minuto)
        delta_pressao_home = delta_fracional(pressao_home, perfil_casa["dangerous_attacks_media"], minuto)
        delta_pressao_away = delta_fracional(pressao_away, perfil_fora["dangerous_attacks_media"], minuto)

        ajuste_home = fator_ajuste_lambda(delta_xg_home, delta_pressao_home)
        ajuste_away = fator_ajuste_lambda(delta_xg_away, delta_pressao_away)

        probs_sem_ajuste = probabilidades_ao_vivo(
            lambda_home, lambda_away, minuto, gols_home_parcial, gols_away_parcial
        )
        probs_com_ajuste = probabilidades_ao_vivo(
            lambda_home, lambda_away, minuto, gols_home_parcial, gols_away_parcial, ajuste_home, ajuste_away
        )

        prob_dada_ao_resultado_sem = probs_sem_ajuste[f"prob_{resultado}"]
        prob_dada_ao_resultado_com = probs_com_ajuste[f"prob_{resultado}"]

        linhas_saida.append({
            "fixture_id": fixture_id,
            "data": data_jogo,
            "liga": fixture.get("league", {}).get("name", "?"),
            "jogo": f"{home['name']} x {away['name']}",
            "placar_final": f"{gols_home_final}-{gols_away_final}",
            "resultado_real": resultado,
            "minuto_checkpoint": minuto,
            "placar_parcial_reconstruido": f"{gols_home_parcial}-{gols_away_parcial}",
            "xg_proxy_home": xg_home,
            "xg_proxy_away": xg_away,
            "ajuste_home": round(ajuste_home, 2),
            "ajuste_away": round(ajuste_away, 2),
            "prob_resultado_sem_ajuste": round(prob_dada_ao_resultado_sem, 4),
            "prob_resultado_com_ajuste": round(prob_dada_ao_resultado_com, 4),
            "melhorou_com_ajuste": prob_dada_ao_resultado_com > prob_dada_ao_resultado_sem,
        })

    print(f"  [OK] {home['name']} x {away['name']} ({gols_home_final}-{gols_away_final}) — {len(CHECKPOINTS)} checkpoints")


def rodar():
    mapa_types = carregar_mapa_types()
    fixtures = sm.fixtures_finalizadas_ligas(DIAS_HISTORICO)
    print(f"{len(fixtures)} jogos finalizados encontrados nas 5 ligas (últimos {DIAS_HISTORICO} dias)\n")

    linhas_saida = []
    for i, f in enumerate(fixtures, 1):
        print(f"[{i}/{len(fixtures)}] processando fixture {f['id']}...")
        try:
            analisar_fixture(f, mapa_types, linhas_saida)
        except Exception as e:
            print(f"  [ERRO] {e}")
        time.sleep(0.3)  # respeita o rate limit sem precisar disso, mas evita rajada

    if not linhas_saida:
        print("\nNenhum resultado gerado. Verifique se as ligas têm cobertura de 'trends'.")
        return

    caminho_csv = os.path.join(config.DATA_DIR, "backtest_resultados.csv")
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(caminho_csv, "w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=linhas_saida[0].keys())
        writer.writeheader()
        writer.writerows(linhas_saida)

    # resumo rápido no terminal
    media_sem = sum(l["prob_resultado_sem_ajuste"] for l in linhas_saida) / len(linhas_saida)
    media_com = sum(l["prob_resultado_com_ajuste"] for l in linhas_saida) / len(linhas_saida)
    pct_melhorou = sum(1 for l in linhas_saida if l["melhorou_com_ajuste"]) / len(linhas_saida) * 100

    # "% de leituras que melhoraram" trata os 5 checkpoints do MESMO jogo como
    # ensaios independentes — não são: se o ajuste ajuda (ou atrapalha) num
    # jogo, tende a ajudar/atrapalhar nos 5 checkpoints dele juntos (mesmo erro
    # sistemático de xG_proxy pro jogo inteiro). É a mesma pseudo-replicação
    # que a pesquisa de gols/escanteios teve que evitar (nunca tratar
    # snapshots do mesmo jogo como jogos independentes). Por isso o número que
    # importa de verdade é por JOGO, não por leitura.
    por_jogo = {}
    for l in linhas_saida:
        delta = l["prob_resultado_com_ajuste"] - l["prob_resultado_sem_ajuste"]
        por_jogo.setdefault(l["fixture_id"], []).append(delta)
    deltas_medios = [sum(ds) / len(ds) for ds in por_jogo.values()]
    n_jogos = len(deltas_medios)
    jogos_melhor = sum(1 for d in deltas_medios if d > 0)
    jogos_pior = sum(1 for d in deltas_medios if d < 0)

    print(f"\n{'='*60}")
    print(f"RESUMO — {len(linhas_saida)} leituras em {len(fixtures)} jogos")
    print(f"{'='*60}")
    print(f"Probabilidade média dada ao resultado real, SEM ajuste: {media_sem*100:.1f}%")
    print(f"Probabilidade média dada ao resultado real, COM ajuste: {media_com*100:.1f}%")
    print(f"Ajuste melhorou a leitura em {pct_melhorou:.1f}% dos casos "
          f"(cuidado: {len(linhas_saida)} leituras não são {len(linhas_saida)} jogos "
          f"independentes — ver número por JOGO abaixo)")
    print(f"\nPor JOGO (n={n_jogos}, a unidade que conta de verdade): "
          f"ajuste melhor em {jogos_melhor}, pior em {jogos_pior} "
          f"({jogos_melhor/n_jogos*100:.1f}% favorável)")
    if n_jogos < 100:
        print(f"Aviso: {n_jogos} jogos é uma amostra pequena — mesmo padrão de rigor do resto do "
              f"projeto pediria centenas de jogos antes de confiar nesse veredito.")
    print(f"\nDetalhes salvos em: {caminho_csv}")


if __name__ == "__main__":
    rodar()
