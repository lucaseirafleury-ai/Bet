"""
Cross-check independente das 78 regras já publicadas em
ligas_live_app/regras_sinais.json — recalcula amostra/p_base/p_condição/
impacto_pp direto dos checkpoints crus (dados/.checkpoint_<liga>.json), com
código novo e escrito do zero (não reaproveita buscar_condicoes.py,
buscar_multiliga.py, probabilidades.py nem estatistica.py), e valida a
significância com um teste ESTATISTICAMENTE DIFERENTE do usado na geração
original: Fisher exato (hipergeométrico, exato) em vez do teste z de duas
proporções (aproximação normal) — dois métodos com premissas matemáticas
distintas que deveriam concordar se a implementação original estiver certa.

Não é uma nova descoberta nem uma recalibração — é uma auditoria: roda em
cima dos MESMOS dados já usados pra gerar as regras, só que com um caminho
de código totalmente separado, pra pegar bugs que a implementação original
e a nova teriam que cometer AMBAS pra passar despercebidos (muito menos
provável que um bug idêntico apareça em duas implementações independentes).

Uso: python3 revalidar_regras_cruzado.py
"""
import glob
import json
import math
import os

DADOS_DIR = os.path.join(os.path.dirname(__file__), "dados")
REGRAS_PATH = os.path.join(os.path.dirname(__file__), "..", "ligas_live_app", "regras_sinais.json")

LIGAS_BRASIL = {648, 651}
LIGAS_CONFIRMACAO_UNIVERSAL = {579, 447, 648, 651}  # todas MENOS a de descoberta (573, Allsvenskan)

TOLERANCIA_AMOSTRA_PCT = 0.05   # 5% de diferença na amostra já é suspeito (deveria ser exigimente igual)
TOLERANCIA_IMPACTO_PP = 1.5     # p.p. de diferença tolerada no impacto antes de marcar como divergência


def _carregar_checkpoints():
    """league_id -> {"resultados": {fid: res}, "snaps": {fid: {minuto: snap}}}"""
    por_liga = {}
    for caminho in glob.glob(f"{DADOS_DIR}/.checkpoint_*.json"):
        league_id = int(os.path.basename(caminho).removeprefix(".checkpoint_").removesuffix(".json"))
        d = json.load(open(caminho, encoding="utf-8"))
        resultados = {int(fid): res for fid, res in d["resultados_alvo"].items()}
        snaps = {}
        for snap in d["snapshots"]:
            snaps.setdefault(snap["fixture_id"], {})[snap["minuto"]] = snap
        por_liga[league_id] = {"resultados": resultados, "snaps": snaps}
    return por_liga


def _condicao_bate(condicoes, snap):
    """Dado ausente -> condição não bate (mesmo critério conservador de gerar_regras_sinais.py)."""
    for c in condicoes:
        v = snap.get(c["stat"])
        if v is None:
            return False
        if c["operador"] == ">=" and v < c["limite"]:
            return False
        if c["operador"] == "<=" and v > c["limite"]:
            return False
    return True


def _log_comb(n, k):
    """log(C(n,k)) via lgamma — estável pra n grande, evita overflow de inteiros gigantes."""
    if k < 0 or k > n:
        return float("-inf")
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def fisher_exato_bicaudal(a, b, c, d):
    """
    Teste exato de Fisher pra tabela 2x2:
                bateu   nao_bateu
    condicao      a         b
    complemento   c         d

    Soma a probabilidade hipergeométrica de toda tabela com as MESMAS margens
    que seja tão ou menos provável que a observada — método exato (sem
    aproximação normal), diferente em espécie do teste z de duas proporções
    usado na geração original (estatistica.py::teste_duas_proporcoes).
    """
    n1, n2 = a + b, c + d
    total_bateu = a + c
    total = n1 + n2
    if n1 == 0 or n2 == 0 or total_bateu == 0 or total_bateu == total:
        return None

    log_denominador = _log_comb(total, total_bateu)

    def log_p(a_):
        c_ = total_bateu - a_
        if c_ < 0 or c_ > n2 or a_ > n1:
            return float("-inf")
        return _log_comb(n1, a_) + _log_comb(n2, c_) - log_denominador

    log_p_obs = log_p(a)
    a_min = max(0, total_bateu - n2)
    a_max = min(n1, total_bateu)

    # Log-sum-exp padrão sobre toda tabela tão ou menos provável que a
    # observada — evita subtrair/exponenciar probabilidades minúsculas direto
    # (log_p chega a milhares de unidades negativas pra amostras grandes).
    logs_relevantes = [log_p(a_) for a_ in range(a_min, a_max + 1) if log_p(a_) <= log_p_obs + 1e-9]
    if not logs_relevantes:
        return None
    maior = max(logs_relevantes)
    log_soma = maior + math.log(sum(math.exp(lp - maior) for lp in logs_relevantes))
    return min(1.0, math.exp(log_soma))


