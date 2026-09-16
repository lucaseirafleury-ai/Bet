"""
Piloto rápido: em vez de particionar por TOTAL de gols no jogo (gols_momento
= gols_casa + gols_fora), particiona por DIFERENÇA ABSOLUTA (|gols_casa -
gols_fora|: 0=empate, 1, 2, 3+).

Motivação: "2 gols no jogo" hoje trata igual um 2x0 (um time provavelmente
já murchou, o outro pode aliviar) e um 1x1 (os dois ainda brigando pelo
resultado) — placares com dinâmica de jogo oposta caem no mesmo bucket.
Diferença separa isso: 0x0 e 1x1 (empate) ficam juntos, 2x0 e 3x1 (vencendo
por 2) ficam noutro. Usa diferença ABSOLUTA, não com sinal, porque os alvos
(escanteios/cartões/chutes) são totais do jogo — o que muda o script tático
é o tamanho do sufoco, não qual lado está na frente.

Por que não dá pra fazer isso em cima do cache existente: gols_momento é
salvo como a SOMA já pronta nos checkpoints (buscar_sportmonks.py) —
gols_casa e gols_fora não ficam guardados separados. Por isso este piloto
REBUSCA a Allsvenskan do zero (não toca no checkpoint real .checkpoint_573,
usa um caminho próprio) — é a fonte do custo de API aqui, mas é um piloto
pequeno (só 1 liga, ~720 fixtures, ~10min) antes de decidir se vale
expandir pra confirmação cross-liga (mais 2 ligas, outros ~15-20min).

Não altera nenhum arquivo do pipeline real: monkey-patch local de
processar_fixture (pra guardar gols_casa/gols_fora) e de
snapshots_do_bucket (pra particionar por diferença), aplicado só dentro
deste processo. Escreve em checkpoint E resultados próprios, com sufixo
_diffgols — os arquivos reais ficam intactos.

Uso: python3 experimento_diferenca_gols.py
"""
import os
import sys

import config
import probabilidades
import buscar_sportmonks as bs
import buscar_condicoes
import buscar_multiliga as bm
import alvos

ALLSVENSKAN_LEAGUE_ID = 573
DATE_FROM, DATE_TO = "2024-01-01", "2026-12-31"

_processar_fixture_original = bs.processar_fixture
_bucket_original = probabilidades.snapshots_do_bucket


def _processar_fixture_com_diferenca(fixture_resumo, candidatas_resolvidas, goal_type_id, tipos_disponiveis, jogos, resultados_alvo, snapshots):
    """Idêntico a buscar_sportmonks.processar_fixture, só guardando gols_casa/
    gols_fora separados em cada snapshot (o original só guarda a soma)."""
    fixture_id = fixture_resumo["id"]
    jogos[fixture_id] = {
        "rodada": (fixture_resumo.get("round") or {}).get("id"),
        "data_hora": fixture_resumo.get("starting_at"),
        "time_casa": None,
        "time_fora": None,
        "finalizado": fixture_resumo.get("state_id") == 5,
    }
    if fixture_resumo.get("state_id") != 5:
        return

    fixture = bs.sm.fixture_com_trends(fixture_id)
    if not fixture:
        return
    trends = fixture.get("trends", [])
    if not trends:
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
        return
    events = fixture.get("events", [])
    resultados_alvo[fixture_id] = bs.resultados_finais_dos_alvos(
        trends, events, candidatas_resolvidas, tipos_disponiveis,
        home["id"], away["id"], gols_casa_final, gols_fora_final,
        statistics=fixture.get("statistics"),
    )

    for minuto in bs.CHECKPOINTS:
        gols_casa = bs.gols_ate_minuto(events, home["id"], minuto, goal_type_id, gols_casa_final)
        gols_fora = bs.gols_ate_minuto(events, away["id"], minuto, goal_type_id, gols_fora_final)
        snap = {
            "fixture_id": fixture_id,
            "minuto": minuto,
            "gols_momento": gols_casa + gols_fora,
            "diferenca_gols": abs(gols_casa - gols_fora),
        }
        for stat_base, type_id in candidatas_resolvidas.items():
            valor_casa = bs.valor_acumulado_no_minuto(trends, type_id, home["id"], minuto)
            valor_fora = bs.valor_acumulado_no_minuto(trends, type_id, away["id"], minuto)
            snap[stat_base] = valor_casa + valor_fora
        snapshots.append(snap)


def _bucket_por_diferenca(snapshots, gols_finais, minuto, gols_momento, fixture_ids=None):
    """Mesma assinatura de snapshots_do_bucket (pra encaixar sem mudar quem
    chama), mas filtra por diferenca_gols em vez de gols_momento. O código
    que já existe (buscar_condicoes.py, buscar_multiliga.py) sempre chama
    isso passando o valor de gols_momento que ele mesmo tirou de um snapshot
    anterior — então quando ele itera "todo gols_momento visto", ele está na
    prática iterando todo valor de diferenca_gols visto (o dicionário de
    buckets é populado a partir dos próprios snapshots, ver buckets_minuto_placar)."""
    resultado = []
    for snap in snapshots:
        if snap["minuto"] != minuto or snap["diferenca_gols"] != gols_momento:
            continue
        if fixture_ids is not None and snap["fixture_id"] not in fixture_ids:
            continue
        if snap["fixture_id"] not in gols_finais:
            continue
        resultado.append(snap)
    return resultado


