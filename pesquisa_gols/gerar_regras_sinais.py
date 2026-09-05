"""
Gera ligas_live_app/regras_sinais.json a partir dos CSVs de confirmação
(resultados/*_confirmacao_*stat.csv) — o mesmo dado usado nos resumos em
Excel/HTML, só que aqui em formato que o painel ao vivo consegue carregar e
avaliar contra estatísticas de jogo em tempo real.

Critério do subconjunto ("sinais fortes"): amostra >= 200 jogos nas ligas de
confirmação E impacto >= 5 p.p. — reduz risco de o painel virar alerta demais
enquanto o comportamento ao vivo ainda não foi observado. Dá pra afrouxar
depois editando AMOSTRA_MINIMA/IMPACTO_MINIMO abaixo e rodando de novo.

Uso: python3 gerar_regras_sinais.py
"""
import csv
import glob
import json
import os

BASE = os.path.join(os.path.dirname(__file__), "resultados")
DADOS_DIR = os.path.join(os.path.dirname(__file__), "dados")
DESTINO = os.path.join(os.path.dirname(__file__), "..", "ligas_live_app", "regras_sinais.json")

AMOSTRA_MINIMA_VALOR_ATUAL = 30  # abaixo disso, a proporção não é confiável — busca o valor_atual vizinho

AMOSTRA_MINIMA = 200
IMPACTO_MINIMO_PP = 5.0

ALVOS = ["escanteios", "chutes_totais", "chutes_no_alvo", "gols", "cartoes"]
ALVO_TITULO = {
    "escanteios": "Escanteios", "chutes_totais": "Chutes totais",
    "chutes_no_alvo": "Chutes no alvo", "gols": "Gols", "cartoes": "Cartões",
}
# stat_base do próprio alvo (o que o mercado "Mais de/Menos de" mede) —
# mesmo campo usado em alvos.ALVOS[alvo]["campos_base"], já resolvido pro
# nome que buscar_sportmonks/xg_pressure usam pra extrair da API.
ALVO_STAT_BASE = {
    "escanteios": "corners", "chutes_totais": "shots_total",
    "chutes_no_alvo": "shots_on_target", "gols": "goals", "cartoes": "cards",
}

# Mesmo dicionário de tradução usado nos resumos em Excel/HTML — mantém o
# rótulo do painel ao vivo legível em português em vez de stat_base cru.
TRAD = {
    "shots_total": "Chutes totais", "shots_on_target": "Chutes no alvo",
    "shots_insidebox": "Chutes de dentro da área", "shots_outsidebox": "Chutes de fora da área",
    "attacks": "Ataques", "dangerous_attacks": "Ataques perigosos",
    "total_crosses": "Cruzamentos", "accurate_crosses": "Cruzamentos certos",
    "key_passes": "Passes-chave", "corners": "Escanteios", "fouls": "Faltas",
    "tackles": "Desarmes", "duels_won": "Duelos vencidos", "offsides": "Impedimentos",
    "interceptions": "Interceptações", "successful_dribbles_percentage": "% dribles certos",
    "successful_dribbles": "Dribles certos", "saves": "Defesas", "goal_attempts": "Finalizações",
}


def nome(stat_base):
    return TRAD.get(stat_base, stat_base)


def ler_csv(caminho):
    try:
        with open(caminho, newline="", encoding="utf-8") as f:
            linhas = list(csv.DictReader(f))
    except FileNotFoundError:
        return []
    if not linhas or "confirmado_bh" not in linhas[0]:
        return []
    return [r for r in linhas if r["confirmado_bh"] == "True"]


def _carregar_dados_pooled():
    """fixture_id -> {minuto: snapshot}, fixture_id -> resultados_alvo — as 5 ligas juntas."""
    snaps_por_fixture = {}
    resultados = {}
    for caminho in glob.glob(f"{DADOS_DIR}/.checkpoint_*.json"):
        d = json.load(open(caminho, encoding="utf-8"))
        for fid_str, res in d["resultados_alvo"].items():
            resultados[int(fid_str)] = res
        for snap in d["snapshots"]:
            snaps_por_fixture.setdefault(snap["fixture_id"], {})[snap["minuto"]] = snap
    return snaps_por_fixture, resultados


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


