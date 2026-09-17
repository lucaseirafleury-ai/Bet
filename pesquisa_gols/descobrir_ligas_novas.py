"""
Descoberta + confirmação nas duas ligas que entraram na assinatura em
17/09/2026: MLS (779) e Liga Profesional Argentina (636).

MOTIVAÇÃO DO DESENHO (ver conversa). O backtest contra odds reais da bet365
mostrou que UMA via de descoberta não basta: confirmacoes=1 rendeu ROI real
de -47,1% (nórdicas) e -49,6% (universal), enquanto confirmacoes=3 (Brasil)
rendeu +17,8%. Ou seja, passar no teste estatístico formal (duas proporções
+ Benjamini-Hochberg) com confirmação fora da amostra NÃO é suficiente —
só a concordância de várias buscas semi-independentes sobrevive ao mercado.

Por isso cada liga roda TRÊS vias, espelhando o que deu certo no Brasil:
  - herdado:   descobre no Brasil (Série A+B juntos) -> confirma na liga nova
  - nativo_12: descobre na 1ª metade cronológica -> confirma na 2ª
  - nativo_21: descobre na 2ª metade cronológica -> confirma na 1ª

A via herdada é a única que testa generalização entre contextos diferentes;
as duas nativas dão o efeito de "múltiplos testes independentes", que é o
que mata falso positivo. Nenhuma liga nova é cruzada com a OUTRA liga nova:
MLS e Argentina têm estilos bem distintos (MLS 3,11 gols/jogo e 4,39
cartões; Argentina 2,03 e 5,23 — esta última quase idêntica à Série A), e
confirmar uma na outra rejeitaria efeito real por pura diferença de
contexto.

SPLIT CRONOLÓGICO — ARMADILHA REAL (pega antes de rodar, 17/09/2026):
buscar_condicoes.dividir_treino_teste agrupa por RODADA, mas a MLS não usa
rodadas na Sportmonks (round_id nulo em 100% dos 1.572 jogos). Com
rodada=None o conjunto de rodadas sai vazio e a função devolve treino=0 /
teste=1409 — a descoberta não testaria NADA, gerando CSVs vazios com exit
code 0 e a conclusão falsa de que "a MLS não tem sinal". Por isso
_split_cronologico abaixo cai para agrupamento por DIA quando não há
rodada, preservando a propriedade que importa: nenhum grupo de jogos
simultâneos fica dividido entre treino e teste.

NÃO sobrescreve nada de produção: usa buscar_condicoes/buscar_multiliga só
como biblioteca (mesmas funções estatísticas) e grava em arquivos com
prefixo próprio por liga.

Uso: python3 descobrir_ligas_novas.py
"""
import os
from collections import defaultdict

import alvos
import buscar_condicoes
import buscar_multiliga as bm
import buscar_sportmonks as bs
import config
import sportmonks as sm

DATE_FROM = "2024-01-01"
DATE_TO = "2026-12-31"

LIGAS_NOVAS = {779: "mls", 636: "argentina", 9: "championship"}
SERIE_A_ID, SERIE_B_ID = 648, 651
ALVOS_ESTUDADOS = ["escanteios", "chutes_totais", "chutes_no_alvo", "cartoes"]


def _split_cronologico(jogos, gols_finais):
    """
    Split cronológico treino/teste com a mesma semântica de
    buscar_condicoes.dividir_treino_teste (grupos ordenados por data, corte em
    config.FRACAO_TREINO, nunca embaralha, só jogos com resultado), mas
    tolerante a liga sem rodada — ver docstring do módulo sobre a MLS.

    Devolve (treino_ids, teste_ids, criterio) — `criterio` é só pro log, pra
    ficar explícito no output qual agrupamento foi usado em cada liga.
    """
    elegiveis = {
        fid: info for fid, info in jogos.items()
        if fid in gols_finais and info.get("data_hora")
    }
    usa_rodada = any(info.get("rodada") is not None for info in elegiveis.values())
    criterio = "rodada" if usa_rodada else "dia"

    def chave_grupo(info):
        return info["rodada"] if usa_rodada else info["data_hora"][:10]

    primeira_data = {}
    for info in elegiveis.values():
        g = chave_grupo(info)
        if g is None:
            continue
        if g not in primeira_data or info["data_hora"] < primeira_data[g]:
            primeira_data[g] = info["data_hora"]

    grupos = sorted(primeira_data, key=lambda g: primeira_data[g])
    corte = max(1, int(len(grupos) * config.FRACAO_TREINO))
    grupos_treino = set(grupos[:corte])

    treino = {fid for fid, info in elegiveis.items() if chave_grupo(info) in grupos_treino}
    teste = {fid for fid, info in elegiveis.items() if chave_grupo(info) not in grupos_treino}
    return treino, teste, criterio


