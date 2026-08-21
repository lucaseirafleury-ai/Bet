"""
Testes estatísticos usados para decidir se uma condição é "real" ou coincidência
de amostra pequena. Só stdlib (math) — sem scipy, no mesmo espírito de dependências
mínimas do resto do repo.
"""
import math


def teste_duas_proporcoes(p1, n1, p2, n2):
    """
    Teste z para diferença entre duas proporções independentes (p1 do grupo que
    cumpre a condição, p2 do grupo que NÃO cumpre — o complemento, não a base
    inteira, para os dois grupos serem de fato independentes).

    Devolve o p-valor bicaudal. None se alguma amostra for pequena demais para
    o teste fazer sentido (n1 ou n2 == 0).
    """
    if n1 == 0 or n2 == 0:
        return None
    p_pool = (p1 * n1 + p2 * n2) / (n1 + n2)
    erro_padrao = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    if erro_padrao == 0:
        return None if p1 == p2 else 0.0
    z = (p1 - p2) / erro_padrao
    # p-valor bicaudal a partir da normal padrão (função erro complementar)
    return math.erfc(abs(z) / math.sqrt(2))


def corrigir_benjamini_hochberg(pvalores, alfa):
    """
    Aplica a correção de Benjamini-Hochberg para controlar a taxa de falsas
    descobertas quando muitas condições são testadas ao mesmo tempo.

    `pvalores`: lista de (chave, p_valor). Devolve o conjunto de chaves que
    permanecem significativas depois da correção.
    """
    validos = [(chave, p) for chave, p in pvalores if p is not None]
    m = len(validos)
    if m == 0:
        return set()
    ordenados = sorted(validos, key=lambda item: item[1])
    maior_k_aceito = -1
    for k, (_, p) in enumerate(ordenados, start=1):
        limite = (k / m) * alfa
        if p <= limite:
            maior_k_aceito = k
    if maior_k_aceito == -1:
        return set()
    return {chave for chave, _ in ordenados[:maior_k_aceito]}
