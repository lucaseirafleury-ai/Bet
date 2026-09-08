"""
Descoberta + confirmação de condições pra BTTS (Ambas Marcam), reaproveitando
o pipeline já existente (buscar_condicoes.py + buscar_multiliga.py) e os
dados JÁ COLETADOS em dados/.checkpoint_*.json — sem nenhuma chamada nova de
API. O campo "btts" (0/1) foi injetado à parte nesses checkpoints (ver
conversa) a partir só do placar final de cada time, sem precisar refazer a
coleta cara de trends/snapshots.

Mesma disciplina de sempre: descoberta só na Allsvenskan (573), confirmação
nas outras ligas com dado de btts disponível (447, 579, 648, 651 — A Lyga/
1.Lyga ficaram de fora, sem acesso da assinatura atual pra recalcular o
placar delas).

Uso: python3 descobrir_btts.py
"""
import json
import os

import alvos
import buscar_condicoes
import buscar_multiliga as bm
import config
from matriz_padrao import CORRELACAO_GOLS_PADRAO

ALVO_ID = "btts"
LIGA_DESCOBERTA = 573  # Allsvenskan
LIGAS_CONFIRMACAO = [447, 579, 648, 651]  # 1.Division, Superettan, Serie A, Serie B


def _carregar_checkpoint_cru(league_id):
    caminho = os.path.join(config.DIR_DADOS, f".checkpoint_{league_id}.json")
    d = json.load(open(caminho, encoding="utf-8"))
    candidatas = sorted(set(d["candidatas"]) - alvos.CAMPOS_SO_ALVO)
    return {
        "jogos": d["jogos"],
        "resultados_alvo": d["resultados_alvo"],
        "gols_finais": {fid: r["gols"] for fid, r in d["resultados_alvo"].items()},
        "matriz": dict(CORRELACAO_GOLS_PADRAO),
        "candidatas": candidatas,
        "snapshots": d["snapshots"],
    }


def _mesclar(datasets):
    jogos, resultados_alvo, snapshots = {}, {}, []
    for d in datasets:
        jogos.update(d["jogos"])
        resultados_alvo.update(d["resultados_alvo"])
        snapshots.extend(d["snapshots"])
    return {
        "jogos": jogos,
        "resultados_alvo": resultados_alvo,
        "gols_finais": {fid: r["gols"] for fid, r in resultados_alvo.items()},
        "matriz": dict(CORRELACAO_GOLS_PADRAO),
        "candidatas": datasets[0]["candidatas"],
        "snapshots": snapshots,
    }


def rodar():
    dados_allsvenskan_bruto = _carregar_checkpoint_cru(LIGA_DESCOBERTA)
    print(f"Allsvenskan (descoberta): {len(dados_allsvenskan_bruto['jogos'])} jogos, "
          f"{len(dados_allsvenskan_bruto['resultados_alvo'])} com resultado")

    datasets_confirmacao = [_carregar_checkpoint_cru(lid) for lid in LIGAS_CONFIRMACAO]
    dados_confirmacao_bruto = _mesclar(datasets_confirmacao)
    print(f"Confirmação ({', '.join(str(l) for l in LIGAS_CONFIRMACAO)}): "
          f"{len(dados_confirmacao_bruto['jogos'])} jogos, "
          f"{len(dados_confirmacao_bruto['resultados_alvo'])} com resultado")

    resumo = bm.rodar_alvo(ALVO_ID, dados_allsvenskan_bruto, dados_confirmacao_bruto)
    print(f"\n{'='*70}\nResumo BTTS\n{'='*70}")
    print(f"{alvos.ALVOS[ALVO_ID]['nome']}: {resumo['validados_1stat']} + {resumo['validados_2stats']} "
          f"validadas na Allsvenskan (1/2 stats) -> {resumo['confirmados_1stat']} + {resumo['confirmados_2stats']} "
          f"confirmadas nas outras ligas")


if __name__ == "__main__":
    rodar()
