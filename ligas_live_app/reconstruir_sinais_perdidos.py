"""
Reconstrói sinais publicados HOJE que se perderam num redeploy (data/*.json
é efêmero, apagado a cada deploy no Render — ver conversa de 2026-09-05).

Só é possível porque, ao contrário dos nossos próprios arquivos efêmeros, a
Sportmonks mantém o histórico completo (trends minuto a minuto + eventos)
de partidas JÁ FINALIZADAS. Reaplicamos exatamente a mesma lógica de regras
(checar_sinais_confirmados/_consolidar_candidatas, regras_sinais.json) sobre
esse histórico reconstruído, nos mesmos checkpoints (15/30/45/60/75/90) que
o monitor ao vivo usa.

O que NÃO dá pra recuperar: a odd real da casa de apostas no momento exato
em que o sinal teria disparado (isso não fica versionado por minuto na API
— só o "latest_bookmaker_update" mais recente, que hoje em dia já reflete
um momento muito depois do sinal). Por isso odds_ao_vivo.buscar_odd_real é
substituído por uma versão que sempre devolve None: as linhas reconstruídas
saem sem odd_real/odd_real_casa/ev_pct/linha_original_sinal, usando só a
odd_minima sintética — mesmo tratamento que qualquer sinal antigo que nunca
achou odd real ao vivo.

Simulação MINUTO A MINUTO (não só nos checkpoints exatos): o monitor real
roda um ciclo a cada ~1min e, dentro da janela de cada checkpoint (ex.:
15-18min pro checkpoint 15), pode ter capturado a condição em qualquer
minuto dessa janela — inclusive DEPOIS de um gol que só saiu no meio dela
(o que muda "gols_momento" e pode fazer uma regra diferente bater). Testado
contra os dados de hoje: um sinal real (Odd x Strømsgodset, "mais de 9.5
escanteios") só aparecia no minuto 33 dentro da janela do checkpoint 30
(15-18/30-33/etc.), não no minuto 30 exato — por isso a simulação varre
minuto a minuto de 15 até 93 (checkpoint 90 + janela), não só os 6
checkpoints, replicando o polling contínuo do ciclo() real.
"""
import sys
import types
from datetime import date, datetime, timezone

# pywebpush não está instalado neste ambiente de reconstrução (não usado
# aqui — este script nunca chama _notificar_push) — stub só pra permitir
# importar live_monitor sem precisar da dependência real de push.
sys.modules.setdefault("pywebpush", types.SimpleNamespace(webpush=lambda *a, **k: None, WebPushException=Exception))

import config
import sportmonks_client as sm
import odds_ao_vivo
from backtest import carregar_mapa_types, valor_acumulado_no_minuto, gols_ate_minuto, identificar_type_id_gol
from xg_pressure import CAMPO_API_REGRAS
import live_monitor as lm

# Nunca inventa odd real — ver docstring do módulo.
odds_ao_vivo.buscar_odd_real = lambda *a, **k: None

MINUTO_INICIAL_SIMULACAO = min(lm.CHECKPOINTS_REGRA)
MINUTO_FINAL_SIMULACAO = max(lm.CHECKPOINTS_REGRA) + lm.JANELA_MINUTOS_REGRA
MINUTO_FINAL_GRADE = 200  # minuto bem alto -> pega o último valor cumulativo real (fim de jogo)


def _valores_combinados(trends, mapa_types, home_id, away_id, minuto, campos):
    valores = {}
    for campo in campos:
        nome_api = CAMPO_API_REGRAS.get(campo)
        type_id = mapa_types.get(nome_api) if nome_api else None
        if type_id is None:
            valores[campo] = 0.0
            continue
        v_home = valor_acumulado_no_minuto(trends, type_id, home_id, minuto)
        v_away = valor_acumulado_no_minuto(trends, type_id, away_id, minuto)
        valores[campo] = v_home + v_away
    return valores


