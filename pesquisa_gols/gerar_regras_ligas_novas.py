"""
Gera as regras publicáveis das ligas novas (MLS, Liga Profesional, Championship)
e as MESCLA em ligas_live_app/regras_sinais.json, preservando as do Brasil.

Critério (18/09/2026, decidido com o usuário):
- só alvo COM mercado ao vivo (escanteios/cartões); chutes não tem odd ao vivo
- as 3 vias de descoberta concordando (herdado do Brasil + as 2 nativas
  cronológicas) -- mesmo criterio de confirmacoes=3 do Brasil
- piso de amostra 116, NAO 200. O 200 do Brasil nunca foi criterio de
  qualidade: e a fracao ~19,4% do conjunto de confirmacao de la (1.033 jogos
  da liga irma). As ligas novas nao tem liga irma, entao confirmam em metade
  da propria liga (~600), e 200 ali seria 33,3% -- uma barra 70% mais alta.
  116 e a MESMA proporcao, traduzida. Ver conversa de 18/09/2026.
- e por fim o PORTAO DE PRODUCAO (o mesmo de live_monitor.py): impacto
  condicionado ao valor atual do alvo >= 5pp e probabilidade >= 70%. E ele
  que corta de 59 familias para 8.

O QUE ESTE NUMERO NAO TEM: ROI real validado. O backtest retroativo contra o
arquivo de odds e inutilizavel (a bet365 move a linha, e procurar uma linha
fixa so acha match onde ela ja esta no dinheiro -- ver roi_ligas_novas.py).
A medicao honesta so vem PARA FRENTE, com a odd capturada ao vivo no instante
do sinal, que e o que historico_sinais.csv acumula. Decisao do usuario de
subir como card ao vivo em vez de modo sombra: o card mede igual, a diferenca
e dinheiro em risco enquanto a amostra junta.

Uso: python3 gerar_regras_ligas_novas.py [--amostra-minima 116] [--dry-run]
"""
import argparse
import json
import os

import alvos
import gerar_regras_sinais as g
import roi_ligas_novas as R

CAMINHO_REGRAS = os.path.join(os.path.dirname(__file__), "..", "ligas_live_app", "regras_sinais.json")

AMOSTRA_MINIMA_LIGAS_NOVAS = 116
# Mesmos portões de live_monitor.py. Não inventar limiar aqui.
IMPACTO_MINIMO_PP_VALOR_ATUAL = 5.0
PROBABILIDADE_MINIMA = 0.70

# Regiões precisam existir em live_monitor.LIGAS_POR_REGIAO, senão a regra
# dispara em TODAS as ligas (fallback "universal"). Conferido no validar().
REGIOES_ESPERADAS = {"mls", "argentina", "championship"}


def _passa_portao(regra):
    """True se ALGUMA entrada de por_valor_atual sustenta a regra — é o que o
    live_monitor exige no momento do sinal (ele olha a entrada do valor atual
    daquele jogo; se nenhuma entrada passa, a regra nunca vira card)."""
    tabela = regra.get("por_valor_atual") or {}
    for entrada in tabela.values():
        if (entrada.get("impacto_pp") or 0) >= IMPACTO_MINIMO_PP_VALOR_ATUAL \
           and (entrada.get("p_condicao") or 0) >= PROBABILIDADE_MINIMA:
            return True
    return False


def _rotulo(regra):
    partes = []
    for c in regra["condicoes"]:
        nome = g.TRAD.get(c["stat"], c["stat"])
        op = "≥" if c["operador"] == ">=" else "≤"
        partes.append(f"{nome} {op} {c['limite']:g}")
    direcao = "Mais de" if regra["mercado"]["direcao"] == "mais_de" else "Menos de"
    alvo_nome = alvos.ALVOS[regra["alvo"]]["nome"].lower()
    return (f"{' E '.join(partes)} aos {regra['minuto']}' "
            f"({regra['gols_momento']} gol(s) no jogo) → "
            f"{direcao} {regra['mercado']['linha']:g} {alvo_nome}")


def montar(amostra_minima):
    publicaveis = []
    for prefixo in R.LIGA_POR_PREFIXO:
        regras = R.familias_da_liga(prefixo, amostra_minima)
        if not regras:
            print(f"  {prefixo:13s} 0 famílias")
            continue
        g.recalibrar_por_valor_atual(regras)
        aprovadas = [r for r in regras if _passa_portao(r)]
        print(f"  {prefixo:13s} {len(regras):3d} famílias -> {len(aprovadas)} passam o portão")
        for i, r in enumerate(sorted(aprovadas, key=lambda x: (x["minuto"], -x["impacto_pp"])), 1):
            direcao = r["mercado"]["direcao"]
            publicaveis.append({
                "id": f"{prefixo}_{r['alvo']}_{i:03d}",
                "alvo": r["alvo"],
                "alvo_nome": alvos.ALVOS[r["alvo"]]["nome"],
                "minuto": r["minuto"],
                "gols_momento": r["gols_momento"],
                "condicoes": r["condicoes"],
                "mercado": r["mercado"],
                "mercado_curto": (f"{'Mais de' if direcao == 'mais_de' else 'Menos de'} "
                                  f"{r['mercado']['linha']:g} {alvos.ALVOS[r['alvo']]['nome'].lower()}"),
                "amostra_confirmacao": r["amostra_confirmacao"],
                "prob_base_confirmacao": round(r["prob_base_confirmacao"], 4),
                "prob_condicao_confirmacao": round(r["prob_condicao_confirmacao"], 4),
                "impacto_pp": r["impacto_pp"],
                "rotulo": _rotulo(r),
                "regiao": prefixo,
                "confirmacoes": 3,
                "liga_restrita": None,
                "por_valor_atual": r["por_valor_atual"],
            })
    return publicaveis


