"""Cálculo automático das 5 notas de estilo (Bloco Baixo, Pressão Alta,
Transição Rápida, Posse/Dominância, Bola Parada/Físico) a partir dos
últimos N jogos de um time.

Antes, essas notas eram atribuídas por julgamento qualitativo do Claude a
cada sessão (ver `tabela-comparativa-time/SKILL.md`, "Notas de estilo (1-5)
— passo MANUAL do Claude"). Aqui viram parâmetros pré-definidos e
documentados, calculados a partir de estatísticas reais dos jogos.

Duas dimensões têm dado direto no CSV do FootyStats (Posse/Dominância via
`posf`; Bloco Baixo via o inverso da posse, ajustado pela organização
defensiva). As outras três (Pressão Alta, Transição Rápida, Bola Parada/
Físico) não têm métrica direta — usam PROXIES estatísticos mais fracos,
documentados abaixo em cada função. Reportar sempre essa diferença de
confiança ao usuário.

Cada jogo em `ultimos_jogos` é um dict no formato produzido por
`planilha_lib.get_historico` (chaves: `posf`, `xgf`, `xga`, `sf`, `sotf`,
`cf` [escanteios pró], `yf` [cartões], `ff` [faltas cometidas]).
"""
from __future__ import annotations

N_JOGOS_PADRAO = 5


def _media(jogos, campo):
    valores = [j[campo] for j in jogos if j.get(campo) is not None]
    if not valores:
        return None
    return sum(valores) / len(valores)


def _clamp(nota, minimo=1, maximo=5):
    return max(minimo, min(maximo, nota))


def _faixa(valor, cortes):
    """`cortes`: lista de (limite_superior, nota) em ordem crescente de
    limite; o último item deve ter limite `None` (catch-all)."""
    for limite, nota in cortes:
        if limite is None or valor < limite:
            return nota
    raise ValueError("faixa mal definida: nenhum corte bateu")


# ---- Posse/Dominância — dado direto (média de posf, % de posse) ----
PARAM_FAIXAS_POSSE = [
    (35, 1), (42, 2), (58, 3), (65, 4), (None, 5),
]


def nota_posse(media_posse):
    return _faixa(media_posse, PARAM_FAIXAS_POSSE)


# ---- Bloco Baixo — proxy: inverso da posse, ajustado por xGA ----
PARAM_XGA_DEFESA_ORGANIZADA = 1.0   # xGA média abaixo disso -> +1 (bloco disciplinado)
PARAM_XGA_TIME_DOMINADO = 1.8       # xGA média acima disso -> -1 (não é bloco, é fragilidade)


def nota_bloco_baixo(media_posse, media_xga):
    nota_base = 6 - nota_posse(media_posse)  # espelha a faixa de posse (posse baixa -> nota alta)
    if media_xga is not None and media_xga < PARAM_XGA_DEFESA_ORGANIZADA:
        nota_base += 1
    elif media_xga is not None and media_xga > PARAM_XGA_TIME_DOMINADO:
        nota_base -= 1
    return _clamp(nota_base)


# ---- Pressão Alta — proxy mais fraco: domínio territorial ----
# (posse + produção ofensiva própria: escanteios e chutes a favor)
PARAM_FAIXAS_ESCANTEIOS_PRO = [(3, 1), (4.5, 2), (6, 3), (7.5, 4), (None, 5)]
PARAM_FAIXAS_CHUTES_PRO = [(8, 1), (11, 2), (14, 3), (17, 4), (None, 5)]


def nota_pressao_alta(media_posse, media_escanteios_pro, media_chutes_pro):
    sub_notas = [nota_posse(media_posse)]
    if media_escanteios_pro is not None:
        sub_notas.append(_faixa(media_escanteios_pro, PARAM_FAIXAS_ESCANTEIOS_PRO))
    if media_chutes_pro is not None:
        sub_notas.append(_faixa(media_chutes_pro, PARAM_FAIXAS_CHUTES_PRO))
    return _clamp(round(sum(sub_notas) / len(sub_notas)))


# ---- Transição Rápida — proxy mais fraco: eficiência ofensiva com pouca posse ----
# razão = xG produzido / posse média (times que criam perigo sem precisar da bola)
PARAM_FAIXAS_RAZAO_TRANSICAO = [(0.015, 1), (0.022, 2), (0.030, 3), (0.040, 4), (None, 5)]


