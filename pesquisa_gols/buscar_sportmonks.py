"""
Monta o mesmo dataset que carregar_dados.carregar_tudo() devolve (jogos,
resultados_alvo, matriz, candidatas, snapshots), mas buscando direto da API
da Sportmonks em vez de precisar de um .xlsx exportado manualmente.

Usa o include `trends` (progressão minuto a minuto), igual
ligas_live_app/backtest.py já faz pra reconstruir estatísticas de jogos
passados — só que aqui para todas as candidatas de alvos.py, não só as 9
usadas no cálculo de xG_proxy/pressão.

Uso:
    export SPORTMONKS_TOKEN=...   # nunca colar o token dentro de um arquivo do repo
    python buscar_sportmonks.py

Precisa da env var SPORTMONKS_TOKEN (ver sportmonks.py). Nada relacionado ao
token é escrito em disco por este script.
"""
import json
import os
import time

import alvos
import config
import sportmonks as sm
from matriz_padrao import CORRELACAO_GOLS_PADRAO

CHECKPOINTS = [15, 30, 45, 60, 75, 90]
MINUTO_FINAL = 999  # maior que qualquer minuto real — pega o último valor acumulado dos trends
ALLSVENSKAN_LEAGUE_ID = 573  # mesmo id já usado em ligas_live_app/config.py
INTERVALO_ENTRE_FIXTURES_SEGUNDOS = 0.3
INTERVALO_CHECKPOINT_FIXTURES = 20  # salva o progresso a cada N fixtures processadas

# Mesmos ids de ligas_live_app/config.py -> LIGAS_MONITORADAS
LIGAS_MONITORADAS = {
    573: "Allsvenskan",
    579: "Superettan",
    405: "A Lyga",
    408: "1. Lyga",
    447: "1. Division",
}

# Nomes já confirmados contra a API real (ligas_live_app/xg_pressure.py,
# conferido em 2026-07-24 direto em /core/types). Para os demais candidatos,
# tenta o nome "Title Case" óbvio e só aceita se bater exatamente com um tipo
# que a API realmente devolveu — nunca assume, porque um nome errado faz o
# valor cair sempre em 0.0 silenciosamente (bug já visto neste repo antes).
NOMES_CONFIRMADOS = {
    "shots_on_target": "Shots On Target",
    "shots_off_target": "Shots Off Target",
    "shots_insidebox": "Shots Insidebox",
    "shots_outsidebox": "Shots Outsidebox",
    "shots_blocked": "Blocked Shots",
    "dangerous_attacks": "Dangerous Attacks",
    "ball_possession_pct": "Ball Possession %",
    "shots_total": "Shots Total",
    "corners": "Corners",
    "offsides": "Offsides",
    "saves": "Saves",
    "attacks": "Attacks",
    "fouls": "Fouls",
    "yellowcards": "Yellowcards",
    "redcards": "Redcards",
}


def resolver_candidatas(tipos_disponiveis, nomes_desejados=None):
    """
    stat_base (nome usado em pesquisa_gols) -> type_id da Sportmonks, só para
    as candidatas que dá pra resolver com confiança. Avisa e pula as que não
    encontrar — nunca assume um type_id errado.

    nomes_desejados: lista de stat_base a resolver. Default: alvos.CAMPOS_PARA_BUSCAR
    (superset de tudo que qualquer alvo precisa — candidatas preditoras +
    campos que só servem de alvo, como yellowcards/redcards para cartões).
    """
    if nomes_desejados is None:
        nomes_desejados = alvos.CAMPOS_PARA_BUSCAR
    resolvidas = {}
    for stat_base in sorted(nomes_desejados):
        if stat_base in config.INDICADORES_EXCLUIDOS:
            continue
        nome_api = NOMES_CONFIRMADOS.get(stat_base, stat_base.replace("_", " ").title())
        type_id = tipos_disponiveis.get(nome_api)
        if type_id is None:
            print(f"  [aviso] não achei o type da Sportmonks pra '{stat_base}' "
                  f"(tentei '{nome_api}') — essa estatística fica de fora desta busca")
            continue
        resolvidas[stat_base] = type_id
    return resolvidas


def identificar_type_id_gol(tipos_disponiveis):
    for candidato in ["Goal", "GOAL", "Goals", "Normal Goal"]:
        if candidato in tipos_disponiveis:
            return tipos_disponiveis[candidato]
    return None


