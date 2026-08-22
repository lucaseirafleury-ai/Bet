"""
Valida (e tenta recalibrar) o modelo de Over/Under 2.5 usado no painel ao vivo
(MODELOS_CALIBRADOS_POR_LIGA, em ligas_live_app/live_poisson.py) usando os
~3.000 jogos já cacheados em pesquisa_gols/dados/.checkpoint_*.json — sem
nenhuma chamada nova à API.

Por que isso e não o re-fetch por time: o usuário indicou que o que importa
de verdade é o Over/Under do JOGO (total combinado), não sinais por time
(vitória casa/fora, BTTS) — e o modelo de O/U já usa exatamente esse tipo de
estatística (casa+fora somado), que é o que os snapshots do pesquisa_gols já
têm. Não precisa buscar nada nôvo pra validar isso.

Metodologia (mesma disciplina do resto do projeto):
- Split cronológico 70/30 por liga (config.FRACAO_TREINO), nunca embaralhado.
- "Somente minuto" (intercepto por checkpoint, sem métrica) é o baseline —
  o intercepto é reajustado com o TREINO desta base (mais dado que os 569
  jogos usados originalmente).
- Pra cada métrica candidata, um coeficiente é ajustado por busca em grade
  1D maximizando log-verossimilhança de Poisson no TREINO (aproximação de
  duas etapas: intercepto vem do ajuste "somente minuto", coeficiente é
  buscado com o intercepto fixo — não é um GLM conjunto de verdade, mas dá
  pra comparar métricas e decidir se algum ritmo ajuda MESMO usando só
  matemática pura, sem numpy/scipy, que não estão disponíveis aqui).
- Avaliação final é sempre no TESTE (30% mais recente), nunca no treino.
- Métrica de avaliação: log-loss de Over 2.5, comparando "somente minuto"
  (coeficiente 0) vs "com métrica" (melhor coeficiente encontrado).

Limitação conhecida: shots_off_target (métrica original da 1. Lyga) não foi
buscada nesta base — 1. Lyga entra só como "somente minuto" + as métricas
alternativas disponíveis, não com sua métrica original.
"""
import json
import math
from glob import glob

CHECKPOINTS = [15, 30, 45, 60, 75]
FRACAO_TREINO = 0.7
GRADE_GOLS = 10

LIGAS = {573: "Allsvenskan", 579: "Superettan", 405: "A Lyga", 408: "1. Lyga", 447: "1. Division"}
METRICA_ORIGINAL = {573: "shots_total", 579: None, 405: None, 408: "shots_off_target (indisponível)", 447: "attacks"}

METRICAS_CANDIDATAS = [
    "shots_total", "shots_on_target", "shots_insidebox", "shots_outsidebox", "shots_blocked",
    "attacks", "dangerous_attacks", "key_passes", "total_crosses", "accurate_crosses",
    "corners", "fouls", "tackles", "duels_won", "goal_attempts", "interceptions",
    "offsides", "saves", "successful_dribbles",
]


def poisson_pmf(k, lam):
    if lam <= 0:
        lam = 0.05
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def carregar_liga(league_id):
    caminho = f"dados/.checkpoint_{league_id}.json"
    d = json.load(open(caminho, encoding="utf-8"))
    jogos, resultados_alvo, snapshots = d["jogos"], d["resultados_alvo"], d["snapshots"]

    por_fixture = {}
    for snap in snapshots:
        if snap["minuto"] not in CHECKPOINTS:
            continue
        fid = snap["fixture_id"]
        if str(fid) not in resultados_alvo and fid not in resultados_alvo:
            continue
        gols_final = resultados_alvo.get(str(fid), resultados_alvo.get(fid, {})).get("gols")
        if gols_final is None:
            continue
        info_jogo = jogos.get(str(fid), jogos.get(fid))
        if not info_jogo or not info_jogo.get("data_hora"):
            continue
        por_fixture.setdefault(fid, {"data_hora": info_jogo["data_hora"], "gols_final": gols_final, "checkpoints": {}})
        por_fixture[fid]["checkpoints"][snap["minuto"]] = snap

    return por_fixture


