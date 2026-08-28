"""Combina a previsão de cartões do motor de times (`retrospectiva.py`)
com a média histórica de cartões do árbitro do jogo — pista promissora
mas ainda abaixo do limiar de significância padrão do projeto (z≈2),
adotada como TERCEIRO critério com stake reduzido (ver `docs/protocolo.md`,
seção "Terceiro critério (stake reduzido)").

Depende de dado externo do Sportmonks (`referee_id` e odds do mercado
"Number of Cards") — vem de `data/sportmonks_serieb/fixtures.jsonl`
(o mesmo arquivo amplo que o painel diário mantém atualizado sozinho
via `sportmonks_atualizar_dado.py`; não existe mais um pull separado
pra isso).
"""
from __future__ import annotations

from collections import defaultdict

from pesos import probabilidade_implicita_2vias, probabilidade_over


def media_arbitro_walk_forward(jogos_ordenados, min_jogos_arbitro=10):
    """Para cada jogo em `jogos_ordenados` (lista de dicts com pelo menos
    `referee_id` e `total_cartoes`, JÁ ORDENADA cronologicamente),
    calcula a média histórica de cartões daquele árbitro usando só jogos
    ANTERIORES (walk-forward, sem look-ahead).

    Retorna uma lista paralela a `jogos_ordenados`: em cada posição, a
    média disponível NAQUELE MOMENTO (ou `None` se o árbitro ainda não
    tiver pelo menos `min_jogos_arbitro` jogos anteriores registrados).
    Jogos com `referee_id` ou `total_cartoes` ausentes (`None`) não
    entram no histórico de ninguém, mas ainda recebem `None` na saída.
    """
    historico = defaultdict(list)
    medias = []
    for jogo in jogos_ordenados:
        referee_id = jogo.get("referee_id")
        total_cartoes = jogo.get("total_cartoes")
        if referee_id is None:
            medias.append(None)
            continue
        hist = historico[referee_id]
        if len(hist) >= min_jogos_arbitro:
            medias.append(sum(hist) / len(hist))
        else:
            medias.append(None)
        if total_cartoes is not None:
            hist.append(total_cartoes)
    return medias


def media_arbitro_atual(jogos, min_jogos_arbitro=10):
    """Média de cartões de cada árbitro usando TODO o histórico
    disponível — diferente de `media_arbitro_walk_forward` (que dá a
    média NO MOMENTO de cada jogo passado, pra backtesting sem
    lookahead), esta função serve pra PREVISÃO AO VIVO: "hoje" é
    realmente agora, então usar o histórico inteiro não tem risco de
    lookahead. `jogos`: lista de dicts com `referee_id`/`total_cartoes`,
    ordem não importa aqui.

    Retorna `{referee_id: media}`, só pros árbitros com pelo menos
    `min_jogos_arbitro` jogos com dado completo."""
    historico = defaultdict(list)
    for jogo in jogos:
        referee_id = jogo.get("referee_id")
        total_cartoes = jogo.get("total_cartoes")
        if referee_id is not None and total_cartoes is not None:
            historico[referee_id].append(total_cartoes)
    return {rid: sum(vals) / len(vals) for rid, vals in historico.items() if len(vals) >= min_jogos_arbitro}


def prever_cartoes_combinado(pred_time, media_arbitro, peso_arbitro=0.3):
    """Média ponderada entre a previsão do modelo de times (`pred_time`)
    e a média histórica do árbitro (`media_arbitro`). Retorna `None`
    quando `media_arbitro` é `None` (árbitro sem histórico suficiente
    ainda) — nesse caso não há como combinar, o chamador decide se quer
    cair de volta pro `pred_time` sozinho ou pular o jogo."""
    if media_arbitro is None:
        return None
    if not 0 <= peso_arbitro <= 1:
        raise ValueError("peso_arbitro deve estar entre 0 e 1")
    return pred_time * (1 - peso_arbitro) + media_arbitro * peso_arbitro


def linha_mais_liquida(jogo, market_id):
    """Entre as linhas (`total`) cotadas pro `market_id` em `jogo['odds']`
    (dict `{market_id: [{bookmaker_id, label, total, value}, ...]}`),
    retorna a linha cotada por mais bookmakers distintos (maior amostra
    pra tirar a média de odd) — `None` se o mercado não estiver presente.

    Como a produção restringe as odds a um único bookmaker (bet365 —
    ver `docs/retrospectiva_bookmaker_bet365_2026-08-27.md`), toda linha
    que ele cota empata em "1 bookmaker" (cartões costuma ter várias
    linhas alternativas do mesmo bookmaker: 3.5/4.5/5.5...). Nesse
    empate (o caso normal hoje, não uma exceção), o desempate cai pra
    a linha com odd Over/Under mais próxima da paridade — proxy padrão
    de mercado pra "linha principal" (linhas alternativas tendem a se
    afastar da paridade quanto mais longe da linha central). Sem esse
    desempate, `max()` devolveria a primeira linha na ordem arbitrária
    de serialização do Sportmonks, não a mais relevante — foi assim que
    o painel sugeriu uma linha que não existia na casa real do usuário
    (ver `docs/retrospectiva_linha_cartoes_bug_2026-08-28.md`)."""
    entradas = jogo.get("odds", {}).get(str(market_id)) or jogo.get("odds", {}).get(market_id)
    if not entradas:
        return None
    contagem = defaultdict(set)
    odds_por_total = defaultdict(lambda: defaultdict(list))
    for e in entradas:
        total = float(e["total"])
        contagem[total].add(e.get("bookmaker_id"))
        if e.get("value") is not None:
            odds_por_total[total][e["label"]].append(float(e["value"]))
    if not contagem:
        return None
    max_bookmakers = max(len(s) for s in contagem.values())
    candidatos = [t for t, s in contagem.items() if len(s) == max_bookmakers]
    if len(candidatos) == 1:
        return candidatos[0]

    def distancia_paridade(total):
        overs = odds_por_total[total].get("Over") or []
        unders = odds_por_total[total].get("Under") or []
        if not overs or not unders:
            return float("inf")
        return abs(sum(overs) / len(overs) - sum(unders) / len(unders))

    return min(candidatos, key=distancia_paridade)


