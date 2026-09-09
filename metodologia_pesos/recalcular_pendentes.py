"""Recalcula manualmente/imediatamente as sugestões PENDENTES do ledger
— versão standalone de `ledger_apostas.recalcular_pendentes`, que desde
29/08/2026 também roda automaticamente dentro da rotina diária
(`gerar_painel_dia.atualizar_painel`, logo depois de
`registrar_novas_sugestoes`) pra manter jogos futuros com a
previsão/odd em dia até o jogo começar.

Ainda útil rodar este script à parte quando: (a) acabou de corrigir um
bug de cálculo e quer forçar a atualização na hora, sem esperar a
próxima execução da rotina (foi assim que a entrada do Goiás x São
Bernardo foi corrigida em
`docs/retrospectiva_estado_fixture_bug_2026-08-28.md`, antes desta
função rodar automaticamente); ou (b) quer conferir/atualizar o ledger
fora do horário da rotina, sem gerar o painel inteiro.

Uso: `python3 recalcular_pendentes.py` — busca fixtures futuros frescos
(mesma função da produção, `previsao_dia.gerar_sugestoes_do_dia`),
recalcula qualquer entrada pendente cujo jogo ainda não começou, imprime
o que mudou, e salva o ledger. Rodar de novo não faz mal (idempotente:
se nada mudou, não reporta nada)."""
from __future__ import annotations

from ledger_apostas import carregar_ledger, recalcular_pendentes, salvar_ledger
from previsao_dia import DIAS_A_FRENTE_PADRAO, gerar_sugestoes_do_dia

CAMINHO_LEDGER = "data/ledger_sugestoes.json"


def rodar(caminho_ledger=CAMINHO_LEDGER, dias_a_frente=DIAS_A_FRENTE_PADRAO):
    ledger = carregar_ledger(caminho_ledger)
    sugestoes_frescas = gerar_sugestoes_do_dia(dias_a_frente=dias_a_frente)
    ledger, alteracoes = recalcular_pendentes(ledger, sugestoes_frescas)
    salvar_ledger(caminho_ledger, ledger)
    return alteracoes


if __name__ == "__main__":
    alteracoes = rodar()
    if not alteracoes:
        print("Nenhuma sugestão pendente precisou ser corrigida.")
    else:
        print(f"{len(alteracoes)} sugestão(ões) pendente(s) corrigida(s):")
        for a in alteracoes:
            print(f"  {a['jogo']} ({a['criterio']}): {a['antes']} -> {a['depois']}")