def split_treino_teste(por_fixture):
    fids_ordenados = sorted(por_fixture.keys(), key=lambda f: por_fixture[f]["data_hora"])
    corte = int(len(fids_ordenados) * FRACAO_TREINO)
    return fids_ordenados[:corte], fids_ordenados[corte:]


def montar_linhas(por_fixture, fids, metrica):
    """Uma linha por (jogo, checkpoint): minuto, ritmo_15min (ou None), gols_momento, gols_restantes_reais."""
    linhas = []
    for fid in fids:
        info = por_fixture[fid]
        for minuto in CHECKPOINTS:
            snap = info["checkpoints"].get(minuto)
            if snap is None:
                continue
            gols_momento = snap["gols_momento"]
            gols_restantes = info["gols_final"] - gols_momento
            if gols_restantes < 0:
                continue  # inconsistência de dado — pula
            ritmo15 = None
            if metrica is not None and metrica in snap:
                ritmo15 = (snap[metrica] / minuto) * 15
            linhas.append({
                "fixture_id": fid, "minuto": minuto, "gols_momento": gols_momento,
                "gols_restantes": gols_restantes, "gols_final": info["gols_final"], "ritmo15": ritmo15,
            })
    return linhas


def ajustar_interceptos(linhas_treino):
    """MLE de Poisson só-intercepto por checkpoint: log(média dos gols restantes observados no treino)."""
    soma = {m: 0.0 for m in CHECKPOINTS}
    conta = {m: 0 for m in CHECKPOINTS}
    for l in linhas_treino:
        soma[l["minuto"]] += l["gols_restantes"]
        conta[l["minuto"]] += 1
    interceptos = {}
    for m in CHECKPOINTS:
        media = soma[m] / conta[m] if conta[m] else 0.3
        interceptos[m] = math.log(max(media, 0.05))
    return interceptos


def log_verossimilhanca_poisson(linhas, interceptos, coef):
    """Soma da log-verossimilhança de Poisson (a menos de uma constante) — maior é melhor."""
    total = 0.0
    for l in linhas:
        ritmo = l["ritmo15"] if l["ritmo15"] is not None else 0.0
        lam = math.exp(interceptos[l["minuto"]] + coef * ritmo)
        lam = max(lam, 1e-6)
        total += l["gols_restantes"] * math.log(lam) - lam
    return total


def buscar_melhor_coef(linhas_treino, interceptos):
    """Busca em grade 1D — a log-verossimilhança de Poisson é côncava em torno do ótimo pra essa faixa."""
    melhor_coef, melhor_ll = 0.0, log_verossimilhanca_poisson(linhas_treino, interceptos, 0.0)
    for coef_milesimos in range(-300, 501, 2):  # -0.300 a +0.500, passo 0.002
        coef = coef_milesimos / 1000
        ll = log_verossimilhanca_poisson(linhas_treino, interceptos, coef)
        if ll > melhor_ll:
            melhor_ll, melhor_coef = ll, coef
    return melhor_coef


def prob_over25(gols_momento, lam, linha=2.5):
    p_over = 0.0
    for n in range(GRADE_GOLS + 1):
        if gols_momento + n > linha:
            p_over += poisson_pmf(n, lam)
    return min(max(p_over, 1e-6), 1 - 1e-6)


def loglosses_individuais(linhas_teste, interceptos, coef):
    valores = []
    for l in linhas_teste:
        ritmo = l["ritmo15"] if l["ritmo15"] is not None else 0.0
        lam = math.exp(interceptos[l["minuto"]] + coef * ritmo)
        p = prob_over25(l["gols_momento"], lam)
        y = 1 if l["gols_final"] > 2.5 else 0
        valores.append(-(y * math.log(p) + (1 - y) * math.log(1 - p)))
    return valores