def identificar_type_ids_cartao(tipos_disponiveis):
    """
    Type_ids de evento de cartão (amarelo, vermelho, segundo amarelo->vermelho).
    Contagem por evento é mais confiável que os `trends` pra cartões — já visto
    num jogo real: trends deu 7 cartões, contagem de eventos deu 8, batendo
    com o total oficial (dois amarelos simultâneos no mesmo minuto parecem
    fazer o trend perder um incremento).
    """
    return [
        tipos_disponiveis[nome] for nome in ("Yellowcard", "Redcard", "Yellow/Red card")
        if nome in tipos_disponiveis
    ]


def gols_ate_minuto(events, participant_id, minuto, goal_type_id, gols_finais_fallback):
    if goal_type_id is None:
        return gols_finais_fallback
    return sum(
        1 for e in events
        if e.get("type_id") == goal_type_id
        and e.get("participant_id") == participant_id
        and (e.get("minute") or 0) <= minuto
    )


def eventos_ate_minuto(events, participant_id, minuto, type_ids):
    return sum(
        1 for e in events
        if e.get("type_id") in type_ids
        and e.get("participant_id") == participant_id
        and (e.get("minute") or 0) <= minuto
    )


def valor_acumulado_no_minuto(trends, type_id, participant_id, minuto):
    candidatos = [
        t for t in trends
        if t.get("type_id") == type_id and t.get("participant_id") == participant_id
        and (t.get("minute") or 0) <= minuto
    ]
    if not candidatos:
        return 0.0
    candidatos.sort(key=lambda t: t.get("minute") or 0)
    try:
        return float(candidatos[-1].get("value"))
    except (TypeError, ValueError):
        return 0.0


# Alvos cujo total final é mais confiável contando eventos do que lendo o
# último ponto dos trends (ver identificar_type_ids_cartao).
ALVOS_POR_EVENTO = {"cartoes": identificar_type_ids_cartao}


def resultados_finais_dos_alvos(trends, events, candidatas_resolvidas, tipos_disponiveis,
                                 home_id, away_id, gols_casa_final, gols_fora_final):
    """
    valor final da partida, para cada alvo em alvos.ALVOS — soma casa+fora.
    'gols' usa o placar oficial (scores), mais preciso. Alvos em
    ALVOS_POR_EVENTO usam contagem de eventos (mais confiável que trends pra
    esses casos). Os demais usam o último ponto dos trends (MINUTO_FINAL),
    que já é buscado mesmo assim para os checkpoints de 15-90 min.
    """
    resultado = {"gols": gols_casa_final + gols_fora_final}
    for alvo_id, definicao in alvos.ALVOS.items():
        if alvo_id == "gols":
            continue
        if alvo_id in ALVOS_POR_EVENTO:
            type_ids = ALVOS_POR_EVENTO[alvo_id](tipos_disponiveis)
            resultado[alvo_id] = (
                eventos_ate_minuto(events, home_id, MINUTO_FINAL, type_ids)
                + eventos_ate_minuto(events, away_id, MINUTO_FINAL, type_ids)
            )
            continue
        total = 0.0
        for campo in definicao["campos_base"]:
            type_id = candidatas_resolvidas.get(campo)
            if type_id is None:
                total = None
                break
            total += (
                valor_acumulado_no_minuto(trends, type_id, home_id, MINUTO_FINAL)
                + valor_acumulado_no_minuto(trends, type_id, away_id, MINUTO_FINAL)
            )
        resultado[alvo_id] = total
    return resultado