def odd_media_na_linha(jogo, market_id, total_alvo, label):
    """Média das odds de todos os bookmakers pro lado `label` ("Over" ou
    "Under") na linha `total_alvo` exata, pro `market_id` em `jogo['odds']`.
    Retorna `None` se não houver nenhuma cotação nessa combinação."""
    entradas = jogo.get("odds", {}).get(str(market_id)) or jogo.get("odds", {}).get(market_id)
    if not entradas:
        return None
    valores = [
        float(e["value"]) for e in entradas
        if float(e["total"]) == total_alvo and e["label"] == label and e.get("value") is not None
    ]
    if not valores:
        return None
    return sum(valores) / len(valores)


def decidir_lado_linha(pred_total, linha, odd_over, odd_under, limiar_edge=0.0):
    """Decide o lado (Over/Under) por edge (probabilidade do modelo menos
    probabilidade implícita do mercado) na `linha` dada — SEM resolver
    vitória/derrota (usado tanto por `simular_aposta_linha`, que já sabe
    o resultado real, quanto por `previsao_dia.py`, que avalia jogos
    futuros onde não existe resultado ainda).

    Como as probabilidades de mercado/modelo são complementares
    (`prob_under = 1 - prob_over` dos dois lados), `edge_under` é sempre
    o negativo de `edge_over` — com `limiar_edge=0.0` (padrão, o que foi
    usado em toda a validação empírica deste critério) a função SEMPRE
    decide um lado, nunca pula o jogo.

    Retorna `None` quando não há edge suficiente (só possível com
    `limiar_edge > 0`). Caso contrário, `{"lado", "odd", "prob_modelo",
    "prob_mercado", "edge"}`."""
    prob_modelo_over = probabilidade_over(pred_total, linha=linha)
    prob_mercado_over = probabilidade_implicita_2vias(odd_over, odd_under)
    edge_over = prob_modelo_over - prob_mercado_over
    edge_under = -edge_over

    if edge_over >= limiar_edge and edge_over >= edge_under:
        return dict(lado="Over", odd=odd_over, prob_modelo=prob_modelo_over,
                     prob_mercado=prob_mercado_over, edge=edge_over)
    if edge_under >= limiar_edge:
        return dict(lado="Under", odd=odd_under, prob_modelo=1 - prob_modelo_over,
                     prob_mercado=1 - prob_mercado_over, edge=edge_under)
    return None


def simular_aposta_linha(pred_total, linha, odd_over, odd_under, real_total, limiar_edge=0.0):
    """Decide o lado (Over/Under) por edge (probabilidade do modelo menos
    probabilidade implícita do mercado) na `linha` dada, e resolve o
    resultado contra `real_total` (total realmente ocorrido no jogo).

    Como as probabilidades de mercado/modelo são complementares
    (`prob_under = 1 - prob_over` dos dois lados), `edge_under` é sempre
    o negativo de `edge_over` — ou seja, com `limiar_edge=0.0` (padrão,
    o que foi usado em toda a validação empírica deste critério) a
    função SEMPRE aposta no lado que o modelo favorece, nunca pula o
    jogo. `limiar_edge > 0` exige uma vantagem mínima antes de apostar
    (pode fazer a função retornar `None`) — não usar um valor diferente
    de `0.0` sem revalidar o ROI/z, já que os números documentados em
    `docs/protocolo.md` foram medidos sem esse filtro.

    Retorna `None` quando não há aposta (só possível com `limiar_edge >
    0`). Caso contrário, retorna `{"lado", "venceu", "lucro", "edge"}`
    — `lucro` é líquido por unidade de stake (`odd - 1` se venceu, `-1`
    se perdeu), sem aplicar nenhuma redução de stake (isso é decisão de
    operação, não da simulação estatística); `edge` é o repassado de
    `decidir_lado_linha` (útil pra analisar, depois do fato, se cortar
    por tamanho de edge teria mudado o resultado — ver
    `docs/retrospectiva_edge_minimo_cartoes_2026-08-28.md`)."""
    decisao = decidir_lado_linha(pred_total, linha, odd_over, odd_under, limiar_edge)
    if decisao is None:
        return None
    if decisao["lado"] == "Over":
        venceu = real_total > linha
    else:
        venceu = real_total <= linha
    return dict(lado=decisao["lado"], venceu=venceu, lucro=(decisao["odd"] - 1) if venceu else -1.0,
                edge=decisao["edge"])