def _tabela_com_fallback(casos_por_valor):
    """{valor_atual: [bateu, ...]} -> {valor_atual: {"n":.., "p":..}}, usando o valor vizinho com amostra
    suficiente quando o valor exato tem poucos jogos (mesmo padrão de fallback do resto do projeto)."""
    com_amostra = sorted(v for v, casos in casos_por_valor.items() if len(casos) >= AMOSTRA_MINIMA_VALOR_ATUAL)
    tabela = {}
    for valor, casos in casos_por_valor.items():
        if len(casos) >= AMOSTRA_MINIMA_VALOR_ATUAL:
            casos_uso = casos
        elif com_amostra:
            casos_uso = casos_por_valor[min(com_amostra, key=lambda v: abs(v - valor))]
        else:
            casos_uso = casos  # último recurso — nenhum valor com amostra boa pra esse alvo/regra
        # n = jogos observados EXATAMENTE nesse valor (transparência); n_usado = amostra
        # de fato usada pra estimar "p" (pode vir de um valor vizinho, se n for pequeno).
        tabela[valor] = {"n": len(casos), "n_usado": len(casos_uso), "p": sum(casos_uso) / len(casos_uso)}
    return tabela


def recalibrar_por_valor_atual(regras):
    """
    Recalcula p_condicao/p_base de cada regra CONDICIONADO ao valor atual
    exato da própria estatística-alvo (escanteios/chutes já ocorridos no
    momento do snapshot) — a versão original só condicionava em
    minuto+placar+condição, então duas partidas no mesmo minuto/placar com a
    mesma condição mas progressos bem diferentes do próprio alvo (1
    escanteio vs. 6 aos 45') recebiam a MESMA probabilidade. Caso real
    reportado: odd mínima de 1,33 mostrada quando a chance real (dado só 1
    escanteio até ali) era >95% — o jogo já tinha decidido o mercado sozinho.

    Usa as 5 ligas juntas (não só a Allsvenskan) — isso não é uma nova
    descoberta de condição (já feita e confirmada antes), é só uma
    reestimativa mais fina de uma condição já fixada, então usar mais dado
    aqui não tem o mesmo risco de vazamento que teria na descoberta original.

    Também recalcula a mesma coisa pras linhas VIZINHAS (±1, mesma direção) —
    caso real reportado: casa de apostas só tinha "mais de 10.5" disponível
    quando o sinal era calibrado pra "mais de 9.5"; sem isso, não dava pra
    saber a probabilidade real de bater a linha que realmente estava
    disponível pra apostar, só a da linha original. Guardado em
    "linhas_vizinhas" pra não mexer no formato já existente (linha original
    continua nas chaves de sempre, por compatibilidade).
    """
    snaps_por_fixture, resultados = _carregar_dados_pooled()

    for regra in regras:
        stat_alvo, linha, direcao = regra["mercado"]["stat"], regra["mercado"]["linha"], regra["mercado"]["direcao"]
        alvo = regra["alvo"]
        linhas_a_calcular = {0: linha, -1: linha - 1, 1: linha + 1}

        # offset -> valor_atual -> [bateu, ...]
        casos_condicao = {off: {} for off in linhas_a_calcular}
        casos_base = {off: {} for off in linhas_a_calcular}
        for fid, snaps in snaps_por_fixture.items():
            snap = snaps.get(regra["minuto"])
            if not snap or snap.get("gols_momento") != regra["gols_momento"]:
                continue
            res = resultados.get(fid)
            if not res or res.get(alvo) is None or snap.get(stat_alvo) is None:
                continue
            valor_atual = int(snap[stat_alvo])
            condicao_ok = _condicao_bate(regra["condicoes"], snap)
            for off, linha_off in linhas_a_calcular.items():
                bateu = (res[alvo] > linha_off) if direcao == "mais_de" else (res[alvo] < linha_off)
                casos_base[off].setdefault(valor_atual, []).append(bateu)
                if condicao_ok:
                    casos_condicao[off].setdefault(valor_atual, []).append(bateu)

        tabelas_condicao = {off: _tabela_com_fallback(casos_condicao[off]) for off in linhas_a_calcular}
        tabelas_base = {off: _tabela_com_fallback(casos_base[off]) for off in linhas_a_calcular}

        por_valor_atual = {}
        for valor, entrada in tabelas_condicao[0].items():
            p_condicao = entrada["p"]
            p_base = tabelas_base[0].get(valor, {"p": regra["prob_base_confirmacao"]})["p"]
            linhas_vizinhas = {}
            for off in (-1, 1):
                entrada_off = tabelas_condicao[off].get(valor)
                if entrada_off is None:
                    continue
                p_off = entrada_off["p"]
                p_base_off = tabelas_base[off].get(valor, {"p": p_base})["p"]
                linhas_vizinhas[str(off)] = {
                    "linha": linhas_a_calcular[off],
                    "n": entrada_off["n"],
                    "n_usado": entrada_off["n_usado"],
                    "p_condicao": round(p_off, 4),
                    "impacto_pp": round((p_off - p_base_off) * 100, 2),
                    "odd_minima": round(1 / p_off, 2) if p_off > 0 else None,
                }
            por_valor_atual[str(valor)] = {
                "n": entrada["n"],
                "n_usado": entrada["n_usado"],
                "p_condicao": round(p_condicao, 4),
                "p_base": round(p_base, 4),
                "impacto_pp": round((p_condicao - p_base) * 100, 2),
                "odd_minima": round(1 / p_condicao, 2) if p_condicao > 0 else None,
                "linhas_vizinhas": linhas_vizinhas,
            }
        regra["por_valor_atual"] = por_valor_atual

    return regras


