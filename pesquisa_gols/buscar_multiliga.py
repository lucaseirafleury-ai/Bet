"""
Descobre condições na Allsvenskan (2024-2026, treino/teste cronológico como
sempre) e confirma se elas se repetem nas outras 4 ligas já monitoradas pelo
ligas_live_app (Superettan, A Lyga, 1. Lyga, 1. Division) — uma barra mais
alta do que só ter mais jogos: exige que o padrão apareça numa liga
DIFERENTE, não só num período diferente da mesma liga.

Roda isso pra cada alvo em alvos.ALVOS (gols, escanteios, cartões, chutes
totais, chutes no alvo) — os dados brutos (snapshots + resultado final de
cada alvo) são buscados UMA VEZ só; o que muda por alvo é só qual campo do
resultado final usar como "gols_finais" pro motor de busca e quais linhas
de mercado (+N/-N) testar.

Cada liga individualmente só tem 3 temporadas disponíveis neste plano da
Sportmonks (2024/2025/2026) — pouco pra validar com rigor sozinha. As outras
4 ligas juntas servem aqui só como confirmação (holdout independente), não
são misturadas com a Allsvenskan na etapa de descoberta — ligas diferentes
têm médias de gols/escanteios/cartões diferentes (o próprio ligas_live_app
usa coeficientes calibrados por liga para o Over/Under), então "achar" e
"confirmar" nas mesmas ligas misturadas infla a confiança sem necessidade.

Uso:
    export SPORTMONKS_TOKEN=...
    python buscar_multiliga.py
"""
import csv
import os

import alvos
import config
import buscar_condicoes
import buscar_sportmonks as bs
import estatistica
import sportmonks as sm
from probabilidades import avaliar_condicao_1stat, snapshots_do_bucket, probabilidades_do_grupo

DATE_FROM = "2024-01-01"
DATE_TO = "2026-12-31"


def dados_do_alvo(dados_base, alvo_id):
    """Recorta o dataset bruto (jogos/resultados_alvo/snapshots) pra um alvo específico."""
    return {
        "jogos": dados_base["jogos"],
        "gols_finais": {fid: r[alvo_id] for fid, r in dados_base["resultados_alvo"].items() if r.get(alvo_id) is not None},
        "matriz": dados_base["matriz"],
        "candidatas": alvos.candidatas_do_alvo(alvo_id, dados_base["candidatas"]),
        "snapshots": dados_base["snapshots"],
    }


def confirmar_1stat(cond, dados_conf):
    bucket = snapshots_do_bucket(dados_conf["snapshots"], dados_conf["gols_finais"], cond["minuto"], cond["gols_momento"])
    r = avaliar_condicao_1stat(bucket, dados_conf["gols_finais"], cond["stat"], cond["operador"], cond["limite"])
    if r["amostra_condicao"] < config.AMOSTRA_MINIMA or r["amostra_complemento"] < config.AMOSTRA_MINIMA:
        return None
    impacto = r["impacto"][cond["mercado"]]
    if impacto is None:
        return None
    p_valor = estatistica.teste_duas_proporcoes(
        r["p_final"][cond["mercado"]], r["amostra_condicao"],
        r["p_complemento"][cond["mercado"]], r["amostra_complemento"],
    )
    return {
        "minuto": cond["minuto"], "gols_momento": cond["gols_momento"],
        "stat": cond["stat"], "operador": cond["operador"], "limite": cond["limite"], "mercado": cond["mercado"],
        "impacto_allsvenskan_treino_pp": cond["impacto_treino_pp"],
        "impacto_allsvenskan_teste_pp": cond["impacto_teste_pp"],
        "amostra_outras_ligas": r["amostra_condicao"],
        "p_final_outras_ligas": r["p_final"][cond["mercado"]],
        "p_base_outras_ligas": r["p_base"][cond["mercado"]],
        "impacto_outras_ligas_pp": impacto * 100,
        "mesma_direcao": (impacto > 0) == (cond["impacto_treino_pp"] > 0),
        "p_valor_outras_ligas": p_valor,
    }


