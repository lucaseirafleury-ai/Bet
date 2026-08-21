"""
Busca condições (1 estatística e pares de 2) que realmente ajudam a prever o
total de gols da partida, com validação fora da amostra — a peça que faltava
na planilha original, que testava tudo em cima dos mesmos ~240 jogos em que
as condições foram "descobertas".

Uso:
    python buscar_condicoes.py

Saída: resultados/condicoes_1stat.csv e resultados/condicoes_2stats.csv,
só com as condições que sobreviveram ao teste fora da amostra.
"""
import csv
import itertools
import os

import config
import carregar_dados
import estatistica
from probabilidades import (
    avaliar_condicao_1stat, limites_candidatos, mercado_bate,
    probabilidades_do_grupo, snapshots_do_bucket,
)


def dividir_treino_teste(jogos, gols_finais):
    """
    Split cronológico por rodada: rodadas iniciais = treino, finais = teste.
    Nunca embaralhar. Restrito a jogos com gols finais conhecidos (alguns
    fixtures podem não ter Stats_Finais preenchido).

    As rodadas são ordenadas pela data do primeiro jogo, não pelo ID bruto de
    rodada — importante ao juntar mais de uma temporada/liga (config.py),
    onde o ID de rodada de uma competição não tem relação com o de outra.

    Só considera jogos com gols_finais conhecido (já disputados) para decidir
    o corte — uma temporada em andamento tem rodadas futuras já cadastradas
    em Jogos, e essas não podem "empurrar" o corte para frente, senão o teste
    vira quase só rodada sem jogo nenhum disputado ainda.
    """
    primeira_data = {}
    for fid, info in jogos.items():
        if info["rodada"] is None or not info["data_hora"] or fid not in gols_finais:
            continue
        atual = primeira_data.get(info["rodada"])
        if atual is None or info["data_hora"] < atual:
            primeira_data[info["rodada"]] = info["data_hora"]
    rodadas = sorted(primeira_data, key=lambda r: primeira_data[r])
    corte = max(1, int(len(rodadas) * config.FRACAO_TREINO))
    rodadas_treino = set(rodadas[:corte])
    treino = {
        fid for fid, info in jogos.items()
        if info["rodada"] in rodadas_treino and fid in gols_finais
    }
    teste = {
        fid for fid, info in jogos.items()
        if info["rodada"] not in rodadas_treino and fid in gols_finais
    }
    return treino, teste


def buckets_minuto_placar(snapshots, fixture_ids):
    """(minuto, gols_momento) -> lista de snapshots, restrito a um conjunto de jogos."""
    buckets = {}
    for snap in snapshots:
        if snap["fixture_id"] not in fixture_ids:
            continue
        chave = (snap["minuto"], snap["gols_momento"])
        buckets.setdefault(chave, []).append(snap)
    return buckets


def _testar_no_teste(snapshots, gols_finais, teste_ids, c):
    """Reavalia uma condição de 1 estatística no conjunto de teste. None se a amostra lá for pequena demais."""
    bucket_teste = snapshots_do_bucket(snapshots, gols_finais, c["minuto"], c["gols_momento"], teste_ids)
    if len(bucket_teste) < config.AMOSTRA_MINIMA:
        return None
    resultado_teste = avaliar_condicao_1stat(bucket_teste, gols_finais, c["stat"], c["operador"], c["limite"])
    if resultado_teste["amostra_condicao"] < config.AMOSTRA_MINIMA:
        return None
    return resultado_teste


