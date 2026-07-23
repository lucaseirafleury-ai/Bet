"""
analise.py — motor de análise em Python puro, sem depender do Excel/LibreOffice.

Reimplementa em Python, número por número, a mesma matemática que hoje vive
nas fórmulas do template (`templates/Copa_Template_Simplificado.xlsx`):
aderência de estilo/favoritismo, peso por recência, a fórmula Pró/Contra V2
(média/desvio-padrão ponderados com corte unilateral/bilateral parametrizado
— o mesmo `Parâmetros!B11` que Lucas troca manualmente de 2.5 para 1.25), λ
de Poisson por time, e o parser de critério que gera P.Plan para cada um dos
20 mercados (`MERCADOS_TEMPLATE_20` em planilha_lib.py).

Isso permite gerar a lista final de apostas do dia (o pós-processamento que
Lucas fazia manualmente: filtrar P.Comb ≥ 65%, testar robustez trocando o
desvio-padrão pra 1.25, cortar odd > 2.0, cruzar Padrões em comum) SEM nunca
abrir o Excel — só quando ele pedir explicitamente uma planilha (pra rever
conceitos visualmente) é que se usa o pipeline antigo (build_workbook +
aplicar_ajuste_mando + montar_aba_padroes + recalc.py +
aplicar_formula_pro_contra + sanitizar_v_vazio).

⚠️ Este módulo foi validado por leitura cuidadosa das fórmulas do template e
por testes de consistência interna (ver scripts/test_analise.py), mas NÃO
foi cross-validado contra uma reabertura real no Excel (o `recalc.py`/
LibreOffice trava no ambiente onde isso foi escrito — ver docs/MIGRACAO.md).
Na primeira vez que usar de verdade, vale conferir um jogo com a planilha
Excel gerada (`--excel`) para confirmar que os números batem.

Uso típico:

    import sys
    sys.path.insert(0, "/mnt/skills/user/planilha-liga-dia/scripts")
    from planilha_lib import get_historico, attach_estilo, load_all_matches, buscar_padroes_liga
    from ligas import estilo_db_path, mando_shrink_k_default
    from analise import analisar_jogo, relatorio_dia

    df = load_all_matches()
    hist_A = attach_estilo(get_historico("Ceará", df), estilo_db_path("serieb"))
    hist_B = attach_estilo(get_historico("Athletic Club", df), estilo_db_path("serieb"))
    jdd_A = dict(fav=0.55, bb=3, pa=3, tr=3, pos=3, bp=3)   # estilo do ADVERSÁRIO (Athletic) na perspectiva de Ceará
    jdd_B = dict(fav=0.45, bb=2, pa=3, tr=3, pos=3, bp=3)   # estilo do ADVERSÁRIO (Ceará) na perspectiva de Athletic

    jogo = dict(teamA="Ceará", teamB="Athletic Club", hist_A=hist_A, hist_B=hist_B,
                jdd_A=jdd_A, jdd_B=jdd_B, favorito="A",
                odds_and_pfont=[("50%", 1.9)] * 20,   # 20 tuplas, ordem de MERCADOS_TEMPLATE_20
                data_jogo="13/07/2026",
                mando_A="Casa", mando_B="Fora",              # Ceará manda o jogo hoje
                mando_k=mando_shrink_k_default("serieb"))    # OBRIGATÓRIO em Série A/B (NUNCA em Copa)

    print(relatorio_dia([jogo], csv_glob=".../data/matches/*seriebmatches*.csv"))
"""
import datetime
import math

import numpy as np

from planilha_lib import MERCADOS_TEMPLATE_20, buscar_padroes_liga

# ---------------------------------------------------------------------------
# 0. Poisson sem scipy (log-space, estável para k até 20 e lambda até ~15)
# ---------------------------------------------------------------------------

def _poisson_pmf(k, lam):
    """P(X=k) para X~Poisson(lam). k pode ser array numpy; lam escalar >=0."""
    k = np.asarray(k, dtype=float)
    lam = max(float(lam), 1e-9)
    log_pmf = k * math.log(lam) - lam - _log_gamma_plus_1(k)
    return np.exp(log_pmf)


def _log_gamma_plus_1(k):
    # log(k!) = lgamma(k+1), vetorizado
    return np.array([math.lgamma(x + 1) for x in np.atleast_1d(k).ravel()]).reshape(np.shape(k))


