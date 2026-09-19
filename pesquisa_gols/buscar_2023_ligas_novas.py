"""
Busca a temporada de 2023 da Championship (9) e da Liga Profesional (636) e
MESCLA no checkpoint que já tem 2024-2026, pra aumentar a amostra das vias
nativas (ver a conversa de 19/09/2026).

Por que só essas duas ligas e só 2023 — medido por amostragem na API em
19/09, contando quantas das 12 estatísticas-chave do pipeline aparecem nos
`trends`:

    2021: 8 tipos de trends,  3/12 chave  -> inutilizável
    2022: ~25 tipos,          8/12 chave  -> faltam total_crosses, key_passes,
          accurate_crosses, interceptions, duels_won. total_crosses sozinha
          está em 17 das 20 regras publicadas das ligas novas, então 2022
          salvaria 1 regra de 20. Não compensa.
    2023: Championship 12/12, Argentina 11/12 (perde accurate_crosses)
    2023 MLS: irregular -- cobertura PARCIAL em quase tudo e um jogo
          finalizado com zero trends. Fica de fora até medir a temporada
          inteira, em vez de arriscar buraco imprevisível.

Pré-requisito já resolvido: probabilidades.com_stats faz o pipeline tolerar
estatística ausente POR CONDIÇÃO, sem contaminar o n (jogo sem a stat sai da
base, do grupo e do complemento juntos). Sem isso, misturar temporadas
estouraria KeyError.

SOBRESCREVE O CHECKPOINT. Faça backup antes (dados/backup_checkpoints/).
buscar() só busca fixture que ainda não está no arquivo, então rodar de novo
é barato e retoma de onde parou.

Uso: python3 buscar_2023_ligas_novas.py
"""
import json
import os

import buscar_sportmonks as bs
import config
import sportmonks as sm

DATE_FROM = "2023-01-01"
DATE_TO = "2023-12-31"

LIGAS = {
    9: "Championship",
    636: "Liga Profesional de Fútbol",
}


def rodar():
    print(f"Buscando {DATE_FROM} a {DATE_TO} — MESCLA no checkpoint existente\n", flush=True)
    print("Buscando tipos de estatística...", flush=True)
    tipos = sm.mapa_types()

    for league_id, nome in LIGAS.items():
        caminho = os.path.join(config.DIR_DADOS, f".checkpoint_{league_id}.json")
        antes = json.load(open(caminho, encoding="utf-8"))
        n_antes, s_antes = len(antes["resultados_alvo"]), len(antes["snapshots"])
        print(f"\n{'='*66}\n{nome} ({league_id})\n{'='*66}", flush=True)
        print(f"  ANTES: {n_antes} jogos com resultado, {s_antes} snapshots", flush=True)

        dados = bs.buscar(
            DATE_FROM, DATE_TO, league_id=league_id,
            tipos_disponiveis=tipos, caminho_checkpoint=caminho,
        )
        n_dep, s_dep = len(dados["resultados_alvo"]), len(dados["snapshots"])
        print(f"  DEPOIS: {n_dep} jogos com resultado (+{n_dep - n_antes}), "
              f"{s_dep} snapshots (+{s_dep - s_antes})", flush=True)


if __name__ == "__main__":
    rodar()
