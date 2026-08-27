"""
Leitura e agregação de historico_sinais.csv (green/red/ROI por tipo de
aposta) — usado tanto pelo endpoint /api/historico-sinais do painel ao vivo
(app.py) quanto pelo gerador do Artifact de histórico
(gerar_painel_historico.py). Fica isolado num módulo próprio porque os dois
lados precisam do mesmo cálculo; sem isso, era fácil os dois divergirem com
o tempo (ex.: um corrigir um bug de ROI e o outro não).
"""
import csv
import os

CAMINHO_CSV_PADRAO = os.path.join(os.path.dirname(__file__), "historico_sinais.csv")

ALVO_NOME = {
    "escanteios": "Escanteios", "chutes_totais": "Chutes totais",
    "chutes_no_alvo": "Chutes no alvo", "gols": "Gols", "cartoes": "Cartões",
}
DIRECAO_NOME = {"mais_de": "Mais de", "menos_de": "Menos de"}


def carregar_linhas(caminho_csv=CAMINHO_CSV_PADRAO):
    """Lê o CSV e devolve só as linhas com resultado fechado (green/red), já com
    odd_usada/fonte_odd/lucro/tipo_aposta calculados, em ordem cronológica."""
    if not os.path.exists(caminho_csv):
        return []
    with open(caminho_csv, newline="", encoding="utf-8") as fp:
        linhas = list(csv.DictReader(fp))
    processadas = []
    for r in linhas:
        if r["resultado"] not in ("green", "red"):
            continue
        odd_real = float(r["odd_real"]) if r.get("odd_real") else None
        odd_minima = float(r["odd_minima"]) if r.get("odd_minima") else None
        odd_usada = odd_real if odd_real else odd_minima
        if odd_usada is None:
            continue
        lucro = (odd_usada - 1) if r["resultado"] == "green" else -1.0
        alvo_label = ALVO_NOME.get(r["alvo"], r["alvo"])
        direcao_label = DIRECAO_NOME.get(r["direcao"], r["direcao"])
        processadas.append({
            **r,
            "odd_usada": odd_usada,
            "fonte_odd": "real" if odd_real else "sintética",
            "lucro": lucro,
            "tipo_aposta": f"{alvo_label} · {direcao_label}",
        })
    processadas.sort(key=lambda r: r["timestamp_sinal"])
    return processadas


def agrupar_por_tipo(linhas):
    grupos = {}
    for r in linhas:
        grupos.setdefault(r["tipo_aposta"], []).append(r)
    resumo = []
    for tipo, itens in grupos.items():
        n = len(itens)
        greens = sum(1 for i in itens if i["resultado"] == "green")
        reds = n - greens
        roi_pct = sum(i["lucro"] for i in itens) / n * 100
        resumo.append({
            "tipo": tipo, "n": n, "greens": greens, "reds": reds,
            "taxa_pct": round(greens / n * 100, 1), "roi_pct": round(roi_pct, 1),
        })
    resumo.sort(key=lambda g: -g["n"])
    return resumo


def curva_roi_acumulado(linhas):
    acumulado = 0.0
    pontos = []
    for r in linhas:
        acumulado += r["lucro"]
        pontos.append(round(acumulado, 3))
    return pontos


def resumo_geral(linhas):
    n_total = len(linhas)
    greens = sum(1 for r in linhas if r["resultado"] == "green")
    reds = n_total - greens
    lucro_total = sum(r["lucro"] for r in linhas)
    roi_pct = (lucro_total / n_total * 100) if n_total else 0.0
    return {
        "n_total": n_total, "greens": greens, "reds": reds,
        "lucro_total_un": round(lucro_total, 3), "roi_pct": round(roi_pct, 1),
    }
