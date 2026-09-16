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
import descobrir_nativo_brasil as dnb
import descobrir_nativo_serieB as dnsb
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
    """Mesma assinatura de snapshots_do_bucket, mas filtra por diferenca_gols
    em vez de gols_momento."""
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


def _buckets_minuto_por_diferenca(snapshots, fixture_ids):
    """
    BUG real encontrado depois de já ter rodado o piloto inteiro (pilotos
    rápido E completo): buscar_condicoes.buckets_minuto_placar é uma função
    SEPARADA de snapshots_do_bucket — lê snap["gols_momento"] direto pra
    montar o dicionário de buckets de TREINO, sem passar pelo patch. O treino
    então bucketava por total de gols (não por diferença), enquanto o
    reteste no conjunto de teste (_testar_no_teste -> snapshots_do_bucket,
    esse sim patcheado) filtrava por diferença — comparando um valor de
    "gols_momento" (0,1,2,3...) contra snap["diferenca_gols"], que tem a
    MESMA faixa de valores mas significado diferente (silenciosamente
    incoerente, não dava erro). Os dois pilotos já rodados estão contaminados
    por isso — precisam ser refeitos com este patch a mais.
    """
    buckets = {}
    for snap in snapshots:
        if snap["fixture_id"] not in fixture_ids:
            continue
        chave = (snap["minuto"], snap["diferenca_gols"])
        buckets.setdefault(chave, []).append(snap)
    return buckets


def _patch():
    bs.processar_fixture = _processar_fixture_com_diferenca
    probabilidades.snapshots_do_bucket = _bucket_por_diferenca
    buscar_condicoes.buckets_minuto_placar = _buckets_minuto_por_diferenca
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
    # Confere buckets_minuto_placar TAMBÉM (bug real: essa é uma função
    # separada de snapshots_do_bucket, usada pra montar o dicionário de
    # treino em buscar_1stat -- ficou de fora do patch original).
    buckets = _buckets_minuto_por_diferenca(snaps, {1, 2, 3})
    assert set(buckets.keys()) == {(30, 0), (30, 1)}
    assert len(buckets[(30, 1)]) == 2
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


def main_completo():
    """
    Expansão do piloto: descoberta na Allsvenskan (reaproveita o cache do
    piloto rápido, copiado pra dados/diffgols_full/.checkpoint_573.json —
    zero custo de API pra essa parte) + confirmação cross-liga em Superettan
    e 1.Division (rebuscadas do zero em dados/diffgols_full/, com o mesmo
    patch de processar_fixture — essa parte SIM gasta API real, ~1448
    fixtures nunca vistas com gols_casa/gols_fora separados).

    Roda o pipeline real (buscar_multiliga.rodar) só com bucket redirecionado
    pra diferenca_gols, igual experimento_gols_momento.py já faz pra "sem
    partição". Resultados em resultados/diffgols/ — não sobrescreve nada real.
    """
    alcancados = _patch()
    print(f"processar_fixture patcheado; snapshots_do_bucket particiona por diferença em: {', '.join(alcancados)}\n")

    dir_dados_exp = os.path.join(config.DIR_DADOS, "diffgols_full")
    dir_resultados_exp = os.path.join(config.DIR_RESULTADOS, "diffgols")
    os.makedirs(dir_dados_exp, exist_ok=True)
    os.makedirs(dir_resultados_exp, exist_ok=True)
    checkpoint_allsvenskan = os.path.join(dir_dados_exp, ".checkpoint_573.json")
    if not os.path.exists(checkpoint_allsvenskan):
        print(f"[aviso] {checkpoint_allsvenskan} não existe ainda — copie o checkpoint do piloto rápido "
              f"({os.path.join(config.DIR_DADOS, '.checkpoint_573_diffgols.json')}) pra esse caminho antes "
              f"de rodar, senão a Allsvenskan também será rebuscada do zero (mais API, sem necessidade).")

    config.DIR_DADOS = dir_dados_exp
    config.DIR_RESULTADOS = dir_resultados_exp
    bm.config.DIR_DADOS = dir_dados_exp
    bm.config.DIR_RESULTADOS = dir_resultados_exp
    print(f"dados em {dir_dados_exp}/, resultados em {dir_resultados_exp}/ (nada real é tocado)\n")

    bm.rodar()


def main_brasil():
    """
    Testa diferença de gols na metodologia NATIVA do Brasil (Série A<->Série
    B, mesma usada pelas 72 regras reais em produção — confirmação cruzada
    sem depender da Allsvenskan). Diferente do teste nórdico: aqui não tem
    cache pré-existente com diferenca_gols, então Série A E Série B são
    rebuscadas do zero (~2.284 fixtures, ~15-25min de API real).

    Roda descobrir_nativo_brasil.rodar() (descobre na Série A, confirma na
    Série B) e descobrir_nativo_serieB.rodar() (espelho) com o bucket
    redirecionado pra diferença de gols. Resultados em
    resultados/diffgols_brasil/, dados em dados/diffgols_brasil/ — não
    sobrescreve nada real (os scripts reais usam .checkpoint_648.json/
    .checkpoint_651.json e resultados/*_serieA_*.csv direto em resultados/,
    caminhos completamente diferentes).
    """
    alcancados = _patch()
    print(f"processar_fixture patcheado; snapshots_do_bucket particiona por diferença em: {', '.join(alcancados)}\n")

    dir_dados_exp = os.path.join(config.DIR_DADOS, "diffgols_brasil")
    dir_resultados_exp = os.path.join(config.DIR_RESULTADOS, "diffgols_brasil")
    os.makedirs(dir_dados_exp, exist_ok=True)
    os.makedirs(dir_resultados_exp, exist_ok=True)
    config.DIR_DADOS = dir_dados_exp
    config.DIR_RESULTADOS = dir_resultados_exp
    print(f"dados em {dir_dados_exp}/, resultados em {dir_resultados_exp}/ (nada real é tocado)\n")

    print(f"{'='*70}\nParte 1/2: descobrir_nativo_brasil (Série A descobre, Série B confirma)\n{'='*70}")
    dnb.rodar()

    print(f"\n{'='*70}\nParte 2/2: descobrir_nativo_serieB (Série B descobre, Série A confirma)\n{'='*70}")
    dnsb.rodar()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "completo":
        main_completo()
    elif len(sys.argv) > 1 and sys.argv[1] == "brasil":
        main_brasil()
    else:
        main()
