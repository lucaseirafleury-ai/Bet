"""Motor de pesos da metodologia (histórico + estilo de jogo).

Reimplementação em Python puro das fórmulas da aba `Times` do template
`Copa_Template_Simplificado.xlsx` (colunas AG-AK: Aderência ao alvo,
Aderência Favoritismo, Peso, Peso Final) e da fórmula "Pró/Contra robusta"
descrita no protocolo (média e desvio-padrão ponderados + corte de outlier
parametrizado, modelo validado por Lucas em 16/07/2026).

Estas funções não dependem de Excel/openpyxl — são o "cérebro" puro que
`excel_writer.py` usa para calcular e gravar valores finais na planilha,
em vez de reescrever fórmulas array/LET a cada sessão (a fonte do bug de
"planilha que não calculava" descrito no protocolo).
"""
from __future__ import annotations

import math

# (limite_em_dias, peso) em ordem crescente — degraus de decaimento por
# recência do jogo histórico em relação à data do jogo analisado.
FAIXAS_RECENCIA = [
    (10, 1.00),
    (20, 0.85),
    (30, 0.70),
    (45, 0.50),
    (90, 0.30),
    (180, 0.15),
]

N_DIMENSOES_ESTILO = 5  # bloco_baixo, pressao_alta, transicao, posse, bola_parada


def aderencia_estilo(notas_jogo, notas_alvo):
    """1 - (soma das diferenças absolutas nas 5 dimensões de estilo) / 20.

    `notas_jogo` e `notas_alvo` são sequências de 5 notas (1-5), na mesma
    ordem: bloco_baixo, pressao_alta, transicao, posse, bola_parada.
    """
    if len(notas_jogo) != N_DIMENSOES_ESTILO or len(notas_alvo) != N_DIMENSOES_ESTILO:
        raise ValueError(f"esperado {N_DIMENSOES_ESTILO} notas de estilo (bb, pa, tr, pos, bp)")
    soma_diff = sum(abs(j - a) for j, a in zip(notas_jogo, notas_alvo))
    return 1 - soma_diff / 20


def aderencia_favoritismo(favoritismo_jogo, favoritismo_alvo):
    """1 - |diferença| entre o favoritismo do jogo histórico e o do alvo."""
    return 1 - abs(favoritismo_jogo - favoritismo_alvo)


def peso_recencia(dias):
    """Degrau de decaimento por recência (dias desde o jogo histórico)."""
    if dias < 0:
        raise ValueError("dias não pode ser negativo")
    for limite, peso in FAIXAS_RECENCIA:
        if dias <= limite:
            return peso
    return 0.0


def peso_final(aderencia_estilo_, aderencia_favoritismo_, peso_recencia_):
    """Peso Final = Aderência Estilo × Aderência Favoritismo × Peso Recência."""
    return aderencia_estilo_ * aderencia_favoritismo_ * peso_recencia_


def calcular_pesos_historico(historico, estilo_alvo, favoritismo_alvo, data_jogo, usar_estilo=True):
    """Calcula aderência/peso para cada jogo histórico em relação ao jogo-alvo.

    `historico`: lista de dicts, um por jogo histórico, cada um com pelo
    menos as chaves `data` (date), `notas_estilo_adv` (5 notas do adversário
    daquele jogo, mesma ordem de `estilo_alvo`) e `favoritismo` (0-1).

    `usar_estilo`: quando `False`, força `aderencia_estilo=1.0` em todo
    jogo (não calcula a diferença de 5 dimensões) — isola a contribuição
    do estilo do resto do modelo (`peso_final` vira só
    `aderência_favoritismo × peso_recência`). Usado pelo teste de ablação
    em `retrospectiva.py` pra medir se o estilo está de fato ajudando.

    Retorna uma NOVA lista (não modifica os dicts originais), cada um com
    `aderencia_estilo`, `aderencia_favoritismo`, `peso_recencia` e
    `peso_final` adicionados.
    """
    resultado = []
    for jogo in historico:
        dias = (data_jogo - jogo["data"]).days
        ae = aderencia_estilo(jogo["notas_estilo_adv"], estilo_alvo) if usar_estilo else 1.0
        af = aderencia_favoritismo(jogo["favoritismo"], favoritismo_alvo)
        pr = peso_recencia(dias)
        pf = peso_final(ae, af, pr)
        novo = dict(jogo)
        novo.update(
            aderencia_estilo=ae,
            aderencia_favoritismo=af,
            peso_recencia=pr,
            peso_final=pf,
        )
        resultado.append(novo)
    return resultado


