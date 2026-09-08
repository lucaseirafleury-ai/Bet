"""
Descoberta NATIVA dentro das próprias ligas nórdicas: Superettan (579) como
liga de descoberta (split cronológico treino/teste, mesmo motor de
buscar_condicoes.py), 1. Division (447) como confirmação — sem depender da
Allsvenskan em nenhum momento.

Mesma pergunta que motivou descobrir_nativo_brasil.py, só que do lado
nórdico (ver conversa: "não faz sentido só 12 sinais nórdicos"): hoje
Superettan e 1. Division nunca descobrem nada sozinhas, só confirmam o que a
Allsvenskan propõe — um limite calibrado na distribuição da Allsvenskan (liga
de elite) pode não ser o corte ideal pra essas duas ligas de acesso, e um
padrão específico delas nunca teria chance de ser proposto.

Por que Superettan -> 1. Division e não o contrário: escolha arbitrária mas
consistente com o padrão já usado (Série A -> Série B, a liga "maior" como
descoberta) — Superettan é a segunda divisão sueca (mais tradicional/maior
volume de dados históricos no Sportmonks que 1. Division, a segunda divisão
dinamarquesa).

CUIDADO (mesmo motivo documentado em descobrir_nativo_brasil.py):
buscar_multiliga.rodar_alvo() escreve em nomes de arquivo FIXOS
({alvo}_allsvenskan_condicoes_*.csv, {alvo}_confirmacao_*.csv) — usá-la aqui
sobrescreveria os arquivos de verdade da Allsvenskan. Por isso este script
reimplementa os mesmos passos com as MESMAS funções, salvando em nomes
próprios:
  - {alvo}_superettan_condicoes_1stat.csv / _2stats.csv     (descoberta)
  - {alvo}_confirmacao_1divisao_1stat.csv / _2stats.csv     (confirmação)

Reaproveita os checkpoints já em cache (.checkpoint_579.json,
.checkpoint_447.json) — bs.buscar() só busca fixtures que ainda não estão
neles.

Uso: python3 descobrir_nativo_nordicas.py
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
SUPERETTAN_ID = 579
DIVISAO1_ID = 447
ALVOS_NATIVOS = ["escanteios", "chutes_totais", "chutes_no_alvo", "cartoes"]


def buscar_dados_brutos():
    print("Buscando tipos de estatística...")
    tipos_disponiveis = sm.mapa_types()

    print(f"\nBuscando Superettan ({DATE_FROM} a {DATE_TO}, liga de descoberta)...")
    dados_superettan = bs.buscar(
        DATE_FROM, DATE_TO, league_id=SUPERETTAN_ID, tipos_disponiveis=tipos_disponiveis,
        caminho_checkpoint=os.path.join(config.DIR_DADOS, f".checkpoint_{SUPERETTAN_ID}.json"),
    )
    print(f"  {len(dados_superettan['jogos'])} jogos, {len(dados_superettan['gols_finais'])} com resultado, "
          f"{len(dados_superettan['snapshots'])} snapshots")

    print(f"\nBuscando 1. Division ({DATE_FROM} a {DATE_TO}, confirmação)...")
    dados_divisao1 = bs.buscar(
        DATE_FROM, DATE_TO, league_id=DIVISAO1_ID, tipos_disponiveis=tipos_disponiveis,
        caminho_checkpoint=os.path.join(config.DIR_DADOS, f".checkpoint_{DIVISAO1_ID}.json"),
    )
    print(f"  {len(dados_divisao1['jogos'])} jogos, {len(dados_divisao1['gols_finais'])} com resultado, "
          f"{len(dados_divisao1['snapshots'])} snapshots")

    return dados_superettan, dados_divisao1


def rodar_alvo_nativo(alvo_id, dados_superettan_bruto, dados_divisao1_bruto):
    definicao = alvos.ALVOS[alvo_id]
    print(f"\n{'='*70}\nAlvo: {definicao['nome']} ({alvo_id}) — descoberta nativa nórdica\n{'='*70}")

    config.MERCADOS = alvos.mercados_do_alvo(alvo_id)
    dados_superettan = bm.dados_do_alvo(dados_superettan_bruto, alvo_id)
    dados_divisao1 = bm.dados_do_alvo(dados_divisao1_bruto, alvo_id)

    treino_ids, teste_ids = buscar_condicoes.dividir_treino_teste(dados_superettan["jogos"], dados_superettan["gols_finais"])
    print(f"  split cronológico (Superettan): {len(treino_ids)} treino, {len(teste_ids)} teste "
          f"({len(dados_superettan['candidatas'])} candidatas, mercados: {', '.join(config.MERCADOS)})")

    validados_1stat, pool_pareamento, exploratorios = buscar_condicoes.buscar_1stat(dados_superettan, treino_ids, teste_ids)
    validados_2stats = buscar_condicoes.buscar_2stats(dados_superettan, pool_pareamento, treino_ids, teste_ids)
    print(f"  {len(validados_1stat)} condições de 1 estatística validadas dentro da Superettan")
    print(f"  {len(validados_2stats)} combinações de 2 estatísticas validadas dentro da Superettan")

    bm.salvar_csv(os.path.join(config.DIR_RESULTADOS, f"{alvo_id}_superettan_condicoes_1stat.csv"), validados_1stat)
    bm.salvar_csv(os.path.join(config.DIR_RESULTADOS, f"{alvo_id}_superettan_condicoes_2stats.csv"), validados_2stats)
    bm.salvar_csv(os.path.join(config.DIR_RESULTADOS, f"{alvo_id}_superettan_exploratorio_1stat.csv"), exploratorios)

    print("  Confirmando condições de 1 estatística na 1. Division...")
    confirmadas_1stat = [c for c in (bm.confirmar_1stat(cond, dados_divisao1) for cond in validados_1stat) if c]
    confirmadas_1stat = bm.aplicar_bh_confirmacao(confirmadas_1stat)
    n_conf_1 = sum(1 for c in confirmadas_1stat if c["confirmado_bh"])
    print(f"    {n_conf_1} de {len(confirmadas_1stat)} sobrevivem ao teste estatístico formal (BH) na 1. Division")

    print("  Confirmando combinações de 2 estatísticas na 1. Division...")
    confirmadas_2stats = [c for c in (bm.confirmar_2stats(cond, dados_divisao1) for cond in validados_2stats) if c]
    confirmadas_2stats = bm.aplicar_bh_confirmacao(confirmadas_2stats)
    n_conf_2 = sum(1 for c in confirmadas_2stats if c["confirmado_bh"])
    print(f"    {n_conf_2} de {len(confirmadas_2stats)} sobrevivem ao teste estatístico formal (BH) na 1. Division")

    caminho_1 = os.path.join(config.DIR_RESULTADOS, f"{alvo_id}_confirmacao_1divisao_1stat.csv")
    caminho_2 = os.path.join(config.DIR_RESULTADOS, f"{alvo_id}_confirmacao_1divisao_2stats.csv")
    bm.salvar_csv(caminho_1, confirmadas_1stat)
    bm.salvar_csv(caminho_2, confirmadas_2stats)
    print(f"  Salvo em {caminho_1} e {caminho_2}")

    return {
        "validados_1stat": len(validados_1stat), "validados_2stats": len(validados_2stats),
        "confirmados_1stat": n_conf_1, "confirmados_2stats": n_conf_2,
    }


def rodar():
    dados_superettan_bruto, dados_divisao1_bruto = buscar_dados_brutos()

    resumo = {}
    for alvo_id in ALVOS_NATIVOS:
        resumo[alvo_id] = rodar_alvo_nativo(alvo_id, dados_superettan_bruto, dados_divisao1_bruto)

    print(f"\n{'='*70}\nResumo geral — descoberta nativa nórdica (Superettan -> 1. Division)\n{'='*70}")
    for alvo_id, r in resumo.items():
        print(f"{alvos.ALVOS[alvo_id]['nome']:16s}: {r['validados_1stat']:2d} + {r['validados_2stats']:2d} validadas na "
              f"Superettan (1/2 stats) -> {r['confirmados_1stat']} + {r['confirmados_2stats']} confirmadas na 1. Division")


if __name__ == "__main__":
    rodar()