def _poisson_cdf(k, lam):
    """P(X<=k) para X~Poisson(lam), k inteiro escalar."""
    ks = np.arange(0, int(k) + 1)
    return float(_poisson_pmf(ks, lam).sum())


# ---------------------------------------------------------------------------
# 1. ADERÊNCIA / PESO / RECÊNCIA (equivalente a Times!AG, AH, AI, AK)
# ---------------------------------------------------------------------------

def _parse_data(s):
    return datetime.datetime.strptime(s, "%d/%m/%Y")


def peso_recencia(dias):
    """Times!AI — bucket de recência (dias entre o jogo de hoje e o histórico)."""
    if dias <= 10:
        return 1.00
    if dias <= 20:
        return 0.85
    if dias <= 30:
        return 0.70
    if dias <= 45:
        return 0.50
    if dias <= 90:
        return 0.30
    if dias <= 180:
        return 0.15
    return 0.0


def aderencia_estilo(rec, jdd):
    """Times!AG — 1 - (soma das diferenças absolutas das 5 notas de estilo)/20.
    Compara o estilo do ADVERSÁRIO no jogo histórico (rec, já preenchido por
    attach_estilo) com o estilo do adversário de HOJE (jdd)."""
    diffs = (abs(rec["bb"] - jdd["bb"]) + abs(rec["pa"] - jdd["pa"]) +
             abs(rec["tr"] - jdd["tr"]) + abs(rec["pos"] - jdd["pos"]) +
             abs(rec["bp"] - jdd["bp"]))
    return 1 - diffs / 20


def aderencia_favoritismo(rec, jdd):
    """Times!AH — 1 - |favoritismo histórico - favoritismo de hoje|."""
    fav_hist = rec["fav"] if rec.get("fav") is not None else 0.0
    return 1 - abs(fav_hist - jdd["fav"])


def preparar_historico(hist, jdd, data_jogo, mando_hoje=None, mando_k=None):
    """Enriquece cada registro do histórico (já com attach_estilo aplicado)
    com aderencia_estilo/aderencia_favoritismo/peso_recencia/peso_final/valid
    — a mesma coisa que Times!AG/AH/AI/AK fazem na planilha, mas calculado
    direto em Python. Não depende de mult_dp (isso só entra em
    pro_contra_stat). Retorna uma NOVA lista (não modifica hist original).

    mando_hoje/mando_k: equivalente a aplicar_ajuste_mando (planilha_lib) —
    OBRIGATÓRIO para Série A/B (torneios com mando real), NUNCA usar na Copa
    (neutra). mando_hoje = "Casa" ou "Fora" (o mando do time HOJE); mando_k =
    fator de encolhimento dos jogos do mando oposto (pegue de
    ligas.mando_shrink_k_default(liga), não invente um valor). Se
    mando_hoje for None, o ajuste de mando NÃO é aplicado (equivale a k=1.0,
    "sem mando" — correto só para a Copa)."""
    hoje = _parse_data(data_jogo)
    out = []
    for rec in hist:
        r = dict(rec)
        r["_ag"] = aderencia_estilo(rec, jdd)
        r["_ah"] = aderencia_favoritismo(rec, jdd)
        dias = (hoje - _parse_data(rec["data"])).days
        r["_ai"] = peso_recencia(dias)
        fator_mando = 1.0
        if mando_hoje is not None:
            fator_mando = 1.0 if rec.get("mando") == mando_hoje else mando_k
        r["_fator_mando"] = fator_mando
        r["_ak"] = r["_ag"] * r["_ah"] * r["_ai"] * fator_mando
        r["_valid"] = (r["_ag"] >= 0.65) and (r["_ah"] >= 0.65)
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# 2. FÓRMULA PRÓ/CONTRA V2 (equivalente a aplicar_formula_pro_contra, mas
#    calculando o NÚMERO diretamente em vez de escrever uma fórmula Excel)
# ---------------------------------------------------------------------------

CORTE_LIMITE_UNILATERAL_DEFAULT = 4
CORTE_MULTIPLICADOR_DP_DEFAULT = 2.5   # Parâmetros!B11 — Lucas troca pra 1.25 na revisão de robustez

