"""PROTOCOLO PADRÃO — o que rodar toda vez que uma liga nova entra no plano.

Uso:
    python3 avaliar_liga_nova.py <chave> <league_id> [--desde-ano 2015] [--pular-pull]

Exemplo:
    python3 avaliar_liga_nova.py portugal 462

Um único comando faz as 3 etapas na ordem certa e grava
`docs/retrospectiva_liga_<chave>_<data>.md`.

================================================================
O QUE É TESTADO, E POR QUE NESSA ORDEM
================================================================

ETAPA 0 — Puxar dado e medir cobertura
    Baixa as temporadas disponíveis (`desde_ano` filtra o lixo antigo) e
    reporta cobertura de odds/estatística/árbitro. Sem odd real não há
    como medir vantagem contra o mercado — comparar o modelo com ele
    mesmo é a armadilha que este projeto evita desde o início. Se a liga
    não tiver odd, o protocolo para aqui.

ETAPA 1 — Reconfirmação (parâmetros do Brasileirão, SEM recalibrar)
    Roda os 3 critérios em produção exatamente como estão:
      · BTTS       — bet365, edge>=5%,  n_historico=10
      · Over 2.5   — Sbo,    edge>=8%,  n_historico=15, filtro União
      · Cartões+Árbitro — bet365, edge>=10%, peso árbitro 0.3
    É o primeiro passo de sempre: se o que já funciona transfere, é o
    sinal mais forte possível (zero risco de superajuste, porque nada
    foi escolhido olhando esta liga). Se não transfere, ainda não
    significa "liga sem edge" — significa "os parâmetros do Brasileirão
    não servem aqui", e aí vai pra Etapa 2.

ETAPA 2 — Calibração própria da liga, COM HOLDOUT
    Grid por liga (fator casa `k_mando`, estilo, filtro de aderência;
    em cartões também o peso do árbitro), treinando nos anos anteriores
    e validando no ano mais recente, que o processo de escolha nunca vê.
    Um grid grande ACHA z alto por acaso — o holdout é o que separa
    achado de miragem. Inclui o teste de ABLAÇÃO do árbitro
    (`peso_arbitro=0`): mede se o componente de árbitro agrega sinal de
    verdade ou se é enfeite.

================================================================
A BARRA PARA ADOTAR UM CRITÉRIO (não negociável)
================================================================
1. `z >= ~2` no período todo, E
2. positivo em TODOS os anos isoladamente (um ano negativo derruba), E
3. `n >= 15` em treino E holdout, E
4. o holdout confirma a magnitude do treino (ROI parecido, não só sinal).

Nada que falhe em qualquer um dos 4 vira critério — vira, no máximo,
"pista para monitorar". Resultado negativo é resultado e fica
documentado igual: o histórico de descartes é o que impede repetir
teste e o que dá contexto para achados futuros.

RESSALVAS QUE O RELATÓRIO SEMPRE MOSTRA
    · `n p/ z=2` (análise de potência): quantas apostas seriam
      necessárias pro ROI observado virar significante. Separa "sem
      edge" de "efeito real, amostra curta".
    · Comparação múltipla: testar N combinações é uma busca; o melhor z
      de treino é quase sempre sorte. Por isso a coluna que vale é a do
      holdout.
    · Dado antigo não é equivalente a dado recente (mercado era menos
      eficiente) — por isso o ano a ano é obrigatório, nunca só o
      agregado.
"""
import sys
from datetime import date

import explorar_ligas_novas as etapa1
import grid_ligas_novas as etapa2
from checar_decaimento import stats
from previsao_dia import CRITERIOS_GOLS, MIN_JOGOS_ARBITRO, PESO_ARBITRO
from sportmonks_client import puxar_fixtures_finalizados, token