brutas = []
for alvo_id in ALVOS:
    for r in ler_csv(f"{BASE}/{alvo_id}_confirmacao_1stat.csv"):
        brutas.append({
            "alvo_id": alvo_id,
            "minuto": int(r["minuto"]),
            "gols_momento": int(r["gols_momento"]),
            "condicao_chave": (r["stat"], r["operador"], r["limite"]),
            "condicoes": [{"stat": r["stat"], "operador": r["operador"], "limite": float(r["limite"])}],
            "linha_mercado": float(r["mercado"][1:]),
            "sinal_mercado": r["mercado"][0],
            "amostra": int(r["amostra_outras_ligas"]),
            "p_base": float(r["p_base_outras_ligas"]),
            "p_condicao": float(r["p_final_outras_ligas"]),
            "impacto": float(r["impacto_outras_ligas_pp"]),
            "p_valor": float(r["p_valor_outras_ligas"]),
        })
    for r in ler_csv(f"{BASE}/{alvo_id}_confirmacao_2stats.csv"):
        p_base = float(r["p_base_outras_ligas"])
        p_cond = float(r["p_conjunta_outras_ligas"])
        brutas.append({
            "alvo_id": alvo_id,
            "minuto": int(r["minuto"]),
            "gols_momento": int(r["gols_momento"]),
            "condicao_chave": (r["stat1"], r["operador1"], r["limite1"], r["stat2"], r["operador2"], r["limite2"]),
            "condicoes": [
                {"stat": r["stat1"], "operador": r["operador1"], "limite": float(r["limite1"])},
                {"stat": r["stat2"], "operador": r["operador2"], "limite": float(r["limite2"])},
            ],
            "linha_mercado": float(r["mercado"][1:]),
            "sinal_mercado": r["mercado"][0],
            "amostra": int(r["amostra_outras_ligas"]),
            "p_base": p_base,
            "p_condicao": p_cond,
            "impacto": (p_cond - p_base) * 100,
            "p_valor": float(r["p_valor_outras_ligas"]),
        })

# Colapsa cada par mais-de/menos-de da mesma linha, ficando só com o lado
# favorável — mesmo critério já usado no Excel "Sinais" (ver conversa: linha
# 28 vs 29 do achados_confirmados.xlsx eram o mesmo achado, sinais opostos).
grupos = {}
for item in brutas:
    chave = (item["alvo_id"], item["minuto"], item["gols_momento"], item["condicao_chave"], item["linha_mercado"])
    grupos.setdefault(chave, []).append(item)

sinais = [max(itens, key=lambda x: x["impacto"]) for itens in grupos.values()]


def _carregar_confirmadas_brasil():
    """
    (alvo_id, minuto, gols_momento, mercado '+/-N', frozenset de (stat,operador,limite))
    confirmadas contra Série A + Série B (pesquisa_gols/confirmar_brasil.py) — mesmo teste
    estatístico formal (duas proporções + Benjamini-Hochberg) usado na confirmação nórdica,
    só que rodado de novo contra o Brasil como dataset de confirmação. Exigir as duas
    (nórdicas E Brasil) garante que uma regra só entra no painel se já se provou fora de
    UMA amostra (nórdicas -> Allsvenskan) E de uma REGIÃO inteira diferente (Brasil), não só
    de mais jogos da mesma vizinhança de ligas.
    """
    chaves = set()
    for alvo_id in ALVOS:
        for r in ler_csv(f"{BASE}/{alvo_id}_confirmacao_brasil_1stat.csv"):
            condset = frozenset({(r["stat"], r["operador"], float(r["limite"]))})
            chaves.add((alvo_id, int(r["minuto"]), int(r["gols_momento"]), r["mercado"], condset))
        for r in ler_csv(f"{BASE}/{alvo_id}_confirmacao_brasil_2stats.csv"):
            condset = frozenset({
                (r["stat1"], r["operador1"], float(r["limite1"])),
                (r["stat2"], r["operador2"], float(r["limite2"])),
            })
            chaves.add((alvo_id, int(r["minuto"]), int(r["gols_momento"]), r["mercado"], condset))
    return chaves