def processar_fixture(fixture_resumo, candidatas_resolvidas, goal_type_id, tipos_disponiveis, jogos, resultados_alvo, snapshots):
    fixture_id = fixture_resumo["id"]
    jogos[fixture_id] = {
        "rodada": (fixture_resumo.get("round") or {}).get("id"),
        "data_hora": fixture_resumo.get("starting_at"),
        "time_casa": None,
        "time_fora": None,
        "finalizado": fixture_resumo.get("state_id") == 5,
    }

    if fixture_resumo.get("state_id") != 5:
        return  # jogo ainda não disputado — só entra em `jogos`, sem snapshot

    fixture = sm.fixture_com_trends(fixture_id)
    if not fixture:
        return
    trends = fixture.get("trends", [])
    if not trends:
        print(f"  [sem trends] fixture {fixture_id} — pulando")
        return

    participants = fixture.get("participants", [])
    home = next((p for p in participants if p["meta"]["location"] == "home"), None)
    away = next((p for p in participants if p["meta"]["location"] == "away"), None)
    if not home or not away:
        return
    jogos[fixture_id]["time_casa"] = home.get("name")
    jogos[fixture_id]["time_fora"] = away.get("name")

    scores = fixture.get("scores", [])
    gols_casa_final = next((s["score"]["goals"] for s in scores
                             if s.get("description") == "CURRENT" and s.get("participant_id") == home["id"]), None)
    gols_fora_final = next((s["score"]["goals"] for s in scores
                             if s.get("description") == "CURRENT" and s.get("participant_id") == away["id"]), None)
    if gols_casa_final is None or gols_fora_final is None:
        print(f"  [sem placar final] fixture {fixture_id} — pulando")
        return
    events = fixture.get("events", [])
    resultados_alvo[fixture_id] = resultados_finais_dos_alvos(
        trends, events, candidatas_resolvidas, tipos_disponiveis,
        home["id"], away["id"], gols_casa_final, gols_fora_final,
    )

    for minuto in CHECKPOINTS:
        gols_casa = gols_ate_minuto(events, home["id"], minuto, goal_type_id, gols_casa_final)
        gols_fora = gols_ate_minuto(events, away["id"], minuto, goal_type_id, gols_fora_final)
        snap = {
            "fixture_id": fixture_id,
            "minuto": minuto,
            "gols_momento": gols_casa + gols_fora,
        }
        for stat_base, type_id in candidatas_resolvidas.items():
            valor_casa = valor_acumulado_no_minuto(trends, type_id, home["id"], minuto)
            valor_fora = valor_acumulado_no_minuto(trends, type_id, away["id"], minuto)
            snap[stat_base] = valor_casa + valor_fora
        snapshots.append(snap)


def _salvar_checkpoint(caminho, jogos, resultados_alvo, snapshots, processados, candidatas_resolvidas):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fp:
        json.dump({
            "candidatas": sorted(candidatas_resolvidas),
            "jogos": {str(k): v for k, v in jogos.items()},
            "resultados_alvo": {str(k): v for k, v in resultados_alvo.items()},
            "snapshots": snapshots,
            "processados": sorted(processados),
        }, fp)
    os.replace(tmp, caminho)  # troca atômica — nunca deixa um checkpoint pela metade


def _carregar_checkpoint(caminho, candidatas_resolvidas):
    """
    Devolve None se o checkpoint não existir OU se tiver sido salvo com um
    conjunto de candidatas diferente do atual (ex.: alvos.py ganhou um campo
    novo desde a última busca) — reaproveitar snapshots que não têm todas as
    chaves esperadas quebraria o resto do pipeline silenciosamente.
    """
    if not os.path.exists(caminho):
        return None
    with open(caminho, encoding="utf-8") as fp:
        dados = json.load(fp)
    candidatas_salvas = dados.get("candidatas")
    if candidatas_salvas != sorted(candidatas_resolvidas):
        print(f"  [aviso] checkpoint em {caminho} foi salvo com candidatas diferentes das atuais "
              f"— ignorando e buscando tudo de novo pra essa liga")
        return None
    return {
        "jogos": {int(k): v for k, v in dados["jogos"].items()},
        "resultados_alvo": {int(k): v for k, v in dados["resultados_alvo"].items()},
        "snapshots": dados["snapshots"],
        "processados": set(dados["processados"]),
    }