def log_loss_over25(linhas_teste, interceptos, coef):
    valores = loglosses_individuais(linhas_teste, interceptos, coef)
    n = len(valores)
    return (sum(valores) / n if n else None), n


def teste_pareado(deltas):
    """t pareado simples (aprox. normal) sobre logloss_base - logloss_metrica por linha — positivo = métrica ajudou."""
    n = len(deltas)
    media = sum(deltas) / n
    var = sum((d - media) ** 2 for d in deltas) / (n - 1)
    ep = math.sqrt(var / n)
    z = media / ep if ep > 0 else 0.0
    return media, z


def rodar():
    print(f"{'Liga':<12} {'jogos':>6} {'melhor métrica':<20} {'logloss só-min':>15} {'logloss c/métrica':>18} "
          f"{'coef':>6} {'Δ por jogo (p.p. de logloss)':>30} {'z (pareado, por jogo)':>22}")
    for league_id, nome in LIGAS.items():
        por_fixture = carregar_liga(league_id)
        n_jogos = len(por_fixture)
        fids_treino, fids_teste = split_treino_teste(por_fixture)

        linhas_treino_base = montar_linhas(por_fixture, fids_treino, None)
        interceptos = ajustar_interceptos(linhas_treino_base)
        linhas_teste_base = montar_linhas(por_fixture, fids_teste, None)
        ll_base_linhas = loglosses_individuais(linhas_teste_base, interceptos, 0.0)
        logloss_base = sum(ll_base_linhas) / len(ll_base_linhas)

        melhor = {"metrica": None, "logloss": logloss_base, "coef": 0.0, "ll_linhas": ll_base_linhas, "linhas": linhas_teste_base}
        for metrica in METRICAS_CANDIDATAS:
            linhas_treino = montar_linhas(por_fixture, fids_treino, metrica)
            if not any(l["ritmo15"] is not None for l in linhas_treino):
                continue
            coef = buscar_melhor_coef(linhas_treino, interceptos)
            linhas_teste = montar_linhas(por_fixture, fids_teste, metrica)
            ll_linhas = loglosses_individuais(linhas_teste, interceptos, coef)
            logloss_m = sum(ll_linhas) / len(ll_linhas)
            if logloss_m < melhor["logloss"]:
                melhor = {"metrica": metrica, "logloss": logloss_m, "coef": coef, "ll_linhas": ll_linhas, "linhas": linhas_teste}

        # Teste pareado por JOGO (não por linha/checkpoint) — média do delta de logloss
        # das linhas de cada jogo, um ponto por jogo, pra não inflar a amostra como
        # aconteceu no backtest.py (5 checkpoints do mesmo jogo não são 5 jogos).
        deltas_por_jogo = {}
        for l, ll_b, ll_m in zip(melhor["linhas"], ll_base_linhas, melhor["ll_linhas"]):
            deltas_por_jogo.setdefault(l["fixture_id"], []).append(ll_b - ll_m)
        deltas_medios = [sum(ds) / len(ds) for ds in deltas_por_jogo.values()]
        media_delta, z = teste_pareado(deltas_medios)

        nome_metrica = melhor["metrica"] or "somente minuto"
        print(f"{nome:<12} {n_jogos:>6} {nome_metrica:<20} {logloss_base:>15.4f} {melhor['logloss']:>18.4f} "
              f"{melhor['coef']:>6.3f} {media_delta*100:>29.2f} {z:>22.2f}")

    print("\nΔ por jogo = quanto o logloss caiu (positivo = melhorou), média por jogo (n = jogos de teste, ~30% mais "
          "recentes de cada liga). z > ~1,96 (ou < -1,96) seria \"estatisticamente distinguível de ruído\" nesse nível.")


if __name__ == "__main__":
    rodar()
