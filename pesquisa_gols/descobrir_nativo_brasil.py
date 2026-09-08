"""
Descoberta NATIVA no Brasil: Série A (648) como liga de descoberta (split
cronológico treino/teste, mesmo motor de buscar_condicoes.py), Série B (651)
como confirmação — sem depender em nada da Allsvenskan.

Pergunta que isso responde (ver conversa): faz sentido usar só a Allsvenskan
como liga de descoberta pra TODAS as regiões, inclusive Brasil? Hoje
confirmar_brasil.py só reconfirma condições JÁ descobertas na Allsvenskan —
nunca deixa o Brasil propor sua própria hipótese. O limite exato de cada
condição (ex.: "Faltas <= 12") é calibrado na distribuição sueca de cada
estatística; se o volume típico no Brasil for sistematicamente diferente, o
corte ótimo pro Brasil pode ser outro — e a Allsvenskan nunca vai propor esse
corte porque ela nunca testa a distribuição do Brasil.

Já existe um precedente igual: descobrir_impedimentos_brasil.py fez
exatamente isso pra impedimentos (resultado nulo, mas provou o mecanismo).
Este script generaliza pros alvos que já têm regras em produção: escanteios,
chutes_totais, chutes_no_alvo, cartões.

CUIDADO (documentado, não é óbvio): buscar_multiliga.rodar_alvo() faz esse
mesmo trabalho, mas escreve em nomes de arquivo FIXOS
({alvo}_allsvenskan_condicoes_*.csv, {alvo}_confirmacao_*.csv) — chamá-la
aqui SOBRESCREVERIA os arquivos de verdade da Allsvenskan, dos quais
confirmar_brasil.py e gerar_regras_sinais.py dependem (achado real de uma
sessão anterior: um erro parecido corrompeu um checkpoint). Por isso este
script NÃO usa rodar_alvo — reimplementa os mesmos passos com as MESMAS
funções (buscar_condicoes.buscar_1stat/buscar_2stats,
bm.confirmar_1stat/confirmar_2stats/aplicar_bh_confirmacao/salvar_csv),
salvando em nomes de arquivo próprios, que não colidem com nada existente:
  - {alvo}_serieA_condicoes_1stat.csv / _2stats.csv   (descoberta)
  - {alvo}_confirmacao_serieB_1stat.csv / _2stats.csv (confirmação)

Reaproveita os checkpoints já em cache (.checkpoint_648.json,
.checkpoint_651.json) — bs.buscar() só busca fixtures que ainda não estão
neles, nenhuma re-coleta do zero.

Uso: python3 descobrir_nativo_brasil.py
"""
import os

import alvos
import buscar_condicoes
import buscar_multiliga as bm
import buscar_sportmonks as bs
import config
import sportmonks as sm

DATE_FROM = "2024-01-01"
DATE_TO = "2026-12-31"
SERIE_A_ID = 648
SERIE_B_ID = 651
ALVOS_NATIVOS = ["escanteios", "chutes_totais", "chutes_no_alvo", "cartoes"]


def buscar_dados_brutos():
    print("Buscando tipos de estatística...")
    tipos_disponiveis = sm.mapa_types()

    print(f"\nBuscando Série A ({DATE_FROM} a {DATE_TO}, liga de descoberta)...")
    dados_serieA = bs.buscar(
        DATE_FROM, DATE_TO, league_id=SERIE_A_ID, tipos_disponiveis=tipos_disponiveis,
        caminho_checkpoint=os.path.join(config.DIR_DADOS, f".checkpoint_{SERIE_A_ID}.json"),
    )
    print(f"  {len(dados_serieA['jogos'])} jogos, {len(dados_serieA['gols_finais'])} com resultado, "
          f"{len(dados_serieA['snapshots'])} snapshots")

    print(f"\nBuscando Série B ({DATE_FROM} a {DATE_TO}, confirmação)...")
    dados_serieB = bs.buscar(
        DATE_FROM, DATE_TO, league_id=SERIE_B_ID, tipos_disponiveis=tipos_disponiveis,
        caminho_checkpoint=os.path.join(config.DIR_DADOS, f".checkpoint_{SERIE_B_ID}.json"),
    )
    print(f"  {len(dados_serieB['jogos'])} jogos, {len(dados_serieB['gols_finais'])} com resultado, "
          f"{len(dados_serieB['snapshots'])} snapshots")

    return dados_serieA, dados_serieB