def buscar(date_from, date_to, league_id=ALLSVENSKAN_LEAGUE_ID, tipos_disponiveis=None, caminho_checkpoint=None):
    """
    Devolve jogos/resultados_alvo/matriz/candidatas/snapshots, buscado direto da API.
    `resultados_alvo[fixture_id][alvo_id]` dá o resultado final da partida
    pra cada alvo em alvos.ALVOS (gols, escanteios, cartões, chutes...).
    Também expõe "gols_finais" (= resultados_alvo mapeado só pro alvo "gols")
    pra quem ainda espera o formato antigo.

    tipos_disponiveis: passe o dict de sm.mapa_types() já buscado se for chamar
    `buscar()` mais de uma vez (outras ligas/temporadas) — a paginação de
    ~1.300 tipos é a mesma pra qualquer liga, não precisa refazer a cada chamada.

    caminho_checkpoint: se informado, salva o progresso a cada
    INTERVALO_CHECKPOINT_FIXTURES fixtures nesse arquivo JSON. Serve dois
    papéis com o mesmo arquivo: (1) checkpoint — uma queda do processo no meio
    retoma dali em vez de recomeçar do zero; (2) cache permanente — o
    arquivo nunca é apagado, então a PRÓXIMA chamada com o mesmo caminho só
    busca fixtures que ainda não estão nele. Invalidado automaticamente se o
    conjunto de candidatas mudar (ver _carregar_checkpoint).
    """
    if tipos_disponiveis is None:
        print("Buscando tipos de estatística...")
        tipos_disponiveis = sm.mapa_types()
    candidatas_resolvidas = resolver_candidatas(tipos_disponiveis)
    goal_type_id = identificar_type_id_gol(tipos_disponiveis)
    if goal_type_id is None:
        print("  [aviso] type_id de 'Goal' não identificado — placar parcial vai usar o final como aproximação")

    nome_liga = LIGAS_MONITORADAS.get(league_id, str(league_id))
    print(f"Buscando fixtures de {nome_liga} entre {date_from} e {date_to}...")
    fixtures = sm.fixtures_da_liga(league_id, date_from, date_to)
    print(f"  {len(fixtures)} fixtures encontradas")

    cache = _carregar_checkpoint(caminho_checkpoint, candidatas_resolvidas) if caminho_checkpoint else None
    if cache:
        jogos, resultados_alvo, snapshots, processados = (
            cache["jogos"], cache["resultados_alvo"], cache["snapshots"], cache["processados"]
        )
        print(f"  {len(processados)} fixtures já em cache (de execuções anteriores), reaproveitando")
    else:
        jogos, resultados_alvo, snapshots, processados = {}, {}, [], set()

    novas = 0
    for i, f in enumerate(fixtures, 1):
        if f["id"] in processados:
            continue
        novas += 1
        print(f"[{nome_liga} {i}/{len(fixtures)}] fixture {f['id']}...")
        try:
            processar_fixture(f, candidatas_resolvidas, goal_type_id, tipos_disponiveis, jogos, resultados_alvo, snapshots)
        except Exception as e:
            print(f"  [ERRO] {e}")
        processados.add(f["id"])
        if caminho_checkpoint and novas % INTERVALO_CHECKPOINT_FIXTURES == 0:
            _salvar_checkpoint(caminho_checkpoint, jogos, resultados_alvo, snapshots, processados, candidatas_resolvidas)
        time.sleep(INTERVALO_ENTRE_FIXTURES_SEGUNDOS)

    if caminho_checkpoint and novas > 0:
        # nunca apaga: o mesmo arquivo funciona como checkpoint (retoma se cair no meio)
        # e como cache permanente (próxima chamada só busca fixtures que ainda não estão aqui —
        # ex.: jogos novos de uma temporada em andamento).
        _salvar_checkpoint(caminho_checkpoint, jogos, resultados_alvo, snapshots, processados, candidatas_resolvidas)
    print(f"  {novas} fixtures novas buscadas nesta execução, {len(processados) - novas} vieram do cache")

    candidatas_preditoras = sorted(set(candidatas_resolvidas) - alvos.CAMPOS_SO_ALVO)
    return {
        "jogos": jogos,
        "resultados_alvo": resultados_alvo,
        "gols_finais": {fid: r["gols"] for fid, r in resultados_alvo.items()},
        "matriz": dict(CORRELACAO_GOLS_PADRAO),
        "candidatas": candidatas_preditoras,
        "snapshots": snapshots,
    }


def mesclar(datasets):
    """
    Junta vários dicts no formato de buscar()/carregar_dados.carregar_tudo() num só.
    Assume que todos vieram de buscar() com o mesmo `tipos_disponiveis` (mesmas
    candidatas resolvidas em todos) — é assim que buscar_multiliga.py usa.
    """
    candidatas = datasets[0]["candidatas"]
    for d in datasets[1:]:
        if d["candidatas"] != candidatas:
            raise ValueError("datasets com candidatas diferentes — junte só datasets vindos do mesmo tipos_disponiveis")

    jogos, resultados_alvo, snapshots = {}, {}, []
    for d in datasets:
        repetidos = set(d["jogos"]) & set(jogos)
        if repetidos:
            raise ValueError(f"fixture_id repetido entre datasets: {sorted(repetidos)[:3]}")
        jogos.update(d["jogos"])
        resultados_alvo.update(d["resultados_alvo"])
        snapshots.extend(d["snapshots"])

    matriz = {}
    for d in datasets:
        matriz.update(d["matriz"])

    return {
        "jogos": jogos,
        "resultados_alvo": resultados_alvo,
        "gols_finais": {fid: r["gols"] for fid, r in resultados_alvo.items()},
        "matriz": matriz,
        "candidatas": candidatas,
        "snapshots": snapshots,
    }


if __name__ == "__main__":
    import buscar_condicoes

    dados = buscar(date_from="2025-01-01", date_to="2026-12-31")
    print(f"\n{len(dados['jogos'])} jogos, {len(dados['gols_finais'])} com resultado, "
          f"{len(dados['snapshots'])} snapshots, {len(dados['candidatas'])} candidatas")

    buscar_condicoes.rodar(dados=dados)