_CAMPOS_PRO_CONTRA = {
    "Gols Pró": "gf", "Gols Contra": "ga",
    "Cartões Pró": "yf", "Cartões Contra": "ya",
    "Escanteios Pró": "cf", "Escanteios Contra": "ca",
    "Chutes Pró": "sf", "Chutes Contra": "sa",
    "Chutes Gol Pró": "sotf", "Chutes Gol Contra": "sota",
    "Gols 1T Pró": "htf", "Gols 1T Contra": "hta",
}


def pro_contra_stat(hist_preparado, campo, mult_dp=CORTE_MULTIPLICADOR_DP_DEFAULT,
                     limite_unilateral=CORTE_LIMITE_UNILATERAL_DEFAULT):
    """Reproduz _formula_mu / _formula_sd / _formula_pro_contra (planilha_lib.py)
    numericamente, para um campo do histórico (ex. 'gf' = Gols Pró).

    hist_preparado: saída de preparar_historico() (já tem _ak e _valid).
    Sem jogos válidos, retorna 0.0 (mesmo IFERROR(...,0) do Excel)."""
    validos = [r for r in hist_preparado if r["_valid"]]
    if not validos:
        return 0.0
    vals = np.array([r[campo] for r in validos], dtype=float)
    pesos = np.array([r["_ak"] for r in validos], dtype=float)
    soma_peso = pesos.sum()
    if soma_peso <= 0:
        return 0.0

    mu = float((vals * pesos).sum() / soma_peso)
    n = len(validos)
    if n < 3:
        return mu  # amostra pequena demais para filtrar outlier: usa todos, ponderado

    soma_peso2 = (pesos ** 2).sum()
    denom = soma_peso - soma_peso2 / soma_peso
    if denom > 0:
        var = float((pesos * (vals - mu) ** 2).sum() / denom)
        sd = math.sqrt(max(var, 0.0))
    else:
        sd = 0.0

    lim = mult_dp * sd
    if mu <= limite_unilateral:
        mask = vals <= (mu + lim)          # corte unilateral: só poda picos pra cima
    else:
        mask = np.abs(vals - mu) <= lim    # corte bilateral

    if not mask.any():
        return mu  # nunca deveria zerar tudo, mas por segurança cai pro mu ponderado
    num = (vals[mask] * pesos[mask]).sum()
    den = pesos[mask].sum()
    return float(num / den) if den > 0 else mu


def jdd_stats(hist_preparado, mult_dp=CORTE_MULTIPLICADOR_DP_DEFAULT,
              limite_unilateral=CORTE_LIMITE_UNILATERAL_DEFAULT):
    """As 12 colunas Pró/Contra de 'Jogos do Dia', para um time, num dict.
    Chaves iguais aos nomes de _CAMPOS_PRO_CONTRA (ex. 'Gols Pró')."""
    return {
        nome: pro_contra_stat(hist_preparado, campo, mult_dp, limite_unilateral)
        for nome, campo in _CAMPOS_PRO_CONTRA.items()
    }


# ---------------------------------------------------------------------------
# 3. λ DE POISSON (equivalente a Mercados!T/U — λ_A/λ_B)
# ---------------------------------------------------------------------------

def lambda_ab(stats_A, stats_B):
    """la = média(Gols Pró de A, Gols Contra de B); lb = média(Gols Pró de B,
    Gols Contra de A) — mesma fórmula do Mercados!T2/U2. Piso em 0."""
    la = max(0.0, (stats_A["Gols Pró"] + stats_B["Gols Contra"]) / 2)
    lb = max(0.0, (stats_B["Gols Pró"] + stats_A["Gols Contra"]) / 2)
    return la, lb


# ---------------------------------------------------------------------------
# 4. PARSER DE CRITÉRIO + P.PLAN (equivalente a Mercados!F — a fórmula LET)
# ---------------------------------------------------------------------------

_GRID_N = 21  # gols 0..20, igual a SEQUENCE(21,,0) do template


def _parse_criterio(raw_full):
    """Separa 'Under 3.5 | 0.84' em (raw='Under 3.5', mult=0.84).
    raw_full pode ser None/''"""
    if not raw_full:
        return "", 1.0
    if "|" in raw_full:
        raw, mult_s = raw_full.split("|", 1)
        try:
            mult = float(mult_s.strip().replace(",", "."))
        except ValueError:
            mult = 1.0
        return raw.strip(), mult
    return raw_full.strip(), 1.0


