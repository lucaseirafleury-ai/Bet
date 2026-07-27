"""
FASE 2 — Monitoramento ao vivo (versão estendida).

A cada ciclo, para cada jogo ao vivo monitorado:
  1. Lê estatísticas acumuladas (xG_proxy, pressão, escanteios, cartões, eficiência
     — usadas no card do painel, não geram sinal sozinhas)
  2. Compara a CONTAGEM de gols real com a esperada (perfil pré-live)
     prorrateada pelo minuto — único tipo de sinal do painel. Só dispara
     quando o desvio é grande em percentual E em número absoluto (ver
     LIMIAR_DELTA_GOLS/LIMIAR_ABS_GOLS em config.py) E o xG_proxy concorda
     com a direção — critério deliberadamente rigoroso: é normal um jogo
     terminar sem gerar nenhum sinal.
  3. Publica:
       - data/live_snapshots.json  → estado atual rico de cada jogo (painel permanente)
       - data/live_insights.json   → só os eventos que cruzaram o limiar (feed de alertas)
"""
import json
import os
import time
from datetime import datetime, timezone

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


# Estados da Sportmonks que significam "bola rolando de verdade" (ver /states).
# A Sportmonks às vezes lista jogos que ainda não começaram (NS) ou já
# terminaram (FT) no feed de /livescores/inplay — sem esse filtro, esses jogos
# aparecem no painel como "ao vivo" travados no minuto 1, com tudo zerado.
ESTADOS_REALMENTE_AO_VIVO = {2, 3, 4, 6, 9, 21, 22, 23, 25}


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


# ── Geração de insights (só os que cruzam limiar) ─────────────

def _insight_base(relatorio, minuto, tipo, time_nome, delta_pct, mensagem):
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fixture_id": relatorio["fixture_id"],
        "jogo": f"{relatorio['home']} x {relatorio['away']}",
        "liga": relatorio["liga"],
        "minuto": minuto,
        "tipo": tipo,
        "time": time_nome,
        "delta_pct": delta_pct,
        "mensagem": mensagem,
    }


def checar_ritmo_gols(relatorio, minuto, time_nome, gols_reais, lambda_time, xg_atual, xg_media_prelive, dados_xg_disponiveis):
    """
    Único tipo de sinal do painel: gols reais x esperado (perfil pré-live
    prorrateado pelo relógio). Só dispara quando os DOIS critérios batem
    (desvio percentual grande E diferença mínima em número absoluto de gols —
    evita sinal bobo tipo "233% acima" quando o esperado até aquele minuto é
    só uma fração de gol) E o xG_proxy concorda com a direção do desvio —
    evita alertar "abaixo do esperado" quando o time nem está criando chance
    nenhuma (aí não é falta de sorte, é falta de processo ofensivo mesmo), ou
    "acima" sem nenhum chute de verdade sustentando o resultado.
    """
    if lambda_time <= 0 or minuto < config.MINUTO_MINIMO_ALERTA:
        return None
    esperado_prorrateado = lambda_time * (minuto / 90)
    if esperado_prorrateado <= 0:
        return None
    diferenca_abs = gols_reais - esperado_prorrateado
    if abs(diferenca_abs) < config.LIMIAR_ABS_GOLS:
        return None
    delta = diferenca_abs / esperado_prorrateado
    if abs(delta) < config.LIMIAR_DELTA_GOLS:
        return None
    direcao = "acima" if delta > 0 else "abaixo"

    if dados_xg_disponiveis and xg_media_prelive > 0:
        xg_esperado = xg_media_prelive * (minuto / 90)
        diff_xg = xg_atual - xg_esperado
        concorda = diff_xg >= 0 if direcao == "acima" else diff_xg <= 0
        if not concorda:
            return None
        confirmacao = (f" xG_proxy também {direcao} do esperado "
                       f"(real: {xg_atual:g}, esperado até aqui: {xg_esperado:.2f}), confirma o sinal.")
    else:
        confirmacao = ""

    msg = (f"min {minuto} — {time_nome}: ritmo de gols {direcao} do esperado "
           f"({gols_reais:g} real vs {esperado_prorrateado:.1f} esperado até aqui, "
           f"{round(abs(delta) * 100, 1)}% de desvio).{confirmacao}")
    return _insight_base(relatorio, minuto, "gols", time_nome, round(delta * 100, 1), msg)


# ── Comparação de mercado: pré-live (estático) x ao vivo ──────
# Mesma pergunta dos sinais ("o jogo está à frente ou atrás do esperado?"),
# aplicada a cada mercado individual (vitória/empate/over-under/BTTS/
# escanteios) pra mostrar um selo ao lado da odd no card, em vez de exigir
# que o usuário digite a odd real pra comparar.

