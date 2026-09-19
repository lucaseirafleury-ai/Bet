"""
Cálculo de P Final / P Base / Impacto sob demanda — substitui as abas
materializadas (Tabela_Probabilidades / Probabilidades_2Stats) por uma função
que filtra o snapshot em memória. Numa base deste tamanho (~1.700 snapshots),
isso custa milissegundos: não há motivo para pré-computar e salvar milhões
de linhas.
"""
import config


def mercado_bate(valor_final, mercado):
    """
    '+N' = resultado final >= N; '-N' = resultado final < N.
    N pode ter casas decimais (ex.: '+9.5') — usado pelos alvos além de gols
    (escanteios, cartões, chutes), que seguem a convenção de linha de aposta
    terminada em .5 pra nunca empatar exatamente em cima do corte.
    """
    n = float(mercado[1:])
    if mercado[0] == "+":
        return valor_final >= n
    return valor_final < n


def com_stats(bucket, *stats):
    """Só os snapshots que TÊM todas as stats pedidas (chave presente e não-None).

    Existe porque a cobertura de `trends` da Sportmonks varia por temporada: as
    temporadas antigas das ligas novas não trazem algumas estatísticas
    (total_crosses e key_passes faltam em 2022 inteiro, accurate_crosses falta
    em 2023 na Argentina). Sem isto, `s[stat]` estoura KeyError ao misturar
    temporadas.

    REGRA DE OURO — filtre o bucket ANTES de dividir em condição/complemento,
    nunca depois. Se a base for calculada sobre todos os jogos e a condição só
    sobre os que têm a stat, os dois grupos medem populações diferentes e o
    impacto (p_condicao - p_base) vira comparação inválida. Jogo sem a stat não
    entra em NENHUM dos três grupos, e portanto não entra no n.
    """
    return [s for s in bucket if all(s.get(st) is not None for st in stats)]


def _condicao_bate(valor, operador, limite):
    if operador == ">=":
        return valor >= limite
    if operador == "<=":
        return valor <= limite
    raise ValueError(f"operador desconhecido: {operador}")


def snapshots_do_bucket(snapshots, gols_finais, minuto, gols_momento, fixture_ids=None):
    """Snapshots naquele minuto/placar-no-momento, restritos a um conjunto de jogos (treino ou teste)."""
    resultado = []
    for snap in snapshots:
        if snap["minuto"] != minuto or snap["gols_momento"] != gols_momento:
            continue
        if fixture_ids is not None and snap["fixture_id"] not in fixture_ids:
            continue
        if snap["fixture_id"] not in gols_finais:
            continue
        resultado.append(snap)
    return resultado


def probabilidades_do_grupo(grupo, gols_finais):
    """P de cada mercado dentro de um grupo de snapshots, mais o tamanho da amostra."""
    n = len(grupo)
    if n == 0:
        return {m: None for m in config.MERCADOS}, 0
    probs = {}
    for mercado in config.MERCADOS:
        acertos = sum(
            1 for snap in grupo if mercado_bate(gols_finais[snap["fixture_id"]], mercado)
        )
        probs[mercado] = acertos / n
    return probs, n


def avaliar_condicao_1stat(bucket_base, gols_finais, stat, operador, limite):
    """
    Divide o bucket (já filtrado por minuto/placar) em quem cumpre a condição
    e quem não cumpre. Devolve P Final (quem cumpre), P Base (o bucket
    inteiro) e o grupo complementar (quem NÃO cumpre — usado no teste
    estatístico, que precisa de dois grupos independentes).
    """
    # Filtra ANTES de dividir (ver com_stats): quem não tem a stat sai da base,
    # da condição e do complemento juntos.
    bucket_base = com_stats(bucket_base, stat)
    grupo_condicao = [s for s in bucket_base if _condicao_bate(s[stat], operador, limite)]
    grupo_complemento = [s for s in bucket_base if not _condicao_bate(s[stat], operador, limite)]

    p_final, amostra_condicao = probabilidades_do_grupo(grupo_condicao, gols_finais)
    p_base, amostra_base = probabilidades_do_grupo(bucket_base, gols_finais)
    p_complemento, amostra_complemento = probabilidades_do_grupo(grupo_complemento, gols_finais)

    impacto = {
        m: (p_final[m] - p_base[m]) if p_final[m] is not None and p_base[m] is not None else None
        for m in config.MERCADOS
    }

    return {
        "amostra_condicao": amostra_condicao,
        "amostra_base": amostra_base,
        "p_final": p_final,
        "p_base": p_base,
        "impacto": impacto,
        "p_complemento": p_complemento,
        "amostra_complemento": amostra_complemento,
    }


def limites_candidatos(bucket_base, stat, num_limites):
    """Limites derivados dos quantis observados do valor da estatística no próprio bucket."""
    valores = sorted(s[stat] for s in com_stats(bucket_base, stat))
    if not valores:
        return []
    limites = set()
    for i in range(1, num_limites + 1):
        idx = min(len(valores) - 1, int(len(valores) * i / (num_limites + 1)))
        limites.add(round(valores[idx]))
    return sorted(limites)