def _parse_linha(raw):
    """'Over 2.5' -> 2.5 ; 'Over 0.5 1T' -> 0.5. Replica TEXTAFTER/TEXTBEFORE
    do template (texto entre o 1º e o 2º espaço)."""
    try:
        after_first_space = raw.split(" ", 1)[1]
        token = (after_first_space + " ").split(" ", 1)[0]
        return float(token.replace(",", "."))
    except (IndexError, ValueError):
        return 0.0


def _parse_handicap(raw):
    """'TimeA AH -1.5' -> -1.5. Replica TEXTAFTER(raw,'AH ')."""
    try:
        return float(raw.split("AH ", 1)[1].replace(",", "."))
    except (IndexError, ValueError):
        return 0.0


def _condicao(raw, x, y, lambda_ft):
    """x: coluna (21,1) gols do time A; y: linha (1,21) gols do time B (mesmo
    grid usado no template, broadcasting faz a matriz 21x21 automaticamente).
    Retorna 1.0 (sem critério), um array 21x21 (condição por placar) ou um
    escalar (mercados de 1º tempo, que usam Poisson univariado em vez do
    grid bivariado — mesma simplificação do template original)."""
    if raw == "":
        return 1.0
    if raw == "BTTS Sim":
        return ((x > 0) & (y > 0)).astype(float)
    if raw == "BTTS Não":
        return ((x == 0) | (y == 0)).astype(float)
    if " 1T" in raw:
        linha = _parse_linha(raw)
        cdf = _poisson_cdf(int(linha), lambda_ft)
        return (1 - cdf) if raw.startswith("Over") else cdf
    if raw.startswith("Over"):
        return ((x + y) > _parse_linha(raw)).astype(float)
    if raw.startswith("Under"):
        return ((x + y) < _parse_linha(raw)).astype(float)
    if raw == "TimeA vence":
        return (x > y).astype(float)
    if raw == "TimeB vence":
        return (y > x).astype(float)
    if raw == "Empate":
        return (x == y).astype(float)
    if raw == "TimeA DC":
        return (x >= y).astype(float)
    if raw == "TimeB DC":
        return (y >= x).astype(float)
    if "TimeA AH" in raw:
        return ((x + _parse_handicap(raw)) > y).astype(float)
    if "TimeB AH" in raw:
        return ((y + _parse_handicap(raw)) > x).astype(float)
    return 1.0


def p_plan(crit_um_full, crit_dois_full, la, lb):
    """Reproduz Mercados!F (P.Plan) — Poisson bivariado independente sobre o
    grid 0..20 gols para cada time, com o parser de critério acima. Igual ao
    template: `SUM(p * condOne * condTwo) * multOne * multTwo`."""
    la, lb = max(0.0, la), max(0.0, lb)
    g = np.arange(_GRID_N, dtype=float)
    x = g.reshape(-1, 1)          # (21,1) — gols do time A (index 0 do critério)
    y = g.reshape(1, -1)          # (1,21) — gols do time B (index 1 do critério)
    p = _poisson_pmf(x, la) * _poisson_pmf(y, lb)   # (21,21)
    lambda_ft = (la + lb) * 0.42  # aproximação de gols do 1º tempo

    raw_um, mult_um = _parse_criterio(crit_um_full)
    raw_dois, mult_dois = _parse_criterio(crit_dois_full)
    cond_um = _condicao(raw_um, x, y, lambda_ft)
    cond_dois = _condicao(raw_dois, x, y, lambda_ft)

    return float(np.sum(p * cond_um * cond_dois)) * mult_um * mult_dois


# ---------------------------------------------------------------------------
# 5. P.COMB / EDGE / VEREDITO / CRITÉRIOS (equivalente a Mercados!H..Q)
# ---------------------------------------------------------------------------

def p_comb(plan, font):
    return plan * 0.45 + font * 0.55


def veredito_tag(comb, edge):
    """Mercados!M — classificação por edge (rótulo visual, diferente do Q)."""
    if comb > 0.60 and -0.15 <= edge <= 0.15:
        return "⭐Conferir"
    if edge > 0.15:
        return "✅✅ Forte Valor"
    if edge > 0.10:
        return "✅ Entra"
    if edge >= 0.0:
        return "🟡 Borderline"
    if edge < -0.15:
        return "🔴 Evitar"
    return "❌ Sem valor"


