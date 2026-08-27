"""Checagem semanal de decaimento dos critérios campeões (Over 2.5 e
BTTS, Série A) e do 3º critério em stake reduzido (Cartões + Árbitro,
Série B) — roda os critérios já validados (`docs/protocolo.md`) contra
os dados disponíveis no momento, mede ROI/z tanto no acumulado quanto
numa janela recente (últimos 90 dias), e registra o resultado em
`docs/decaimento_semanal.md` pra dar pra acompanhar a tendência ao
longo de várias semanas.

Não busca dado novo sozinho — assume que os CSVs em `data/` já foram
atualizados manualmente (Lucas exporta do FootyStats e substitui/adiciona
os arquivos) e que `data/sportmonks_serieb_cartoes/fixtures.jsonl` já foi
atualizado rodando `sportmonks_pull_serieb_cartoes.py` (precisa de
`SPORTMONKS_TOKEN` no ambiente pra isso, mas NÃO pra esta checagem — ela
só lê o arquivo já salvo). Se esse arquivo não existir, o 3º critério é
pulado com um aviso — não quebra a checagem dos outros dois.

Uso: `python3 checar_decaimento.py`.
"""
from __future__ import annotations

import glob
import json
import math
import os
from datetime import date, datetime, timedelta

import pandas as pd

from cartoes_arbitro import (
    linha_mais_liquida,
    media_arbitro_walk_forward,
    odd_media_na_linha,
    prever_cartoes_combinado,
    simular_aposta_linha,
)
from retrospectiva import rodar_retrospectiva, simular_apostas

CAMINHO_LOG = "docs/decaimento_semanal.md"
CAMINHO_SPORTMONKS_CARTOES = "data/sportmonks_serieb_cartoes/fixtures.jsonl"
MARKET_NUMBER_OF_CARDS = 255

# Cartões + Árbitro (Série B) — parâmetros do 3º critério (stake reduzido,
# ver docs/protocolo.md): corte de outlier do BTTS + reescala pra cartões
# (ESCALA_CARTOES=1.9 × limite_unilateral=2), peso_arbitro=0.3, histórico
# mínimo de 10 jogos por árbitro antes de confiar na média dele.
PARAMS_CARTOES_TIME = dict(
    k_mando=0.7, usar_estilo=True, filtro_estilo=0.8, filtro_favoritismo=0.65,
    multiplicador_dp=1.5, limite_unilateral=2,
    limite_unilateral_por_campo={"cartoes_pro": 3.8, "cartoes_contra": 3.8},
)
N_HISTORICO_CARTOES = 10
MIN_JOGOS_ARBITRO = 10
PESO_ARBITRO = 0.3

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


