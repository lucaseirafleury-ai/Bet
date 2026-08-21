"""
Correlação indicador -> mercado de Gols, extraída da aba `Matriz` da planilha
original (Allsvenskan 2025). É conhecimento sobre o que cada estatística do
FootyStats/Sportmonks representa, não dado específico de uma temporada — por
isso vive aqui como padrão do pipeline, em vez de precisar ser recriada (ou
copiada) em cada nova planilha de liga/temporada.

Se um arquivo de entrada tiver sua própria aba `Matriz`, ela tem prioridade
sobre este padrão (ver carregar_dados.carregar_matriz).
"""

CORRELACAO_GOLS_PADRAO = {
    "penalties": "Direto",
    "shots_total": "Indireto forte",
    "goal_attempts": "Indireto forte",
    "shots_on_target": "Direto",
    "shots_blocked": "Indireto fraco",
    "shots_insidebox": "Indireto forte",
    "shots_outsidebox": "Indireto fraco",
    "hit_woodwork": "Direto",
    "big_chances_created": "Direto",
    "big_chances_missed": "Direto",
    "assists": "Direto",
    "corners": "Indireto fraco",
    "total_crosses": "Indireto fraco",
    "accurate_crosses": "Indireto fraco",
    "dangerous_attacks": "Indireto forte",
    "attacks": "Indireto fraco",
    "key_passes": "Indireto forte",
    "saves": "Indireto fraco",
    "successful_dribbles": "Indireto fraco",
    "successful_dribbles_percentage": "Indireto fraco",
    "ball_possession_pct": "Indireto fraco",
    "offsides": "Indireto fraco",
}
