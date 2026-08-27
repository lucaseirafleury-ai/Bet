"""
Testa se exigir que um sinal apareça em DUAS minutagens diferentes (ex.: já
recomendou "Menos de 9.5 escanteios" aos 15' E de novo aos 30') antes de
considerar "entrar" tem alguma vantagem real de acerto sobre entrar já na
primeira aparição — pergunta feita pelo usuário sobre o painel ao vivo.

Reaproveita os dados já cacheados (dados/.checkpoint_*.json, 7 ligas) e as 52
regras hoje ativas em ligas_live_app/regras_sinais.json. Para cada jogo,
simula quais regras teriam disparado em cada checkpoint (15/30/45/60/75/90)
e agrupa por (alvo, direção):
  - "único": só disparou em UM checkpoint pra esse jogo/alvo/direção.
  - "persistiu": disparou em 2+ checkpoints diferentes (mesma direção).

Compara a taxa de acerto real (contra o resultado final da partida) entre os
dois grupos, com teste estatístico formal (mesmo teste de duas proporções já
usado no resto do projeto).

Uso: python testar_persistencia.py (não precisa de token — só dados locais)
"""
import glob
import json
import os

import estatistica

BASE = os.path.dirname(__file__)
DADOS_DIR = os.path.join(BASE, "dados")
CAMINHO_REGRAS = os.path.join(BASE, "..", "ligas_live_app", "regras_sinais.json")


def _condicao_bate(condicoes, snap):
    for c in condicoes:
        v = snap.get(c["stat"])
        if v is None:
            return False
        if c["operador"] == ">=" and v < c["limite"]:
            return False
        if c["operador"] == "<=" and v > c["limite"]:
            return False
    return True


def _bateu_mercado(valor_final, direcao, linha):
    return (valor_final > linha) if direcao == "mais_de" else (valor_final < linha)


def carregar_dados_pooled():
    snaps_por_fixture = {}
    resultados = {}
    for caminho in glob.glob(f"{DADOS_DIR}/.checkpoint_*.json"):
        d = json.load(open(caminho, encoding="utf-8"))
        for fid_str, res in d["resultados_alvo"].items():
            resultados[int(fid_str)] = res
        for snap in d["snapshots"]:
            snaps_por_fixture.setdefault(snap["fixture_id"], {})[snap["minuto"]] = snap
    return snaps_por_fixture, resultados


def rodar():
    snaps_por_fixture, resultados = carregar_dados_pooled()
    with open(CAMINHO_REGRAS, encoding="utf-8") as fp:
        regras = json.load(fp)["regras"]
    print(f"{len(regras)} regras, {len(snaps_por_fixture)} jogos com snapshots, {len(resultados)} com resultado final\n")

    # fixture -> (alvo, direcao) -> {minuto: linha} (se mais de uma regra disparar no
    # mesmo checkpoint pro mesmo alvo/direcao, fica só a última — não importa pra este teste)
    disparos = {}
    for regra in regras:
        alvo, direcao, linha = regra["alvo"], regra["mercado"]["direcao"], regra["mercado"]["linha"]
        minuto, gols_momento = regra["minuto"], regra["gols_momento"]
        for fid, snaps in snaps_por_fixture.items():
            snap = snaps.get(minuto)
            if not snap or snap.get("gols_momento") != gols_momento:
                continue
            if not _condicao_bate(regra["condicoes"], snap):
                continue
            disparos.setdefault(fid, {}).setdefault((alvo, direcao), {})[minuto] = linha

    casos_unico = []    # (alvo, direcao, bateu)
    casos_persistiu = []  # (alvo, direcao, bateu) -- avaliado na linha do ÚLTIMO checkpoint

    for fid, por_mercado in disparos.items():
        res = resultados.get(fid)
        if not res:
            continue
        for (alvo, direcao), checkpoints in por_mercado.items():
            valor_final = res.get(alvo)
            if valor_final is None:
                continue
            minutos = sorted(checkpoints)
            if len(minutos) == 1:
                linha = checkpoints[minutos[0]]
                casos_unico.append((alvo, direcao, _bateu_mercado(valor_final, direcao, linha)))
            else:
                linha_ultima = checkpoints[minutos[-1]]
                casos_persistiu.append((alvo, direcao, _bateu_mercado(valor_final, direcao, linha_ultima)))

    def resumo(casos, alvo_filtro=None):
        sel = [c for c in casos if alvo_filtro is None or c[0] == alvo_filtro]
        n = len(sel)
        if n == 0:
            return n, None
        acertos = sum(1 for c in sel if c[2])
        return n, acertos / n

    print("=" * 70)
    print("Geral (todos os alvos juntos)")
    print("=" * 70)
    n_u, p_u = resumo(casos_unico)
    n_p, p_p = resumo(casos_persistiu)
    print(f"  único checkpoint : n={n_u:5d}, acerto={p_u*100:.1f}%" if p_u is not None else f"  único: n={n_u}")
    print(f"  persistiu (2+)   : n={n_p:5d}, acerto={p_p*100:.1f}%" if p_p is not None else f"  persistiu: n={n_p}")
    if p_u is not None and p_p is not None:
        p_valor = estatistica.teste_duas_proporcoes(p_p, n_p, p_u, n_u)
        diff_pp = (p_p - p_u) * 100
        print(f"  diferença: {diff_pp:+.1f} p.p. | p-valor (persistiu vs único): {p_valor:.4f}"
              f" {'(SIGNIFICATIVO)' if p_valor is not None and p_valor < 0.05 else '(não significativo)'}")

    print(f"\n{'='*70}\nPor alvo\n{'='*70}")
    alvos_presentes = sorted(set(c[0] for c in casos_unico + casos_persistiu))
    for alvo in alvos_presentes:
        n_u, p_u = resumo(casos_unico, alvo)
        n_p, p_p = resumo(casos_persistiu, alvo)
        txt_u = f"n={n_u:5d}, acerto={p_u*100:.1f}%" if p_u is not None else f"n={n_u} (sem casos)"
        txt_p = f"n={n_p:5d}, acerto={p_p*100:.1f}%" if p_p is not None else f"n={n_p} (sem casos)"
        print(f"\n  {alvo}:")
        print(f"    único    : {txt_u}")
        print(f"    persistiu: {txt_p}")
        if p_u is not None and p_p is not None and n_p > 0:
            p_valor = estatistica.teste_duas_proporcoes(p_p, n_p, p_u, n_u)
            diff_pp = (p_p - p_u) * 100
            sig = "(SIGNIFICATIVO)" if p_valor is not None and p_valor < 0.05 else "(não significativo)"
            print(f"    diferença: {diff_pp:+.1f} p.p. | p-valor: {p_valor:.4f} {sig}")

    total_disparos_jogo_mercado = len(casos_unico) + len(casos_persistiu)
    print(f"\n{'='*70}")
    print(f"Volume: {len(casos_persistiu)}/{total_disparos_jogo_mercado} "
          f"({len(casos_persistiu)/total_disparos_jogo_mercado*100:.1f}%) dos casos jogo+mercado teriam "
          f"'persistido' (2+ checkpoints) — ou seja, exigir isso corta ~"
          f"{(1 - len(casos_persistiu)/total_disparos_jogo_mercado)*100:.0f}% do volume de sinais.")


if __name__ == "__main__":
    rodar()
