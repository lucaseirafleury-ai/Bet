"""
Script de recuperação pontual: reconstrói dados/.checkpoint_579.json
(Superettan) do zero, depois que um teste manual acidentalmente invalidou o
checkpoint bom (720 jogos) chamando bs.buscar(..., tipos_disponiveis={})
por engano — um dict vazio nunca resolve nenhuma candidata, o que fez
_carregar_checkpoint descartar o checkpoint válido e recomeçar com
candidatas quebradas (ver conversa). Backup do estado quebrado preservado em
dados/.checkpoint_579.json.backup_corrompido, só por precaução/debug.

Correto desta vez: busca tipos_disponiveis de verdade (sm.mapa_types()),
sequencial (sem paralelismo — mais seguro pra rate limit, já validado antes
nesta pesquisa), com o mesmo checkpoint incremental de sempre (retoma sozinho
se cair no meio).

Uso: python3 recuperar_superettan.py
"""
import os

import buscar_sportmonks as bs
import sportmonks as sm

LEAGUE_ID = 579  # Superettan
DATE_FROM = "2024-01-01"
DATE_TO = "2026-12-31"
CAMINHO_CHECKPOINT = os.path.join("dados", ".checkpoint_579.json")


def rodar():
    print("Buscando tipos de estatística (uma vez só)...")
    tipos_disponiveis = sm.mapa_types()
    print(f"  {len(tipos_disponiveis)} tipos carregados")

    print(f"\nRecuperando Superettan ({DATE_FROM} a {DATE_TO})...")
    dados = bs.buscar(
        DATE_FROM, DATE_TO, league_id=LEAGUE_ID, tipos_disponiveis=tipos_disponiveis,
        caminho_checkpoint=CAMINHO_CHECKPOINT,
    )
    print(f"\nConcluído: {len(dados['jogos'])} jogos, {len(dados['resultados_alvo'])} com resultado, "
          f"{len(dados['snapshots'])} snapshots, candidatas={len(dados['candidatas'])}")


if __name__ == "__main__":
    rodar()
