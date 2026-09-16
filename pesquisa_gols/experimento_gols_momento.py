"""
Experimento: quanto o `gols_momento` como chave de partição obrigatória
custa em amostra, e quanto entrega em precisão?

Motivação (medida antes de escrever isto, sobre os 3.876 jogos das 5 ligas):

  CUSTO — a partição fragmenta o pool, e cada vez mais tarde no jogo. A maior
  fatia de gols_momento é 72% dos jogos aos 15min, mas só 30% aos 75min. Como
  gerar_regras_sinais.AMOSTRA_MINIMA é 200, isso estrangula justamente os
  checkpoints tardios, onde o delta até a linha é menor e o sinal seria mais
  confiável.

  INFORMAÇÃO — quase nada, e depende do alvo. Testando o efeito sobre o que
  ainda FALTA acontecer (valor final menos valor atual), de 0 para 2 gols:
    escanteios      -0,20 / +0,02 / -0,06   (nenhum checkpoint significativo)
    chutes no alvo  +0,49 / +0,32 / +0,19   (** / * / não)
    cartões         -0,26 / -0,20 / -0,30   (* / * / ***)
    chutes totais   -0,79 / -0,20 / -0,29   (** / não / não)
  Escanteios é o caso extremo e é onde estão 57 das 105 regras publicadas:
  saber o placar não diz nada sobre quantos escanteios ainda saem.

  E reavaliando as 105 regras publicadas com o critério solto: 1,7x mais
  instâncias (1.663 -> 2.841) por 1,9pp de taxa (74,6% -> 72,7%). Esse 1,9pp
  é um TETO, não o custo real — as regras foram descobertas condicionadas
  àquele placar, então a coluna "com" tem viés de seleção a favor dela.

Este script roda a MESMA descoberta de buscar_multiliga.py com a partição
desligada (gols_momento=None => não filtra), gravando em arquivos separados
com sufixo _poolgols pra não sobrescrever os resultados reais. Depois é só
comparar nº de condições validadas/confirmadas e amostra média.

Não altera nenhum arquivo do pipeline: monkey-patch local de
probabilidades.snapshots_do_bucket, aplicado só dentro deste processo.

Uso: python3 experimento_gols_momento.py
"""
import os
import sys

import probabilidades
import buscar_multiliga as bm
import config

_bucket_original = probabilidades.snapshots_do_bucket


def _bucket_sem_particao(snapshots, gols_finais, minuto, gols_momento, fixture_ids=None):
    """
    Idêntico ao original, menos o filtro por gols_momento.

    BUG pego pelo sanity check abaixo antes da primeira tentativa de rodar
    isto: delegar pro original com gols_momento=None não funciona, porque o
    original compara `snap["gols_momento"] != gols_momento` — com None, essa
    comparação é True pra TODO snapshot real (nenhum tem gols_momento=None),
    então tudo era descartado (0 resultados, não "sem filtro"). Tem que
    reimplementar o corpo sem essa comparação, não tentar contornar via
    argumento.
    """
    resultado = []
    for snap in snapshots:
        if snap["minuto"] != minuto:
            continue
        if fixture_ids is not None and snap["fixture_id"] not in fixture_ids:
            continue
        if snap["fixture_id"] not in gols_finais:
            continue
        resultado.append(snap)
    return resultado


def _patch_bucket():
    """
    Faz snapshots_do_bucket ignorar gols_momento. Precisa remendar TAMBÉM as
    referências já ligadas nos módulos que fizeram `from probabilidades import
    snapshots_do_bucket` — remendar só o atributo do módulo de origem não
    alcança quem já importou o nome direto.
    """
    probabilidades.snapshots_do_bucket = _bucket_sem_particao
    alcancados = ["probabilidades"]
    for nome, mod in list(sys.modules.items()):
        if mod is None or not hasattr(mod, "snapshots_do_bucket"):
            continue
        if getattr(mod, "snapshots_do_bucket") is _bucket_original:
            setattr(mod, "snapshots_do_bucket", _bucket_sem_particao)
            alcancados.append(nome)
    return alcancados


def main():
    # gols_momento=None tem que significar "não filtra" — o original compara
    # snap["gols_momento"] != gols_momento, então None nunca bateria. Confere
    # que o patch faz o que promete antes de rodar 30+ minutos de descoberta.
    snaps = [{"minuto": 30, "gols_momento": g, "fixture_id": g} for g in range(4)]
    gols_finais = {g: 2 for g in range(4)}
    assert len(_bucket_original(snaps, gols_finais, 30, 1)) == 1
    assert len(_bucket_sem_particao(snaps, gols_finais, 30, 1)) == 4
    print("sanidade ok: partição original devolve 1 de 4; sem partição devolve 4 de 4\n")

    alcancados = _patch_bucket()
    print(f"partição desligada em: {', '.join(alcancados)}\n")

    # Sufixo nos arquivos de saída pra não sobrescrever os resultados reais.
    dir_original = config.DIR_RESULTADOS
    dir_exp = os.path.join(dir_original, "poolgols")
    os.makedirs(dir_exp, exist_ok=True)
    config.DIR_RESULTADOS = dir_exp
    bm.config.DIR_RESULTADOS = dir_exp
    print(f"resultados deste experimento vão pra {dir_exp}/ (os reais ficam intactos em {dir_original}/)\n")

    bm.rodar()


if __name__ == "__main__":
    main()
