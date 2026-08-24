"""
FASE 2 — Monitoramento ao vivo (versão estendida).

A cada ciclo, para cada jogo ao vivo monitorado:
  1. Lê estatísticas acumuladas (xG_proxy, pressão, escanteios, cartões, eficiência
     — usadas no card do painel, não geram sinal sozinhas)
  2. Compara a CONTAGEM de gols real com a esperada (perfil pré-live)
     prorrateada pelo minuto — único tipo de sinal do painel. Só dispara
     quando o desvio é grande em percentual E em número absoluto (ver
     LIMIAR_DELTA_GOLS/LIMIAR_ABS_GOLS em config.py) E o xG_proxy DIVERGE do
     placar na direção certa (time devendo gols mas criando mais chance do
     que o esperado, ou marcando mais gols do que o processo sustenta) —
     é essa divergência que indica uma entrada de valor, não a concordância
     entre placar e processo. Critério deliberadamente rigoroso: é normal um
     jogo terminar sem gerar nenhum sinal.
  3. Publica:
       - data/live_snapshots.json  → estado atual rico de cada jogo (painel permanente)
       - data/live_insights.json   → só os eventos que cruzaram o limiar (feed de alertas)
"""
import json
import os
import time
from datetime import datetime, timedelta, timezone

from pywebpush import webpush, WebPushException