def validar(novas, payload_final):
    """Falha alto e cedo. Cada check aqui corresponde a um jeito conhecido de
    quebrar em silêncio, não a paranoia genérica."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ligas_live_app"))

    regioes = {r["regiao"] for r in novas}
    assert regioes <= REGIOES_ESPERADAS, f"região inesperada: {regioes - REGIOES_ESPERADAS}"

    # A checagem que importa: região não registrada em live_monitor faz a regra
    # valer em TODAS as ligas. Lê o arquivo em vez de importar (live_monitor
    # puxa pywebpush, que não está instalado no ambiente de pesquisa).
    fonte_lm = open(os.path.join(os.path.dirname(__file__), "..", "ligas_live_app", "live_monitor.py"),
                    encoding="utf-8").read()
    assert "LIGAS_POR_REGIAO" in fonte_lm, "live_monitor.py sem LIGAS_POR_REGIAO — regra nova valeria em todas as ligas"
    for regiao in regioes:
        assert f'"{regiao}":' in fonte_lm, f"região '{regiao}' não registrada em live_monitor.LIGAS_POR_REGIAO"

    for r in novas:
        assert r["por_valor_atual"], f"{r['id']} sem tabela por_valor_atual (nunca viraria card)"
        assert _passa_portao(r), f"{r['id']} não passa o próprio portão"
        assert r["alvo"] in ("escanteios", "cartoes"), f"{r['id']}: alvo sem mercado ao vivo"
        assert r["amostra_confirmacao"] >= AMOSTRA_MINIMA_LIGAS_NOVAS, f"{r['id']} abaixo do piso"

    ids = [r["id"] for r in payload_final["regras"]]
    assert len(ids) == len(set(ids)), "IDs duplicados no arquivo final"
    brasil = [r for r in payload_final["regras"] if r.get("regiao") == "brasil"]
    assert len(brasil) == 70, f"regras do Brasil deviam continuar 70, viraram {len(brasil)}"
    print(f"  [ok] {len(novas)} novas, {len(brasil)} do Brasil preservadas, "
          f"{payload_final['total_regras']} no total")


def rodar(amostra_minima, dry_run):
    print(f"Gerando regras das ligas novas (piso de amostra {amostra_minima})...\n")
    novas = montar(amostra_minima)
    print(f"\n{len(novas)} regras publicáveis:\n")
    for r in novas:
        print(f"  {r['id']:32s} {r['rotulo']}")
        print(f"  {'':32s}   n={r['amostra_confirmacao']} impacto bruto {r['impacto_pp']:+.1f}pp")

    payload = json.load(open(CAMINHO_REGRAS, encoding="utf-8"))
    antigas = [r for r in payload["regras"] if r.get("regiao") not in REGIOES_ESPERADAS]
    payload["regras"] = antigas + novas
    payload["total_regras"] = len(payload["regras"])
    payload["criterio"] += (
        f" | LIGAS NOVAS (18/09/2026): {len(novas)} regras de MLS/Liga Profesional/Championship, "
        f"confirmacoes=3 com piso de amostra {amostra_minima} (não 200 — ver docstring de "
        f"gerar_regras_ligas_novas.py: 200 é a fração do conjunto de confirmação do Brasil, que tem "
        f"liga irmã; as novas confirmam em metade da própria liga e {amostra_minima} é a MESMA "
        f"proporção) + portão de produção (impacto por valor atual >= 5pp e probabilidade >= 70%). "
        f"SEM ROI real validado: o backtest retroativo contra o arquivo de odds é enviesado (a bet365 "
        f"move a linha), então a medição honesta só vem para frente, via odd capturada ao vivo em "
        f"historico_sinais.csv."
    )

    print("\nValidando...")
    validar(novas, payload)

    if dry_run:
        print("\n[dry-run] nada foi escrito")
        return
    with open(CAMINHO_REGRAS, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\nregras_sinais.json atualizado: {payload['total_regras']} regras")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--amostra-minima", type=int, default=AMOSTRA_MINIMA_LIGAS_NOVAS)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    rodar(a.amostra_minima, a.dry_run)
