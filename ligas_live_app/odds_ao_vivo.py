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
específica não ofertada, linha fechada/suspensa no momento, ou erro de
rede). Nunca deve derrubar o monitor por causa disso.

NOTA: até esta correção, sportmonks_client.odds_inplay_fixture() chamava um
endpoint (/odds/inplay/fixtures/{id}) que sempre devolvia "no access" nesta
assinatura — por isso NENHUM dos 7 sinais gerados até aqui tinha achado odd
real, mesmo em ligas com cobertura confirmada. Agora usa /fixtures/{id}
?include=odds, que tem os mesmos dados e funciona (confirmado ao vivo).
"""
from datetime import datetime, timezone

import sportmonks_client as sm

# Quanto tempo uma linha pode ficar sem atualização da própria casa antes de
# deixarmos de tratá-la como "preço ao vivo agora" — descoberto investigando
# uma discrepância real (usuário viu 1.46 na bet365 pro mesmo mercado que o
# painel mostrou 2.20, minutos depois do sinal, sem o placar de escanteios
# ter mudado o suficiente pra justificar). Causa: outros mercados do mesmo
# jogo (vencedor, over/under gols) tinham dezenas de timestamps distintos
# ao longo do jogo, mas o grupo de ESCANTEIOS ficava parado num único
# horário e nunca mais atualizava depois disso — bet365/Sportmonks parecem
# atualizar esse mercado de nicho bem mais devagar que os principais. Sem
# checar isso, o painel podia mostrar um preço morto como se fosse atual.
# 10 minutos é uma primeira estimativa conservadora, a validar com checagens
# ao vivo lado a lado com o app real (ver conversa) — pode precisar ajustar.
IDADE_MAXIMA_ODD_MINUTOS = 10

# stat_base do alvo -> market_id da Sportmonks para o mercado "total do jogo
# Over/Under" equivalente (mesma estrutura nos 3: label "Over"/"Under",
# total=linha, value=odd decimal) — descoberto inspecionando /odds/pre-match
# em jogos reais (Allsvenskan/Superettan/1.Division + Série A).
MARKET_ID_POR_ALVO = {
    "escanteios": 67,       # "Corners Over Under" (linha .5 — mercado principal)
    "chutes_totais": 292,   # "Match Shots"
    "chutes_no_alvo": 291,  # "Match Shots on Target"
}

# Fallback só pra escanteios: "Match Corners" (linha INTEIRA, 3 vias
# Over/Exactly/Under) — descoberto testando um jogo real da Série B (Goiás x
# São Bernardo) que só tinha esse mercado ao vivo, não o "Corners Over Under"
# de linha .5. Conversão pra ficar equivalente à nossa linha .5:
#   mais_de X.5  == Over  X    (final >= X+1, mesma coisa que mais_de X.5)
#   menos_de X.5 == Under X+1  (final <= X,   mesma coisa que menos_de X.5)
MARKET_ID_FALLBACK_ESCANTEIOS = 68  # "Match Corners"

# Só casas confirmadas como autorizadas pela SPA/MF no Brasil (checado em
# ago/2026 — ver conversa) — outras (Unibet, 10Bet, Betfair etc.) ficam de
# fora mesmo que apareçam nos dados, porque o usuário não consegue de fato
# apostar nelas. bet365 primeiro (a que ele usa), 1xbet como fallback: a
# bet365 só mantém 1 linha de escanteios aberta por vez (perto do placar
# atual), enquanto a 1xbet cobre dezenas de linhas .5 simultaneamente —
# testado ao vivo em jogos da Série B, onde a Betfair não tinha NENHUMA
# linha de escanteios. Nota: a autorização da 1xbet no Brasil aparece em
# agregadores mas não foi confirmada direto no SIGAP — aceito pelo usuário
# mesmo assim, dado que é a única opção com cobertura real de escanteios na
# Série B.
CASAS_ACEITAS = ["bet365", "1xbet"]


def _idade_minutos(atualizado_em):
    """Minutos desde latest_bookmaker_update até agora, ou None se não der pra calcular
    (formato inesperado) — nesse caso o chamador trata como se não tivesse idade conhecida."""
    if not atualizado_em:
        return None
    try:
        dt = datetime.strptime(atualizado_em, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    return (datetime.now(timezone.utc) - dt).total_seconds() / 60


def _candidatas_no_mercado(linhas, market_id, label, total_alvo):
    candidatas = []
    for o in linhas:
        if o.get("stopped"):
            continue  # linha fechada/suspensa pela casa — não é um preço aceitável agora
        if o.get("market_id") != market_id or o.get("label") != label:
            continue
        try:
            if float(o.get("total")) != float(total_alvo):
                continue
            odd = float(o.get("value"))
        except (TypeError, ValueError):
            continue
        if odd > 0:
            candidatas.append({**o, "_odd": odd})
    return candidatas


def _tentativas_mercado(alvo, direcao, linha):
    """
    (market_id, label, total) a tentar — TODAS são tentadas e combinadas (não
    para na primeira que achar candidata), porque casas diferentes usam
    formatos diferentes pro mesmo mercado 67 de escanteios: a maioria usa
    linha .5 (Over/Under 8.5), mas a bet365 usa linha INTEIRA dentro do MESMO
    market_id 67 (Over/Under/Exactly 9) — se parássemos na primeira tentativa
    que achasse qualquer candidata, a bet365 nunca entraria no pool pra
    CASAS_PREFERENCIA escolher, mesmo sendo a casa preferida.
    """
    market_id = MARKET_ID_POR_ALVO.get(alvo)
    if market_id is None:
        return []
    label = "Over" if direcao == "mais_de" else "Under"
    tentativas = [(market_id, label, linha)]
    if alvo == "escanteios":
        total_inteiro = int(linha - 0.5) if direcao == "mais_de" else int(linha + 0.5)
        tentativas.append((market_id, label, total_inteiro))  # formato bet365, mesmo market_id
        tentativas.append((MARKET_ID_FALLBACK_ESCANTEIOS, label, total_inteiro))  # formato de outras casas, market_id 68
    return tentativas


def buscar_odd_real(fixture_id, alvo, direcao, linha):
    """
    Devolve {"odd", "casa", "probabilidade_implicita", "atualizado_em"} para
    o mercado/linha exatos do sinal, ou None se não achar.
    """
    tentativas = _tentativas_mercado(alvo, direcao, linha)
    if not tentativas:
        return None

    try:
        linhas = sm.odds_inplay_fixture(fixture_id)
    except Exception as e:
        print(f"  [odds ao vivo] erro buscando fixture {fixture_id}: {e}")
        return None
    if not linhas:
        print(f"  [odds ao vivo] fixture {fixture_id}: API não retornou nenhuma linha de odds ao vivo ainda")
        return None

    candidatas = []
    for market_id, label, total_alvo in tentativas:
        candidatas.extend(_candidatas_no_mercado(linhas, market_id, label, total_alvo))
    if not candidatas:
        # Loga o que a API TEM (pra distinguir "mercado não coberto nesse jogo"
        # de "coberto, mas a linha/label exatos do sinal não bateram") — sem
        # isso, um buscar_odd_real que não acha nada é indistinguível de um bug.
        market_ids_presentes = sorted(set(o.get("market_id") for o in linhas))
        tentado_str = ", ".join(f"market={m} label={l} total={t}" for m, l, t in tentativas)
        print(
            f"  [odds ao vivo] fixture {fixture_id}: nenhuma linha bateu (tentado: {tentado_str}); "
            f"markets presentes na API pra esse jogo: {market_ids_presentes}"
        )
        return None

    try:
        casas = sm.bookmakers_mapa()
    except Exception:
        casas = {}
    por_nome_casa = {casas.get(o["bookmaker_id"], str(o["bookmaker_id"])): o for o in candidatas}
    escolhida = nome_casa = None
    for aceita in CASAS_ACEITAS:
        candidata = por_nome_casa.get(aceita)
        if candidata is None:
            continue
        idade = _idade_minutos(candidata.get("latest_bookmaker_update"))
        if idade is not None and idade > IDADE_MAXIMA_ODD_MINUTOS:
            print(
                f"  [odds ao vivo] fixture {fixture_id}: linha da {aceita} desatualizada há "
                f"{idade:.0f}min (>{IDADE_MAXIMA_ODD_MINUTOS}min) — tratando como preço morto, ignorando"
            )
            continue
        escolhida, nome_casa = candidata, aceita
        break
    if escolhida is None:
        print(f"  [odds ao vivo] fixture {fixture_id}: nenhuma linha fresca em {CASAS_ACEITAS} agora — sem odd real")
        return None

    return {
        "odd": escolhida["_odd"],
        "casa": nome_casa,
        "probabilidade_implicita": round(1 / escolhida["_odd"], 4),
        "atualizado_em": escolhida.get("latest_bookmaker_update"),
    }