def carregar_serieb():
    """Mesmo padrão de `carregar_seriea()`, pra Série B."""
    caminhos = sorted(glob.glob("data/footystats_serieb_*/matches.csv")) + [
        "data/footystats_serieb/matches.csv"
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


def _data_footystats(row):
    return datetime.strptime(row["date_GMT"].split(" - ")[0], "%b %d %Y").date()


def _carregar_sportmonks_cartoes(caminho):
    with open(caminho) as f:
        jogos = [json.loads(linha) for linha in f]
    for j in jogos:
        j["_data"] = datetime.strptime(j["date"][:10], "%Y-%m-%d").date()
        j["total_cartoes"] = j["cartoes_casa"] + j["cartoes_fora"]
    return sorted(jogos, key=lambda j: j["_data"])


def _indexar_sportmonks_por_nome_data(jogos_sm):
    idx = {}
    for j in jogos_sm:
        for delta in (0, -1, 1):
            idx[(j["home_team"], j["away_team"], j["_data"] + timedelta(days=delta))] = j
    return idx


def rodar_checagem_cartoes_arbitro():
    """3º critério (stake reduzido) — Cartões + Árbitro, Série B. Retorna
    `(resumo_item, linha_log)`, ou `(None, None)` quando o arquivo do
    Sportmonks ainda não foi gerado (não é erro, é dado externo opcional
    que só Lucas atualiza — ver `sportmonks_pull_serieb_cartoes.py`)."""
    if not os.path.exists(CAMINHO_SPORTMONKS_CARTOES):
        print(f"aviso: {CAMINHO_SPORTMONKS_CARTOES} não existe — pulando Cartões+Árbitro "
              f"(rode sportmonks_pull_serieb_cartoes.py pra gerar)", flush=True)
        return None, None

    jogos_sm = _carregar_sportmonks_cartoes(CAMINHO_SPORTMONKS_CARTOES)
    if not jogos_sm:
        print(f"aviso: {CAMINHO_SPORTMONKS_CARTOES} está vazio — pulando Cartões+Árbitro", flush=True)
        return None, None

    idx_sm = _indexar_sportmonks_por_nome_data(jogos_sm)
    medias_arbitro = media_arbitro_walk_forward(jogos_sm, min_jogos_arbitro=MIN_JOGOS_ARBITRO)
    media_arbitro_por_fixture = {j["fixture_id"]: m for j, m in zip(jogos_sm, medias_arbitro)}

    df = carregar_serieb()
    rel = rodar_retrospectiva(
        df, params=PARAMS_CARTOES_TIME, min_jogos_historico=8, min_jogos_estilo=5,
        n_historico=N_HISTORICO_CARTOES,
    )

    apostas = []
    for jogo in rel["jogos"]:
        m_pro = jogo["mercados"].get("cartoes_pro")
        m_contra = jogo["mercados"].get("cartoes_contra")
        if not m_pro or not m_contra:
            continue
        pred_time = m_pro["pred"] + m_contra["pred"]
        real_total = m_pro["real"] + m_contra["real"]

        home, away = jogo["jogo"].split(" x ")
        sm = idx_sm.get((home, away, jogo["data"]))
        if sm is None:
            continue
        media_arb = media_arbitro_por_fixture.get(sm["fixture_id"])
        pred_combinado = prever_cartoes_combinado(pred_time, media_arb, peso_arbitro=PESO_ARBITRO)
        if pred_combinado is None:
            continue

        linha = linha_mais_liquida(sm, MARKET_NUMBER_OF_CARDS)
        if linha is None:
            continue
        odd_over = odd_media_na_linha(sm, MARKET_NUMBER_OF_CARDS, linha, "Over")
        odd_under = odd_media_na_linha(sm, MARKET_NUMBER_OF_CARDS, linha, "Under")
        if odd_over is None or odd_under is None:
            continue

        aposta = simular_aposta_linha(pred_combinado, linha, odd_over, odd_under, real_total)
        if aposta is not None:
            aposta["data"] = jogo["data"]
            apostas.append(aposta)

    hoje = date.today()
    corte_recente = hoje - timedelta(days=JANELA_RECENTE_DIAS)
    s_total = stats(apostas)
    s_recente = stats([a for a in apostas if a["data"] >= corte_recente])
    resumo_item = dict(nome="Cartões+Árbitro (Série B, stake reduzido)", total=s_total, recente=s_recente)
    linha_log = f"| {hoje.isoformat()} | Cartões+Árbitro (Série B, stake reduzido) | {fmt(s_total)} | {fmt(s_recente)} |"
    return resumo_item, linha_log


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

    item_cartoes, linha_cartoes = rodar_checagem_cartoes_arbitro()
    if item_cartoes is not None:
        resumo.append(item_cartoes)
        linhas_log.append(linha_cartoes)

    print(f"Checagem de {hoje.isoformat()}:")
    for item in resumo:
        print(f"  {item['nome']}: acumulado 2023-2026 -> {fmt(item['total'])} | "
              f"últimos {JANELA_RECENTE_DIAS}d -> {fmt(item['recente'])}")
    atualizar_log(linhas_log, hoje)
    print(f"Log atualizado em {CAMINHO_LOG}")


if __name__ == "__main__":
    main()
