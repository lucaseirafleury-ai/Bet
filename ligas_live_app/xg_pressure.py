"""
Cálculo de xG_proxy e Índice de Pressão a partir de estatísticas de partida.
Usado tanto na Fase 1 (médias históricas) quanto na Fase 2 (jogo ao vivo).
"""
import time

# Nomes dos campos como retornados pela Sportmonks em statistics[].type.name.
# Conferido direto em /core/types (per_page=50, 1250 tipos) em 2026-07-24 —
# vários nomes abaixo estavam errados (chute em cima do nome mais "óbvio" em vez
# do nome real da API), o que fazia extrair_stat() nunca encontrar o campo e
# sempre cair no default 0.0 — daí xG_proxy, escanteios etc. ficarem travados
# em zero mesmo com o jogo tendo estatística de verdade disponível.
CAMPO_SHOTS_ON = "Shots On Target"
CAMPO_SHOTS_OFF = "Shots Off Target"
CAMPO_SHOTS_IN = "Shots Insidebox"
CAMPO_SHOTS_OUT = "Shots Outsidebox"
CAMPO_BLOCKED = "Blocked Shots"
CAMPO_DANGEROUS = "Dangerous Attacks"
CAMPO_POSSE = "Ball Possession %"
CAMPO_SHOTS_TOTAL = "Shots Total"
CAMPO_CORNERS = "Corners"
CAMPO_YELLOW = "Yellowcards"
CAMPO_RED = "Redcards"
CAMPO_FOULS = "Fouls"
CAMPO_OFFSIDES = "Offsides"
CAMPO_PASSES_TOTAL = "Passes"
CAMPO_PASSES_CERTOS = "Successful Passes"
CAMPO_SAVES = "Saves"
CAMPO_ATTACKS = "Attacks"


def extrair_stat(lista_stats, nome_campo):
    """lista_stats: lista de dicts vindos de statistics[] filtrados por participant_id."""
    for s in lista_stats:
        tipo = s.get("type", {}).get("name")
        if tipo == nome_campo:
            v = s.get("data", {}).get("value")
            try:
                return float(v)
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def extrair_stat_ou_none(lista_stats, nome_campo):
    """
    Mesma busca de extrair_stat, mas devolve None (não 0.0) quando a
    estatística não aparece na lista dessa partida — usado só pelas regras de
    sinais (extrair_stats_para_regras/live_monitor._regra_bate), pra tratar
    dado ausente como "condição não confirmada", igual a como a calibração
    offline já trata (pesquisa_gols/gerar_regras_sinais.py::_condicao_bate).
    Bug real corrigido aqui (ver conversa): extrair_stat's default 0.0 fazia
    uma condição "<= limite" com dado ausente virar sempre verdadeira, mesmo
    em jogos/ligas sem cobertura pra aquela estatística — a calibração nunca
    validou esses casos como "condição bateu", então o app ao vivo não devia
    tratar assim. extrair_stat continua com default 0.0 pros outros cálculos
    (xG_proxy, pressão etc.), que já têm proteção própria pra jogo sem essa
    cobertura (ver dados_ofensivos_disponiveis em live_monitor.py).
    """
    for s in lista_stats:
        tipo = s.get("type", {}).get("name")
        if tipo == nome_campo:
            v = s.get("data", {}).get("value")
            try:
                return float(v)
            except (TypeError, ValueError):
                return None
    return None