def rodar_alvo_nativo(alvo_id, dados_serieA_bruto, dados_serieB_bruto):
    definicao = alvos.ALVOS[alvo_id]
    print(f"\n{'='*70}\nAlvo: {definicao['nome']} ({alvo_id}) — descoberta nativa Brasil\n{'='*70}")

    config.MERCADOS = alvos.mercados_do_alvo(alvo_id)
    dados_serieA = bm.dados_do_alvo(dados_serieA_bruto, alvo_id)
    dados_serieB = bm.dados_do_alvo(dados_serieB_bruto, alvo_id)

    treino_ids, teste_ids = buscar_condicoes.dividir_treino_teste(dados_serieA["jogos"], dados_serieA["gols_finais"])
    print(f"  split cronológico (Série A): {len(treino_ids)} treino, {len(teste_ids)} teste "
          f"({len(dados_serieA['candidatas'])} candidatas, mercados: {', '.join(config.MERCADOS)})")

    validados_1stat, pool_pareamento, exploratorios = buscar_condicoes.buscar_1stat(dados_serieA, treino_ids, teste_ids)
    validados_2stats = buscar_condicoes.buscar_2stats(dados_serieA, pool_pareamento, treino_ids, teste_ids)
    print(f"  {len(validados_1stat)} condições de 1 estatística validadas dentro da Série A")
    print(f"  {len(validados_2stats)} combinações de 2 estatísticas validadas dentro da Série A")

    bm.salvar_csv(os.path.join(config.DIR_RESULTADOS, f"{alvo_id}_serieA_condicoes_1stat.csv"), validados_1stat)
    bm.salvar_csv(os.path.join(config.DIR_RESULTADOS, f"{alvo_id}_serieA_condicoes_2stats.csv"), validados_2stats)
    bm.salvar_csv(os.path.join(config.DIR_RESULTADOS, f"{alvo_id}_serieA_exploratorio_1stat.csv"), exploratorios)

    print("  Confirmando condições de 1 estatística na Série B...")
    confirmadas_1stat = [c for c in (bm.confirmar_1stat(cond, dados_serieB) for cond in validados_1stat) if c]
    confirmadas_1stat = bm.aplicar_bh_confirmacao(confirmadas_1stat)
    n_conf_1 = sum(1 for c in confirmadas_1stat if c["confirmado_bh"])
    print(f"    {n_conf_1} de {len(confirmadas_1stat)} sobrevivem ao teste estatístico formal (BH) na Série B")

    print("  Confirmando combinações de 2 estatísticas na Série B...")
    confirmadas_2stats = [c for c in (bm.confirmar_2stats(cond, dados_serieB) for cond in validados_2stats) if c]
    confirmadas_2stats = bm.aplicar_bh_confirmacao(confirmadas_2stats)
    n_conf_2 = sum(1 for c in confirmadas_2stats if c["confirmado_bh"])
    print(f"    {n_conf_2} de {len(confirmadas_2stats)} sobrevivem ao teste estatístico formal (BH) na Série B")

    caminho_1 = os.path.join(config.DIR_RESULTADOS, f"{alvo_id}_confirmacao_serieB_1stat.csv")
    caminho_2 = os.path.join(config.DIR_RESULTADOS, f"{alvo_id}_confirmacao_serieB_2stats.csv")
    bm.salvar_csv(caminho_1, confirmadas_1stat)
    bm.salvar_csv(caminho_2, confirmadas_2stats)
    print(f"  Salvo em {caminho_1} e {caminho_2}")

    return {
        "validados_1stat": len(validados_1stat), "validados_2stats": len(validados_2stats),
        "confirmados_1stat": n_conf_1, "confirmados_2stats": n_conf_2,
    }


def rodar():
    dados_serieA_bruto, dados_serieB_bruto = buscar_dados_brutos()

    resumo = {}
    for alvo_id in ALVOS_NATIVOS:
        resumo[alvo_id] = rodar_alvo_nativo(alvo_id, dados_serieA_bruto, dados_serieB_bruto)

    print(f"\n{'='*70}\nResumo geral — descoberta nativa Brasil (Série A -> Série B)\n{'='*70}")
    for alvo_id, r in resumo.items():
        print(f"{alvos.ALVOS[alvo_id]['nome']:16s}: {r['validados_1stat']:2d} + {r['validados_2stats']:2d} validadas na "
              f"Série A (1/2 stats) -> {r['confirmados_1stat']} + {r['confirmados_2stats']} confirmadas na Série B")


if __name__ == "__main__":
    rodar()
