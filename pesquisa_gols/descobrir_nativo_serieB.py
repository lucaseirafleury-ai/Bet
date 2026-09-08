"""
Descoberta NATIVA com Série B (651) como liga de descoberta, Série A (648)
como confirmação — o espelho invertido de descobrir_nativo_brasil.py (que
usa Série A pra descobrir, Série B pra confirmar).

Por quê (ver conversa): descobrir_nativo_brasil.py só deixa a Série A propor
hipóteses — a Série B nunca teve chance de sugerir seu PRÓPRIO limite ótimo,
só de confirmar o que a Série A (ou a Allsvenskan) já tinha decidido testar.
Achado real que motivou isso: testando o MESMO limite de faltas (herdado da
Allsvenskan) separadamente em cada série, a sensibilidade a faltas prevendo
cartões é maior na Série B na segunda metade do jogo (ex.: aos 60', impacto
-12.4pp na Série B contra -10.2pp na Série A) mas maior na Série A no início
do jogo (aos 30', 0x0) — ou seja, o limite ideal pode ser diferente por
série, não só a magnitude do mesmo limite. Rodar descoberta nativa também
pela Série B fecha essa lacuna.

CUIDADO (mesmo motivo documentado nos outros scripts de descoberta nativa):
não usa buscar_multiliga.rodar_alvo() (sobrescreveria os arquivos da
Allsvenskan) — reimplementa os mesmos passos, salvando em nomes próprios:
  - {alvo}_serieB_condicoes_1stat.csv / _2stats.csv     (descoberta)
  - {alvo}_confirmacao_serieA_1stat.csv / _2stats.csv   (confirmação)

Reaproveita os checkpoints já em cache (.checkpoint_648.json,
.checkpoint_651.json) — nenhuma chamada nova de API.

Uso: python3 descobrir_nativo_serieB.py
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

    print(f"\nBuscando Série B ({DATE_FROM} a {DATE_TO}, liga de descoberta)...")
    dados_serieB = bs.buscar(
        DATE_FROM, DATE_TO, league_id=SERIE_B_ID, tipos_disponiveis=tipos_disponiveis,
        caminho_checkpoint=os.path.join(config.DIR_DADOS, f".checkpoint_{SERIE_B_ID}.json"),
    )
    print(f"  {len(dados_serieB['jogos'])} jogos, {len(dados_serieB['gols_finais'])} com resultado, "
          f"{len(dados_serieB['snapshots'])} snapshots")

    print(f"\nBuscando Série A ({DATE_FROM} a {DATE_TO}, confirmação)...")
    dados_serieA = bs.buscar(
        DATE_FROM, DATE_TO, league_id=SERIE_A_ID, tipos_disponiveis=tipos_disponiveis,
        caminho_checkpoint=os.path.join(config.DIR_DADOS, f".checkpoint_{SERIE_A_ID}.json"),
    )
    print(f"  {len(dados_serieA['jogos'])} jogos, {len(dados_serieA['gols_finais'])} com resultado, "
          f"{len(dados_serieA['snapshots'])} snapshots")

    return dados_serieB, dados_serieA


def rodar_alvo_nativo(alvo_id, dados_serieB_bruto, dados_serieA_bruto):
    definicao = alvos.ALVOS[alvo_id]
    print(f"\n{'='*70}\nAlvo: {definicao['nome']} ({alvo_id}) — descoberta nativa Série B\n{'='*70}")

    config.MERCADOS = alvos.mercados_do_alvo(alvo_id)
    dados_serieB = bm.dados_do_alvo(dados_serieB_bruto, alvo_id)
    dados_serieA = bm.dados_do_alvo(dados_serieA_bruto, alvo_id)

    treino_ids, teste_ids = buscar_condicoes.dividir_treino_teste(dados_serieB["jogos"], dados_serieB["gols_finais"])
    print(f"  split cronológico (Série B): {len(treino_ids)} treino, {len(teste_ids)} teste "
          f"({len(dados_serieB['candidatas'])} candidatas, mercados: {', '.join(config.MERCADOS)})")

    validados_1stat, pool_pareamento, exploratorios = buscar_condicoes.buscar_1stat(dados_serieB, treino_ids, teste_ids)
    validados_2stats = buscar_condicoes.buscar_2stats(dados_serieB, pool_pareamento, treino_ids, teste_ids)
    print(f"  {len(validados_1stat)} condições de 1 estatística validadas dentro da Série B")
    print(f"  {len(validados_2stats)} combinações de 2 estatísticas validadas dentro da Série B")

    bm.salvar_csv(os.path.join(config.DIR_RESULTADOS, f"{alvo_id}_serieB_condicoes_1stat.csv"), validados_1stat)
    bm.salvar_csv(os.path.join(config.DIR_RESULTADOS, f"{alvo_id}_serieB_condicoes_2stats.csv"), validados_2stats)
    bm.salvar_csv(os.path.join(config.DIR_RESULTADOS, f"{alvo_id}_serieB_exploratorio_1stat.csv"), exploratorios)

    print("  Confirmando condições de 1 estatística na Série A...")
    confirmadas_1stat = [c for c in (bm.confirmar_1stat(cond, dados_serieA) for cond in validados_1stat) if c]
    confirmadas_1stat = bm.aplicar_bh_confirmacao(confirmadas_1stat)
    n_conf_1 = sum(1 for c in confirmadas_1stat if c["confirmado_bh"])
    print(f"    {n_conf_1} de {len(confirmadas_1stat)} sobrevivem ao teste estatístico formal (BH) na Série A")

    print("  Confirmando combinações de 2 estatísticas na Série A...")
    confirmadas_2stats = [c for c in (bm.confirmar_2stats(cond, dados_serieA) for cond in validados_2stats) if c]
    confirmadas_2stats = bm.aplicar_bh_confirmacao(confirmadas_2stats)
    n_conf_2 = sum(1 for c in confirmadas_2stats if c["confirmado_bh"])
    print(f"    {n_conf_2} de {len(confirmadas_2stats)} sobrevivem ao teste estatístico formal (BH) na Série A")

    caminho_1 = os.path.join(config.DIR_RESULTADOS, f"{alvo_id}_confirmacao_serieA_1stat.csv")
    caminho_2 = os.path.join(config.DIR_RESULTADOS, f"{alvo_id}_confirmacao_serieA_2stats.csv")
    bm.salvar_csv(caminho_1, confirmadas_1stat)
    bm.salvar_csv(caminho_2, confirmadas_2stats)
    print(f"  Salvo em {caminho_1} e {caminho_2}")

    return {
        "validados_1stat": len(validados_1stat), "validados_2stats": len(validados_2stats),
        "confirmados_1stat": n_conf_1, "confirmados_2stats": n_conf_2,
    }


def rodar():
    dados_serieB_bruto, dados_serieA_bruto = buscar_dados_brutos()

    resumo = {}
    for alvo_id in ALVOS_NATIVOS:
        resumo[alvo_id] = rodar_alvo_nativo(alvo_id, dados_serieB_bruto, dados_serieA_bruto)

    print(f"\n{'='*70}\nResumo geral — descoberta nativa Série B (Série B -> Série A)\n{'='*70}")
    for alvo_id, r in resumo.items():
        print(f"{alvos.ALVOS[alvo_id]['nome']:16s}: {r['validados_1stat']:2d} + {r['validados_2stats']:2d} validadas na "
              f"Série B (1/2 stats) -> {r['confirmados_1stat']} + {r['confirmados_2stats']} confirmadas na Série A")


if __name__ == "__main__":
    rodar()