def criterios_tag(plan, font, mkt, comb, odd, edge):
    """Mercados!Q — as 4 categorias do PROTOCOLO_BETS_LUCAS.md."""
    if plan > font and font >= mkt and mkt >= 0.60:
        return "🎯 Edge Real"
    if font >= mkt and mkt >= 0.60:
        return "📡 Sinal Externo"
    if comb >= 0.65 and odd <= 1.80:
        return "✅ Alta Certeza"
    if comb >= 0.55 and edge > 0.10:
        return "📊 Referência"
    return "❌ Sem critério"


def stake_kelly(odd):
    """Mercados!P (Stake) — mesma fórmula de fracional-Kelly do template,
    usada lá sobre 'Odd Betano' (a odd JÁ CONFIRMADA na casa). Aqui é
    aplicada sobre a odd pesquisada (odd_mercado) na falta de uma odd
    confirmada separada — trate como SUGESTÃO, não como odd validada
    (Regra 6 do protocolo: nunca recomendar 'entrar' sem odd real
    conferida). Retorna None se a odd não é utilizável (<=1)."""
    if odd is None or odd <= 1:
        return None
    if odd < 1 / 0.483:
        return 0.0
    return round(min(3, max(0.5, 0.25 * ((odd * 0.483 - 1) / (odd - 1)) * 10)), 1)


def avaliar_mercados(teamA, teamB, favorito, odds_and_pfont, la, lb,
                      displayA=None, displayB=None):
    """Para os 20 mercados de MERCADOS_TEMPLATE_20 (mesma ordem/textos do
    Excel), calcula P.Plan/P.Font/P.Mkt/P.Comb/Odd Gatilho/Edge/Veredito/
    Critérios. odds_and_pfont: 20 tuplas (p_font_str_ou_float, odd), na
    mesma ordem de MERCADOS_TEMPLATE_20 (igual ao que já se usa em
    mercados_rows_for_game)."""
    dA, dB = displayA or teamA, displayB or teamB
    fav_name, dog_name = (dA, dB) if favorito == "A" else (dB, dA)
    fav_key, dog_key = ("TimeA", "TimeB") if favorito == "A" else ("TimeB", "TimeA")
    jogo = f"{teamA} x {teamB}"

    linhas = []
    for (mercado_t, tipo, c1_t, c2_t), (pfont_raw, odd) in zip(MERCADOS_TEMPLATE_20, odds_and_pfont):
        mercado = mercado_t.format(A=dA, B=dB, FAV=fav_name, DOG=dog_name)
        c1 = c1_t.format(FAVKEY=fav_key, DOGKEY=dog_key) if c1_t else c1_t
        c2 = c2_t

        plan = p_plan(c1, c2, la, lb)
        font = float(str(pfont_raw).replace("%", "").replace(",", ".")) / (
            100 if isinstance(pfont_raw, str) and "%" in pfont_raw else 1)
        odd = float(odd)
        mkt = 1 / odd
        comb = p_comb(plan, font)
        odd_gatilho = 1 / comb if comb > 0 else float("inf")
        edge = (odd / odd_gatilho) - 1 if odd_gatilho not in (0, float("inf")) else float("-inf")

        linhas.append(dict(
            jogo=jogo, mercado=mercado, tipo=tipo,
            p_plan=plan, p_font=font, p_mkt=mkt, p_comb=comb,
            odd_gatilho=odd_gatilho, odd_mercado=odd, edge=edge,
            veredito=veredito_tag(comb, edge),
            criterio=criterios_tag(plan, font, mkt, comb, odd, edge),
            stake=stake_kelly(odd),
        ))
    return linhas


# ---------------------------------------------------------------------------
# 6. ORQUESTRAÇÃO POR JOGO (equivalente ao pipeline inteiro build_workbook+...)
# ---------------------------------------------------------------------------