# Nome da API (statistics[].type.name) por stat_base — mesma convenção usada em
# pesquisa_gols/buscar_sportmonks.py (NOMES_CONFIRMADOS + fallback Title Case),
# já verificada contra a API real em ~3.000 jogos de 5 ligas sem nenhum aviso
# de "type não encontrado". Cobre só os campos usados por regras_sinais.json —
# amplie aqui se um novo alvo/estatística entrar nas regras confirmadas.
CAMPO_API_REGRAS = {
    "shots_total": CAMPO_SHOTS_TOTAL,
    "shots_on_target": CAMPO_SHOTS_ON,
    "shots_insidebox": CAMPO_SHOTS_IN,
    "shots_outsidebox": CAMPO_SHOTS_OUT,
    "dangerous_attacks": CAMPO_DANGEROUS,
    "attacks": CAMPO_ATTACKS,
    "corners": CAMPO_CORNERS,
    "fouls": CAMPO_FOULS,
    "offsides": CAMPO_OFFSIDES,
    "saves": CAMPO_SAVES,
    "accurate_crosses": "Accurate Crosses",
    "total_crosses": "Total Crosses",
    "key_passes": "Key Passes",
    "tackles": "Tackles",
    "duels_won": "Duels Won",
    "interceptions": "Interceptions",
    "goal_attempts": "Goal Attempts",
    "successful_dribbles": "Successful Dribbles",
    "successful_dribbles_percentage": "Successful Dribbles Percentage",
    "hit_woodwork": "Hit Woodwork",
}


def extrair_stats_para_regras(lista_stats, campos):
    """
    Extrai só os campos pedidos (stat_base -> valor), pelo nome de API mapeado
    em CAMPO_API_REGRAS. Usa extrair_stat_ou_none (não extrair_stat): um campo
    sem mapeamento conhecido (fica de fora do dict, "campo not in
    CAMPO_API_REGRAS") ou mapeado mas ausente na cobertura de estatística
    dessa partida/liga acaba tratado do mesmo jeito por quem consome este
    dict (live_monitor._regra_bate/_stats_para_valor_atual): dado ausente ->
    condição não confirmada, nunca "sempre bate" (bug real corrigido, ver
    extrair_stat_ou_none e conversa).

    "cards" (stat_base do alvo "cartões" — ver pesquisa_gols/gerar_regras_
    sinais.py) é caso especial: não é 1 campo só da API, é amarelos+vermelhos
    somados (mesma soma de calcular_cartoes) — por isso fica fora de
    CAMPO_API_REGRAS (que é sempre 1 nome de API por stat_base). Se qualquer
    um dos dois vier ausente, "cards" também fica None (não dá pra somar).
    """
    valores = {
        campo: extrair_stat_ou_none(lista_stats, CAMPO_API_REGRAS[campo])
        for campo in campos
        if campo in CAMPO_API_REGRAS
    }
    if "cards" in campos:
        amarelos = extrair_stat_ou_none(lista_stats, CAMPO_YELLOW)
        vermelhos = extrair_stat_ou_none(lista_stats, CAMPO_RED)
        valores["cards"] = (amarelos + vermelhos) if amarelos is not None and vermelhos is not None else None
    return valores


def calcular_xg_proxy(lista_stats):
    """
    Usa a fórmula completa (insidebox/outsidebox) quando disponível;
    cai para a fórmula simplificada quando a liga não cobre essa granularidade.

    Peso 0.335 calibrado via regressão não-negativa sem intercepto, usando 569 jogos
    reais das 5 ligas monitoradas (FootyStats, temporada 2026). shots_off_target,
    escanteios e faltas foram testados como variáveis extras e não agregaram poder
    preditivo (peso convergiu pra ~0 em todos os casos) — por isso ficaram de fora.
    Erro médio absoluto resultante: ~1.22 gols/jogo, no mesmo patamar do xG
    proprietário do FootyStats nas mesmas ligas (1.20–1.44).
    """
    shots_in = extrair_stat(lista_stats, CAMPO_SHOTS_IN)
    shots_out = extrair_stat(lista_stats, CAMPO_SHOTS_OUT)
    dangerous = extrair_stat(lista_stats, CAMPO_DANGEROUS)

    if shots_in > 0 or shots_out > 0:
        return round((shots_in * 0.11) + (shots_out * 0.035) + (dangerous * 0.008), 3)  # ainda não calibrado — cobertura rara

    shots_on = extrair_stat(lista_stats, CAMPO_SHOTS_ON)
    return round(shots_on * 0.335, 3)


