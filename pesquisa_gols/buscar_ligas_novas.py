"""
Busca os dados (trends minuto a minuto + statistics + eventos) das duas ligas
que entraram na assinatura em 17/09/2026 no lugar de Superliga/2.Bundesliga:
MLS (779) e Liga Profesional Argentina (636).

Não roda descoberta nenhuma — só popula dados/.checkpoint_<liga>.json, que é
pré-requisito de qualquer estudo posterior (descoberta nativa, confirmação
cruzada, backtest de odds). Separado de buscar_multiliga.py porque aquele é
o fluxo da Allsvenskan (liga que saiu da assinatura) e não deve ser alterado
enquanto os resultados dele ainda sustentam as regras publicadas hoje.

O checkpoint serve de cache permanente: rodar de novo só busca fixture que
ainda não está no arquivo (ver buscar_sportmonks.buscar).

Uso:
    export SPORTMONKS_TOKEN=...
    python3 buscar_ligas_novas.py
"""
import os

import buscar_sportmonks as bs
import config
import sportmonks as sm

DATE_FROM = "2024-01-01"
DATE_TO = "2026-12-31"

# Cobertura estatística conferida antes de rodar (17/09/2026): trends das duas
# trazem 40-43 tipos, incluindo todas as candidatas que o pipeline usa
# (Dangerous Attacks, Total Crosses, Accurate Crosses, Shots Insidebox, Key
# Passes, Saves, Tackles, Duels Won, Fouls, Corners) — mesmo patamar da Série A
# (41 tipos). Ou seja, não há limitação de dado que impeça o estudo.
LIGAS = {
    779: "Major League Soccer",
    636: "Liga Profesional de Fútbol",
    # Championship entrou na assinatura antes das outras duas (no lugar das
    # nórdicas) e já está em ligas_live_app/config.py, mas os dados nunca
    # tinham sido buscados — sem checkpoint dela, ficaria de fora do estudo
    # por omissão. Tem round_id preenchido em 552/556 fixtures, então o split
    # cronológico por rodada funciona nativamente (ao contrário da MLS).
    9: "Championship",
}


def rodar():
    print("Buscando tipos de estatística (compartilhado entre as ligas)...")
    tipos_disponiveis = sm.mapa_types()

    for league_id, nome in LIGAS.items():
        caminho = os.path.join(config.DIR_DADOS, f".checkpoint_{league_id}.json")
        print(f"\n{'='*60}\n{nome} ({league_id}) — {DATE_FROM} a {DATE_TO}\n{'='*60}")
        dados = bs.buscar(
            DATE_FROM, DATE_TO, league_id=league_id,
            tipos_disponiveis=tipos_disponiveis, caminho_checkpoint=caminho,
        )
        print(f"{nome}: {len(dados['jogos'])} jogos, {len(dados['snapshots'])} snapshots, "
              f"{len(dados['resultados_alvo'])} com resultado de alvo")


if __name__ == "__main__":
    rodar()