def analisar_jogo(teamA, teamB, hist_A, hist_B, jdd_A, jdd_B, favorito,
                   odds_and_pfont, data_jogo, displayA=None, displayB=None,
                   mult_dp=CORTE_MULTIPLICADOR_DP_DEFAULT,
                   mando_A=None, mando_B=None, mando_k=None):
    """Pipeline completo pra 1 jogo, sem Excel: aderência/peso/mando ->
    Pró/Contra V2 -> λ -> P.Plan/P.Comb/Critérios pros 20 mercados. Retorna
    a lista de linhas de avaliar_mercados().

    mando_A/mando_B ("Casa"/"Fora") + mando_k: equivalente a
    aplicar_ajuste_mando (planilha_lib) — OBRIGATÓRIO pra Série A/B (ver
    ligas.mando_shrink_k_default(liga)), NUNCA passar pra Copa (neutra). O
    ajuste só é de fato aplicado se mando_k não for None — assim
    gerar_shortlist() pode ter mando_A/mando_B com default ("Casa"/"Fora",
    usados só pra padroes_em_comum) sem acidentalmente ligar o ajuste de
    mando sem um k explícito."""
    mando_A_ok = mando_A if mando_k is not None else None
    mando_B_ok = mando_B if mando_k is not None else None
    hp_A = preparar_historico(hist_A, jdd_A, data_jogo, mando_hoje=mando_A_ok, mando_k=mando_k)
    hp_B = preparar_historico(hist_B, jdd_B, data_jogo, mando_hoje=mando_B_ok, mando_k=mando_k)
    stats_A = jdd_stats(hp_A, mult_dp=mult_dp)
    stats_B = jdd_stats(hp_B, mult_dp=mult_dp)
    la, lb = lambda_ab(stats_A, stats_B)
    return avaliar_mercados(teamA, teamB, favorito, odds_and_pfont, la, lb,
                             displayA=displayA, displayB=displayB)


# ---------------------------------------------------------------------------
# 7. PADRÕES EM COMUM (os dois times entram no mesmo padrão da aba Padrões)
# ---------------------------------------------------------------------------

def padroes_em_comum(teamA, teamB, csv_glob, mando_A="Casa", mando_B="Fora",
                      min_pct=0.8, min_jogos=7):
    """Acha métricas em que TANTO teamA (no mando_A) QUANTO teamB (no
    mando_B) têm recorrência >= min_pct — o cruzamento manual que Lucas faz
    olhando a aba Padrões dos dois times ao mesmo tempo (ex.: os dois entram
    em 'chutes_total acima de 22.5'). Sugestão de stake fixa em 1.0, igual ao
    que Lucas já faz manualmente."""
    achados = buscar_padroes_liga(csv_glob=csv_glob, min_jogos=min_jogos,
                                   teams=[teamA, teamB], min_pct=min_pct)
    if len(achados) == 0:
        return []
    a = achados[(achados.time == teamA) & (achados.mando == mando_A)]
    b = achados[(achados.time == teamB) & (achados.mando == mando_B)]
    comuns = a.merge(b, on=["metrica", "limiar", "direcao"], suffixes=("_A", "_B"))
    out = []
    for _, row in comuns.iterrows():
        out.append(dict(
            jogo=f"{teamA} x {teamB}", metrica=row["metrica"], limiar=row["limiar"],
            direcao=row["direcao"],
            pct_A=row["pct_A"], n_A=row["n_A"], pct_B=row["pct_B"], n_B=row["n_B"],
            stake_sugerido=1.0,
        ))
    return out


# ---------------------------------------------------------------------------
# 8. RELATÓRIO DO DIA — automatiza o pós-processamento manual de Lucas
# ---------------------------------------------------------------------------

