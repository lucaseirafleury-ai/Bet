"""
Configurações da pesquisa de probabilidades de gols.

Fase 1 (atual): pesquisa isolada, independente do ligas_live_app. Só depois
de validar quais condições realmente se sustentam fora da amostra é que elas
devem virar um mercado calibrado dentro do app (ver README.md, seção "Fase 2").
"""

# Arquivo(s) de entrada: cada um precisa ter as abas Jogos, Snapshots e
# Stats_Finais no mesmo formato da planilha original (ver README.md). A aba
# Matriz é opcional — se faltar, usa o padrão embutido em matriz_padrao.py.
# Pode listar mais de um arquivo (ex.: temporadas diferentes da mesma liga)
# para juntar tudo num único dataset antes da busca.
ARQUIVOS_ENTRADA = [
    "dados/Allsvenskan_2025_snapshots_r01.xlsx",
    "dados/Allsvenskan_2026_snapshots.xlsx",
]

DIR_RESULTADOS = "resultados"
DIR_DADOS = "dados"

# Mercados de total de gols na partida avaliados.
# "+N" = pelo menos N gols na partida; "-N" = menos de N gols na partida.
MERCADOS = ["+4", "+3", "+2", "+1", "-1", "-2", "-3", "-4"]

# Fração (cronológica, por rodada) usada como treino. O restante — as rodadas
# mais recentes — vira teste. Nunca embaralhar: o objetivo é simular o que
# seria descoberto só com dados passados e confirmado em dados futuros.
FRACAO_TREINO = 0.7

# Amostra mínima (nº de jogos) para uma condição ser sequer considerada,
# tanto no treino quanto no teste.
AMOSTRA_MINIMA = 30

# Nível de significância aceito, DEPOIS da correção de Benjamini-Hochberg
# para múltiplas comparações (essencial dado o volume de condições testadas).
ALFA = 0.05

# Impacto mínimo (em pontos percentuais, |P Final - P Base|) para uma condição
# ser reportada — evita destacar efeitos estatisticamente "significativos" mas
# pequenos demais para importar na prática.
IMPACTO_MINIMO_PP = 5.0

# Barra mais baixa, só para uma condição individual entrar no POOL de
# candidatas a formar par com outra estatística. É mais baixa de propósito:
# duas estatísticas fracas sozinhas podem ter um efeito conjunto real (efeito
# de interação) que nenhuma das duas mostra isoladamente — exigir que cada
# metade já validasse sozinha (como uma primeira versão deste pipeline fazia)
# descartava esse tipo de combinação antes mesmo de testá-la.
IMPACTO_MINIMO_PAREAMENTO_PP = 2.0

# Quantos limites (thresholds) testar por estatística, com base nos quantis
# observados da própria estatística no treino (em vez de testar todo valor
# inteiro possível, o que infla o número de comparações à toa).
NUM_LIMITES_TESTADOS = 5

# Ao revalidar no teste, quanto do impacto observado no treino a condição
# precisa reter (mesma direção) para ser considerada confirmada.
FRACAO_MINIMA_IMPACTO_TESTE = 0.5

# Tolerância de estabilidade usada na comparação de efeito conjunto (2 stats),
# no mesmo espírito da regra já documentada na planilha original.
TOLERANCIA_EFEITO_CONJUNTO_PP = 0.5

# Nomes de indicadores que representam o próprio placar/contagem de gols —
# nunca testados como "estatística candidata" porque seriam circulares em
# relação à dimensão "Gols no Momento" já usada como filtro.
INDICADORES_EXCLUIDOS = {"goals", "placar_casa", "placar_fora"}
