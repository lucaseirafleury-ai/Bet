"""Checagem semanal de decaimento dos critérios campeões (Over 2.5 e
BTTS, Série A) — roda os dois critérios já validados
(`docs/protocolo.md`) contra os dados disponíveis no momento, mede ROI/z
tanto no acumulado 2023-2026 quanto numa janela recente (últimos 90
dias), e registra o resultado em `docs/decaimento_semanal.md` pra dar
pra acompanhar a tendência ao longo de várias semanas.

Não busca dado novo sozinho — assume que os CSVs em `data/` já foram
atualizados manualmente (Lucas exporta do FootyStats e substitui/adiciona
os arquivos). Uso: `python3 checar_decaimento.py`.
"""
from __future__ import annotations

import glob
import math
from datetime import date, timedelta

import pandas as pd

from retrospectiva import rodar_retrospectiva, simular_apostas

CAMINHO_LOG = "docs/decaimento_semanal.md"

CRITERIOS = [
    dict(
        nome="Over 2.5",
        mercado="over25",
        limiar_edge=0.05,
        n_historico=15,
        params=dict(
            k_mando=0.5, usar_estilo=False, filtro_aderencia=0.8,
            multiplicador_dp=1.5, limite_unilateral=2,
        ),
    ),
    dict(
        nome="BTTS",
        mercado="btts",
        limiar_edge=0.05,
        n_historico=10,
        params=dict(
            k_mando=0.7, usar_estilo=True, filtro_estilo=0.8, filtro_favoritismo=0.65,
            multiplicador_dp=1.5, limite_unilateral=2,
        ),
    ),
]

JANELA_RECENTE_DIAS = 90


def carregar_seriea():
    """Carrega todos os `matches.csv` da Série A disponíveis em `data/`
    (temporadas fechadas `footystats_seriea_AAAA` + a temporada corrente
    `footystats_seriea`), sem precisar listar anos manualmente — assim
    novos arquivos que Lucas for adicionando entram automaticamente."""
    caminhos = sorted(glob.glob("data/footystats_seriea_*/matches.csv")) + [
        "data/footystats_seriea/matches.csv"
    ]
    dfs = []
    for caminho in caminhos:
        df = pd.read_csv(caminho)
        df["__src"] = caminho.split("/")[-2] + ".csv"
        dfs.append(df[df["status"] == "complete"])
    return pd.concat(dfs, ignore_index=True, sort=False)


def zscore(lucros):
    n = len(lucros)
    if n == 0:
        return None
    media = sum(lucros) / n
    var = sum((x - media) ** 2 for x in lucros) / (n - 1) if n > 1 else 0
    se = math.sqrt(var / n) if n > 1 else float("nan")
    return media / se if se else float("nan")


def stats(apostas):
    n = len(apostas)
    if n == 0:
        return dict(n=0, roi=None, z=None, acerto=None)
    lucro = sum(a["lucro"] for a in apostas)
    return dict(
        n=n, roi=(lucro / n), z=zscore([a["lucro"] for a in apostas]),
        acerto=sum(1 for a in apostas if a["venceu"]) / n,
    )


def fmt(s):
    if s["n"] == 0:
        return "sem apostas"
    return f"n={s['n']} ROI={s['roi']*100:+.1f}% z={s['z']:+.2f}"


def rodar_checagem():
    df = carregar_seriea()
    hoje = date.today()
    corte_recente = hoje - timedelta(days=JANELA_RECENTE_DIAS)

    linhas_log = []
    resumo = []
    for crit in CRITERIOS:
        rel = rodar_retrospectiva(
            df, params=crit["params"], min_jogos_historico=8, min_jogos_estilo=5,
            n_historico=crit["n_historico"],
        )
        r = simular_apostas(rel["jogos"], mercado=crit["mercado"], limiar_edge=crit["limiar_edge"])
        apostas_2023_26 = [a for a in r["apostas"] if a["data"] >= date(2023, 1, 1)]
        apostas_recentes = [a for a in r["apostas"] if a["data"] >= corte_recente]

        s_total = stats(apostas_2023_26)
        s_recente = stats(apostas_recentes)
        resumo.append(dict(nome=crit["nome"], total=s_total, recente=s_recente))
        linhas_log.append(
            f"| {hoje.isoformat()} | {crit['nome']} | {fmt(s_total)} | {fmt(s_recente)} |"
        )

    return resumo, linhas_log, hoje


def atualizar_log(linhas_log, hoje):
    try:
        with open(CAMINHO_LOG, "r") as f:
            conteudo = f.read()
    except FileNotFoundError:
        conteudo = (
            "# Decaimento semanal — Over 2.5 / BTTS (Série A)\n\n"
            "Checagem recorrente (rotina semanal) do ROI/z dos critérios "
            f"campeões (`docs/protocolo.md`), acumulado 2023-2026 vs. janela "
            f"móvel dos últimos {JANELA_RECENTE_DIAS} dias — a janela recente é "
            "o que importa pra pegar decaimento cedo, o acumulado se move "
            "devagar demais pra isso.\n\n"
            f"| Data da checagem | Critério | Acumulado 2023-2026 | Últimos {JANELA_RECENTE_DIAS} dias |\n"
            "|---|---|---|---|\n"
        )
    conteudo += "\n".join(linhas_log) + "\n"
    with open(CAMINHO_LOG, "w") as f:
        f.write(conteudo)


def main():
    resumo, linhas_log, hoje = rodar_checagem()
    print(f"Checagem de {hoje.isoformat()}:")
    for item in resumo:
        print(f"  {item['nome']}: acumulado 2023-2026 -> {fmt(item['total'])} | "
              f"últimos {JANELA_RECENTE_DIAS}d -> {fmt(item['recente'])}")
    atualizar_log(linhas_log, hoje)
    print(f"Log atualizado em {CAMINHO_LOG}")


if __name__ == "__main__":
    main()