def _arg(nome, default=None):
    if nome in sys.argv:
        i = sys.argv.index(nome)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def cobertura(chave):
    """Etapa 0: a liga tem o dado mínimo pra ser avaliável?"""
    import json

    total = com_odds = com_ref = com_stats = 0
    anos = set()
    with open(etapa1.caminho(chave)) as fh:
        for linha in fh:
            d = json.loads(linha)
            total += 1
            anos.add(d["date"][:4])
            if d.get("odds"):
                com_odds += 1
            if d.get("referee_id") is not None:
                com_ref += 1
            if d.get("corners_home") is not None:
                com_stats += 1
    return dict(total=total, anos=sorted(anos), odds=com_odds, arbitro=com_ref, stats=com_stats)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    chave, league_id = sys.argv[1], int(sys.argv[2])
    desde_ano = int(_arg("--desde-ano", 2015))

    linhas = [f"# Liga nova: `{chave}` (league_id {league_id}) — protocolo padrão ({date.today()})", ""]

    # ---------- ETAPA 0 ----------
    if "--pular-pull" not in sys.argv:
        import os

        os.makedirs(f"data/sportmonks_{chave}", exist_ok=True)
        print(f"[0/2] Puxando histórico ({desde_ano}+)...", flush=True)
        puxar_fixtures_finalizados(token(), league_id, etapa1.caminho(chave), desde_ano=desde_ano)

    cob = cobertura(chave)
    pct = lambda x: f"{x / cob['total'] * 100:.0f}%" if cob["total"] else "—"
    linhas += [
        "## Etapa 0 — cobertura do dado", "",
        f"- Jogos finalizados: **{cob['total']}** ({cob['anos'][0]}-{cob['anos'][-1]})",
        f"- Com odds: {cob['odds']} ({pct(cob['odds'])}) — sem odd não há como medir edge",
        f"- Com árbitro: {cob['arbitro']} ({pct(cob['arbitro'])})",
        f"- Com estatística de detalhe: {cob['stats']} ({pct(cob['stats'])})",
        "",
    ]
    if cob["odds"] < 100:
        linhas += ["**Protocolo interrompido**: cobertura de odds insuficiente — sem odd real "
                   "a liga não é avaliável por este método.", ""]
        _gravar(chave, linhas)
        return

    # ---------- ETAPA 1 ----------
    print("[1/2] Reconfirmação com os parâmetros do Brasileirão...", flush=True)
    linhas += ["## Etapa 1 — parâmetros do Brasileirão, sem recalibrar", "",
               "| Critério | Período | n | acerto | ROI | z |", "|---|---|---|---|---|---|"]
    for criterio in CRITERIOS_GOLS:
        try:
            apostas = etapa1.avaliar_gols(chave, criterio)
        except Exception as e:
            linhas.append(f"| {criterio['nome']} | — | não avaliável: `{e}` | | | |")
            continue
        linhas.append(_linha(criterio["nome"], "**total**", stats(apostas)))
        for ano, s in etapa1._por_ano(apostas).items():
            linhas.append(_linha("", str(ano), s))
    try:
        apostas_c, sem_arb, sem_merc = etapa1.avaliar_cartoes(chave)
        linhas.append(_linha("Cartões+Árbitro", "**total**", stats(apostas_c)))
        for ano, s in etapa1._por_ano(apostas_c).items():
            linhas.append(_linha("", str(ano), s))
        linhas += ["", f"Jogos pulados em cartões: {sem_arb} sem árbitro com "
                   f"{MIN_JOGOS_ARBITRO}+ jogos, {sem_merc} sem mercado cotado.", ""]
    except Exception as e:
        linhas += ["", f"Cartões não avaliável: `{e}`", ""]

    # ---------- ETAPA 2 ----------
    print("[2/2] Grid próprio com holdout...", flush=True)
    linhas += ["## Etapa 2 — calibração própria da liga (treino vs holdout)", ""]
    etapa2.rodar_liga_gols(chave, linhas)
    etapa2.rodar_liga_cartoes(chave, linhas)

    linhas += ["## Veredito", "",
               "Aplicar a barra: z>=~2 no período todo **E** positivo em todos os anos **E** "
               "n>=15 nos dois lados **E** holdout confirmando a magnitude do treino. "
               "Qualquer falha em um desses quatro = não adotar (no máximo, monitorar).", ""]
    _gravar(chave, linhas)


def _linha(criterio, periodo, s):
    if s["n"] == 0:
        return f"| {criterio} | {periodo} | 0 | — | — | — |"
    return (f"| {criterio} | {periodo} | {s['n']} | {s['acerto']*100:.0f}% | "
            f"{s['roi']*100:+.1f}% | {s['z']:+.2f} |")


def _gravar(chave, linhas):
    saida = f"docs/retrospectiva_liga_{chave}_{date.today()}.md"
    with open(saida, "w") as fh:
        fh.write("\n".join(linhas) + "\n")
    print(f"\nRelatório: {saida}")


if __name__ == "__main__":
    main()