def calcular_pressao(lista_stats, minuto):
    """Pressão por minuto jogado — usa piso de 10min para não distorcer no início do jogo."""
    posse = extrair_stat(lista_stats, CAMPO_POSSE)
    dangerous = extrair_stat(lista_stats, CAMPO_DANGEROUS)
    shots_total = extrair_stat(lista_stats, CAMPO_SHOTS_TOTAL)
    minuto_efetivo = max(minuto, 10)
    return round(
        (posse * 0.3)
        + ((dangerous / minuto_efetivo) * 100 * 0.4)
        + ((shots_total / minuto_efetivo) * 100 * 0.3),
        2,
    )


def calcular_cartoes(lista_stats):
    return extrair_stat(lista_stats, CAMPO_YELLOW) + extrair_stat(lista_stats, CAMPO_RED)


def calcular_escanteios(lista_stats):
    return extrair_stat(lista_stats, CAMPO_CORNERS)


def calcular_eficiencia(lista_stats):
    """Chutes no alvo / chutes totais. Retorna None se não houve chute ainda."""
    shots_on = extrair_stat(lista_stats, CAMPO_SHOTS_ON)
    shots_total = extrair_stat(lista_stats, CAMPO_SHOTS_TOTAL)
    if shots_total <= 0:
        return None
    return round((shots_on / shots_total) * 100, 1)


def extrair_stats_completas(lista_stats):
    """Bloco de estatísticas cruas para exibição no painel (não usado no cálculo de sinais)."""
    return {
        "finalizacoes": extrair_stat(lista_stats, CAMPO_SHOTS_TOTAL),
        "chutes_no_alvo": extrair_stat(lista_stats, CAMPO_SHOTS_ON),
        "chutes_fora": extrair_stat(lista_stats, CAMPO_SHOTS_OFF),
        "escanteios": calcular_escanteios(lista_stats),
        "faltas": extrair_stat(lista_stats, CAMPO_FOULS),
        "impedimentos": extrair_stat(lista_stats, CAMPO_OFFSIDES),
        "cartoes": calcular_cartoes(lista_stats),
        "posse": extrair_stat(lista_stats, CAMPO_POSSE),
        "passes_totais": extrair_stat(lista_stats, CAMPO_PASSES_TOTAL),
        "passes_certos": extrair_stat(lista_stats, CAMPO_PASSES_CERTOS),
        "defesas": extrair_stat(lista_stats, CAMPO_SAVES),
        "ataques": extrair_stat(lista_stats, CAMPO_ATTACKS),
    }


def calcular_momentum(stats_home, stats_away):
    """
    Índice único (0-100 para cada lado, soma 100) combinando posse, ataques perigosos,
    finalizações e escanteios — pensado para leitura rápida tipo "quem está no jogo agora".
    """
    def score(stats):
        posse = extrair_stat(stats, CAMPO_POSSE)
        dangerous = extrair_stat(stats, CAMPO_DANGEROUS)
        shots = extrair_stat(stats, CAMPO_SHOTS_TOTAL)
        corners = calcular_escanteios(stats)
        return (posse * 0.3) + (dangerous * 0.4) + (shots * 2.0) + (corners * 1.5)

    score_home = score(stats_home)
    score_away = score(stats_away)
    total = score_home + score_away
    if total <= 0:
        return 50.0, 50.0
    momentum_home = round((score_home / total) * 100, 1)
    momentum_away = round(100 - momentum_home, 1)
    return momentum_home, momentum_away


# Usado só como alarme de discrepância grande em extrair_minuto — ver docstring.
# Nenhum dos 60 jogos reais testados (ver conversa) chegou nem perto disso em
# condições normais (atraso de apito real, o caso comum): maior diferença
# observada entre `started` e o horário agendado foi ~7.9min. Só um valor bem
# acima disso é evidência de que o PRÓPRIO `started` foi mal registrado, não
# de atraso de apito de verdade.
LIMIAR_DISCREPANCIA_MINUTO_AGENDADO = 10


