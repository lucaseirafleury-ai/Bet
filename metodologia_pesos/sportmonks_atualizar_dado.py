"""Atualiza `data/sportmonks_{seriea,serieb}/fixtures.jsonl` (histórico
de fixtures finalizados, usado pelo walk-forward e como base de
histórico da previsão ao vivo — `previsao_dia.py`).

Uso: `SPORTMONKS_TOKEN=... python3 sportmonks_atualizar_dado.py`

Roda dentro da rotina diária (`gerar_painel_dia.py`) antes de gerar as
sugestões — não precisa mais de passo manual do Lucas (diferente do
CSV do FootyStats, que era upload manual).

Incremental: `atualizar_fixtures_finalizados` só rebaixa os jogos dos
últimos dias (não as ~1000 fixtures históricas da liga inteira) depois
da 1ª vez — ver docstring em `sportmonks_client.py`.
"""
from __future__ import annotations

import os

from sportmonks_client import LEAGUE_IDS, atualizar_fixtures_finalizados, token

CAMINHO_HIST = {
    "seriea": "data/sportmonks_seriea/fixtures.jsonl",
    "serieb": "data/sportmonks_serieb/fixtures.jsonl",
}


def atualizar_tudo():
    tok = token()
    totais = {}
    for liga, path in CAMINHO_HIST.items():
        os.makedirs(os.path.dirname(path), exist_ok=True)
        totais[liga] = atualizar_fixtures_finalizados(tok, LEAGUE_IDS[liga], path)
    return totais


if __name__ == "__main__":
    totais = atualizar_tudo()
    for liga, total in totais.items():
        print(f"{liga}: {total} fixtures novos salvos em {CAMINHO_HIST[liga]}", flush=True)
