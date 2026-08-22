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
import json
import os

BASE = os.path.join(os.path.dirname(__file__), "resultados")
DESTINO = os.path.join(os.path.dirname(__file__), "..", "ligas_live_app", "regras_sinais.json")

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

fortes = [s for s in sinais if s["amostra"] >= AMOSTRA_MINIMA and s["impacto"] >= IMPACTO_MINIMO_PP]
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
    rotulo = (
        f"{cond_txt} aos {s['minuto']}' ({s['gols_momento']} gol(s) no jogo) "
        f"→ {'Mais' if direcao == 'mais_de' else 'Menos'} de {s['linha_mercado']:g} {ALVO_TITULO[alvo_id].lower()}"
    )

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
        "amostra_confirmacao": s["amostra"],
        "prob_base_confirmacao": round(s["p_base"], 4),
        "prob_condicao_confirmacao": round(s["p_condicao"], 4),
        "impacto_pp": round(s["impacto"], 2),
        "p_valor_confirmacao": s["p_valor"],
        "odd_minima_referencia": round(1 / s["p_condicao"], 2) if s["p_condicao"] > 0 else None,
        "rotulo": rotulo,
    })

payload = {
    "criterio": f"amostra_confirmacao >= {AMOSTRA_MINIMA} e impacto_pp >= {IMPACTO_MINIMO_PP}",
    "fonte": "pesquisa_gols/resultados/*_confirmacao_*.csv (confirmado_bh=True)",
    "total_regras": len(regras),
    "regras": regras,
}

os.makedirs(os.path.dirname(DESTINO), exist_ok=True)
with open(DESTINO, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
print(f"\nsalvo em {os.path.abspath(DESTINO)}")
