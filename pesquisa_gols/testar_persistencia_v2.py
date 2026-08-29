"""
Reavaliação de testar_persistencia.py — o primeiro teste só simulava a
persistência (2+ checkpoints) isolada, usando a condição BRUTA da regra.
Só que o painel ao vivo empilha DOIS filtros a mais antes de considerar um
candidato (ver live_monitor.py: IMPACTO_MINIMO_PP_VALOR_ATUAL,
PROBABILIDADE_MINIMA_VALOR_ATUAL, _stats_para_valor_atual) — impacto ≥5pp E
probabilidade ≥75%, ambos CONDICIONADOS ao valor atual exato do próprio alvo
(não só minuto+placar+condição). O teste anterior nunca simulou esses dois
filtros, por isso superestimou quantos jogos teriam sinal.

Reproduz aqui os MESMOS 4 filtros da produção (exceto o de EV/odd real, que
não dá pra testar retroativamente — Sportmonks não guarda histórico de odd
ao vivo, já confirmado numa conversa anterior):
  1. condição bate (regra["condicoes"])
  2. impacto_pp >= 5.0 (via por_valor_atual)
  3. p_condicao >= 0.75 (via por_valor_atual)
  4. persistência: mesmo (alvo, direção) bate em 2+ checkpoints diferentes

Uso: python testar_persistencia_v2.py
"""
import glob
import json
import os

BASE = os.path.dirname(__file__)
DADOS_DIR = os.path.join(BASE, "dados")
CAMINHO_REGRAS = os.path.join(BASE, "..", "ligas_live_app", "regras_sinais.json")

IMPACTO_MINIMO_PP = 5.0
PROBABILIDADE_MINIMA = 0.75


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


def _stats_para_valor_atual(regra, snap):
    tabela = regra.get("por_valor_atual")
    if not tabela:
        return None
    valor_atual = int(round(snap.get(regra["mercado"]["stat"], 0.0)))
    entrada = tabela.get(str(valor_atual))
    if entrada is None:
        disponiveis = [int(v) for v in tabela.keys()]
        if not disponiveis:
            return None
        mais_proximo = min(disponiveis, key=lambda v: abs(v - valor_atual))
        entrada = tabela[str(mais_proximo)]
    return entrada


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
    print(f"{len(regras)} regras (as mesmas do painel hoje), {len(snaps_por_fixture)} jogos com snapshots\n")

    # fixture -> (alvo, direcao) -> {minuto: linha}, só candidatos que passam nos 3 filtros
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
            stats = _stats_para_valor_atual(regra, snap)
            if stats is None:
                continue
            if stats["impacto_pp"] < IMPACTO_MINIMO_PP:
                continue
            if stats["p_condicao"] < PROBABILIDADE_MINIMA:
                continue
            disparos.setdefault(fid, {}).setdefault((alvo, direcao), {})[minuto] = linha

    total_jogos = len(snaps_por_fixture)
    jogos_com_candidato = 0
    jogos_com_persistido = 0
    total_candidatos_jogo_mercado = 0
    total_persistidos_jogo_mercado = 0

    for fid, por_mercado in disparos.items():
        res = resultados.get(fid)
        if not res:
            continue
        tem_candidato = False
        tem_persistido = False
        for (alvo, direcao), checkpoints in por_mercado.items():
            if res.get(alvo) is None:
                continue
            tem_candidato = True
            total_candidatos_jogo_mercado += 1
            if len(checkpoints) > 1:
                tem_persistido = True
                total_persistidos_jogo_mercado += 1
        if tem_candidato:
            jogos_com_candidato += 1
        if tem_persistido:
            jogos_com_persistido += 1

    print("=" * 70)
    print("Com os 3 filtros de produção simulados (condição + impacto≥5pp + prob≥75%,")
    print("todos condicionados ao valor atual do próprio alvo):")
    print("=" * 70)
    print(f"  jogos com pelo menos 1 candidato (ANTES de exigir persistência): "
          f"{jogos_com_candidato}/{total_jogos} ({jogos_com_candidato/total_jogos*100:.1f}%)")
    print(f"  jogos com pelo menos 1 candidato PERSISTIDO (2+ checkpoints, o que o painel exige hoje): "
          f"{jogos_com_persistido}/{total_jogos} ({jogos_com_persistido/total_jogos*100:.1f}%)")
    print()
    print(f"  candidatos jogo+mercado (antes de persistência): {total_candidatos_jogo_mercado}")
    print(f"  desses, persistidos (2+ checkpoints):             {total_persistidos_jogo_mercado} "
          f"({total_persistidos_jogo_mercado/total_candidatos_jogo_mercado*100:.1f}%)" if total_candidatos_jogo_mercado else "")
    print()
    print("(Não simulado aqui: o filtro de EV contra odd real — Sportmonks não guarda histórico de odd")
    print(" ao vivo pra testar retroativamente, então o número acima é o TETO, o real pode ser menor.)")


if __name__ == "__main__":
    rodar()
