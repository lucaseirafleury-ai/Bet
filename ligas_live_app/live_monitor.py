"""
FASE 2 — Monitoramento ao vivo (versão estendida).

A cada ciclo, para cada jogo ao vivo monitorado:
  1. Lê estatísticas acumuladas (xG_proxy, pressão, escanteios, cartões, eficiência)
  2. Guarda um snapshot no histórico da partida (para calcular momentum)
  3. Compara com o esperado (perfil pré-live) em 4 frentes:
       - ritmo de gols
       - ritmo de escanteios
       - ritmo de cartões
       - pressão / xG_proxy (com confirmação de tendência via momentum)
  4. Compara xG_proxy acumulado x gols reais, por time (divergência)
  5. Publica:
       - data/live_snapshots.json  → estado atual rico de cada jogo (painel permanente)
       - data/live_insights.json   → só os eventos que cruzaram o limiar (feed de alertas)
"""
import json
import os
import time
from datetime import datetime

from pywebpush import webpush, WebPushException

import config
import sportmonks_client as sm
from xg_pressure import (
    calcular_xg_proxy, calcular_pressao, calcular_cartoes,
    calcular_escanteios, calcular_eficiencia, calcular_momentum,
    extrair_stats_completas, extrair_minuto,
)
from live_poisson import (
    probabilidades_ao_vivo, probabilidade_escanteios,
    delta_fracional, fator_ajuste_lambda,
    probabilidades_over_under_calibrado, MODELOS_CALIBRADOS_POR_LIGA,
)


# ── Persistência simples em JSON ──────────────────────────────

def _carregar(caminho, default):
    if not os.path.exists(caminho):
        return default
    with open(caminho, encoding="utf-8") as fp:
        return json.load(fp)


def _salvar(caminho, obj):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as fp:
        json.dump(obj, fp, ensure_ascii=False, indent=2)


# ── Notificação push (Web Push) ────────────────────────────────

def _notificar_push(insight):
    if not config.VAPID_PRIVATE_KEY:
        return
    inscricoes = _carregar(config.PUSH_SUBS_FILE, [])
    if not inscricoes:
        return

    payload = json.dumps({
        "title": insight["jogo"],
        "body": insight["mensagem"],
        "url": "/",
    })

    validas = []
    for sub in inscricoes:
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=config.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": config.VAPID_CLAIMS_EMAIL},
            )
            validas.append(sub)
        except WebPushException as e:
            codigo = getattr(e.response, "status_code", None)
            if codigo not in (404, 410):  # inscrição expirada/removida pelo navegador
                print(f"[push] erro ao enviar (mantendo inscrição): {e}")
                validas.append(sub)
            else:
                print(f"[push] inscrição expirada removida: {e}")
        except Exception as e:
            print(f"[push] erro ao enviar: {e}")
            validas.append(sub)

    if len(validas) != len(inscricoes):
        _salvar(config.PUSH_SUBS_FILE, validas)


def carregar_prelive():
    data = _carregar(config.PRELIVE_FILE, {"relatorios": []})
    return {r["fixture_id"]: r for r in data.get("relatorios", [])}


# ── Momentum: confirma se a tendência é consistente ───────────

def direcao_consistente(valores):
    """
    valores: lista de floats, do mais antigo pro mais recente (últimas N leituras).
    Retorna 'subindo', 'descendo' ou None (sem tendência clara).
    """
    if len(valores) < 2:
        return None
    diffs = [valores[i] - valores[i - 1] for i in range(1, len(valores))]
    positivos = sum(1 for d in diffs if d > 0)
    negativos = sum(1 for d in diffs if d < 0)
    if positivos >= config.MIN_LEITURAS_CONSISTENTES and negativos == 0:
        return "subindo"
    if negativos >= config.MIN_LEITURAS_CONSISTENTES and positivos == 0:
        return "descendo"
    return None


