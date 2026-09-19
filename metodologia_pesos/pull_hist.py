"""Recarga completa do histórico das 5 ligas do plano, a partir de um ano.

`python3 pull_hist.py` sobrescreve `data/sportmonks_<liga>/fixtures.jsonl`
de cada liga com tudo de 2015 em diante.

Por que 2015 (medido em 19/09/2026, com o add-on Historical Data ativo):
o plano expõe 22 temporadas, mas a profundidade útil é menor e depende do
que se quer medir — odds só existem de ~2018 (sem odd não dá pra medir
edge), estatística + árbitro de ~2015, e antes de 2015 não vem nada. Puxar
de 2015 aproveita os anos sem odd para engordar a média histórica dos
árbitros, que é o que destrava jogos hoje bloqueados por árbitro sem os
10 jogos mínimos.

Cuidado: sobrescreve o arquivo que a rotina do painel usa. Rodar fora das
janelas da rotina (11h/15h/19h UTC).
"""
import os

from sportmonks_client import puxar_fixtures_finalizados, token

LIGAS = {"seriea": 648, "serieb": 651, "championship": 9, "argentina": 636, "mls": 779}
DESDE_ANO = 2015

if __name__ == "__main__":
    tok = token()
    for chave, league_id in LIGAS.items():
        os.makedirs(f"data/sportmonks_{chave}", exist_ok=True)
        n = puxar_fixtures_finalizados(
            tok, league_id, f"data/sportmonks_{chave}/fixtures.jsonl", desde_ano=DESDE_ANO
        )
        print(f"{chave}: {n} fixtures ({DESDE_ANO}+)", flush=True)
    print("PULL COMPLETO")