def _chave_brasil(item):
    condset = frozenset((c["stat"], c["operador"], c["limite"]) for c in item["condicoes"])
    mercado = f"{item['sinal_mercado']}{item['linha_mercado']:g}"
    return (item["alvo_id"], item["minuto"], item["gols_momento"], mercado, condset)


CONFIRMADAS_BRASIL = _carregar_confirmadas_brasil()

fortes = [
    s for s in sinais
    if s["amostra"] >= AMOSTRA_MINIMA and s["impacto"] >= IMPACTO_MINIMO_PP
    and _chave_brasil(s) in CONFIRMADAS_BRASIL
]
fortes.sort(key=lambda x: (x["alvo_id"], -x["impacto"]))

print(f"sinais totais: {len(sinais)} | subconjunto forte (amostra>={AMOSTRA_MINIMA}, impacto>={IMPACTO_MINIMO_PP}pp): {len(fortes)}")
for alvo_id in ALVOS:
    n = sum(1 for s in fortes if s["alvo_id"] == alvo_id)
    if n:
        print(f"  {ALVO_TITULO[alvo_id]}: {n}")

campos_usados = set()
for s in fortes:
    for c in s["condicoes"]:
        campos_usados.add(c["stat"])
    campos_usados.add(ALVO_STAT_BASE[s["alvo_id"]])
print("campos crus necessários da API (condição + alvo):", sorted(campos_usados))

regras = []
contador = {}
for s in fortes:
    alvo_id = s["alvo_id"]
    contador[alvo_id] = contador.get(alvo_id, 0) + 1
    regra_id = f"{alvo_id}_{contador[alvo_id]:03d}"

    op_txt = {">=": "≥", "<=": "≤"}
    cond_txt = " E ".join(
        f"{nome(c['stat'])} {op_txt[c['operador']]} {c['limite']:g}" for c in s["condicoes"]
    )
    direcao = "mais_de" if s["sinal_mercado"] == "+" else "menos_de"
    stat_alvo = ALVO_STAT_BASE[alvo_id]
    mercado_curto = (
        f"{'Mais' if direcao == 'mais_de' else 'Menos'} de {s['linha_mercado']:g} {ALVO_TITULO[alvo_id].lower()}"
    )
    rotulo = f"{cond_txt} aos {s['minuto']}' ({s['gols_momento']} gol(s) no jogo) → {mercado_curto}"

    regras.append({
        "id": regra_id,
        "alvo": alvo_id,
        "alvo_nome": ALVO_TITULO[alvo_id],
        "minuto": s["minuto"],
        "gols_momento": s["gols_momento"],
        "condicoes": s["condicoes"],
        "mercado": {
            "stat": stat_alvo,
            "direcao": direcao,
            "linha": s["linha_mercado"],
        },
        "mercado_curto": mercado_curto,
        "amostra_confirmacao": s["amostra"],
        "prob_base_confirmacao": round(s["p_base"], 4),
        "prob_condicao_confirmacao": round(s["p_condicao"], 4),
        "impacto_pp": round(s["impacto"], 2),
        "p_valor_confirmacao": s["p_valor"],
        "odd_minima_referencia": round(1 / s["p_condicao"], 2) if s["p_condicao"] > 0 else None,
        "rotulo": rotulo,
    })

print("\nrecalibrando cada regra por valor atual do próprio alvo (escanteios/chutes já ocorridos)...")
regras = recalibrar_por_valor_atual(regras)
coberturas = [len(r["por_valor_atual"]) for r in regras]
amostras_min = [min(v["n_usado"] for v in r["por_valor_atual"].values()) for r in regras]
print(f"  cobertura: {sum(coberturas)/len(coberturas):.1f} valores distintos por regra em média "
      f"(min {min(coberturas)}, max {max(coberturas)})")
print(f"  amostra usada por valor: pior caso = {min(amostras_min)} jogos (após fallback pro vizinho)")

payload = {
    "criterio": f"amostra_confirmacao >= {AMOSTRA_MINIMA} e impacto_pp >= {IMPACTO_MINIMO_PP}, "
                "confirmado nas nórdicas E no Brasil (Série A + Série B)",
    "fonte": "pesquisa_gols/resultados/*_confirmacao_*.csv (confirmado_bh=True) + "
             "*_confirmacao_brasil_*.csv (confirmado_bh=True) + recalibração por valor atual "
             "do alvo sobre as 7 ligas (ver recalibrar_por_valor_atual em gerar_regras_sinais.py)",
    "total_regras": len(regras),
    "regras": regras,
}

os.makedirs(os.path.dirname(DESTINO), exist_ok=True)
with open(DESTINO, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
print(f"\nsalvo em {os.path.abspath(DESTINO)}")