def _reconstruir_fixture(fixture_resumo, mapa_types, data_hoje_str):
    fixture_id = fixture_resumo["id"]
    fixture = sm.fixture_com_trends(fixture_id)
    if not fixture:
        return None, "sem dados do fixture"

    data_jogo = (fixture.get("starting_at") or "")[:10]
    if data_jogo != data_hoje_str:
        return None, f"não é de hoje ({data_jogo})"

    trends = fixture.get("trends", [])
    if not trends:
        return None, "sem cobertura de trends"

    participants = fixture.get("participants", [])
    home = next((p for p in participants if p["meta"]["location"] == "home"), None)
    away = next((p for p in participants if p["meta"]["location"] == "away"), None)
    if not home or not away:
        return None, "participantes não identificados"

    liga_nome = config.LIGAS_MONITORADAS.get(fixture_resumo.get("league", {}).get("id"), fixture.get("league", {}).get("name", "?"))

    scores = fixture.get("scores", [])
    gols_home_final = next((s["score"]["goals"] for s in scores
                             if s.get("description") == "CURRENT" and s.get("participant_id") == home["id"]), None)
    gols_away_final = next((s["score"]["goals"] for s in scores
                             if s.get("description") == "CURRENT" and s.get("participant_id") == away["id"]), None)
    if gols_home_final is None or gols_away_final is None:
        return None, "placar final não encontrado"

    events = fixture.get("events", [])
    goal_type_id = identificar_type_id_gol(mapa_types)

    relatorio_min = {
        "fixture_id": fixture_id,
        "liga": liga_nome,
        "home": home["name"],
        "away": away["name"],
    }

    insights_deste_jogo = []
    for minuto in range(MINUTO_INICIAL_SIMULACAO, MINUTO_FINAL_SIMULACAO + 1):
        valores_combinados = _valores_combinados(trends, mapa_types, home["id"], away["id"], minuto, lm.CAMPOS_REGRAS_SINAIS)
        gols_home_parcial = gols_ate_minuto(events, home["id"], minuto, goal_type_id, gols_home_final)
        gols_away_parcial = gols_ate_minuto(events, away["id"], minuto, goal_type_id, gols_away_final)
        gols_totais_jogo = gols_home_parcial + gols_away_parcial

        # Mesma lógica de checar_sinais_confirmados (checkpoint <= minuto <=
        # checkpoint+janela) — reimplementada em vez de chamada direta porque
        # aqui o "minuto" é simulado, não vem de extrair_minuto(fixture).
        candidatas = []
        for checkpoint in lm.CHECKPOINTS_REGRA:
            if not (checkpoint <= minuto <= checkpoint + lm.JANELA_MINUTOS_REGRA):
                continue
            for regra in lm.REGRAS_POR_CHECKPOINT_PLACAR.get((checkpoint, gols_totais_jogo), []):
                if not lm._regra_bate(regra, valores_combinados):
                    continue
                stats = lm._stats_para_valor_atual(regra, valores_combinados)
                if stats is None or stats["impacto_pp"] < lm.IMPACTO_MINIMO_PP_VALOR_ATUAL:
                    continue
                if stats["p_condicao"] < lm.PROBABILIDADE_MINIMA_VALOR_ATUAL:
                    continue
                stats = dict(stats, valor_atual_real=int(round(valores_combinados.get(regra["mercado"]["stat"], 0.0))))
                candidatas.append((regra, stats))

        direcoes_ja_disparadas = lm._direcoes_ja_disparadas(insights_deste_jogo, fixture_id)
        novos = lm._consolidar_candidatas(relatorio_min, candidatas, direcoes_ja_disparadas, minuto)
        for n in novos:
            chave = (n["fixture_id"], n["tipo"], n["time"])
            if any((i["fixture_id"], i["tipo"], i["time"]) == chave for i in insights_deste_jogo):
                continue
            insights_deste_jogo.append(n)

    if not insights_deste_jogo:
        return [], None

    # Grade final (mesma fórmula de _avaliar_sinais_confirmados) usando o
    # valor cumulativo real de fim de jogo (minuto bem alto -> pega o último
    # trend registrado, que é o total real da partida).
    valores_finais = _valores_combinados(trends, mapa_types, home["id"], away["id"], MINUTO_FINAL_GRADE, ["corners", "shots_total", "shots_on_target"])
    valor_final_por_alvo = {
        "escanteios": valores_finais["corners"],
        "chutes_totais": valores_finais["shots_total"],
        "chutes_no_alvo": valores_finais["shots_on_target"],
    }
    for sinal in insights_deste_jogo:
        alvo = sinal.get("alvo")
        if not alvo or alvo not in valor_final_por_alvo or "linha" not in sinal:
            continue
        valor_final = valor_final_por_alvo[alvo]
        bateu = (valor_final > sinal["linha"]) if sinal["direcao"] == "mais_de" else (valor_final < sinal["linha"])
        sinal["valor_final_alvo"] = valor_final
        sinal["resultado"] = "green" if bateu else "red"
        sinal["data_jogo"] = data_jogo

    return insights_deste_jogo, None


def rodar(data_alvo=None):
    data_alvo_str = data_alvo or date.today().isoformat()
    mapa_types = carregar_mapa_types()
    fixtures = sm.fixtures_finalizadas_ligas(dias_para_tras=2)
    print(f"{len(fixtures)} fixtures finalizadas nas 5 ligas (últimos 2 dias) — filtrando pra {data_alvo_str}")

    todos_insights = []
    for i, f in enumerate(fixtures, 1):
        print(f"[{i}/{len(fixtures)}] fixture {f['id']} ({f.get('league', {}).get('name', '?')})...")
        try:
            insights, motivo = _reconstruir_fixture(f, mapa_types, data_alvo_str)
        except Exception as e:
            print(f"  [ERRO] {e}")
            continue
        if insights is None:
            print(f"  [pulado] {motivo}")
            continue
        if not insights:
            print("  [ok] nenhuma condição bateu nesse jogo")
            continue
        print(f"  [OK] {len(insights)} sinal(is) reconstruído(s)")
        todos_insights.extend(insights)

    print(f"\nTotal reconstruído: {len(todos_insights)} sinais")
    return todos_insights


if __name__ == "__main__":
    data_arg = sys.argv[1] if len(sys.argv) > 1 else None
    resultado = rodar(data_arg)
    import json
    with open("/tmp/sinais_reconstruidos.json", "w", encoding="utf-8") as fp:
        json.dump(resultado, fp, ensure_ascii=False, indent=2, default=str)
    print("Salvo em /tmp/sinais_reconstruidos.json")
