"""
Gera um conjunto de regras "sombra" com candidatos que JÁ SÃO estatisticamente
confirmados (confirmado_bh=True, teste de duas proporções + Benjamini-Hochberg
— mesmo rigor de tudo mais) e batem o impacto mínimo do painel, mas foram
excluídos do conjunto principal só por não terem amostra suficiente ainda no
pool de confirmação nórdico (Superettan+1.Division, ~1448 jogos) pra bater o
piso AMOSTRA_MINIMA_NORDICAS=150 do painel — pedido do usuário (ver conversa):
"nórdicas só tem 23 [regras] por falta de N... podemos rodar em background os
que atingem as regras mas não têm N suficiente?".

Achado real ao checar isso: 208 condições nórdicas passam confirmado_bh=True
no total; 60 delas (~29%) têm amostra abaixo de 150. Rodar essas em modo
sombra (mesmo padrão de PERFIS_SOMBRA em live_monitor.py — nunca publica card
nem push, só registra) deixa elas acumularem avaliação ao vivo real; ao vivo
não aumenta o N da confirmação HISTÓRICA (isso é fixo, já rodou), mas dá uma
leitura de ROI/acerto real independente, exatamente como fizemos pros
conjuntos de 204/105 regras do Brasil.

Piso inferior (30): mesmo piso já usado DENTRO de confirmar_1stat/2stats
(pesquisa_gols/config.py::AMOSTRA_MINIMA) pra sequer tentar calcular o teste —
abaixo disso a própria confirmação já teria descartado o candidato antes de
chegar a um p-valor, então não faz sentido incluir aqui (não é "só falta de
N", é "N baixo demais pra testar rigor nenhum").

Uso: python3 gerar_regras_sombra_baixa_amostra.py
(usa os mesmos CSVs de resultados/*_confirmacao_*.csv já gerados por
buscar_multiliga.py — não busca dado novo, não gasta API)
"""
import json
import os

import gerar_regras_sinais as grs

AMOSTRA_MINIMA_BAIXA = 30
DESTINO = os.path.join(os.path.dirname(__file__), "..", "ligas_live_app", "regras_sinais_sombra_nordicas_baixa_n.json")


def gerar():
    sinais = grs._colapsar(grs._carregar_brutas(grs.ALVOS))
    confirmadas_brasil = grs._carregar_confirmadas_brasil()

    candidatos = [
        s for s in sinais
        if AMOSTRA_MINIMA_BAIXA <= s["amostra"] < grs.AMOSTRA_MINIMA_NORDICAS
        and s["impacto"] >= grs.IMPACTO_MINIMO_PP
    ]
    for s in candidatos:
        # Mesma lógica de universal-vs-só-nórdicas do pipeline principal —
        # a maioria cai em "nordicas" (a amostra baixa é do próprio pool
        # nórdico), mas se por acaso a mesma condição também confirmou no
        # Brasil (com amostra própria lá, independente), vale universal.
        s["regiao"] = "universal" if grs._chave_brasil(s) in confirmadas_brasil else "nordicas"

    print(f"{len(sinais)} sinais nórdicos confirmados no total | "
          f"{len(candidatos)} na faixa de amostra {AMOSTRA_MINIMA_BAIXA}-{grs.AMOSTRA_MINIMA_NORDICAS-1} "
          f"(abaixo do piso do painel, mas já confirmado_bh=True e impacto>={grs.IMPACTO_MINIMO_PP}pp)")

    fortes = grs._deduplicar_familia(candidatos)
    print(f"depois de colapsar famílias quase-duplicadas: {len(fortes)}")

    regras = grs.montar_regras(fortes)

    payload = {
        "criterio": f"confirmado_bh=True (teste de duas proporções + Benjamini-Hochberg, mesmo rigor "
                    f"do conjunto principal) e impacto_pp >= {grs.IMPACTO_MINIMO_PP}, mas amostra_confirmacao "
                    f"entre {AMOSTRA_MINIMA_BAIXA} e {grs.AMOSTRA_MINIMA_NORDICAS - 1} — abaixo do piso "
                    f"AMOSTRA_MINIMA_NORDICAS={grs.AMOSTRA_MINIMA_NORDICAS} do painel principal, então nunca "
                    "publicado; roda só em modo sombra (ver live_monitor.py::PERFIS_SOMBRA) pra acumular "
                    "avaliação ao vivo real enquanto a amostra histórica de confirmação não cresce mais "
                    "(essa não muda com jogo novo — é fixa; o que cresce aqui é a leitura de ROI ao vivo).",
        "fonte": "pesquisa_gols/resultados/*_confirmacao_*.csv (nórdicas), mesmos arquivos do conjunto "
                 "principal — só o piso de amostra pro painel (AMOSTRA_MINIMA_NORDICAS) é relaxado aqui, "
                 "não o teste estatístico em si.",
        "total_regras": len(regras),
        "regras": regras,
    }

    os.makedirs(os.path.dirname(DESTINO), exist_ok=True)
    with open(DESTINO, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\nsalvo em {os.path.abspath(DESTINO)}")


if __name__ == "__main__":
    gerar()