def buscar_1stat(dados, treino_ids, teste_ids):
    """
    Devolve três coisas:
    - validados: condições de 1 estatística que passam Benjamini-Hochberg no treino
      E se confirmam no teste — essas são reportadas como "achado" individual.
    - pool_pareamento: candidatas com uma barra bem mais baixa (config.IMPACTO_MINIMO_PAREAMENTO_PP),
      cada uma já com o resultado no treino E no teste — usado só como matéria-prima para
      buscar_2stats, que aplica sua PRÓPRIA validação (BH + fora da amostra) sobre o efeito
      CONJUNTO. Duas estatísticas fracas sozinhas podem ter um efeito de interação real que
      nenhuma mostra isoladamente — por isso a barra de entrada no pool é mais baixa que a de
      "validado", e não a mesma.
    - exploratorios: top 50 por p-valor bruto, sem correção nem validação (só para inspeção manual).
    """
    snapshots, gols_finais, candidatas = dados["snapshots"], dados["gols_finais"], dados["candidatas"]
    buckets_treino = buckets_minuto_placar(snapshots, treino_ids)

    candidatos_brutos = []
    for (minuto, gols_momento), bucket_treino in buckets_treino.items():
        if len(bucket_treino) < config.AMOSTRA_MINIMA:
            continue
        for stat in candidatas:
            for limite in limites_candidatos(bucket_treino, stat, config.NUM_LIMITES_TESTADOS):
                for operador in (">=", "<="):
                    resultado = avaliar_condicao_1stat(bucket_treino, gols_finais, stat, operador, limite)
                    if resultado["amostra_condicao"] < config.AMOSTRA_MINIMA:
                        continue
                    if resultado["amostra_complemento"] < config.AMOSTRA_MINIMA:
                        continue
                    for mercado in config.MERCADOS:
                        impacto = resultado["impacto"][mercado]
                        if impacto is None or abs(impacto) * 100 < config.IMPACTO_MINIMO_PAREAMENTO_PP:
                            continue
                        p_valor = estatistica.teste_duas_proporcoes(
                            resultado["p_final"][mercado], resultado["amostra_condicao"],
                            resultado["p_complemento"][mercado], resultado["amostra_complemento"],
                        )
                        candidatos_brutos.append({
                            "minuto": minuto, "gols_momento": gols_momento,
                            "stat": stat, "operador": operador, "limite": limite,
                            "mercado": mercado, "p_valor": p_valor,
                            "impacto_treino_pp": impacto * 100,
                            "p_final_treino": resultado["p_final"][mercado],
                            "p_base_treino": resultado["p_base"][mercado],
                            "amostra_condicao_treino": resultado["amostra_condicao"],
                            "amostra_base_treino": resultado["amostra_base"],
                        })

    exploratorios = sorted(
        (c for c in candidatos_brutos if c["p_valor"] is not None),
        key=lambda c: c["p_valor"],
    )[:50]

    # pool de pareamento: todo candidato acima da barra baixa, já com o resultado no teste anexado
    pool_pareamento = []
    for c in candidatos_brutos:
        resultado_teste = _testar_no_teste(snapshots, gols_finais, teste_ids, c)
        if resultado_teste is None:
            continue
        pool_pareamento.append({
            **c,
            "p_final_teste": resultado_teste["p_final"][c["mercado"]],
            "amostra_condicao_teste": resultado_teste["amostra_condicao"],
        })

    # validados (achado individual "de verdade"): barra alta + Benjamini-Hochberg + confirmação no teste
    candidatos_altos = [c for c in candidatos_brutos if abs(c["impacto_treino_pp"]) >= config.IMPACTO_MINIMO_PP]
    chaves_significativas = estatistica.corrigir_benjamini_hochberg(
        [(i, c["p_valor"]) for i, c in enumerate(candidatos_altos)], config.ALFA
    )

    validados = []
    for i in chaves_significativas:
        c = candidatos_altos[i]
        resultado_teste = _testar_no_teste(snapshots, gols_finais, teste_ids, c)
        if resultado_teste is None:
            continue
        impacto_teste = resultado_teste["impacto"][c["mercado"]]
        if impacto_teste is None:
            continue
        mesma_direcao = (impacto_teste > 0) == (c["impacto_treino_pp"] > 0)
        reteve_magnitude = abs(impacto_teste * 100) >= abs(c["impacto_treino_pp"]) * config.FRACAO_MINIMA_IMPACTO_TESTE
        if not (mesma_direcao and reteve_magnitude):
            continue
        validados.append({
            **c,
            "p_final_teste": resultado_teste["p_final"][c["mercado"]],
            "p_base_teste": resultado_teste["p_base"][c["mercado"]],
            "impacto_teste_pp": impacto_teste * 100,
            "amostra_condicao_teste": resultado_teste["amostra_condicao"],
        })
    return validados, pool_pareamento, exploratorios


def _chave_stat(v):
    return (v["minuto"], v["gols_momento"], v["stat"], v["operador"], v["limite"])