import config
import sportmonks_client as sm
from xg_pressure import (
    calcular_xg_proxy, calcular_pressao, calcular_cartoes,
    calcular_escanteios, calcular_eficiencia, calcular_momentum,
    extrair_stats_completas, extrair_minuto, extrair_stats_para_regras,
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


# ── Jogos anteriores (arquivo de partidas encerradas) ──────────

def extrair_eventos_gols(fixture):
    """Lista de gols do jogo (minuto + time), a partir de fixture['events']."""
    participantes = {p["id"]: p["name"] for p in fixture.get("participants", [])}
    eventos = []
    for e in fixture.get("events", []):
        tipo = (e.get("type") or {}).get("name") or ""
        if "goal" not in tipo.lower():
            continue
        minuto = e.get("minute") or 0
        extra = e.get("extra_minute")
        rotulo_contra = " (contra)" if "own" in tipo.lower() else ""
        eventos.append({
            "minuto": minuto,
            "minuto_texto": f"{minuto}+{extra}" if extra else f"{minuto}",
            "time": participantes.get(e.get("participant_id"), "?") + rotulo_contra,
        })
    eventos.sort(key=lambda ev: ev["minuto"])
    return eventos


def _podar_jogos_antigos(jogos_anteriores):
    limite = datetime.now(timezone.utc) - timedelta(days=config.RETENCAO_JOGOS_ANTERIORES_DIAS)
    jogos_anteriores[:] = [
        j for j in jogos_anteriores
        if datetime.fromisoformat(j["arquivado_em"]) >= limite
    ]


def _arquivar_jogo_finalizado(fixture_id, snapshot_final, insights):
    """
    Chamado quando um fixture some do feed de "ao vivo" — busca o placar
    final e os eventos de gol direto na Sportmonks (uma chamada extra, só
    aqui, pra pegar o minuto de cada gol) e arquiva junto com o último
    snapshot conhecido e todos os sinais que dispararam nesse jogo.
    """
    if snapshot_final is None:
        return

    eventos_gols = []
    gols_home_final = snapshot_final.get("gols_home")
    gols_away_final = snapshot_final.get("gols_away")
    try:
        fixture = sm.fixture_by_id(fixture_id, include="events.type;participants;scores")
    except Exception as e:
        fixture = None
        print(f"[arquivo] não deu pra buscar detalhes finais do fixture {fixture_id}: {e}")

    if fixture:
        eventos_gols = extrair_eventos_gols(fixture)
        participants = fixture.get("participants", [])
        home_p = next((p for p in participants if p["meta"]["location"] == "home"), None)
        away_p = next((p for p in participants if p["meta"]["location"] == "away"), None)
        scores = fixture.get("scores", [])
        if home_p:
            gols_home_final = next(
                (s["score"]["goals"] for s in scores
                 if s.get("description") == "CURRENT" and s.get("participant_id") == home_p["id"]),
                gols_home_final,
            )
        if away_p:
            gols_away_final = next(
                (s["score"]["goals"] for s in scores
                 if s.get("description") == "CURRENT" and s.get("participant_id") == away_p["id"]),
                gols_away_final,
            )

    sinais_do_jogo = [i for i in insights if i.get("fixture_id") == fixture_id]

    registro = {
        "fixture_id": fixture_id,
        "liga": snapshot_final.get("liga"),
        "home": snapshot_final.get("home"),
        "away": snapshot_final.get("away"),
        "gols_home": gols_home_final,
        "gols_away": gols_away_final,
        "eventos_gols": eventos_gols,
        "xg_proxy_home": snapshot_final.get("xg_proxy_home"),
        "xg_proxy_away": snapshot_final.get("xg_proxy_away"),
        "divergencia_xg_gols_home": snapshot_final.get("divergencia_xg_gols_home"),
        "divergencia_xg_gols_away": snapshot_final.get("divergencia_xg_gols_away"),
        "escanteios_home": snapshot_final.get("escanteios_home"),
        "escanteios_away": snapshot_final.get("escanteios_away"),
        "cartoes_home": snapshot_final.get("cartoes_home"),
        "cartoes_away": snapshot_final.get("cartoes_away"),
        "eficiencia_home": snapshot_final.get("eficiencia_home"),
        "eficiencia_away": snapshot_final.get("eficiencia_away"),
        "momentum_home": snapshot_final.get("momentum_home"),
        "momentum_away": snapshot_final.get("momentum_away"),
        "stats_completas_home": snapshot_final.get("stats_completas_home"),
        "stats_completas_away": snapshot_final.get("stats_completas_away"),
        "placar_modal_prelive": snapshot_final.get("placar_modal_prelive"),
        "sinais": sinais_do_jogo,
        "arquivado_em": datetime.now(timezone.utc).isoformat(),
    }

    jogos_anteriores = _carregar(config.JOGOS_ANTERIORES_FILE, [])
    jogos_anteriores = [j for j in jogos_anteriores if j["fixture_id"] != fixture_id]
    jogos_anteriores.append(registro)
    _podar_jogos_antigos(jogos_anteriores)
    jogos_anteriores.sort(key=lambda j: j["arquivado_em"], reverse=True)
    _salvar(config.JOGOS_ANTERIORES_FILE, jogos_anteriores)
    print(f"[arquivo] {registro['home']} x {registro['away']} arquivado em jogos anteriores.")


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


# Rótulos dos mercados de gols (os mesmos exibidos no card, em "odd mínima").
# Escanteios ficam de fora — não têm relação causal com um desvio de gols/xG.
ROTULOS_MERCADO_GOLS = {
    "prob_casa": "Vitória {home}",
    "prob_empate": "Empate",
    "prob_fora": "Vitória {away}",
    "prob_over25": "Over 2.5 gols",
    "prob_under25": "Under 2.5 gols",
    "prob_btts_sim": "Ambas marcam - Sim",
    "prob_btts_nao": "Ambas marcam - Não",
}


def _mercados_favorecidos(relatorio, comparacao):
    """
    Traduz o sinal em "onde entrar": lista os mercados de gols que já estão
    fortemente favorecidos (mesmo critério/limiar usado no selo do card),
    pra não deixar o usuário com o diagnóstico sem a aposta correspondente.
    """
    if not comparacao:
        return ""
    favorecidos = []
    for mercado, rotulo in ROTULOS_MERCADO_GOLS.items():
        c = comparacao.get(mercado)
        if not c or not c.get("forte"):
            continue
        seta = "▲" if c["situacao"] == "acima" else "▼"
        favorecidos.append(f"{rotulo.format(home=relatorio['home'], away=relatorio['away'])} {seta}")
    if not favorecidos:
        return ""
    return " Mercados que já refletem esse desvio: " + ", ".join(favorecidos) + "."


def checar_ritmo_gols(relatorio, minuto, time_nome, gols_reais, lambda_time, xg_atual, xg_media_prelive,
                       dados_xg_disponiveis, gols_restantes_calibrado, gols_totais_jogo, comparacao=None):
    """
    Único tipo de sinal do painel. O critério que decide SE existe desvio é
    pré-definido e fixo (perfil pré-live prorrateado pelo relógio, com limiar
    duplo — percentual E absoluto). xG_proxy e o modelo calibrado por liga
    entram só DEPOIS, como filtros eliminatórios — nenhum dos dois cria sinal
    sozinho, só têm poder de veto sobre um candidato que já passou no
    critério principal:

      1. xG_proxy do time: precisa DIVERGIR do placar na direção de valor —
         devendo gols no placar, mas criando mais chance do que o de costume
         (gol pode estar a caminho); ou gols demais no placar, mas sem
         processo por trás (risco de regressão). Se os dois concordam (time
         realmente jogando mal ou bem nos dois sentidos), elimina — isso é
         só o óbvio, sem edge de mercado.
      2. Modelo calibrado por liga (ritmo de chutes/ataques + minuto, o
         mesmo usado no mercado Over/Under): projeta quantos gols o JOGO
         (os dois times somados) deve terminar tendo, dado o ritmo atual de
         jogo. Se essa projeção contradiz a direção do sinal, elimina — o
         ritmo real de chutes do jogo não sustenta a tese.

    Exige xG_proxy e modelo calibrado disponíveis: sem eles não dá pra saber
    se é uma divergência de valor ou só a continuação óbvia do esperado.
    """
    if lambda_time <= 0 or minuto < config.MINUTO_MINIMO_ALERTA:
        return None
    if not dados_xg_disponiveis or xg_media_prelive <= 0 or gols_restantes_calibrado is None:
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
    direcao_gols = "abaixo" if delta < 0 else "acima"

    # Filtro eliminatório 1: xG_proxy do time precisa divergir do placar.
    xg_esperado = xg_media_prelive * (minuto / 90)
    diff_xg = xg_atual - xg_esperado
    if direcao_gols == "abaixo" and diff_xg <= 0:
        return None  # também sem criar chance -> sem edge, só jogo ruim
    if direcao_gols == "acima" and diff_xg >= 0:
        return None  # processo sustenta os gols -> sem edge, merecido

    # Filtro eliminatório 2: ritmo de chutes do JOGO (modelo calibrado por
    # liga) não pode contradizer a direção do sinal.
    esperado_prelive_total = relatorio["lambda_home"] + relatorio["lambda_away"]
    projetado_final = gols_totais_jogo + gols_restantes_calibrado
    diff_calibrado = projetado_final - esperado_prelive_total
    if direcao_gols == "abaixo" and diff_calibrado < 0:
        return None  # ritmo do jogo também aponta pra menos gols -> sem edge
    if direcao_gols == "acima" and diff_calibrado > 0:
        return None  # ritmo do jogo também sustenta mais gols -> sem edge

    if direcao_gols == "abaixo":
        rotulo = "prestes a marcar"
        motivo = (f"devendo {abs(diferenca_abs):.1f} gol(s) em relação ao esperado "
                  f"({gols_reais:g} real vs {esperado_prorrateado:.1f} esperado até aqui), mas o xG_proxy está "
                  f"acima do próprio esperado (real: {xg_atual:g}, esperado até aqui: {xg_esperado:.2f}) e o ritmo "
                  f"de chutes do jogo projeta {projetado_final:.1f} gols no total (esperado pré-jogo: "
                  f"{esperado_prelive_total:.1f}) — criando mais chance do que o de costume, gol pode estar a caminho.")
        delta_pct_exibido = abs(round(delta * 100, 1))  # positivo -> selo verde, sinal de oportunidade
    else:
        rotulo = "sorte, risco de regressão"
        motivo = (f"{diferenca_abs:.1f} gol(s) acima do esperado "
                  f"({gols_reais:g} real vs {esperado_prorrateado:.1f} esperado até aqui), mas o xG_proxy está "
                  f"abaixo do próprio esperado (real: {xg_atual:g}, esperado até aqui: {xg_esperado:.2f}) e o ritmo "
                  f"de chutes do jogo projeta só {projetado_final:.1f} gols no total (esperado pré-jogo: "
                  f"{esperado_prelive_total:.1f}) — gols não sustentados pelo processo, risco de regressão.")
        delta_pct_exibido = -abs(round(delta * 100, 1))  # negativo -> selo vermelho, sinal de alerta

    msg = f"min {minuto} — {time_nome}: {rotulo} — {motivo}{_mercados_favorecidos(relatorio, comparacao)}"
    return _insight_base(relatorio, minuto, "gols", time_nome, delta_pct_exibido, msg)


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


# ── Sinais confirmados (pesquisa cross-liga) ──────────────────
# Regras estatísticas geradas por pesquisa_gols/gerar_regras_sinais.py: cada
# uma é uma condição (minuto + placar-no-momento + estatística(s) do jogo)
# validada dentro da Allsvenskan (split treino/teste) e depois CONFIRMADA de
# forma independente em 4 outras ligas (teste de duas proporções +
# Benjamini-Hochberg) — ver pesquisa_gols/README.md pra metodologia completa.
# Diferente de checar_ritmo_gols (heurística ao vivo deste app), aqui a
# validação estatística já foi feita fora do painel; o papel deste bloco é
# só comparar o jogo real contra as regras já confirmadas.
CAMINHO_REGRAS_SINAIS = os.path.join(os.path.dirname(__file__), "regras_sinais.json")
CHECKPOINTS_REGRA = [15, 30, 45, 60, 75, 90]
# Tolerância: uma regra do minuto X pode disparar em qualquer ciclo entre X e
# X+JANELA (polling a cada 60s raramente cai exatamente no minuto do
# checkpoint). Menor que os 15min entre checkpoints, então nunca contamina o
# checkpoint seguinte.
JANELA_MINUTOS_REGRA = 3


IMPACTO_MINIMO_PP_VALOR_ATUAL = 5.0  # mesmo limiar usado pra selecionar as regras "fortes" (gerar_regras_sinais.py)
# Exigir só vantagem sobre a base deixa passar casos tipo "20% -> 27%": bateu
# a base (impacto +7pp), mas ainda é uma aposta ruim (73% de chance de
# perder). Esse segundo filtro exige que a PROBABILIDADE em si (não só o
# ganho sobre a base) já esteja alta — critério ajustável, pode mudar depois.
PROBABILIDADE_MINIMA_VALOR_ATUAL = 0.75


def _carregar_regras_sinais():
    if not os.path.exists(CAMINHO_REGRAS_SINAIS):
        print(f"[sinais confirmados] {CAMINHO_REGRAS_SINAIS} não encontrado — sinal desativado")
        return []
    with open(CAMINHO_REGRAS_SINAIS, encoding="utf-8") as fp:
        regras = json.load(fp).get("regras", [])
    print(f"[sinais confirmados] {len(regras)} regras carregadas de {CAMINHO_REGRAS_SINAIS}")
    return regras


REGRAS_SINAIS = _carregar_regras_sinais()
CAMPOS_REGRAS_SINAIS = sorted(
    {c["stat"] for r in REGRAS_SINAIS for c in r["condicoes"]}
    | {r["mercado"]["stat"] for r in REGRAS_SINAIS}
)
REGRAS_POR_CHECKPOINT_PLACAR = {}
for _r in REGRAS_SINAIS:
    REGRAS_POR_CHECKPOINT_PLACAR.setdefault((_r["minuto"], _r["gols_momento"]), []).append(_r)


def _regra_bate(regra, valores):
    for c in regra["condicoes"]:
        valor = valores.get(c["stat"], 0.0)
        if c["operador"] == ">=" and valor < c["limite"]:
            return False
        if c["operador"] == "<=" and valor > c["limite"]:
            return False
    return True


def _stats_para_valor_atual(regra, valores_combinados):
    """
    Busca a estimativa de probabilidade/impacto da regra CONDICIONADA ao
    valor atual exato do próprio alvo (escanteios/chutes já ocorridos no
    momento do snapshot) — não só minuto+placar+condição, que era o critério
    original e escondia casos como: mesmo minuto/placar/condição, mas um jogo
    com 1 escanteio até ali e outro com 6, recebendo a MESMA probabilidade.
    Ver pesquisa_gols/gerar_regras_sinais.py::recalibrar_por_valor_atual —
    tabela pré-computada sobre as 5 ligas (~3.000 jogos).

    Retorna None se não houver tabela pra essa regra (nunca deveria
    acontecer nas regras atuais, mas não impede o painel se faltar).
    """
    tabela = regra.get("por_valor_atual")
    if not tabela:
        return None
    valor_atual = int(round(valores_combinados.get(regra["mercado"]["stat"], 0.0)))
    entrada = tabela.get(str(valor_atual))
    if entrada is None:
        # valor nunca visto nos ~3.000 jogos de referência — usa o mais próximo disponível
        disponiveis = [int(v) for v in tabela.keys()]
        mais_proximo = min(disponiveis, key=lambda v: abs(v - valor_atual))
        entrada = tabela[str(mais_proximo)]
    return entrada


def _direcoes_ja_disparadas(insights_existentes, fixture_id):
    """{alvo: direção} já mostrada nesta partida — usado pra nunca disparar um sinal
    contrário ao que já foi mostrado (ver _consolidar_candidatas)."""
    disparadas = {}
    for i in insights_existentes:
        if i.get("fixture_id") != fixture_id or not (i.get("tipo") or "").startswith("sinal_"):
            continue
        if i.get("alvo") and i.get("direcao"):
            disparadas[i["alvo"]] = i["direcao"]
    return disparadas


def _consolidar_candidatas(relatorio, candidatas, direcoes_ja_disparadas, minuto):
    """
    Agrupa as regras que bateram por (alvo, direção do mercado) — várias
    condições diferentes costumam apontar pro MESMO mercado ao mesmo tempo
    (ex.: 3 regras de escanteios recomendando "Menos de 11,5" juntas), e sem
    isso cada uma virava um card repetido no painel. Só a melhor evidência
    do grupo (maior impacto) vira o card; as demais só somam como "N
    condições concordam", reforçando em vez de poluir.

    Também nunca deixa passar uma direção CONTRÁRIA à que já foi mostrada
    pro mesmo alvo nesta partida (ex.: já mostrou "Menos de" escanteios,
    então "Mais de" escanteios não dispara mais depois) — caso real
    reportado: painel recomendou Under 8,5 e minutos depois Over, sem
    nenhuma indicação de que uma coisa cancelava a outra.
    """
    grupos = {}
    for regra, stats in candidatas:
        chave = (regra["alvo"], regra["mercado"]["direcao"])
        grupos.setdefault(chave, []).append((regra, stats))

    insights = []
    for (alvo, direcao), itens in grupos.items():
        direcao_oposta = "mais_de" if direcao == "menos_de" else "menos_de"
        if direcoes_ja_disparadas.get(alvo) == direcao_oposta:
            continue  # contradiria um sinal já mostrado pra esse alvo nesta partida

        melhor_regra, melhor_stats = max(itens, key=lambda par: par[1]["impacto_pp"])
        n_condicoes = len(itens)
        reforco = (
            f" Confirmado por {n_condicoes} condições independentes (a mais forte: {melhor_regra['rotulo']})."
            if n_condicoes > 1 else f" Condição: {melhor_regra['rotulo']}."
        )
        nome_alvo_valor = "escanteios" if alvo == "escanteios" else ("chutes totais" if alvo == "chutes_totais" else "chutes no alvo")
        mensagem = (
            f"min {minuto} — {melhor_regra['mercado_curto']}.{reforco} Recalculado já considerando que o jogo "
            f"tem {melhor_stats['valor_atual_real']} {nome_alvo_valor} até agora: {melhor_stats['n']} jogos de "
            f"referência com esse mesmo valor (impacto +{melhor_stats['impacto_pp']:.1f} p.p. sobre a base nesse "
            f"estado de jogo). Probabilidade estimada: {melhor_stats['p_condicao']*100:.1f}%. Odd mínima de "
            f"referência: {melhor_stats['odd_minima']:.2f} (estimada da amostra histórica, não do modelo ao "
            f"vivo deste painel)."
        )
        insight = _insight_base(
            relatorio, minuto, f"sinal_{alvo}_{direcao}", "Jogo", melhor_stats["impacto_pp"], mensagem
        )
        # Campos extras (além do formato padrão de insight): permitem o painel
        # mostrar só "mercado + odd mínima" fechado — ver htmlSinalItem() em
        # static/app.js — e o gate de contradição acima em partidas futuras.
        insight["resumo"] = melhor_regra["mercado_curto"]
        insight["odd_minima"] = melhor_stats["odd_minima"]
        insight["probabilidade"] = round(melhor_stats["p_condicao"] * 100, 1)
        insight["alvo"] = alvo
        insight["direcao"] = direcao
        insights.append(insight)
    return insights


def checar_sinais_confirmados(relatorio, minuto, gols_totais_jogo, valores_combinados, insights_existentes, fixture_id):
    """
    Um insight por (alvo, direção) confirmada que bate com o jogo agora — não
    mais um por regra, ver _consolidar_candidatas. No máximo uma vez por
    (alvo, direção) por partida (dedup por (fixture_id, tipo) já cuida disso
    em ciclo(), já que o tipo agora é estável por alvo+direção).
    """
    candidatas = []
    for checkpoint in CHECKPOINTS_REGRA:
        if not (checkpoint <= minuto <= checkpoint + JANELA_MINUTOS_REGRA):
            continue
        for regra in REGRAS_POR_CHECKPOINT_PLACAR.get((checkpoint, gols_totais_jogo), []):
            if not _regra_bate(regra, valores_combinados):
                continue
            stats = _stats_para_valor_atual(regra, valores_combinados)
            if stats is None or stats["impacto_pp"] < IMPACTO_MINIMO_PP_VALOR_ATUAL:
                # dado o placar parcial ATUAL do próprio alvo, a condição não agrega
                # impacto real (às vezes porque o placar sozinho já decidiu o mercado,
                # às vezes porque o "impacto" original era em boa parte confundido com
                # o valor atual, não um efeito genuíno da condição) — não mostra.
                continue
            if stats["p_condicao"] < PROBABILIDADE_MINIMA_VALOR_ATUAL:
                # bateu a base, mas a probabilidade em si ainda é baixa demais pra
                # ser uma aposta assertiva (ex.: 20% -> 27% é +7pp de impacto, mas
                # ainda 73% de chance de perder) — vantagem sobre a base não basta.
                continue
            # Cópia (não muta a entrada compartilhada de por_valor_atual, reaproveitada
            # entre partidas) só pra anotar o valor ATUAL de verdade do jogo — pode
            # diferir da chave usada na tabela quando caiu no fallback pro vizinho.
            stats = dict(stats, valor_atual_real=int(round(valores_combinados.get(regra["mercado"]["stat"], 0.0))))
            candidatas.append((regra, stats))

    direcoes_ja_disparadas = _direcoes_ja_disparadas(insights_existentes, fixture_id)
    return _consolidar_candidatas(relatorio, candidatas, direcoes_ja_disparadas, minuto)


# ── Ciclo principal ────────────────────────────────────────────

def ciclo():
    prelive = carregar_prelive()
    insights = _carregar(config.LIVE_INSIGHTS_FILE, [])
    snapshots_ciclo_anterior = _carregar(config.LIVE_SNAPSHOTS_FILE, {})
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

    # Jogos que estavam "ao vivo" no ciclo passado e sumiram do feed agora —
    # a Sportmonks não avisa quando um jogo termina, só para de listar ele em
    # /livescores/inplay, então é assim que detectamos o fim de uma partida.
    ids_atuais = {f["id"] for f in fixtures_monitoradas}
    for fixture_id_str, snap in snapshots_ciclo_anterior.items():
        fixture_id_antigo = int(fixture_id_str)
        if fixture_id_antigo not in ids_atuais:
            try:
                _arquivar_jogo_finalizado(fixture_id_antigo, snap, insights)
            except Exception as e:
                print(f"[arquivo] erro ao arquivar fixture {fixture_id_antigo}: {e}")

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
        valores_regras_home = extrair_stats_para_regras(stats_home, CAMPOS_REGRAS_SINAIS)
        valores_regras_away = extrair_stats_para_regras(stats_away, CAMPOS_REGRAS_SINAIS)
        valores_regras_combinados = {
            campo: valores_regras_home.get(campo, 0.0) + valores_regras_away.get(campo, 0.0)
            for campo in CAMPOS_REGRAS_SINAIS
        }

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

        gols_restantes_calibrado = probs.get("xg_restante_total_calibrado")
        gols_totais_jogo = gols_home + gols_away

        candidatos = [
            # Único sinal do painel: ritmo de gols (real x esperado). xG_proxy
            # do time e o modelo calibrado por liga (ritmo de chutes, mesmo
            # usado no Over/Under) entram só como filtros eliminatórios, e a
            # mensagem já lista os mercados que refletem o desvio.
            checar_ritmo_gols(relatorio, minuto, home["name"], gols_home, lambda_home, xg_home, perfil_c["xg_proxy_media"], dados_ofensivos_disponiveis, gols_restantes_calibrado, gols_totais_jogo, probs["comparacao"]),
            checar_ritmo_gols(relatorio, minuto, away["name"], gols_away, lambda_away, xg_away, perfil_f["xg_proxy_media"], dados_ofensivos_disponiveis, gols_restantes_calibrado, gols_totais_jogo, probs["comparacao"]),
        ]
        # Sinais de escanteios/chutes confirmados por pesquisa cross-liga —
        # ver comentário acima de checar_sinais_confirmados(). Pode gerar mais
        # de um insight por ciclo (alvos diferentes podem bater ao mesmo
        # tempo — já consolidado por (alvo, direção), não mais por regra
        # individual), por isso extend em vez de um único item na lista.
        candidatos.extend(checar_sinais_confirmados(
            relatorio, minuto, gols_totais_jogo, valores_regras_combinados, insights, fixture_id
        ))

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
