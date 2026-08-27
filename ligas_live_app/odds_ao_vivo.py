"""
Busca a odd AO VIVO real (Sportmonks) para o mercado de um sinal confirmado,
quando existir — complementa (não substitui) o "odd mínima" que já aparece no
card, que é só uma estimativa sintética (1 / probabilidade histórica), não um
preço real de casa de apostas.

Cobertura por liga já checada manualmente antes de escrever isto: as ligas
nórdicas hoje só têm mercado de ESCANTEIOS ao vivo (chutes e cartões não têm
odd nenhuma nelas); Série A/B do Brasil tem escanteios, chutes totais e
chutes no alvo. Por isso esta busca nunca assume cobertura — só tenta achar
a linha exata e devolve None quando não encontra (liga sem o mercado, linha
específica não ofertada, jogo sem odds ao vivo ainda, ou erro de rede). Nunca
deve derrubar o monitor por causa disso.
"""
import sportmonks_client as sm

# stat_base do alvo -> market_id da Sportmonks para o mercado "total do jogo
# Over/Under" equivalente (mesma estrutura nos 3: label "Over"/"Under",
# total=linha, value=odd decimal) — descoberto inspecionando /odds/pre-match
# em jogos reais (Allsvenskan/Superettan/1.Division + Série A).
MARKET_ID_POR_ALVO = {
    "escanteios": 67,       # "Corners Over Under"
    "chutes_totais": 292,   # "Match Shots"
    "chutes_no_alvo": 291,  # "Match Shots on Target"
}

# Ordem de preferência por confiabilidade/profundidade observada (bet365 é a
# mais completa nas ligas já checadas) — usa a primeira que tiver a linha exata.
CASAS_PREFERENCIA = ["bet365", "Unibet", "10Bet", "1xbet"]


def buscar_odd_real(fixture_id, alvo, direcao, linha):
    """
    Devolve {"odd", "casa", "probabilidade_implicita", "atualizado_em"} para
    o mercado/linha exatos do sinal, ou None se não achar.
    """
    market_id = MARKET_ID_POR_ALVO.get(alvo)
    if market_id is None:
        return None
    label_alvo = "Over" if direcao == "mais_de" else "Under"

    try:
        linhas = sm.odds_inplay_fixture(fixture_id)
    except Exception as e:
        print(f"  [odds ao vivo] erro buscando fixture {fixture_id}: {e}")
        return None
    if not linhas:
        return None

    candidatas = []
    for o in linhas:
        if o.get("market_id") != market_id or o.get("label") != label_alvo:
            continue
        try:
            if float(o.get("total")) != float(linha):
                continue
            odd = float(o.get("value"))
        except (TypeError, ValueError):
            continue
        if odd > 0:
            candidatas.append({**o, "_odd": odd})
    if not candidatas:
        return None

    try:
        casas = sm.bookmakers_mapa()
    except Exception:
        casas = {}
    por_nome_casa = {casas.get(o["bookmaker_id"], str(o["bookmaker_id"])): o for o in candidatas}
    escolhida = nome_casa = None
    for preferida in CASAS_PREFERENCIA:
        if preferida in por_nome_casa:
            escolhida, nome_casa = por_nome_casa[preferida], preferida
            break
    if escolhida is None:
        escolhida = candidatas[0]
        nome_casa = casas.get(escolhida["bookmaker_id"], str(escolhida["bookmaker_id"]))

    return {
        "odd": escolhida["_odd"],
        "casa": nome_casa,
        "probabilidade_implicita": round(1 / escolhida["_odd"], 4),
        "atualizado_em": escolhida.get("latest_bookmaker_update"),
    }
