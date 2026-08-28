"""Corrige manualmente as sugestões PENDENTES do ledger depois de um bug
consertado na lógica de sugestão (`previsao_dia.py`/`cartoes_arbitro.py`)
— NUNCA rodado pela rotina diária automática, só sob demanda.

Contexto: `ledger_apostas.registrar_novas_sugestoes` propositalmente
nunca sobrescreve uma entrada `(fixture_id, criterio)` já registrada
(protege contra o painel mudar a odd de uma aposta que o Lucas já tenha
feito) — mas isso significa que uma sugestão registrada com valor
ERRADO por bug nunca se autocorrige sozinha, mesmo depois do bug ser
corrigido. Este script é o jeito deliberado de corrigir isso quando (e
só quando) houver um motivo real pra reconferir — ver
`docs/retrospectiva_estado_fixture_bug_2026-08-28.md` (a entrada do
Goiás x São Bernardo foi corrigida manualmente porque este script ainda
não existia).

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