MERCADOS_COMPARAVEIS = [
    "prob_casa", "prob_empate", "prob_fora",
    "prob_over25", "prob_under25",
    "prob_btts_sim", "prob_btts_nao",
    "prob_over_escanteios", "prob_under_escanteios",
]


def _probs_prelive_estaticas(relatorio):
    """Probabilidade de cada mercado ANTES do jogo começar (minuto 0, 0x0, sem ajuste ao vivo)."""
    base = probabilidades_ao_vivo(relatorio["lambda_home"], relatorio["lambda_away"], 0, 0, 0, 1.0, 1.0)
    base.update(probabilidade_escanteios(
        relatorio["perfil_casa"]["escanteios_media"], relatorio["perfil_fora"]["escanteios_media"],
        0, 0, 0, config.LINHA_ESCANTEIROS,
    ))
    return base


def comparar_mercados(relatorio, probs_ao_vivo):
    prelive_estatico = _probs_prelive_estaticas(relatorio)
    comparacao = {}
    for mercado in MERCADOS_COMPARAVEIS:
        diff_pp = round((probs_ao_vivo[mercado] - prelive_estatico[mercado]) * 100, 1)
        if abs(diff_pp) >= config.LIMIAR_PP_MERCADO_FORTE:
            situacao, forte = ("acima" if diff_pp > 0 else "abaixo"), True
        elif abs(diff_pp) >= config.LIMIAR_PP_MERCADO:
            situacao, forte = ("acima" if diff_pp > 0 else "abaixo"), False
        else:
            situacao, forte = "equilibrado", False
        comparacao[mercado] = {"situacao": situacao, "forte": forte, "diff_pp": diff_pp}
    return comparacao


# ── Ciclo principal ────────────────────────────────────────────

def ciclo():
    prelive = carregar_prelive()
    insights = _carregar(config.LIVE_INSIGHTS_FILE, [])
    snapshots = {}

    # Chave sem o minuto: cada combinação (jogo, tipo de sinal, time) dispara no
    # máximo uma vez por partida. Sem isso, um desvio que persiste (ex: time que
    # abre 2 gols de vantagem sobre o esperado) reenvia o mesmo sinal a cada
    # ciclo de 60s pelo resto do jogo — é o que causava "centenas de sinais".
    ids_ja_gerados = {(i["fixture_id"], i["tipo"], i["time"]) for i in insights}

    fixtures = sm.live_fixtures()
    fixtures_monitoradas = [
        f for f in fixtures
        if f.get("league_id") in config.LIGAS_MONITORADAS
        and f.get("state_id") in ESTADOS_REALMENTE_AO_VIVO
    ]

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
        # Algumas ligas/partidas não têm o feed de chutes/ataques perigosos da
        # Sportmonks preenchido (fica tudo zerado a partida toda). Sem essa
        # guarda, xG_proxy=0 vira falso sinal de "eficiência anormal" assim que
        # sai um gol, e o ajuste de pressão/xG usa uma base de dados inexistente.
        dados_ofensivos_disponiveis = minuto < 30 or xg_home > 0 or xg_away > 0
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
        # Só aplica esse ajuste quando há dado ofensivo de verdade — sem essa
        # guarda, xG_proxy=0 (jogo sem feed de chutes) distorce a probabilidade
        # ao vivo exibida no card, não só os sinais.
        if minuto >= config.MINUTO_MINIMO_ALERTA and dados_ofensivos_disponiveis:
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

        # ── comparação pré-live x ao vivo, por mercado (pra badge no card) ──
        probs["comparacao"] = comparar_mercados(relatorio, probs)

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
            # Único sinal do painel: ritmo de gols (real x esperado), com
            # confirmação do xG_proxy quando disponível.
            checar_ritmo_gols(relatorio, minuto, home["name"], gols_home, lambda_home, xg_home, perfil_c["xg_proxy_media"], dados_ofensivos_disponiveis),
            checar_ritmo_gols(relatorio, minuto, away["name"], gols_away, lambda_away, xg_away, perfil_f["xg_proxy_media"], dados_ofensivos_disponiveis),
        ]

        for c in candidatos:
            if c is None:
                continue
            chave = (c["fixture_id"], c["tipo"], c["time"])
            if chave in ids_ja_gerados:
                continue
            insights.append(c)
            ids_ja_gerados.add(chave)
            print(f"[INSIGHT] {c['jogo']} — {c['mensagem']}")
            _notificar_push(c)

    _salvar(config.LIVE_INSIGHTS_FILE, insights)
    _salvar(config.LIVE_SNAPSHOTS_FILE, snapshots)
    _atualizar_status(len(fixtures_monitoradas))


def _atualizar_status(qtd_jogos_live):
    _salvar(config.STATUS_FILE, {
        "ultima_checagem": datetime.now(timezone.utc).isoformat(),
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