def atualizar_historico(historico, fixture_id, minuto, ponto):
    """Acrescenta um ponto ao histórico da partida, evitando duplicar o mesmo minuto."""
    hist_jogo = historico.setdefault(str(fixture_id), [])
    if hist_jogo and hist_jogo[-1]["minuto"] == minuto:
        hist_jogo[-1] = ponto  # atualiza o último ponto em vez de duplicar
    else:
        hist_jogo.append(ponto)
    historico[str(fixture_id)] = hist_jogo[-config.JANELA_MOMENTUM:]
    return historico[str(fixture_id)]


# ── Geração de insights (só os que cruzam limiar) ─────────────

def _insight_base(relatorio, minuto, tipo, time_nome, delta_pct, mensagem):
    return {
        "timestamp": datetime.now().isoformat(),
        "fixture_id": relatorio["fixture_id"],
        "jogo": f"{relatorio['home']} x {relatorio['away']}",
        "liga": relatorio["liga"],
        "minuto": minuto,
        "tipo": tipo,
        "time": time_nome,
        "delta_pct": delta_pct,
        "mensagem": mensagem,
    }


def checar_ritmo_mercado(relatorio, minuto, time_nome, valor_real_acumulado, valor_esperado_90min, tipo, limiar):
    if valor_esperado_90min <= 0 or minuto < config.MINUTO_MINIMO_ALERTA:
        return None
    esperado_prorrateado = valor_esperado_90min * (minuto / 90)
    if esperado_prorrateado <= 0:
        return None
    delta = (valor_real_acumulado - esperado_prorrateado) / esperado_prorrateado
    if abs(delta) < limiar:
        return None
    direcao = "acima" if delta > 0 else "abaixo"
    nomes = {"gols": "ritmo de gols", "escanteios": "ritmo de escanteios", "cartoes": "ritmo de cartões"}
    msg = (f"min {minuto} — {time_nome}: {nomes[tipo]} {round(abs(delta) * 100, 1)}% {direcao} "
           f"do esperado para esse momento.")
    return _insight_base(relatorio, minuto, tipo, time_nome, round(delta * 100, 1), msg)


def checar_pressao_xg_com_momentum(relatorio, minuto, time_nome, tipo, historico_time, valor_atual, valor_esperado_90min, limiar):
    if minuto < config.MINUTO_MINIMO_ALERTA or valor_esperado_90min <= 0:
        return None
    esperado_prorrateado = valor_esperado_90min * (minuto / 90)
    if esperado_prorrateado <= 0:
        return None
    delta = (valor_atual - esperado_prorrateado) / esperado_prorrateado
    if abs(delta) < limiar:
        return None

    lado = "home" if time_nome == relatorio["home"] else "away"
    valores = [p.get(f"{tipo}_{lado}") for p in historico_time]
    valores = [v for v in valores if v is not None]
    direcao_tendencia = direcao_consistente(valores)
    if delta > 0 and direcao_tendencia != "subindo":
        return None
    if delta < 0 and direcao_tendencia != "descendo":
        return None

    direcao = "acima" if delta > 0 else "abaixo"
    nomes = {"pressao": "Pressão", "xg": "xG_proxy"}
    msg = (f"min {minuto} — {time_nome}: {nomes[tipo]} {round(abs(delta) * 100, 1)}% {direcao} do esperado, "
           f"tendência confirmada nas últimas {config.JANELA_MOMENTUM} leituras.")
    return _insight_base(relatorio, minuto, tipo, time_nome, round(delta * 100, 1), msg)


