"""Livro-caixa das sugestões do painel diário — registra cada sugestão
feita (`previsao_dia.gerar_sugestoes_do_dia`), resolve Green/Red quando
o jogo termina (usando o histórico do Sportmonks já atualizado, que já
tem o placar real) e calcula o resumo (nº de entradas, green, red, ROI)
mostrado na lateral do painel.

Stake fixo por critério — decisão de gestão de banca do Lucas, não é a
mesma coisa que "stake normal/reduzido" (que reflete confiança
estatística): BTTS sempre 1 unidade, os outros sempre 0,5.
"""
from __future__ import annotations

import json
import os

STAKE_POR_CRITERIO = {"BTTS": 1.0, "Over 2.5": 0.5, "Cartões+Árbitro": 0.5}


def carregar_ledger(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def salvar_ledger(path, ledger):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(ledger, f, indent=2, ensure_ascii=False, default=str)


def _chave(entrada):
    return (entrada["fixture_id"], entrada["criterio"])


def registrar_novas_sugestoes(ledger, sugestoes, data_registro):
    """Acrescenta ao `ledger` as sugestões que ainda não estavam
    registradas (mesma `fixture_id`+`criterio` já registrado, pendente
    ou resolvido, não entra de novo — evita duplicar enquanto o jogo
    ainda não foi jogado e a rotina roda de novo todo dia). Sugestões
    sem `fixture_id` são ignoradas (não dá pra resolver depois)."""
    chaves_existentes = {_chave(e) for e in ledger}
    for s in sugestoes:
        if s.get("fixture_id") is None:
            continue
        chave = _chave(s)
        if chave in chaves_existentes:
            continue
        ledger.append(dict(
            fixture_id=s["fixture_id"], criterio=s["criterio"], stake=s["stake"], liga=s["liga"], liga_chave=s["liga_chave"],
            jogo=s["jogo"], data_jogo=s["data"], lado=s["lado"], linha_aposta=s.get("linha_aposta"),
            odd=s["odd"], edge=s["edge"], data_registro=data_registro, casa_ref=s.get("casa_ref"),
            resultado="pendente", lucro=None,
        ))
        chaves_existentes.add(chave)
    return ledger


def _resolver_um(entrada, row):
    total_gols = row["home_team_goal_count"] + row["away_team_goal_count"]
    if entrada["criterio"] == "BTTS":
        venceu = row["home_team_goal_count"] > 0 and row["away_team_goal_count"] > 0
    elif entrada["criterio"] == "Over 2.5":
        venceu = total_gols > 2.5
    elif entrada["criterio"] == "Cartões+Árbitro":
        total_cartoes = (
            row["home_team_yellow_cards"] + row["home_team_red_cards"]
            + row["away_team_yellow_cards"] + row["away_team_red_cards"]
        )
        lado_over = entrada["lado"].startswith("Over")
        venceu = (total_cartoes > entrada["linha_aposta"]) if lado_over else (total_cartoes <= entrada["linha_aposta"])
    else:
        raise ValueError(f"critério desconhecido pra resolução: {entrada['criterio']!r}")
    stake = STAKE_POR_CRITERIO[entrada["criterio"]]
    lucro = stake * (entrada["odd"] - 1) if venceu else -stake
    return ("green" if venceu else "red"), lucro


def resolver_pendentes(ledger, dfs_por_liga):
    """Pra cada entrada ainda `pendente`, procura o `fixture_id` no
    DataFrame de histórico da liga correspondente (já teria o placar
    real se o jogo já tivesse acabado E o pull mais recente já tivesse
    rodado). Jogo não encontrado = ainda não jogado (ou pull ainda não
    pegou) — fica pendente, tentamos de novo no próximo dia."""
    for entrada in ledger:
        if entrada["resultado"] != "pendente":
            continue
        df = dfs_por_liga.get(entrada["liga_chave"])
        if df is None:
            continue
        linhas = df[df["_fixture_id"] == entrada["fixture_id"]]
        if linhas.empty:
            continue
        resultado, lucro = _resolver_um(entrada, linhas.iloc[0])
        entrada["resultado"] = resultado
        entrada["lucro"] = lucro
    return ledger


def calcular_resumo(ledger):
    """Resumo agregado + por critério, só das entradas JÁ RESOLVIDAS
    (pendentes não entram no ROI - ainda não têm resultado)."""
    resolvidos = [e for e in ledger if e["resultado"] != "pendente"]
    por_criterio = {}
    for e in resolvidos:
        c = por_criterio.setdefault(e["criterio"], dict(n=0, n_green=0, lucro=0.0, stake=0.0))
        c["n"] += 1
        c["n_green"] += 1 if e["resultado"] == "green" else 0
        c["lucro"] += e["lucro"]
        c["stake"] += STAKE_POR_CRITERIO[e["criterio"]]
    for c in por_criterio.values():
        c["n_red"] = c["n"] - c["n_green"]
        c["roi"] = (c["lucro"] / c["stake"]) if c["stake"] else None

    n = len(resolvidos)
    n_green = sum(c["n_green"] for c in por_criterio.values())
    lucro_total = sum(c["lucro"] for c in por_criterio.values())
    stake_total = sum(c["stake"] for c in por_criterio.values())
    return dict(
        n=n, n_green=n_green, n_red=n - n_green,
        lucro_total=lucro_total, roi=(lucro_total / stake_total) if stake_total else None,
        por_criterio=por_criterio,
    )