def ajuste_mando(historico_com_pesos, mando_alvo, k=0.35):
    """Reescala `peso_final` pelo mando do jogo-alvo (shrinkage de mando).

    Jogos históricos do MESMO mando do jogo-alvo mantêm peso 1×; jogos do
    mando oposto valem `k`× (encolhimento). `k=1.0` reproduz o
    comportamento sem ajuste de mando (equivalente a não aplicar).

    `historico_com_pesos`: lista de dicts com `mando` ('Casa'/'Fora') e
    `peso_final` (normalmente já processados por `calcular_pesos_historico`).
    `mando_alvo`: 'Casa' ou 'Fora' — mando do time no jogo analisado hoje.

    Retorna nova lista com `peso_final` sobrescrito (mesma ordem/tamanho).
    """
    if mando_alvo not in ("Casa", "Fora"):
        raise ValueError("mando_alvo deve ser 'Casa' ou 'Fora'")
    resultado = []
    for jogo in historico_com_pesos:
        fator = 1.0 if jogo["mando"] == mando_alvo else k
        novo = dict(jogo)
        novo["peso_final"] = jogo["peso_final"] * fator
        resultado.append(novo)
    return resultado


def media_ponderada(valores, pesos):
    """Equivalente a SUMPRODUCT(válido*valor*peso)/SUMPRODUCT(válido*peso).

    Ignora pares onde o valor é None ou o peso é zero/None. Retorna None se
    não sobrar nenhum par válido (peso total zero).
    """
    pares = [(v, p) for v, p in zip(valores, pesos) if v is not None and p]
    soma_pesos = sum(p for _, p in pares)
    if soma_pesos == 0:
        return None
    return sum(v * p for v, p in pares) / soma_pesos


def desvio_padrao_ponderado(valores, pesos, media):
    """Desvio-padrão ponderado (reliability weights, com correção de viés):

        sd = sqrt( Σw(x-média)² / (Σw - Σw²/Σw) )

    Retorna 0.0 quando não há variância residual suficiente para estimar
    (ex.: um único ponto válido).
    """
    pares = [(v, p) for v, p in zip(valores, pesos) if v is not None and p]
    soma_w = sum(p for _, p in pares)
    if soma_w == 0:
        return 0.0
    soma_w2 = sum(p * p for _, p in pares)
    denom = soma_w - soma_w2 / soma_w
    if denom <= 0:
        return 0.0
    soma_desvios = sum(p * (v - media) ** 2 for v, p in pares)
    return math.sqrt(soma_desvios / denom)


def corte_outlier(valores, pesos, media, sd, limite_unilateral=4, multiplicador_dp=2.5):
    """Filtra (valores, pesos) removendo outliers em torno da média ponderada.

    Corte UNILATERAL (remove só valores ACIMA de média+limite) quando
    `media <= limite_unilateral` — não penaliza jogos de placar baixo/
    típico, só remove picos anômalos pra cima. Corte BILATERAL
    (`|x-média| <= limite`) caso contrário. `limite = multiplicador_dp * sd`.

    Retorna `(valores_filtrados, pesos_filtrados)`.
    """
    limite = multiplicador_dp * sd
    valores_filtrados, pesos_filtrados = [], []
    for v, p in zip(valores, pesos):
        if v is None:
            continue
        if media <= limite_unilateral:
            manter = v <= media + limite
        else:
            manter = abs(v - media) <= limite
        if manter:
            valores_filtrados.append(v)
            pesos_filtrados.append(p)
    return valores_filtrados, pesos_filtrados


def indicador_pro_contra(valores, pesos, limite_unilateral=4, multiplicador_dp=2.5):
    """Pipeline completo de um mercado Pró/Contra (modelo validado 16/07/2026):

    média ponderada -> desvio-padrão ponderado -> corte de outlier
    parametrizado -> média ponderada final (o valor que vai na célula).

    Retorna dict com `media_bruta`, `sd`, `media_final` (pós-corte) e
    `n_removidos` (quantos pontos válidos o corte de outlier descartou) —
    os três primeiros compõem a trilha de auditoria (coluna auxiliar `_avg`
    do protocolo guarda `media_bruta`).
    """
    media_bruta = media_ponderada(valores, pesos)
    if media_bruta is None:
        return dict(media_bruta=None, sd=None, media_final=None, n_removidos=0)
    sd = desvio_padrao_ponderado(valores, pesos, media_bruta)
    v_filt, p_filt = corte_outlier(valores, pesos, media_bruta, sd, limite_unilateral, multiplicador_dp)
    media_final = media_ponderada(v_filt, p_filt)
    n_validos = len([v for v in valores if v is not None])
    n_removidos = n_validos - len(v_filt)
    return dict(media_bruta=media_bruta, sd=sd, media_final=media_final, n_removidos=n_removidos)