def checar_divergencia_xg_gols(relatorio, minuto, time_nome, xg_acumulado, gols_atuais):
    if minuto < config.MINUTO_MINIMO_ALERTA:
        return None
    divergencia = xg_acumulado - gols_atuais
    if abs(divergencia) < config.LIMIAR_DIVERGENCIA_XG_GOLS:
        return None
    if divergencia > 0:
        msg = (f"min {minuto} — {time_nome}: xG_proxy acumulado ({xg_acumulado}) está "
               f"{round(divergencia, 2)} acima dos gols reais ({gols_atuais}). Time criando mais do que converte.")
    else:
        msg = (f"min {minuto} — {time_nome}: gols reais ({gols_atuais}) acima do xG_proxy acumulado "
               f"({xg_acumulado}). Eficiência anormal, risco de regressão.")
    return _insight_base(relatorio, minuto, "divergencia_xg_gols", time_nome, round(divergencia, 2), msg)


# ── Ciclo principal ────────────────────────────────────────────

def ciclo():
    prelive = carregar_prelive()
    insights = _carregar(config.LIVE_INSIGHTS_FILE, [])
    historico = _carregar(config.LIVE_HISTORY_FILE, {})
    snapshots = {}

    ids_ja_gerados = {(i["fixture_id"], i["minuto"], i["tipo"], i["time"]) for i in insights}

    fixtures = sm.live_fixtures()
    fixtures_monitoradas = [f for f in fixtures if f.get("league_id") in config.LIGAS_MONITORADAS]

    for f in fixtures_monitoradas:
        fixture_id = f["id"]
        league_id = f.get("league_id")
        relatorio = prelive.get(fixture_id)
        if not relatorio:
            continue  # jogo sem análise pré-live correspondente

        minuto = extrair_minuto(f)

        participants = f.get("participants", [])
        home = next((p for p in participants if p["meta"]["location"] == "home"), None)
        away = next((p for p in participants if p["meta"]["location"] == "away"), None)
        if not home or not away:
            continue

        stats = f.get("statistics", [])
        stats_home = [s for s in stats if s.get("participant_id") == home["id"]]
        stats_away = [s for s in stats if s.get("participant_id") == away["id"]]

        xg_home = calcular_xg_proxy(stats_home)
        xg_away = calcular_xg_proxy(stats_away)
        pressao_home = calcular_pressao(stats_home, minuto)
        pressao_away = calcular_pressao(stats_away, minuto)
        escanteios_home = calcular_escanteios(stats_home)
        escanteios_away = calcular_escanteios(stats_away)
        cartoes_home = calcular_cartoes(stats_home)
        cartoes_away = calcular_cartoes(stats_away)
        eficiencia_home = calcular_eficiencia(stats_home)
        eficiencia_away = calcular_eficiencia(stats_away)
        momentum_home, momentum_away = calcular_momentum(stats_home, stats_away)
        stats_completas_home = extrair_stats_completas(stats_home)
        stats_completas_away = extrair_stats_completas(stats_away)

        scores = f.get("scores", [])
        gols_home = next((s["score"]["goals"] for s in scores
                           if s.get("description") == "CURRENT" and s.get("participant_id") == home["id"]), 0) or 0
        gols_away = next((s["score"]["goals"] for s in scores
                           if s.get("description") == "CURRENT" and s.get("participant_id") == away["id"]), 0) or 0

        perfil_c, perfil_f = relatorio["perfil_casa"], relatorio["perfil_fora"]

        # ── ajuste dinâmico do lambda: pré-live + desvio de xG/pressão observado ──
        if minuto >= config.MINUTO_MINIMO_ALERTA:
            delta_xg_home = delta_fracional(xg_home, perfil_c["xg_proxy_media"], minuto)
            delta_xg_away = delta_fracional(xg_away, perfil_f["xg_proxy_media"], minuto)
            delta_pressao_home = delta_fracional(pressao_home, perfil_c["dangerous_attacks_media"], minuto)
            delta_pressao_away = delta_fracional(pressao_away, perfil_f["dangerous_attacks_media"], minuto)
            ajuste_home = fator_ajuste_lambda(delta_xg_home, delta_pressao_home)
            ajuste_away = fator_ajuste_lambda(delta_xg_away, delta_pressao_away)
        else:
            ajuste_home = ajuste_away = 1.0  # antes do minuto mínimo, só pré-live + relógio

        probs = probabilidades_ao_vivo(
            relatorio["lambda_home"], relatorio["lambda_away"], minuto, gols_home, gols_away,
            ajuste_home, ajuste_away,
        )
        probs_escanteios = probabilidade_escanteios(
            perfil_c["escanteios_media"], perfil_f["escanteios_media"],
            minuto, escanteios_home, escanteios_away, config.LINHA_ESCANTEIROS,
        )
        probs.update(probs_escanteios)
        probs["linha_escanteios"] = config.LINHA_ESCANTEIROS
        probs["ajuste_home"] = round(ajuste_home, 2)
        probs["ajuste_away"] = round(ajuste_away, 2)

        # ── Over/Under 2.5: usa o modelo calibrado ESPECÍFICO da liga quando existir
        # (validado fora da amostra); cai no ajuste heurístico se a liga não tiver
        # métrica incremental confiável (ex: A Lyga, Superettan usam "somente minuto",
        # que já é a versão mais segura pra elas — mesma matemática, coef=0) ──
        metrica_liga = MODELOS_CALIBRADOS_POR_LIGA.get(league_id, {}).get("metrica")
        if metrica_liga == "shots_total_rate15":
            valor_metrica = stats_completas_home["finalizacoes"] + stats_completas_away["finalizacoes"]
        elif metrica_liga == "shots_off_target_rate15":
            valor_metrica = stats_completas_home["chutes_fora"] + stats_completas_away["chutes_fora"]
        elif metrica_liga == "attacks_rate15":
            valor_metrica = stats_completas_home["ataques"] + stats_completas_away["ataques"]
        else:
            valor_metrica = 0  # "somente minuto" — coef=0, valor não importa

        probs_ou_calibrado = probabilidades_over_under_calibrado(
            valor_metrica, minuto, gols_home + gols_away, league_id
        )
        if probs_ou_calibrado is not None:
            probs["prob_over25"] = probs_ou_calibrado["prob_over25_calibrado"]
            probs["prob_under25"] = probs_ou_calibrado["prob_under25_calibrado"]
            probs["xg_restante_total_calibrado"] = probs_ou_calibrado["xg_restante_total_calibrado"]
            probs["over_under_fonte"] = f"calibrado_{probs_ou_calibrado['metrica_usada']}"
        else:
            probs["over_under_fonte"] = "heuristico_nao_calibrado"

        # ── histórico p/ momentum ──
        ponto = {
            "minuto": minuto, "xg_home": xg_home, "xg_away": xg_away,
            "pressao_home": pressao_home, "pressao_away": pressao_away,
        }
        hist_jogo = atualizar_historico(historico, fixture_id, minuto, ponto)

        # ── snapshot rico p/ o painel (sempre publicado, sem limiar) ──
        snapshots[str(fixture_id)] = {
            "fixture_id": fixture_id, "liga": relatorio["liga"], "minuto": minuto,
            "home": home["name"], "away": away["name"],
            "gols_home": gols_home, "gols_away": gols_away,
            "xg_proxy_home": xg_home, "xg_proxy_away": xg_away,
            "divergencia_xg_gols_home": round(xg_home - gols_home, 2),
            "divergencia_xg_gols_away": round(xg_away - gols_away, 2),
            "pressao_home": pressao_home, "pressao_away": pressao_away,
            "escanteios_home": escanteios_home, "escanteios_away": escanteios_away,
            "cartoes_home": cartoes_home, "cartoes_away": cartoes_away,
            "eficiencia_home": eficiencia_home, "eficiencia_away": eficiencia_away,
            "momentum_home": momentum_home, "momentum_away": momentum_away,
            "ajuste_lambda_home": round(ajuste_home, 2), "ajuste_lambda_away": round(ajuste_away, 2),
            "stats_completas_home": stats_completas_home,
            "stats_completas_away": stats_completas_away,
            "probabilidades": probs,
            "placar_modal_prelive": relatorio["placar_modal"],
            "favorito_pressao_prelive": relatorio["favorito_pressao"],
            "favorito_xg_prelive": relatorio["favorito_xg"],
        }

        if minuto < config.MINUTO_MINIMO_ALERTA:
            continue

        # esperados por 90min, vindos do perfil pré-live
        lambda_home, lambda_away = relatorio["lambda_home"], relatorio["lambda_away"]

        candidatos = [
            # ritmo de mercado
            checar_ritmo_mercado(relatorio, minuto, home["name"], gols_home, lambda_home, "gols", config.LIMIAR_DELTA_GOLS),
            checar_ritmo_mercado(relatorio, minuto, away["name"], gols_away, lambda_away, "gols", config.LIMIAR_DELTA_GOLS),
            checar_ritmo_mercado(relatorio, minuto, home["name"], escanteios_home, perfil_c["escanteios_media"], "escanteios", config.LIMIAR_DELTA_ESCANTEIROS),
            checar_ritmo_mercado(relatorio, minuto, away["name"], escanteios_away, perfil_f["escanteios_media"], "escanteios", config.LIMIAR_DELTA_ESCANTEIROS),
            checar_ritmo_mercado(relatorio, minuto, home["name"], cartoes_home, perfil_c["cartoes_media"], "cartoes", config.LIMIAR_DELTA_CARTOES),
            checar_ritmo_mercado(relatorio, minuto, away["name"], cartoes_away, perfil_f["cartoes_media"], "cartoes", config.LIMIAR_DELTA_CARTOES),
            # pressão / xG com momentum
            checar_pressao_xg_com_momentum(relatorio, minuto, home["name"], "xg", hist_jogo, xg_home, perfil_c["xg_proxy_media"], config.LIMIAR_DELTA_XG),
            checar_pressao_xg_com_momentum(relatorio, minuto, away["name"], "xg", hist_jogo, xg_away, perfil_f["xg_proxy_media"], config.LIMIAR_DELTA_XG),
            checar_pressao_xg_com_momentum(relatorio, minuto, home["name"], "pressao", hist_jogo, pressao_home, perfil_c["dangerous_attacks_media"], config.LIMIAR_DELTA_PRESSAO),
            checar_pressao_xg_com_momentum(relatorio, minuto, away["name"], "pressao", hist_jogo, pressao_away, perfil_f["dangerous_attacks_media"], config.LIMIAR_DELTA_PRESSAO),
            # divergência xG x gols reais
            checar_divergencia_xg_gols(relatorio, minuto, home["name"], xg_home, gols_home),
            checar_divergencia_xg_gols(relatorio, minuto, away["name"], xg_away, gols_away),
        ]

        for c in candidatos:
            if c is None:
                continue
            chave = (c["fixture_id"], c["minuto"], c["tipo"], c["time"])
            if chave in ids_ja_gerados:
                continue
            insights.append(c)
            ids_ja_gerados.add(chave)
            print(f"[INSIGHT] {c['jogo']} — {c['mensagem']}")
            _notificar_push(c)

    _salvar(config.LIVE_INSIGHTS_FILE, insights)
    _salvar(config.LIVE_HISTORY_FILE, historico)
    _salvar(config.LIVE_SNAPSHOTS_FILE, snapshots)
    _atualizar_status(len(fixtures_monitoradas))


def _atualizar_status(qtd_jogos_live):
    _salvar(config.STATUS_FILE, {
        "ultima_checagem": datetime.now().isoformat(),
        "jogos_ao_vivo_monitorados": qtd_jogos_live,
    })


def rodar_continuo():
    print("Monitoramento ao vivo iniciado. Ctrl+C para parar.")
    while True:
        try:
            ciclo()
        except Exception as e:
            print(f"[ERRO no ciclo] {e}")
        time.sleep(config.INTERVALO_POLLING_SEGUNDOS)


if __name__ == "__main__":
    rodar_continuo()