def confirmar_2stats(cond, dados_conf):
    bucket = snapshots_do_bucket(dados_conf["snapshots"], dados_conf["gols_finais"], cond["minuto"], cond["gols_momento"])

    def bate(s):
        v1 = (s[cond["stat1"]] >= cond["limite1"]) if cond["operador1"] == ">=" else (s[cond["stat1"]] <= cond["limite1"])
        v2 = (s[cond["stat2"]] >= cond["limite2"]) if cond["operador2"] == ">=" else (s[cond["stat2"]] <= cond["limite2"])
        return v1 and v2

    grupo = [s for s in bucket if bate(s)]
    complemento = [s for s in bucket if not bate(s)]
    p_g, n_g = probabilidades_do_grupo(grupo, dados_conf["gols_finais"])
    p_c, n_c = probabilidades_do_grupo(complemento, dados_conf["gols_finais"])
    if n_g < config.AMOSTRA_MINIMA or n_c < config.AMOSTRA_MINIMA:
        return None
    p_base, n_base = probabilidades_do_grupo(bucket, dados_conf["gols_finais"])
    p_valor = estatistica.teste_duas_proporcoes(p_g[cond["mercado"]], n_g, p_c[cond["mercado"]], n_c)
    return {
        "minuto": cond["minuto"], "gols_momento": cond["gols_momento"], "mercado": cond["mercado"],
        "stat1": cond["stat1"], "operador1": cond["operador1"], "limite1": cond["limite1"],
        "stat2": cond["stat2"], "operador2": cond["operador2"], "limite2": cond["limite2"],
        "classificacao_allsvenskan": cond["classificacao"],
        "amostra_outras_ligas": n_g,
        "p_conjunta_outras_ligas": p_g[cond["mercado"]],
        "p_base_outras_ligas": p_base[cond["mercado"]],
        "p_valor_outras_ligas": p_valor,
    }


def aplicar_bh_confirmacao(confirmadas):
    """
    Aplica Benjamini-Hochberg sobre o p-valor calculado NAS OUTRAS LIGAS —
    mesma disciplina que buscar_1stat/buscar_2stats já aplicam dentro da
    Allsvenskan. São poucas condições nesta etapa (só as que já sobreviveram
    à Allsvenskan), então a correção é leve — mas sem ela, "mesma direção e
    magnitude parecida" não é o mesmo que "estatisticamente confirmado".
    """
    significativas = estatistica.corrigir_benjamini_hochberg(
        [(i, c["p_valor_outras_ligas"]) for i, c in enumerate(confirmadas)], config.ALFA
    )
    for i, c in enumerate(confirmadas):
        c["confirmado_bh"] = i in significativas
    return confirmadas


