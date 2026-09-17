"""
Cruza as três vias de descoberta das ligas novas (ver descobrir_ligas_novas.py)
e conta, por família de condição, quantas vias independentes confirmaram cada
uma — o número que no Brasil separou ROI real de +17,8% (3 vias) de -47%/-49%
(1 via).

NÃO decide nada: só produz a contagem por nível de confirmação (1, 2, 3), pra
que a escolha do piso seja feita medindo ROI real contra odds da bet365 DENTRO
de cada liga, em vez de herdar o critério do Brasil.

Reaproveita de gerar_regras_sinais.py a lógica de agrupamento por família
(_ancoras_1stat/_chave_familia/_colapsar) — é o que colapsa as milhares de
variações quase idênticas (mesma história com limite/linha vizinhos) em
histórias distintas de verdade. Só o LEITOR é próprio: os CSVs das ligas novas
saem como "{alvo}_{prefixo}_confirmacao_*.csv", ordem diferente do padrão de
produção ("{alvo}_confirmacao{sufixo}_*.csv") que _carregar_brutas espera,
embora o conteúdo (17 colunas) seja idêntico.

Uso: python3 cruzar_vias_ligas_novas.py [--liga mls] [--alvo escanteios]
"""
import csv
import os
from collections import defaultdict

import gerar_regras_sinais as g
from descobrir_ligas_novas import ALVOS_ESTUDADOS, LIGAS_NOVAS

VIAS = ["herdado", "nativo12", "nativo21"]


def _ler_via(alvo_id, prefixo_liga, via):
    """CSVs de uma via -> mesma estrutura que gerar_regras_sinais._carregar_brutas
    produz, pra poder usar as funções de família dele sem adaptação.

    Aplica os MESMOS filtros do pipeline publicado (confirmado_bh, amostra >=
    AMOSTRA_MINIMA, impacto >= IMPACTO_MINIMO_PP) — sem eles entram condições
    estatisticamente reais mas economicamente triviais, erro já cometido nesta
    sessão ao calcular ROI sem o piso de impacto.
    """
    brutas = []
    base = f"{alvo_id}_{prefixo_liga}_{via}_confirmacao"

    caminho_1 = os.path.join(g.BASE, f"{base}_1stat.csv")
    for r in g.ler_csv(caminho_1):
        amostra = int(r["amostra_outras_ligas"])
        impacto = float(r["impacto_outras_ligas_pp"])
        if amostra < g.AMOSTRA_MINIMA or abs(impacto) < g.IMPACTO_MINIMO_PP:
            continue
        brutas.append({
            "alvo_id": alvo_id, "minuto": int(r["minuto"]), "gols_momento": int(r["gols_momento"]),
            "condicao_chave": (r["stat"], r["operador"], r["limite"]),
            "condicoes": [{"stat": r["stat"], "operador": r["operador"], "limite": float(r["limite"])}],
            "linha_mercado": float(r["mercado"][1:]), "sinal_mercado": r["mercado"][0],
            "amostra": amostra, "p_base": float(r["p_base_outras_ligas"]),
            "p_condicao": float(r["p_final_outras_ligas"]), "impacto": impacto,
            "p_valor": float(r["p_valor_outras_ligas"]), "origem": via,
        })

    caminho_2 = os.path.join(g.BASE, f"{base}_2stats.csv")
    for r in g.ler_csv(caminho_2):
        amostra = int(r["amostra_outras_ligas"])
        p_base = float(r["p_base_outras_ligas"])
        p_cond = float(r["p_conjunta_outras_ligas"])
        impacto = (p_cond - p_base) * 100
        if amostra < g.AMOSTRA_MINIMA or abs(impacto) < g.IMPACTO_MINIMO_PP:
            continue
        brutas.append({
            "alvo_id": alvo_id, "minuto": int(r["minuto"]), "gols_momento": int(r["gols_momento"]),
            "condicao_chave": (r["stat1"], r["operador1"], r["limite1"], r["stat2"], r["operador2"], r["limite2"]),
            "condicoes": [
                {"stat": r["stat1"], "operador": r["operador1"], "limite": float(r["limite1"])},
                {"stat": r["stat2"], "operador": r["operador2"], "limite": float(r["limite2"])},
            ],
            "linha_mercado": float(r["mercado"][1:]), "sinal_mercado": r["mercado"][0],
            "amostra": amostra, "p_base": p_base, "p_condicao": p_cond, "impacto": impacto,
            "p_valor": float(r["p_valor_outras_ligas"]), "origem": via,
        })
    return brutas


def cruzar(alvo_id, prefixo_liga):
    """Devolve (familias_por_nivel, detalhe) — quantas famílias tiveram 1, 2 ou
    3 vias confirmando, e a melhor variação de cada família com 3 vias."""
    por_via = {via: g._colapsar(_ler_via(alvo_id, prefixo_liga, via)) for via in VIAS}
    combinado = [item for itens in por_via.values() for item in itens]
    if not combinado:
        return {1: 0, 2: 0, 3: 0}, [], {v: 0 for v in VIAS}

    ancoras = g._ancoras_1stat(combinado)
    grupos = defaultdict(list)
    for item in combinado:
        grupos[g._chave_familia(item, ancoras)].append(item)

    niveis = {1: 0, 2: 0, 3: 0}
    triplas = []
    for grupo in grupos.values():
        origens = {i["origem"] for i in grupo}
        niveis[len(origens)] = niveis.get(len(origens), 0) + 1
        if len(origens) >= 3:
            triplas.append(max(grupo, key=lambda x: x["impacto"]))
    return niveis, triplas, {v: len(por_via[v]) for v in VIAS}


def rodar(ligas=None, alvos_sel=None):
    prefixos = [p for p in LIGAS_NOVAS.values() if ligas is None or p in ligas]
    alvos_rodada = [a for a in ALVOS_ESTUDADOS if alvos_sel is None or a in alvos_sel]

    print(f"{'liga':12s} {'alvo':16s} {'herdado':>8s} {'nat12':>7s} {'nat21':>7s} "
          f"| {'1 via':>6s} {'2 vias':>7s} {'3 vias':>7s}")
    print("-" * 82)
    total_triplas = defaultdict(list)
    for prefixo in prefixos:
        for alvo_id in alvos_rodada:
            niveis, triplas, por_via = cruzar(alvo_id, prefixo)
            print(f"{prefixo:12s} {alvo_id:16s} {por_via['herdado']:8d} {por_via['nativo12']:7d} "
                  f"{por_via['nativo21']:7d} | {niveis.get(1,0):6d} {niveis.get(2,0):7d} {niveis.get(3,0):7d}")
            total_triplas[prefixo].extend(triplas)

    print()
    for prefixo, triplas in total_triplas.items():
        print(f"{prefixo}: {len(triplas)} famílias com as 3 vias concordando")
        for t in sorted(triplas, key=lambda x: -x["impacto"])[:5]:
            cond = " E ".join(f"{c['stat']}{c['operador']}{c['limite']:g}" for c in t["condicoes"])
            print(f"   {t['alvo_id']:14s} {t['minuto']:3d}' g={t['gols_momento']} | {cond} -> "
                  f"{t['sinal_mercado']}{t['linha_mercado']:g} | impacto {t['impacto']:+.1f}pp, n={t['amostra']}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--liga", action="append", help="prefixo da liga (mls/argentina/championship)")
    ap.add_argument("--alvo", action="append", choices=ALVOS_ESTUDADOS)
    a = ap.parse_args()
    rodar(a.liga, a.alvo)