def nota_transicao(media_posse, media_xgf):
    if not media_posse or media_xgf is None:
        return 3  # neutro quando falta dado
    razao = media_xgf / media_posse
    return _faixa(razao, PARAM_FAIXAS_RAZAO_TRANSICAO)


# ---- Bola Parada/Físico — proxy mais fraco: físico (faltas/cartões) + ameaça em bola parada (escanteios a favor) ----
PARAM_FAIXAS_CARTOES = [(1.0, 1), (1.5, 2), (2.2, 3), (3.0, 4), (None, 5)]


def nota_bola_parada(media_cartoes, media_escanteios_pro):
    sub_notas = []
    if media_cartoes is not None:
        sub_notas.append(_faixa(media_cartoes, PARAM_FAIXAS_CARTOES))
    if media_escanteios_pro is not None:
        sub_notas.append(_faixa(media_escanteios_pro, PARAM_FAIXAS_ESCANTEIOS_PRO))
    if not sub_notas:
        return 3
    return _clamp(round(sum(sub_notas) / len(sub_notas)))


def calcular_notas_estilo(ultimos_jogos):
    """Calcula as 5 notas de estilo a partir dos últimos jogos de um time.

    `ultimos_jogos`: lista de dicts no formato de `get_historico` (o
    chamador já deve ter cortado para os últimos N jogos, tipicamente 5 —
    ver `N_JOGOS_PADRAO`).

    Retorna dict com `bb`, `pa`, `tr`, `pos`, `bp` (cada um em 1-5) e
    `n_jogos` (quantos jogos entraram na média — útil pra sinalizar amostra
    pequena).
    """
    if not ultimos_jogos:
        raise ValueError("ultimos_jogos não pode ser vazio")

    media_posse = _media(ultimos_jogos, "posf")
    media_xga = _media(ultimos_jogos, "xga")
    media_xgf = _media(ultimos_jogos, "xgf")
    media_escanteios_pro = _media(ultimos_jogos, "cf")
    media_chutes_pro = _media(ultimos_jogos, "sf")
    media_faltas = _media(ultimos_jogos, "ff")
    media_cartoes_amarelos = _media(ultimos_jogos, "yf")
    media_cartoes = None
    if media_faltas is not None and media_cartoes_amarelos is not None:
        # físico = faltas + cartões (proxy combinado de agressividade)
        media_cartoes = (media_faltas / 10) + media_cartoes_amarelos

    if media_posse is None:
        raise ValueError("nenhum jogo com dado de posse (posf) — não dá pra calcular estilo")

    return dict(
        bb=nota_bloco_baixo(media_posse, media_xga),
        pa=nota_pressao_alta(media_posse, media_escanteios_pro, media_chutes_pro),
        tr=nota_transicao(media_posse, media_xgf),
        pos=nota_posse(media_posse),
        bp=nota_bola_parada(media_cartoes, media_escanteios_pro),
        n_jogos=len(ultimos_jogos),
    )


def atualizar_banco_estilo(times_df_map, estilo_db_path, n=N_JOGOS_PADRAO):
    """Recalcula e SOBRESCREVE as notas de estilo de vários times no banco
    JSON persistente — o banco vira um cache sempre atualizado, não mais
    editado à mão.

    `times_df_map`: dict {time: lista_de_jogos_mais_recentes_primeiro}, já
    filtrada aos últimos `n` jogos de cada time (tipicamente vinda de
    `planilha_lib.get_historico(time, df, n=n)`).

    Retorna dict {time: notas_calculadas} (mesmo que grava no arquivo).
    """
    import json
    import os

    banco = {}
    if os.path.exists(estilo_db_path):
        with open(estilo_db_path, encoding="utf-8") as f:
            banco = json.load(f)

    calculadas = {}
    for time, jogos in times_df_map.items():
        notas = calcular_notas_estilo(jogos[:n])
        calculadas[time] = notas
        banco[time] = dict(
            estilo_text=banco.get(time, {}).get("estilo_text", ""),
            bb=notas["bb"], pa=notas["pa"], tr=notas["tr"],
            pos=notas["pos"], bp=notas["bp"],
        )

    with open(estilo_db_path, "w", encoding="utf-8") as f:
        json.dump(banco, f, ensure_ascii=False, indent=2, sort_keys=True)

    return calculadas