def _filtrar_dataset(dados, fixture_ids):
    """
    Recorta o dataset bruto pra um subconjunto de fixtures.

    Filtra TODAS as estruturas indexadas por fixture — jogos, resultados_alvo,
    gols_finais e snapshots. `matriz` e `candidatas` não dependem de fixture e
    passam inteiras. Esquecer uma dessas estruturas é falha silenciosa (a
    descoberta rodaria com um conjunto e o rótulo viria de outro), por isso a
    conferência de consistência logo abaixo em _conferir_particao.
    """
    ids = set(fixture_ids)
    return {
        "jogos": {fid: v for fid, v in dados["jogos"].items() if fid in ids},
        "resultados_alvo": {fid: v for fid, v in dados["resultados_alvo"].items() if fid in ids},
        "gols_finais": {fid: v for fid, v in dados["gols_finais"].items() if fid in ids},
        "snapshots": [s for s in dados["snapshots"] if s["fixture_id"] in ids],
        "matriz": dados["matriz"],
        "candidatas": dados["candidatas"],
    }


def _conferir_particao(nome, d1, d2, dados_origem):
    """Falha alto e cedo se a partição perdeu ou duplicou jogo — ver _filtrar_dataset."""
    f1, f2 = set(d1["jogos"]), set(d2["jogos"])
    assert not (f1 & f2), f"{nome}: {len(f1 & f2)} fixtures nas duas metades"
    com_resultado = {fid for fid in dados_origem["jogos"] if fid in dados_origem["gols_finais"]}
    perdidos = com_resultado - (f1 | f2)
    assert not perdidos, f"{nome}: {len(perdidos)} jogos com resultado ficaram fora das duas metades"
    for lado, d in (("metade1", d1), ("metade2", d2)):
        snaps_fix = {s["fixture_id"] for s in d["snapshots"]}
        orfaos = snaps_fix - set(d["jogos"])
        assert not orfaos, f"{nome}/{lado}: {len(orfaos)} snapshots de fixture fora do subconjunto"
    print(f"    [ok] partição consistente: {len(f1)} + {len(f2)} jogos, sem sobreposição nem perda")


def particionar_cronologico(dados):
    """Duas metades cronológicas de tamanho igual, cortando na mediana da data."""
    com_res = [
        (fid, info["data_hora"]) for fid, info in dados["jogos"].items()
        if fid in dados["gols_finais"] and info.get("data_hora")
    ]
    com_res.sort(key=lambda x: x[1])
    meio = len(com_res) // 2
    ids1 = [fid for fid, _ in com_res[:meio]]
    ids2 = [fid for fid, _ in com_res[meio:]]
    return _filtrar_dataset(dados, ids1), _filtrar_dataset(dados, ids2)