def classificar_efeito_conjunto(p_conjunta, p_ind1, p_ind2, tolerancia):
    if p_conjunta > p_ind1 + tolerancia and p_conjunta > p_ind2 + tolerancia:
        return "Melhora conjunta"
    if p_conjunta < p_ind1 - tolerancia and p_conjunta < p_ind2 - tolerancia:
        return "Redução conjunta"
    if abs(p_conjunta - p_ind1) <= tolerancia and abs(p_conjunta - p_ind2) <= tolerancia:
        return "Mantém ambas"
    return "Misto / irrelevante"


def _bate(snap, cond):
    op, lim, stat = cond["operador"], cond["limite"], cond["stat"]
    return (snap[stat] >= lim) if op == ">=" else (snap[stat] <= lim)


def buscar_2stats(dados, pool_pareamento, treino_ids, teste_ids):
    """
    Combina pares dentro do pool de pareamento (barra baixa — config.IMPACTO_MINIMO_PAREAMENTO_PP,
    ver buscar_1stat) em vez de exigir que cada estatística já tenha validado sozinha. Duas
    estatísticas fracas isoladamente podem ter um efeito de interação real: aqui a validação
    (Benjamini-Hochberg + confirmação fora da amostra) é aplicada ao efeito CONJUNTO, não a cada
    metade — mais fiel ao que estava sendo avaliado na planilha original.

    Ainda assim, isso é ~1500 pares no treino (medido na base da Allsvenskan), não 544 mil,
    porque só entram no pool candidatas com algum impacto mínimo — em vez de testar todos os
    pares de todas as estatísticas com todos os limites possíveis.
    """
    snapshots, gols_finais = dados["snapshots"], dados["gols_finais"]
    tolerancia = config.TOLERANCIA_EFEITO_CONJUNTO_PP / 100

    por_bucket_mercado = {}
    for v in pool_pareamento:
        chave = (v["minuto"], v["gols_momento"], v["mercado"])
        por_bucket_mercado.setdefault(chave, []).append(v)

    candidatos_brutos = []
    for chave, grupo in por_bucket_mercado.items():
        minuto, gols_momento, mercado = chave
        bucket_treino = snapshots_do_bucket(snapshots, gols_finais, minuto, gols_momento, treino_ids)
        vistos = set()
        for v1, v2 in itertools.combinations(grupo, 2):
            if v1["stat"] == v2["stat"]:
                continue
            par_id = frozenset([_chave_stat(v1), _chave_stat(v2)])
            if par_id in vistos:
                continue
            vistos.add(par_id)

            grupo_conjunto = [s for s in bucket_treino if _bate(s, v1) and _bate(s, v2)]
            complemento_conjunto = [s for s in bucket_treino if not (_bate(s, v1) and _bate(s, v2))]
            p_conjunta_treino, amostra_conjunta_treino = probabilidades_do_grupo(grupo_conjunto, gols_finais)
            p_complemento_treino, amostra_complemento_treino = probabilidades_do_grupo(complemento_conjunto, gols_finais)
            if amostra_conjunta_treino < config.AMOSTRA_MINIMA or amostra_complemento_treino < config.AMOSTRA_MINIMA:
                continue

            classificacao_treino = classificar_efeito_conjunto(
                p_conjunta_treino[mercado], v1["p_final_treino"], v2["p_final_treino"], tolerancia,
            )
            if classificacao_treino not in ("Melhora conjunta", "Redução conjunta"):
                continue

            p_valor = estatistica.teste_duas_proporcoes(
                p_conjunta_treino[mercado], amostra_conjunta_treino,
                p_complemento_treino[mercado], amostra_complemento_treino,
            )
            candidatos_brutos.append({
                "minuto": minuto, "gols_momento": gols_momento, "mercado": mercado,
                "stat1": v1["stat"], "operador1": v1["operador"], "limite1": v1["limite"],
                "stat2": v2["stat"], "operador2": v2["operador"], "limite2": v2["limite"],
                "p_valor": p_valor,
                "classificacao_treino": classificacao_treino,
                "p_conjunta_treino": p_conjunta_treino[mercado],
                "amostra_conjunta_treino": amostra_conjunta_treino,
                "v1": v1, "v2": v2,
            })

    chaves_significativas = estatistica.corrigir_benjamini_hochberg(
        [(i, c["p_valor"]) for i, c in enumerate(candidatos_brutos)], config.ALFA
    )

    validados = []
    for i in chaves_significativas:
        c = candidatos_brutos[i]
        minuto, gols_momento, mercado = c["minuto"], c["gols_momento"], c["mercado"]
        v1, v2 = c["v1"], c["v2"]
        bucket_teste = snapshots_do_bucket(snapshots, gols_finais, minuto, gols_momento, teste_ids)
        grupo_conjunto_teste = [s for s in bucket_teste if _bate(s, v1) and _bate(s, v2)]
        p_conjunta_teste, amostra_conjunta_teste = probabilidades_do_grupo(grupo_conjunto_teste, gols_finais)
        if amostra_conjunta_teste < config.AMOSTRA_MINIMA:
            continue
        classificacao_teste = classificar_efeito_conjunto(
            p_conjunta_teste[mercado], v1["p_final_teste"], v2["p_final_teste"], tolerancia,
        )
        if classificacao_teste != c["classificacao_treino"]:
            continue  # só confirma se a mesma direção do efeito conjunto aparece fora da amostra

        validados.append({
            "minuto": minuto, "gols_momento": gols_momento, "mercado": mercado,
            "stat1": v1["stat"], "operador1": v1["operador"], "limite1": v1["limite"],
            "stat2": v2["stat"], "operador2": v2["operador"], "limite2": v2["limite"],
            "classificacao": c["classificacao_treino"],
            "p_conjunta_treino": c["p_conjunta_treino"],
            "p_conjunta_teste": p_conjunta_teste[mercado],
            "amostra_conjunta_treino": c["amostra_conjunta_treino"],
            "amostra_conjunta_teste": amostra_conjunta_teste,
        })
    return validados