def gerar_shortlist(teamA, teamB, hist_A, hist_B, jdd_A, jdd_B, favorito,
                     odds_and_pfont, data_jogo, csv_glob,
                     displayA=None, displayB=None,
                     p_comb_min=0.65, mult_dp_robustez=1.25, odd_max=2.0,
                     mando_A="Casa", mando_B="Fora", mando_k=None):
    """Reproduz o fluxo manual de Lucas pra 1 jogo:
      1. Avalia os 20 mercados com o desvio-padrão padrão (2.5).
      2. Filtra P.Comb >= p_comb_min (65% por padrão).
      3. Reavalia SÓ o P.Plan com o desvio-padrão de robustez (1.25 por
         padrão) e descarta quem cair abaixo de p_comb_min nessa reavaliação.
      4. Descarta odd de mercado > odd_max (2.0 por padrão).
      5. Cruza a aba Padrões dos dois times (padroes_em_comum).
    Retorna dict(entradas=[...], padroes_comuns=[...]).

    mando_A/mando_B: mando de cada time HOJE ("Casa"/"Fora") — usados tanto
    no ajuste de mando do λ quanto no cruzamento de Padrões. mando_k: pegue
    de ligas.mando_shrink_k_default(liga); passe None só para Copa (torneio
    neutro, sem ajuste de mando).
    """
    linhas_base = analisar_jogo(teamA, teamB, hist_A, hist_B, jdd_A, jdd_B, favorito,
                                 odds_and_pfont, data_jogo, displayA, displayB,
                                 mult_dp=CORTE_MULTIPLICADOR_DP_DEFAULT,
                                 mando_A=mando_A, mando_B=mando_B, mando_k=mando_k)
    linhas_robustas = analisar_jogo(teamA, teamB, hist_A, hist_B, jdd_A, jdd_B, favorito,
                                     odds_and_pfont, data_jogo, displayA, displayB,
                                     mult_dp=mult_dp_robustez,
                                     mando_A=mando_A, mando_B=mando_B, mando_k=mando_k)
    plan_robusto = {l["mercado"]: l["p_plan"] for l in linhas_robustas}

    entradas = []
    for l in linhas_base:
        if l["p_comb"] < p_comb_min:
            continue
        if l["odd_mercado"] > odd_max:
            continue
        if plan_robusto.get(l["mercado"], 0.0) < p_comb_min:
            continue
        l2 = dict(l)
        l2["p_plan_robusto"] = plan_robusto.get(l["mercado"])
        entradas.append(l2)

    comuns = padroes_em_comum(teamA, teamB, csv_glob, mando_A=mando_A, mando_B=mando_B)
    return dict(entradas=entradas, padroes_comuns=comuns)


def relatorio_dia(games_com_csv_glob):
    """games_com_csv_glob: lista de dicts, um por jogo, cada um com as chaves
    de gerar_shortlist (teamA, teamB, hist_A, hist_B, jdd_A, jdd_B, favorito,
    odds_and_pfont, data_jogo, csv_glob, e opcionalmente displayA/displayB/
    mando_A/mando_B/p_comb_min/mult_dp_robustez/odd_max).
    Retorna uma string markdown com a lista final pronta pra ler, sem abrir
    Excel."""
    partes = []
    for g in games_com_csv_glob:
        kwargs = {k: v for k, v in g.items() if k not in ("teamA", "teamB")}
        r = gerar_shortlist(g["teamA"], g["teamB"], **kwargs)
        titulo = f"## {g['teamA']} x {g['teamB']}"
        partes.append(titulo)
        if not r["entradas"]:
            partes.append("_Nenhuma entrada passou nos filtros (P.Comb ≥ 65%, robusto a σ=1.25, odd ≤ 2.0)._")
        else:
            partes.append("| Mercado | P.Plan | P.Font | P.Mkt | P.Comb | Odd Gatilho | Odd Mercado | Edge | Stake | Critério |")
            partes.append("|---|---|---|---|---|---|---|---|---|---|")
            for l in sorted(r["entradas"], key=lambda x: -x["p_comb"]):
                stake_txt = f"{l['stake']:.1f}" if l.get("stake") is not None else "—"
                partes.append(
                    f"| {l['mercado']} | {l['p_plan']:.0%} | {l['p_font']:.0%} | "
                    f"{l['p_mkt']:.0%} | {l['p_comb']:.0%} | {l['odd_gatilho']:.2f} | "
                    f"{l['odd_mercado']:.2f} | {l['edge']:+.0%} | {stake_txt} | {l['criterio']} |"
                )
        if r["padroes_comuns"]:
            partes.append("\n**Padrões em comum (stake sugerido 1.0):**")
            for c in r["padroes_comuns"]:
                partes.append(
                    f"- {c['metrica']} {c['direcao']} de {c['limiar']} — "
                    f"{g['teamA']} {c['pct_A']:.0f}% (n={c['n_A']}) e "
                    f"{g['teamB']} {c['pct_B']:.0f}% (n={c['n_B']})"
                )
        partes.append("")
    return "\n".join(partes)