def rodar_via(alvo_id, dados_descoberta, dados_confirmacao, prefixo, rotulo):
    """
    Uma via de descoberta+confirmação: descobre em dados_descoberta (split
    cronológico interno treino/teste + Benjamini-Hochberg) e confirma em
    dados_confirmacao (teste de duas proporções + BH). Mesmas funções que
    descobrir_nativo_brasil.py usa — só muda de onde vêm os dois conjuntos.
    """
    config.MERCADOS = alvos.mercados_do_alvo(alvo_id)
    desc = bm.dados_do_alvo(dados_descoberta, alvo_id)
    conf = bm.dados_do_alvo(dados_confirmacao, alvo_id)

    treino_ids, teste_ids, criterio = _split_cronologico(desc["jogos"], desc["gols_finais"])
    print(f"    [{rotulo}] split por {criterio}: {len(treino_ids)} treino / {len(teste_ids)} teste "
          f"| confirmação: {len(conf['gols_finais'])} jogos")
    if not treino_ids or not teste_ids:
        print(f"    [ABORTA] split degenerado em {rotulo} — nada seria testado")
        return {"validados": 0, "confirmados": 0}

    val_1 = buscar_condicoes.buscar_1stat(desc, treino_ids, teste_ids)
    validados_1stat, pool, exploratorios = val_1
    validados_2stats = buscar_condicoes.buscar_2stats(desc, pool, treino_ids, teste_ids)

    conf_1 = [c for c in (bm.confirmar_1stat(c, conf) for c in validados_1stat) if c]
    conf_1 = bm.aplicar_bh_confirmacao(conf_1)
    conf_2 = [c for c in (bm.confirmar_2stats(c, conf) for c in validados_2stats) if c]
    conf_2 = bm.aplicar_bh_confirmacao(conf_2)

    n1 = sum(1 for c in conf_1 if c["confirmado_bh"])
    n2 = sum(1 for c in conf_2 if c["confirmado_bh"])
    print(f"    [{rotulo}] validadas: {len(validados_1stat)} (1stat) + {len(validados_2stats)} (2stats) "
          f"-> confirmadas BH: {n1} + {n2}")

    bm.salvar_csv(os.path.join(config.DIR_RESULTADOS, f"{alvo_id}_{prefixo}_confirmacao_1stat.csv"), conf_1)
    bm.salvar_csv(os.path.join(config.DIR_RESULTADOS, f"{alvo_id}_{prefixo}_confirmacao_2stats.csv"), conf_2)
    return {"validados": len(validados_1stat) + len(validados_2stats), "confirmados": n1 + n2}


def rodar(league_ids=None):
    """league_ids=None roda todas; passe uma lista pra rodar só parte delas
    (útil quando os dados de uma liga ainda estão sendo baixados)."""
    ligas = {lid: p for lid, p in LIGAS_NOVAS.items() if league_ids is None or lid in league_ids}
    print(f"Ligas nesta execução: {', '.join(ligas.values())}")
    print("Buscando tipos de estatística...")
    tipos = sm.mapa_types()

    def carregar(lid):
        return bs.buscar(DATE_FROM, DATE_TO, league_id=lid, tipos_disponiveis=tipos,
                         caminho_checkpoint=os.path.join(config.DIR_DADOS, f".checkpoint_{lid}.json"))

    print("\nCarregando Brasil (fonte da via herdada)...")
    brasil = bs.mesclar([carregar(SERIE_A_ID), carregar(SERIE_B_ID)])
    print(f"  Brasil pooled: {len(brasil['gols_finais'])} jogos com resultado")

    resumo = defaultdict(dict)
    for league_id, prefixo in ligas.items():
        print(f"\n{'='*70}\n{prefixo.upper()} ({league_id})\n{'='*70}")
        dados = carregar(league_id)
        print(f"  {len(dados['gols_finais'])} jogos com resultado")
        metade1, metade2 = particionar_cronologico(dados)
        _conferir_particao(prefixo, metade1, metade2, dados)

        for alvo_id in ALVOS_ESTUDADOS:
            print(f"\n  --- {alvos.ALVOS[alvo_id]['nome']} ({alvo_id}) ---")
            resumo[prefixo][alvo_id] = {
                "herdado": rodar_via(alvo_id, brasil, dados, f"{prefixo}_herdado", "herdado"),
                "nativo_12": rodar_via(alvo_id, metade1, metade2, f"{prefixo}_nativo12", "nativo_12"),
                "nativo_21": rodar_via(alvo_id, metade2, metade1, f"{prefixo}_nativo21", "nativo_21"),
            }

    print(f"\n{'='*70}\nRESUMO\n{'='*70}")
    for prefixo, por_alvo in resumo.items():
        for alvo_id, vias in por_alvo.items():
            partes = " | ".join(f"{v}: {r['confirmados']}/{r['validados']}" for v, r in vias.items())
            print(f"  {prefixo:10s} {alvo_id:16s} {partes}")


if __name__ == "__main__":
    import sys
    ids = [int(a) for a in sys.argv[1:]] or None
    rodar(ids)