def salvar_csv(caminho, linhas):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    if not linhas:
        with open(caminho, "w", encoding="utf-8") as fp:
            fp.write("(nenhuma condição sobreviveu à validação fora da amostra)\n")
        return
    with open(caminho, "w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(linhas[0].keys()))
        writer.writeheader()
        writer.writerows(linhas)


def rodar():
    print("Carregando dados...")
    dados = carregar_dados.carregar_tudo()
    print(f"  {len(dados['jogos'])} jogos cadastrados ({len(dados['gols_finais'])} já disputados), "
          f"{len(dados['snapshots'])} snapshots, {len(dados['candidatas'])} estatísticas candidatas")

    treino_ids, teste_ids = dividir_treino_teste(dados["jogos"], dados["gols_finais"])
    print(f"  split cronológico: {len(treino_ids)} jogos treino, {len(teste_ids)} jogos teste")

    print("Buscando condições de 1 estatística (treino) e validando fora da amostra (teste)...")
    validados_1stat, pool_pareamento, exploratorios_1stat = buscar_1stat(dados, treino_ids, teste_ids)
    print(f"  {len(validados_1stat)} condições individuais validadas "
          f"(passam Benjamini-Hochberg no treino E se confirmam no teste)")
    print(f"  {len(pool_pareamento)} candidatas no pool de pareamento "
          f"(barra mais baixa, {config.IMPACTO_MINIMO_PAREAMENTO_PP}pp, matéria-prima para os pares)")
    if not validados_1stat:
        print("  Nenhuma condição individual sobreviveu ao critério rigoroso nesta amostra — isso é uma")
        print(f"  resposta válida (não um bug): com {len(dados['gols_finais'])} jogos disputados e milhares")
        print("  de combinações testadas, é esperado que boa parte dos padrões 'fortes' vistos numa amostra")
        print("  menor sejam ruído. Veja resultados/exploratorio_1stat.csv (não validado, só para referência).")

    print("Buscando pares de 2 estatísticas dentro do pool de pareamento...")
    validados_2stats = buscar_2stats(dados, pool_pareamento, treino_ids, teste_ids)
    print(f"  {len(validados_2stats)} combinações validadas")

    caminho_1 = os.path.join(config.DIR_RESULTADOS, "condicoes_1stat.csv")
    caminho_2 = os.path.join(config.DIR_RESULTADOS, "condicoes_2stats.csv")
    caminho_exploratorio = os.path.join(config.DIR_RESULTADOS, "exploratorio_1stat.csv")
    salvar_csv(caminho_1, validados_1stat)
    salvar_csv(caminho_2, validados_2stats)
    salvar_csv(caminho_exploratorio, exploratorios_1stat)
    print(f"\nSalvo em {caminho_1}, {caminho_2} e {caminho_exploratorio}")


if __name__ == "__main__":
    rodar()