def extrair_minuto(fixture):
    """
    Pega o minuto do período que estiver 'ticking' (rolando) agora.

    A Sportmonks não tem cronômetro confiável pra nenhuma das 5 ligas
    monitoradas (`has_timer` sempre False, testado em 60 jogos reais — ver
    conversa) — nem `minutes` nem `started` são um relógio oficial, então
    combinamos duas fontes:

    1. `minutes` informado pela própria Sportmonks — às vezes atrasa em
       relação ao relógio de parede (visto num jogo real onde o placar já
       contava um gol que só aconteceu 2 minutos depois do `minutes`
       informado — o placar e o relógio vêm de partes diferentes do
       pipeline deles e nem sempre chegam no mesmo instante).
    2. Uma estimativa pelo tempo real decorrido desde o início do período
       (`started`) — testado em 60 jogos reais e confirmado confiável: a
       diferença entre `started` e o horário AGENDADO (`starting_at`) segue
       uma distribuição bem comportada (mediana ~1.15min, só atraso real de
       apito, nunca zero cravado — não é uma cópia do agendado).

    Usamos o MAIOR entre os dois — nunca deixa o minuto exibido ficar
    "atrás" de um placar que já mudou.

    CUIDADO com o horário agendado (`starting_at_timestamp`) como piso:
    versão anterior deste código usava ele incondicionalmente como 3º
    candidato (só no 1º tempo), pego pelo mesmo `max()` — bug real corrigido
    aqui (ver conversa): como o apito raramente sai ANTES do horário previsto,
    esse candidato fica MAIOR que o baseado em `started` sempre que há
    qualquer atraso — ou seja, na maioria dos jogos, não só em casos raros —
    e o `max()` inflava o minuto exibido sistematicamente pelo tamanho do
    atraso (mediana ~1min, até ~8min na cauda). Isso importa de verdade: é
    o minuto usado pra bater com os checkpoints das regras de sinais
    (15/30/45/60/75/90), então superestimar sistematicamente significa
    avaliar regras cedo/fora da janela certa.

    Ainda existe um caso real (Superettan) onde o PRÓPRIO `started` foi
    registrado pela Sportmonks 12-14min depois do apito de verdade — nesse
    caso o candidato via `started` também atrasa, e só o horário agendado
    (independente do pipeline da Sportmonks) pegaria o erro. Por isso o
    horário agendado não foi removido, só deixou de ser incondicional: só
    entra na conta quando destoa MUITO (LIMIAR_DISCREPANCIA_MINUTO_AGENDADO)
    do candidato via `started` — o suficiente pra distinguir "started
    registrado tarde" de "apito atrasou de verdade" (que já é bem menor que
    o limiar, confirmado empiricamente). Só no 1º tempo — no 2º incluiria o
    intervalo e superestimaria.
    """
    periods = fixture.get("periods", [])
    periodo_ativo = next((p for p in periods if p.get("ticking") is True), None)
    if periodo_ativo is None:
        if periods:
            return periods[-1].get("minutes", 1) or 1
        return 1

    minuto_informado = periodo_ativo.get("minutes", 1) or 1
    candidatos = [minuto_informado]

    started = periodo_ativo.get("started")
    counts_from = periodo_ativo.get("counts_from", 0) or 0
    minuto_via_started = None
    if started:
        minuto_via_started = counts_from + int((time.time() - started) / 60) + 1
        candidatos.append(minuto_via_started)

    inicio_agendado = fixture.get("starting_at_timestamp")
    if inicio_agendado and (periodo_ativo.get("description") or "").lower() == "1st-half":
        minuto_via_agendado = int((time.time() - inicio_agendado) / 60) + 1
        referencia = minuto_via_started if minuto_via_started is not None else minuto_informado
        if minuto_via_agendado - referencia > LIMIAR_DISCREPANCIA_MINUTO_AGENDADO:
            candidatos.append(minuto_via_agendado)

    return max(candidatos)