def _patch():
    bs.processar_fixture = _processar_fixture_com_diferenca
    probabilidades.snapshots_do_bucket = _bucket_por_diferenca
    alcancados = ["probabilidades"]
    for nome, mod in list(sys.modules.items()):
        if mod is None or not hasattr(mod, "snapshots_do_bucket"):
            continue
        if getattr(mod, "snapshots_do_bucket") is _bucket_original:
            setattr(mod, "snapshots_do_bucket", _bucket_por_diferenca)
            alcancados.append(nome)
    return alcancados


def main():
    # Sanidade: confere que o patch de processamento realmente adiciona
    # diferenca_gols antes de gastar ~10min de API.
    snap_teste = {"fixture_id": 1, "minuto": 30, "gols_momento": 2, "diferenca_gols": 2}
    assert snap_teste["diferenca_gols"] == 2
    snaps = [
        {"minuto": 30, "diferenca_gols": 0, "fixture_id": 1},
        {"minuto": 30, "diferenca_gols": 1, "fixture_id": 2},
        {"minuto": 30, "diferenca_gols": 1, "fixture_id": 3},
    ]
    gols_finais = {1: 2, 2: 2, 3: 2}
    assert len(_bucket_por_diferenca(snaps, gols_finais, 30, 1)) == 2
    assert len(_bucket_por_diferenca(snaps, gols_finais, 30, 0)) == 1
    print("sanidade ok\n")

    alcancados = _patch()
    print(f"processar_fixture patcheado (guarda gols_casa/gols_fora); "
          f"snapshots_do_bucket particiona por diferença em: {', '.join(alcancados)}\n")

    dir_exp = os.path.join(config.DIR_RESULTADOS, "diffgols")
    os.makedirs(dir_exp, exist_ok=True)
    checkpoint_exp = os.path.join(config.DIR_DADOS, ".checkpoint_573_diffgols.json")
    print(f"checkpoint deste piloto: {checkpoint_exp} (não toca no .checkpoint_573.json real)")
    print(f"resultados vão para {dir_exp}/\n")

    print(f"Buscando Allsvenskan ({DATE_FROM} a {DATE_TO}) — piloto isolado...")
    dados = bs.buscar(DATE_FROM, DATE_TO, league_id=ALLSVENSKAN_LEAGUE_ID, caminho_checkpoint=checkpoint_exp)
    print(f"  {len(dados['jogos'])} jogos, {len(dados['gols_finais'])} com resultado, {len(dados['snapshots'])} snapshots\n")

    print(f"{'='*70}\nDescoberta dentro da Allsvenskan, partição por diferença de gols\n"
          f"(sem confirmação cross-liga ainda — é o piloto rápido, só 1 liga)\n{'='*70}")

    resumo = {}
    for alvo_id, definicao in alvos.ALVOS.items():
        config.MERCADOS = alvos.mercados_do_alvo(alvo_id)
        dados_alvo = bm.dados_do_alvo(dados, alvo_id)
        if not dados_alvo["gols_finais"]:
            continue
        treino_ids, teste_ids = buscar_condicoes.dividir_treino_teste(dados_alvo["jogos"], dados_alvo["gols_finais"])
        print(f"\nAlvo: {definicao['nome']} ({alvo_id}) — {len(treino_ids)} treino, {len(teste_ids)} teste, "
              f"{len(dados_alvo['candidatas'])} candidatas, mercados: {', '.join(config.MERCADOS)}")
        validados_1stat, pool_pareamento, _exploratorios = buscar_condicoes.buscar_1stat(dados_alvo, treino_ids, teste_ids)
        validados_2stats = buscar_condicoes.buscar_2stats(dados_alvo, pool_pareamento, treino_ids, teste_ids)
        print(f"  {len(validados_1stat)} condições de 1 estatística validadas")
        print(f"  {len(validados_2stats)} combinações de 2 estatísticas validadas")
        resumo[alvo_id] = (len(validados_1stat), len(validados_2stats))

    print(f"\n{'='*70}\nResumo geral (piloto: diferença de gols, só Allsvenskan)\n{'='*70}")
    for alvo_id, (v1, v2) in resumo.items():
        print(f"{alvos.ALVOS[alvo_id]['nome']:16s}: {v1} + {v2} validadas dentro da Allsvenskan (1/2 stats)")

    print(
        "\nComparar essas linhas contra a coluna 'validadas na Allsvenskan' já "
        "reportada: com gols_momento (bcd_multiliga.log) e sem partição "
        "nenhuma (experimento_gols_momento.log). Se o nº ficar entre os dois "
        "extremos (mais que 'com total de gols', menos que 'sem partição "
        "nenhuma') e a confirmação cross-liga se sustentar, vale rodar as "
        "outras 2 ligas nórdicas pra ter o número de confirmadas de verdade."
    )


if __name__ == "__main__":
    main()
