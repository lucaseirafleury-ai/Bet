"""
Testa se os critérios já confirmados nas 4 ligas nórdicas (o que gerou as 85
regras hoje em ligas_live_app/regras_sinais.json) também se sustentam no
Brasileirão Série A (648) e Série B (651) — mesmo teste estatístico formal já
usado por buscar_multiliga.py (duas proporções + Benjamini-Hochberg), só que
a "liga de confirmação" aqui é o Brasil em vez das nórdicas.

Não descobre nada novo: reaproveita as condições já validadas dentro da
Allsvenskan (resultados/{alvo}_allsvenskan_condicoes_*.csv, a mesma etapa de
descoberta que já rodou) e só roda a etapa de CONFIRMAÇÃO de novo, contra um
dataset diferente. Ao final, cruza com regras_sinais.json pra dizer
especificamente: das 85 regras hoje ativas no painel, quantas replicam no
Brasil.

Uso:
    export SPORTMONKS_TOKEN=...
    python confirmar_brasil.py
"""
import csv
import json
import os

import alvos
import config
import buscar_multiliga as bm
import buscar_sportmonks as bs
import sportmonks as sm

DATE_FROM = "2024-01-01"
DATE_TO = "2026-12-31"
SERIE_A_ID = 648
SERIE_B_ID = 651

CAMINHO_REGRAS_ADOTADAS = os.path.join(os.path.dirname(__file__), "..", "ligas_live_app", "regras_sinais.json")
CAMINHO_RESUMO_ADOTADAS = os.path.join(config.DIR_RESULTADOS, "regras_adotadas_vs_brasil.csv")
CAMINHO_LOG_RESUMO = os.path.join(config.DIR_RESULTADOS, "resumo_confirmacao_brasil.txt")


def carregar_condicoes_1stat(alvo_id):
    caminho = os.path.join(config.DIR_RESULTADOS, f"{alvo_id}_allsvenskan_condicoes_1stat.csv")
    if not os.path.exists(caminho):
        return []
    with open(caminho, newline="", encoding="utf-8") as fp:
        linhas = list(csv.DictReader(fp))
    return [
        {
            "minuto": int(float(r["minuto"])), "gols_momento": int(float(r["gols_momento"])),
            "stat": r["stat"], "operador": r["operador"], "limite": float(r["limite"]),
            "mercado": r["mercado"], "impacto_treino_pp": float(r["impacto_treino_pp"]),
            "impacto_teste_pp": float(r["impacto_teste_pp"]),
        }
        for r in linhas
    ]


def carregar_condicoes_2stats(alvo_id):
    caminho = os.path.join(config.DIR_RESULTADOS, f"{alvo_id}_allsvenskan_condicoes_2stats.csv")
    if not os.path.exists(caminho):
        return []
    with open(caminho, newline="", encoding="utf-8") as fp:
        linhas = list(csv.DictReader(fp))
    return [
        {
            "minuto": int(float(r["minuto"])), "gols_momento": int(float(r["gols_momento"])),
            "mercado": r["mercado"],
            "stat1": r["stat1"], "operador1": r["operador1"], "limite1": float(r["limite1"]),
            "stat2": r["stat2"], "operador2": r["operador2"], "limite2": float(r["limite2"]),
            "classificacao": r["classificacao"],
        }
        for r in linhas
    ]


def carregar_regras_adotadas():
    """(minuto, gols_momento, mercado '+/-N', frozenset de (stat,operador,limite)) -> regra original."""
    with open(CAMINHO_REGRAS_ADOTADAS, encoding="utf-8") as fp:
        regras = json.load(fp)["regras"]
    mapa = {}
    for r in regras:
        linha = r["mercado"]["linha"]
        mercado = f"+{linha}" if r["mercado"]["direcao"] == "mais_de" else f"-{linha}"
        condset = frozenset((c["stat"], c["operador"], c["limite"]) for c in r["condicoes"])
        mapa[(r["minuto"], r["gols_momento"], mercado, condset)] = r
    return mapa


def chave_resultado_1stat(r):
    return (r["minuto"], r["gols_momento"], r["mercado"], frozenset({(r["stat"], r["operador"], r["limite"])}))


def chave_resultado_2stats(r):
    condset = frozenset({(r["stat1"], r["operador1"], r["limite1"]), (r["stat2"], r["operador2"], r["limite2"])})
    return (r["minuto"], r["gols_momento"], r["mercado"], condset)


def buscar_dados_brasil():
    print("Buscando tipos de estatística...")
    tipos_disponiveis = sm.mapa_types()
    datasets = []
    for lid, nome in ((SERIE_A_ID, "Série A"), (SERIE_B_ID, "Série B")):
        print(f"\nBuscando {nome} ({DATE_FROM} a {DATE_TO})...")
        d = bs.buscar(
            DATE_FROM, DATE_TO, league_id=lid, tipos_disponiveis=tipos_disponiveis,
            caminho_checkpoint=os.path.join(config.DIR_DADOS, f".checkpoint_{lid}.json"),
        )
        print(f"  {nome}: {len(d['jogos'])} jogos, {len(d['gols_finais'])} com resultado, {len(d['snapshots'])} snapshots")
        datasets.append(d)
    return bs.mesclar(datasets)