def _recalcular_regra(regra, por_liga):
    ligas = LIGAS_BRASIL if regra.get("regiao") == "brasil" else LIGAS_CONFIRMACAO_UNIVERSAL
    alvo = regra["alvo"]
    minuto, gols_momento = regra["minuto"], regra["gols_momento"]
    direcao, linha = regra["mercado"]["direcao"], regra["mercado"]["linha"]

    bucket = []  # (bateu: bool, condicao_ok: bool)
    for lid in ligas:
        liga = por_liga.get(lid)
        if not liga:
            continue
        for fid, snaps in liga["snaps"].items():
            snap = snaps.get(minuto)
            if not snap or snap.get("gols_momento") != gols_momento:
                continue
            res = liga["resultados"].get(fid)
            if not res or res.get(alvo) is None:
                continue
            valor_final = res[alvo]
            bateu = (valor_final > linha) if direcao == "mais_de" else (valor_final < linha)
            condicao_ok = _condicao_bate(regra["condicoes"], snap)
            bucket.append((bateu, condicao_ok))

    n_base = len(bucket)
    if n_base == 0:
        return None

    grupo_condicao = [b for b, ok in bucket if ok]
    grupo_complemento = [b for b, ok in bucket if not ok]
    n_cond, n_comp = len(grupo_condicao), len(grupo_complemento)
    if n_cond == 0 or n_comp == 0:
        return None

    p_base = sum(b for b, _ in bucket) / n_base
    p_condicao = sum(grupo_condicao) / n_cond
    p_complemento = sum(grupo_complemento) / n_comp
    impacto_pp = (p_condicao - p_base) * 100

    a = sum(grupo_condicao)               # condição, bateu
    b_ = n_cond - a                        # condição, não bateu
    c = sum(grupo_complemento)             # complemento, bateu
    d = n_comp - c                         # complemento, não bateu
    p_valor_fisher = fisher_exato_bicaudal(a, b_, c, d)

    return {
        "amostra": n_cond, "p_base": p_base, "p_condicao": p_condicao,
        "impacto_pp": impacto_pp, "p_valor_fisher": p_valor_fisher,
    }


def rodar():
    por_liga = _carregar_checkpoints()
    regras = json.load(open(REGRAS_PATH, encoding="utf-8"))["regras"]

    divergencias = []
    ok = 0
    sem_dado = 0

    for regra in regras:
        recalc = _recalcular_regra(regra, por_liga)
        if recalc is None:
            sem_dado += 1
            print(f"[sem dado suficiente pra recalcular] {regra['id']}")
            continue

        amostra_original = regra["amostra_confirmacao"]
        impacto_original = regra["impacto_pp"]
        p_valor_original = regra["p_valor_confirmacao"]

        diff_amostra_pct = abs(recalc["amostra"] - amostra_original) / amostra_original
        diff_impacto = abs(recalc["impacto_pp"] - impacto_original)
        significativo_original = p_valor_original < 0.05
        significativo_fisher = (recalc["p_valor_fisher"] is not None) and (recalc["p_valor_fisher"] < 0.05)

        suspeito = (
            diff_amostra_pct > TOLERANCIA_AMOSTRA_PCT
            or diff_impacto > TOLERANCIA_IMPACTO_PP
            or significativo_original != significativo_fisher
        )

        if suspeito:
            divergencias.append({
                "id": regra["id"], "rotulo": regra["rotulo"],
                "amostra_original": amostra_original, "amostra_recalculada": recalc["amostra"],
                "impacto_original": impacto_original, "impacto_recalculado": round(recalc["impacto_pp"], 2),
                "p_valor_original": p_valor_original, "p_valor_fisher": recalc["p_valor_fisher"],
            })
        else:
            ok += 1

    print(f"\n{'='*70}\nCross-check independente — {len(regras)} regras\n{'='*70}")
    print(f"Concordam (dentro da tolerância): {ok}")
    print(f"Sem dado suficiente pra recalcular: {sem_dado}")
    print(f"DIVERGÊNCIAS: {len(divergencias)}\n")
    for d in divergencias:
        print(f"[{d['id']}] {d['rotulo']}")
        print(f"    amostra: original={d['amostra_original']} recalculada={d['amostra_recalculada']}")
        print(f"    impacto_pp: original={d['impacto_original']:.2f} recalculado={d['impacto_recalculado']:.2f}")
        pv_fisher = f"{d['p_valor_fisher']:.2e}" if d['p_valor_fisher'] is not None else "None"
        print(f"    p_valor: original(z)={d['p_valor_original']:.2e} fisher={pv_fisher}")
        print()


if __name__ == "__main__":
    rodar()