def salvar_csv(caminho, linhas):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    if not linhas:
        with open(caminho, "w", encoding="utf-8") as fp:
            fp.write("(nenhuma condição teve amostra suficiente pra confirmar nas outras ligas)\n")
        return
    with open(caminho, "w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(linhas[0].keys()))
        writer.writeheader()
        writer.writerows(linhas)


def buscar_dados_brutos():
    """Busca (ou reaproveita do cache) os dados de todas as 5 ligas, com todos os campos de alvos.py."""
    print("Buscando tipos de estatística (uma vez só, reaproveitado pra todas as ligas)...")
    tipos_disponiveis = sm.mapa_types()

    print(f"\nBuscando Allsvenskan ({DATE_FROM} a {DATE_TO})...")
    dados_allsvenskan = bs.buscar(
        DATE_FROM, DATE_TO, league_id=573, tipos_disponiveis=tipos_disponiveis,
        caminho_checkpoint=os.path.join(config.DIR_DADOS, ".checkpoint_573.json"),
    )
    print(f"  {len(dados_allsvenskan['jogos'])} jogos, {len(dados_allsvenskan['gols_finais'])} com resultado, "
          f"{len(dados_allsvenskan['snapshots'])} snapshots")

    outras_ligas = {lid: nome for lid, nome in bs.LIGAS_MONITORADAS.items() if lid != 573}
    print(f"\nBuscando confirmação: {', '.join(outras_ligas.values())} ({DATE_FROM} a {DATE_TO})...")
    datasets_outras = []
    for lid, nome in outras_ligas.items():
        d = bs.buscar(
            DATE_FROM, DATE_TO, league_id=lid, tipos_disponiveis=tipos_disponiveis,
            caminho_checkpoint=os.path.join(config.DIR_DADOS, f".checkpoint_{lid}.json"),
        )
        print(f"  {nome}: {len(d['jogos'])} jogos, {len(d['gols_finais'])} com resultado, {len(d['snapshots'])} snapshots")
        datasets_outras.append(d)
    dados_confirmacao_bruto = bs.mesclar(datasets_outras)
    print(f"  total confirmação: {len(dados_confirmacao_bruto['jogos'])} jogos, "
          f"{len(dados_confirmacao_bruto['gols_finais'])} com resultado, {len(dados_confirmacao_bruto['snapshots'])} snapshots")

    return dados_allsvenskan, dados_confirmacao_bruto


def rodar_alvo(alvo_id, dados_allsvenskan_bruto, dados_confirmacao_bruto):
    definicao = alvos.ALVOS[alvo_id]
    print(f"\n{'='*70}\nAlvo: {definicao['nome']} ({alvo_id})\n{'='*70}")

    config.MERCADOS = alvos.mercados_do_alvo(alvo_id)
    dados_allsvenskan = dados_do_alvo(dados_allsvenskan_bruto, alvo_id)
    dados_confirmacao = dados_do_alvo(dados_confirmacao_bruto, alvo_id)

    treino_ids, teste_ids = buscar_condicoes.dividir_treino_teste(dados_allsvenskan["jogos"], dados_allsvenskan["gols_finais"])
    print(f"  split cronológico: {len(treino_ids)} treino, {len(teste_ids)} teste "
          f"({len(dados_allsvenskan['candidatas'])} candidatas, mercados: {', '.join(config.MERCADOS)})")

    validados_1stat, pool_pareamento, exploratorios = buscar_condicoes.buscar_1stat(dados_allsvenskan, treino_ids, teste_ids)
    validados_2stats = buscar_condicoes.buscar_2stats(dados_allsvenskan, pool_pareamento, treino_ids, teste_ids)
    print(f"  {len(validados_1stat)} condições de 1 estatística validadas dentro da Allsvenskan")
    print(f"  {len(validados_2stats)} combinações de 2 estatísticas validadas dentro da Allsvenskan")

    salvar_csv(os.path.join(config.DIR_RESULTADOS, f"{alvo_id}_allsvenskan_condicoes_1stat.csv"), validados_1stat)
    salvar_csv(os.path.join(config.DIR_RESULTADOS, f"{alvo_id}_allsvenskan_condicoes_2stats.csv"), validados_2stats)
    salvar_csv(os.path.join(config.DIR_RESULTADOS, f"{alvo_id}_allsvenskan_exploratorio_1stat.csv"), exploratorios)

    print("  Confirmando condições de 1 estatística nas outras ligas...")
    confirmadas_1stat = [c for c in (confirmar_1stat(cond, dados_confirmacao) for cond in validados_1stat) if c]
    confirmadas_1stat = aplicar_bh_confirmacao(confirmadas_1stat)
    print(f"    {sum(1 for c in confirmadas_1stat if c['confirmado_bh'])} de {len(confirmadas_1stat)} "
          f"sobrevivem ao teste estatístico formal (Benjamini-Hochberg) do lado da confirmação")

    print("  Confirmando combinações de 2 estatísticas nas outras ligas...")
    confirmadas_2stats = [c for c in (confirmar_2stats(cond, dados_confirmacao) for cond in validados_2stats) if c]
    confirmadas_2stats = aplicar_bh_confirmacao(confirmadas_2stats)
    print(f"    {sum(1 for c in confirmadas_2stats if c['confirmado_bh'])} de {len(confirmadas_2stats)} "
          f"sobrevivem ao teste estatístico formal (Benjamini-Hochberg) do lado da confirmação")

    caminho_1 = os.path.join(config.DIR_RESULTADOS, f"{alvo_id}_confirmacao_1stat.csv")
    caminho_2 = os.path.join(config.DIR_RESULTADOS, f"{alvo_id}_confirmacao_2stats.csv")
    salvar_csv(caminho_1, confirmadas_1stat)
    salvar_csv(caminho_2, confirmadas_2stats)
    print(f"  Salvo em {caminho_1} e {caminho_2}")

    return {
        "validados_1stat": len(validados_1stat), "validados_2stats": len(validados_2stats),
        "confirmados_1stat": sum(1 for c in confirmadas_1stat if c["confirmado_bh"]),
        "confirmados_2stats": sum(1 for c in confirmadas_2stats if c["confirmado_bh"]),
    }


def rodar():
    dados_allsvenskan_bruto, dados_confirmacao_bruto = buscar_dados_brutos()

    resumo = {}
    for alvo_id in alvos.ALVOS:
        resumo[alvo_id] = rodar_alvo(alvo_id, dados_allsvenskan_bruto, dados_confirmacao_bruto)

    print(f"\n{'='*70}\nResumo geral\n{'='*70}")
    for alvo_id, r in resumo.items():
        print(f"{alvos.ALVOS[alvo_id]['nome']:16s}: {r['validados_1stat']:2d} + {r['validados_2stats']:2d} validadas na "
              f"Allsvenskan (1/2 stats) -> {r['confirmados_1stat']} + {r['confirmados_2stats']} confirmadas nas outras ligas")


if __name__ == "__main__":
    rodar()
