"""
Define os "alvos" (o que estamos tentando prever) além de gols: escanteios,
cartões, chutes totais e chutes no alvo. Cada alvo especifica:

- campos_base: nome(s) de estatística da Snapshots a somar (casa+fora) pra
  achar o resultado final da partida naquele quesito. Uma lista porque
  "cartões" é a soma de dois campos (amarelos + vermelhos).
- linhas: valores de corte no estilo linha de aposta (terminados em .5 pra
  nunca empatar exatamente em cima da linha — útil pra maioria dos mercados,
  diferente de gols, que usa linhas inteiras por convenção já estabelecida).

O restante do pipeline (probabilidades.py, buscar_condicoes.py,
estatistica.py) não muda nada — só precisa receber, pra cada alvo, um dict
diferente de "resultado final por jogo" e uma lista de candidatas que
exclua o(s) campo(s) do próprio alvo (evita testar "escanteios prevê
escanteios").
"""
from matriz_padrao import CORRELACAO_GOLS_PADRAO

ALVOS = {
    "gols": {
        "nome": "Gols",
        "campos_base": ["goals"],
        "linhas": [1, 2, 3, 4],
    },
    "btts": {
        "nome": "Ambas Marcam (BTTS)",
        # Diferente dos outros alvos: não é soma de nenhuma candidata (é
        # derivado de gols_casa/gols_fora finais, que nem entram no pool de
        # snapshots) — por isso campos_base vazio, não exclui nada extra do
        # pool de candidatas. resultado final já vem pronto como 0/1 direto
        # de resultados_alvo[fid]["btts"] (injetado à parte, ver conversa).
        "campos_base": [],
        # Só 1 linha possível — BTTS já é binário (0 ou 1), "+1" = ambas
        # marcaram (valor final >= 1), "-1" = não (valor final < 1). Não faz
        # sentido testar outras linhas pra um alvo 0/1.
        "linhas": [1],
    },
    "escanteios": {
        "nome": "Escanteios",
        "campos_base": ["corners"],
        "linhas": [7.5, 8.5, 9.5, 10.5, 11.5],
    },
    "cartoes": {
        "nome": "Cartões",
        "campos_base": ["yellowcards", "redcards"],
        "linhas": [1.5, 2.5, 3.5, 4.5, 5.5],
    },
    "impedimentos": {
        "nome": "Impedimentos",
        "campos_base": ["offsides"],
        "linhas": [1.5, 2.5, 3.5, 4.5, 5.5],
    },
    "chutes_totais": {
        "nome": "Chutes totais",
        "campos_base": ["shots_total"],
        "linhas": [18.5, 20.5, 22.5, 24.5, 26.5, 28.5],
    },
    "chutes_no_alvo": {
        "nome": "Chutes no alvo",
        "campos_base": ["shots_on_target"],
        "linhas": [6.5, 7.5, 8.5, 9.5, 10.5],
    },
}

# Além das ~22 já usadas pra prever gols, essas ajudam principalmente pra
# cartões (jogo mais faltoso/disputado) e como preditoras cruzadas entre
# mercados (ex.: interceptações como preditor de escanteios).
CANDIDATAS_EXTRAS = {"fouls", "tackles", "interceptions", "duels_won"}

# Campos que só existem pra servir de ALVO (nunca como preditor) — cartões
# em si não entram no pool de candidatas de nenhum alvo.
CAMPOS_SO_ALVO = {"yellowcards", "redcards"}

CANDIDATAS_TODAS = sorted(set(CORRELACAO_GOLS_PADRAO) | CANDIDATAS_EXTRAS)

# Superset de campos que buscar_sportmonks.py precisa resolver/buscar da API
# pra dar conta de todos os alvos de uma vez (evita buscar de novo por alvo).
CAMPOS_PARA_BUSCAR = sorted(set(CANDIDATAS_TODAS) | CAMPOS_SO_ALVO)


def mercados_do_alvo(alvo_id):
    """Lista de mercados '+linha'/'-linha' (formato já usado por probabilidades.mercado_bate)."""
    mercados = []
    for linha in ALVOS[alvo_id]["linhas"]:
        mercados.append(f"+{linha}")
        mercados.append(f"-{linha}")
    return mercados


# Estatísticas que são partes mecânicas do MESMO fenômeno do alvo, não só o
# próprio campo-base. Achado ao rodar chutes_totais/chutes_no_alvo em escala:
# shots_total ≈ shots_on_target + shots_off_target + shots_blocked (partição
# por resultado) e shots_total ≈ shots_insidebox + shots_outsidebox (partição
# por local) — e "saves" de um time reflete quase 1:1 os chutes no alvo do
# adversário. Deixar essas como "candidatas" não é achar um sinal preditivo,
# é medir "resultado parcial de X prevê resultado final de X" — 57-78% das
# condições "validadas" antes desta correção eram exatamente isso.
#
# key_passes entrou nesta lista em 18/09/2026, no estudo das ligas novas: 87%
# das famílias com as 3 vias concordando dependiam dele. Key pass é, por
# definição, passe que resulta em finalização — ou seja, contagem PARCIAL de
# chutes, o mesmo vazamento descrito acima. Medido nas 5 ligas aos 30':
# key_passes <= shots_total em ~99% dos snapshots, correlação 0,77-0,83 (todas
# as outras candidatas ficam em 0,15-0,28) e razão key_passes/chutes 0,68-0,72.
# Teste direto (MLS, 30', 0x0, alvo +24.5): "key_passes>=5" dá +35,3pp e o
# shots_total cru (>=6) dá +38,8pp — é proxy PIOR do óbvio, não sinal novo.
#
# Só em chutes_totais: contra chutes_NO_ALVO a relação se inverte (correlação
# 0,41-0,50, key_passes MAIOR que o alvo em ~82% dos snapshots, razão ~2,0).
# Lá não há contenção mecânica, e excluir seria perder preditor legítimo.
EXCLUSOES_EXTRAS = {
    "chutes_totais": {"shots_on_target", "shots_insidebox", "shots_outsidebox", "shots_blocked", "goal_attempts", "saves", "key_passes"},
    "chutes_no_alvo": {"shots_total", "shots_insidebox", "shots_outsidebox", "shots_blocked", "goal_attempts", "saves"},
}


def candidatas_do_alvo(alvo_id, candidatas_disponiveis):
    """Remove os campos-base do próprio alvo (e partes mecânicas do mesmo fenômeno) da lista de candidatas."""
    excluidos = set(ALVOS[alvo_id]["campos_base"]) | EXCLUSOES_EXTRAS.get(alvo_id, set())
    return [c for c in candidatas_disponiveis if c not in excluidos]