# ---------------------------------------------------------------------------
# Conversão de gols esperados -> probabilidade (pra comparar com odd de
# mercado e medir vantagem real, não só acerto de Over/Under).
# ---------------------------------------------------------------------------

def _poisson_pmf(k, lam):
    return math.exp(-lam) * lam**k / math.factorial(k)


def probabilidade_over(media_total_gols, linha=2.5, limite_somatoria=60):
    """P(total de gols > linha), tratando o total como Poisson(λ=media_total_gols).

    Soma de duas Poisson independentes (gols pró + gols contra) também é
    Poisson com λ = soma dos dois λs — não precisa modelar a dependência
    entre os times pra essa conta, só a soma dos gols esperados do jogo.

    `linha`: 2.5, 1.5, 3.5 etc. (linhas .5 nunca empatam, mas a função
    aceita qualquer valor — conta P(total > linha)). `limite_somatoria`:
    corta a série infinita de Poisson num k grande o suficiente pra erro
    numérico ser desprezível (60 gols é bem além de qualquer jogo real).
    """
    if media_total_gols < 0:
        raise ValueError("media_total_gols não pode ser negativa")
    k_max_under = math.floor(linha)  # maior inteiro que ainda conta como "under"
    p_under_ou_igual = sum(_poisson_pmf(k, media_total_gols) for k in range(0, k_max_under + 1))
    return max(0.0, min(1.0, 1 - p_under_ou_igual))


def probabilidade_btts(gols_pro_esperado, gols_contra_esperado):
    """P(ambos os times marcam), tratando os gols de cada lado como Poisson
    independentes: `1 - P(pró=0) - P(contra=0) + P(pró=0 E contra=0)`."""
    if gols_pro_esperado < 0 or gols_contra_esperado < 0:
        raise ValueError("gols esperados não podem ser negativos")
    p_pro_zero = math.exp(-gols_pro_esperado)
    p_contra_zero = math.exp(-gols_contra_esperado)
    return max(0.0, min(1.0, 1 - p_pro_zero - p_contra_zero + p_pro_zero * p_contra_zero))


def probabilidade_implicita(odd):
    """Probabilidade implícita bruta de uma odd decimal (`1/odd`), SEM
    remover a margem da casa (overround) — superestima a probabilidade
    real na proporção da margem embutida. Use `probabilidade_implicita_2vias`
    quando tiver as odds dos dois lados de um mercado (ex.: BTTS sim/não),
    que permite normalizar removendo a margem de verdade."""
    if odd <= 1:
        raise ValueError("odd decimal deve ser > 1")
    return 1 / odd


def probabilidade_implicita_2vias(odd_lado, odd_lado_oposto):
    """Probabilidade implícita do `odd_lado`, normalizada pela margem da
    casa usando as odds dos dois lados de um mercado binário (ex.: BTTS
    Sim/Não). Mais correta que `probabilidade_implicita` porque remove o
    overround em vez de superestimar os dois lados."""
    p1 = probabilidade_implicita(odd_lado)
    p2 = probabilidade_implicita(odd_lado_oposto)
    soma = p1 + p2
    if soma <= 0:
        raise ValueError("soma das probabilidades implícitas deve ser positiva")
    return p1 / soma


def probabilidade_resultado(gols_pro_esperado, gols_contra_esperado, limite_gols=10):
    """P(vitória do mandante), P(empate), P(vitória do visitante) — gols de
    cada lado como Poisson independentes (mesma premissa de
    `probabilidade_btts`), somando a grade conjunta de placares possíveis
    até `limite_gols` por time (10 já cobre >99.9% da massa de probabilidade
    de qualquer confronto real).

    Não modela correlação entre os times (ex.: jogo aberto favorece mais
    gols dos dois lados ao mesmo tempo) — mesma limitação já documentada
    pra `probabilidade_over`/`probabilidade_btts`.
    """
    if gols_pro_esperado < 0 or gols_contra_esperado < 0:
        raise ValueError("gols esperados não podem ser negativos")
    p_pro = [_poisson_pmf(k, gols_pro_esperado) for k in range(limite_gols + 1)]
    p_contra = [_poisson_pmf(k, gols_contra_esperado) for k in range(limite_gols + 1)]
    vitoria = empate = derrota = 0.0
    for i, pi in enumerate(p_pro):
        for j, pj in enumerate(p_contra):
            conjunta = pi * pj
            if i > j:
                vitoria += conjunta
            elif i == j:
                empate += conjunta
            else:
                derrota += conjunta
    soma = vitoria + empate + derrota
    if soma <= 0:
        return dict(vitoria=0.0, empate=0.0, derrota=0.0)
    return dict(vitoria=vitoria / soma, empate=empate / soma, derrota=derrota / soma)