def rodar():
    dados_brasil_bruto = buscar_dados_brasil()
    adotadas = carregar_regras_adotadas()
    print(f"\n{len(adotadas)} regras hoje ativas no painel (regras_sinais.json) a checar contra o Brasil")

    resumo = {}
    linhas_resumo_adotadas = []

    for alvo_id in alvos.ALVOS:
        print(f"\n{'='*70}\nAlvo: {alvos.ALVOS[alvo_id]['nome']} ({alvo_id})\n{'='*70}")
        config.MERCADOS = alvos.mercados_do_alvo(alvo_id)
        dados_brasil = bm.dados_do_alvo(dados_brasil_bruto, alvo_id)

        cond_1 = carregar_condicoes_1stat(alvo_id)
        cond_2 = carregar_condicoes_2stats(alvo_id)
        print(f"  {len(cond_1)} condições de 1 estatística e {len(cond_2)} de 2 estatísticas "
          f"já validadas na Allsvenskan, testando contra o Brasil...")

        resultados_1 = bm.aplicar_bh_confirmacao(
            [r for r in (bm.confirmar_1stat(cond, dados_brasil) for cond in cond_1) if r]
        )
        resultados_2 = bm.aplicar_bh_confirmacao(
            [r for r in (bm.confirmar_2stats(cond, dados_brasil) for cond in cond_2) if r]
        )

        bm.salvar_csv(os.path.join(config.DIR_RESULTADOS, f"{alvo_id}_confirmacao_brasil_1stat.csv"), resultados_1)
        bm.salvar_csv(os.path.join(config.DIR_RESULTADOS, f"{alvo_id}_confirmacao_brasil_2stats.csv"), resultados_2)

        conf_1 = sum(1 for r in resultados_1 if r["confirmado_bh"])
        conf_2 = sum(1 for r in resultados_2 if r["confirmado_bh"])
        print(f"    1 estatística: {conf_1}/{len(resultados_1)} confirmadas no Brasil (amostra suficiente)")
        print(f"    2 estatísticas: {conf_2}/{len(resultados_2)} confirmadas no Brasil (amostra suficiente)")
        resumo[alvo_id] = {
            "validadas_1": len(cond_1), "validadas_2": len(cond_2),
            "testadas_1": len(resultados_1), "testadas_2": len(resultados_2),
            "confirmadas_brasil_1": conf_1, "confirmadas_brasil_2": conf_2,
        }

        for r in resultados_1:
            regra = adotadas.get(chave_resultado_1stat(r))
            if regra:
                linhas_resumo_adotadas.append({
                    "regra_id": regra["id"], "alvo": alvo_id, "mercado_curto": regra["mercado_curto"],
                    "rotulo": regra["rotulo"],
                    "amostra_brasil": r["amostra_outras_ligas"],
                    "p_valor_brasil": r["p_valor_outras_ligas"],
                    "mesma_direcao_brasil": r["mesma_direcao"],
                    "confirmado_brasil": r["confirmado_bh"],
                })
        for r in resultados_2:
            regra = adotadas.get(chave_resultado_2stats(r))
            if regra:
                linhas_resumo_adotadas.append({
                    "regra_id": regra["id"], "alvo": alvo_id, "mercado_curto": regra["mercado_curto"],
                    "rotulo": regra["rotulo"],
                    "amostra_brasil": r["amostra_outras_ligas"],
                    "p_valor_brasil": r["p_valor_outras_ligas"],
                    "mesma_direcao_brasil": None,  # confirmar_2stats não calcula isso
                    "confirmado_brasil": r["confirmado_bh"],
                })

    bm.salvar_csv(CAMINHO_RESUMO_ADOTADAS, linhas_resumo_adotadas)

    linhas_saida = []
    linhas_saida.append(f"{'='*70}\nResumo geral\n{'='*70}")
    for alvo_id, r in resumo.items():
        linhas_saida.append(
            f"{alvos.ALVOS[alvo_id]['nome']:16s}: {r['testadas_1']:4d}+{r['testadas_2']:4d} testadas no Brasil "
            f"(amostra suficiente) -> {r['confirmadas_brasil_1']:3d}+{r['confirmadas_brasil_2']:3d} confirmadas"
        )
    linhas_saida.append("")
    linhas_saida.append(f"Das {len(adotadas)} regras hoje ativas no painel, {len(linhas_resumo_adotadas)} tiveram "
                         f"amostra suficiente no Brasil pra testar. Dessas:")
    confirmadas_adotadas = [l for l in linhas_resumo_adotadas if l["confirmado_brasil"]]
    linhas_saida.append(f"  {len(confirmadas_adotadas)} se confirmaram (mesma direção + significativas, BH) no Brasil")
    for l in confirmadas_adotadas:
        linhas_saida.append(f"    [{l['alvo']}] {l['rotulo']} (p={l['p_valor_brasil']:.4f}, n={l['amostra_brasil']})")
    texto = "\n".join(linhas_saida)
    print("\n" + texto)
    with open(CAMINHO_LOG_RESUMO, "w", encoding="utf-8") as fp:
        fp.write(texto + "\n")


if __name__ == "__main__":
    rodar()
