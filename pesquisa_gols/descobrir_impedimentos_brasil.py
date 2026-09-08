"""
Exploração de condições para Impedimentos, restrita ao Brasil (pedido do
usuário: "só para Brasil") — descoberta na Série A (648, treino+teste
cronológico, como sempre), confirmação na Série B (651), sem misturar as
duas ligas na etapa de descoberta (mesma disciplina de buscar_multiliga.py).

Reaproveita os dados JÁ COLETADOS em dados/.checkpoint_648.json e
.checkpoint_651.json — nenhuma chamada nova de API. "offsides" já é uma
candidata coletada em todo snapshot (usada hoje como preditor de escanteios,
ex.: "Impedimentos <= 1"), então dá pra rodar isso inteiramente do cache.

APROXIMAÇÃO IMPORTANTE (documentada, não escondida): o valor final de
impedimentos usado aqui é o snapshot do minuto 90 (o último checkpoint
salvo), não o total real de fim de jogo — os snapshots deste pipeline só
guardam os checkpoints 15/30/45/60/75/90 (ver buscar_sportmonks.CHECKPOINTS),
não o último ponto real dos trends (esse "final de verdade" só é calculado
em resultados_finais_dos_alvos, no momento da coleta, pra alvos que já
existiam quando cada fixture foi buscada). Isso SUBESTIMA sistematicamente
o total de impedimentos que acontecem no acréscimo — então os números aqui
são só para uma checagem exploratória barata ("vale a pena investigar mais
a fundo?"); se algo aparecer promissor, o próximo passo é recotar as
fixtures do Brasil com o total real (minuto 999) antes de considerar
qualquer regra pronta para produção.

Uso: python3 descobrir_impedimentos_brasil.py
"""
import json
import os

import alvos
import buscar_multiliga as bm
import config
from matriz_padrao import CORRELACAO_GOLS_PADRAO

ALVO_ID = "impedimentos"
LIGA_DESCOBERTA = 648  # Série A
LIGA_CONFIRMACAO = 651  # Série B


def _carregar_com_impedimentos(league_id):
    caminho = os.path.join(config.DIR_DADOS, f".checkpoint_{league_id}.json")
    d = json.load(open(caminho, encoding="utf-8"))

    # Chaves mantidas como string (igual d["jogos"]/d["resultados_alvo"] cru,
    # do jeito que vêm do JSON) — dividir_treino_teste cruza jogos x
    # gols_finais pela mesma chave; misturar int/str aqui faz o cruzamento
    # falhar silenciosamente (0 treino, 0 teste, bug real encontrado rodando
    # este script pela primeira vez).
    finais_por_fixture = {}
    for snap in d["snapshots"]:
        if snap["minuto"] != 90:
            continue
        finais_por_fixture[str(snap["fixture_id"])] = snap["offsides"]

    resultados_alvo = {}
    for fid_str, r in d["resultados_alvo"].items():
        r = dict(r)
        if fid_str in finais_por_fixture:
            r["impedimentos"] = finais_por_fixture[fid_str]
        resultados_alvo[fid_str] = r

    candidatas = sorted(set(d["candidatas"]) - alvos.CAMPOS_SO_ALVO)
    return {
        "jogos": d["jogos"],
        "resultados_alvo": resultados_alvo,
        "gols_finais": {fid: r["gols"] for fid, r in resultados_alvo.items()},
        "matriz": dict(CORRELACAO_GOLS_PADRAO),
        "candidatas": candidatas,
        "snapshots": d["snapshots"],
    }


def rodar():
    dados_descoberta = _carregar_com_impedimentos(LIGA_DESCOBERTA)
    com_impedimentos_desc = sum(1 for r in dados_descoberta["resultados_alvo"].values() if r.get("impedimentos") is not None)
    print(f"Série A (descoberta): {len(dados_descoberta['jogos'])} jogos, {com_impedimentos_desc} com impedimentos final (aprox. 90')")

    dados_confirmacao = _carregar_com_impedimentos(LIGA_CONFIRMACAO)
    com_impedimentos_conf = sum(1 for r in dados_confirmacao["resultados_alvo"].values() if r.get("impedimentos") is not None)
    print(f"Série B (confirmação): {len(dados_confirmacao['jogos'])} jogos, {com_impedimentos_conf} com impedimentos final (aprox. 90')")

    resumo = bm.rodar_alvo(ALVO_ID, dados_descoberta, dados_confirmacao)
    print(f"\n{'='*70}\nResumo Impedimentos (Brasil)\n{'='*70}")
    print(f"{alvos.ALVOS[ALVO_ID]['nome']}: {resumo['validados_1stat']} + {resumo['validados_2stats']} "
          f"validadas na Série A (1/2 stats) -> {resumo['confirmados_1stat']} + {resumo['confirmados_2stats']} "
          f"confirmadas na Série B")


if __name__ == "__main__":
    rodar()
