"""
Gera ligas_live_app/regras_sinais.json a partir dos CSVs de confirmação
(resultados/*_confirmacao_*stat.csv) — o mesmo dado usado nos resumos em
Excel/HTML, só que aqui em formato que o painel ao vivo consegue carregar e
avaliar contra estatísticas de jogo em tempo real.

Critério do subconjunto ("sinais fortes"): amostra >= 200 jogos nas ligas de
confirmação E impacto >= 5 p.p. — reduz risco de o painel virar alerta demais
enquanto o comportamento ao vivo ainda não foi observado. Dá pra afrouxar
depois editando AMOSTRA_MINIMA/IMPACTO_MINIMO abaixo e rodando de novo.

Uso: python3 gerar_regras_sinais.py
"""
import csv
import glob
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from buscar_sportmonks import VERSAO_ROTULO

BASE = os.path.join(os.path.dirname(__file__), "resultados")
DADOS_DIR = os.path.join(os.path.dirname(__file__), "dados")
DESTINO = os.path.join(os.path.dirname(__file__), "..", "ligas_live_app", "regras_sinais.json")

AMOSTRA_MINIMA_VALOR_ATUAL = 30  # abaixo disso, a proporção não é confiável — busca o valor_atual vizinho

# Offsets de linha pra recalibrar em recalibrar_por_valor_atual (ver docstring)
# — case real reportado (Norrby x Varberg BoIS, 14/09/2026): sinal calibrado
# pra "mais de 11.5" escanteios aos 30min (9 escanteios já feitos) só tinha
# linhas_vizinhas ±1 (10.5/12.5) pra tentar achar odd real, mas o mercado
# (bet365, market 68, escanteios) já tinha fechado 10.5/12.5/13.5 no momento
# do sinal — jogo com ritmo de escanteios muito acima do normal, o mercado
# ao vivo reprecifica rápido demais pra ±1 linha acompanhar. Ampliado pra ±3
# pra dar mais chance de achar uma linha ainda aberta com probabilidade
# calibrada (não é ilimitado: linhas mais distantes já têm amostra mais fraca
# do próprio valor_atual, e _tabela_com_fallback já lida com isso).
OFFSETS_LINHAS_VIZINHAS = (-3, -2, -1, 1, 2, 3)

AMOSTRA_MINIMA = 200
IMPACTO_MINIMO_PP = 5.0

# Piso mais permissivo só pra confirmação nórdica (Superettan+1.Division) —
# ver conversa: esse pool tem só 1.448 jogos no total (Allsvenskan fica de
# fora, é a liga de descoberta), contra ~2.284 do Brasil, então exigir os
# mesmos 200 de lá deixa MUITA condição sem amostra suficiente pra sequer ser
# testada. Baixar pra 150 recupera sinal genuíno ali (12 -> 23 aplicáveis em
# jogo nórdico, a maioria virando "universal"). NÃO se aplica ao Brasil — lá
# a amostra já é abundante, e afrouxar o piso só pioraria o problema que a
# dedup por âncora foi criada pra conter (excesso de sinal, não falta).
AMOSTRA_MINIMA_NORDICAS = 150

ALVOS = ["escanteios", "chutes_totais", "chutes_no_alvo", "gols", "cartoes"]
# Alvos com regras "regiao=brasil" — confirmam contra Série A/B mas NÃO
# confirmaram nas ligas nórdicas (ou nem chegaram a amostra_confirmacao>=200
# lá), então só entram no painel restritas a jogos do Brasil (ver
# live_monitor.py::_regra_vale_para_liga). Ver histórico da decisão na
# conversa: cartões confirma forte no Brasil (28/32 + 72/128, vários
# p<0.0001) mas 0/14 + 0/46 nas nórdicas.
#
# Estendido pra escanteios/chutes_totais/chutes_no_alvo (ver conversa,
# "estratégias pra mais sinais"): depois de corrigir LIGAS_MONITORADAS
# (A Lyga/1.Lyga saíram do pool nórdico), a amostra nas nórdicas ficou menor
# (só Superettan+1.Division) e várias condições que antes confirmavam
# universalmente passaram a faltar amostra lá — mas continuam com amostra de
# sobra no Brasil (Série A+B, ~2200 jogos). Em vez de juntar as regiões num
# teste só (risco real de paradoxo de Simpson — um efeito forte só no Brasil
# pode "carregar" um teste combinado mesmo sem existir nas nórdicas, ou
# mascarar o inverso), cada condição prova o que prova na sua própria
# região, exatamente como cartões já fazia.
ALVOS_REGIAO_BRASIL = ["escanteios", "chutes_totais", "chutes_no_alvo", "cartoes"]
ALVO_TITULO = {
    "escanteios": "Escanteios", "chutes_totais": "Chutes totais",
    "chutes_no_alvo": "Chutes no alvo", "gols": "Gols", "cartoes": "Cartões",
}
# stat_base do próprio alvo (o que o mercado "Mais de/Menos de" mede) —
# mesmo campo usado em alvos.ALVOS[alvo]["campos_base"], já resolvido pro
# nome que buscar_sportmonks/xg_pressure usam pra extrair da API.
ALVO_STAT_BASE = {
    "escanteios": "corners", "chutes_totais": "shots_total",
    "chutes_no_alvo": "shots_on_target", "gols": "goals", "cartoes": "cards",
}

# Mesmo dicionário de tradução usado nos resumos em Excel/HTML — mantém o
# rótulo do painel ao vivo legível em português em vez de stat_base cru.
TRAD = {
    "shots_total": "Chutes totais", "shots_on_target": "Chutes no alvo",
    "shots_insidebox": "Chutes de dentro da área", "shots_outsidebox": "Chutes de fora da área",
    "attacks": "Ataques", "dangerous_attacks": "Ataques perigosos",
    "total_crosses": "Cruzamentos", "accurate_crosses": "Cruzamentos certos",
    "key_passes": "Passes-chave", "corners": "Escanteios", "fouls": "Faltas",
    "tackles": "Desarmes", "duels_won": "Duelos vencidos", "offsides": "Impedimentos",
    "interceptions": "Interceptações", "successful_dribbles_percentage": "% dribles certos",
    "successful_dribbles": "Dribles certos", "saves": "Defesas", "goal_attempts": "Finalizações",
}


def nome(stat_base):
    return TRAD.get(stat_base, stat_base)


def ler_csv(caminho):
    try:
        with open(caminho, newline="", encoding="utf-8") as f:
            linhas = list(csv.DictReader(f))
    except FileNotFoundError:
        return []
    if not linhas or "confirmado_bh" not in linhas[0]:
        return []
    return [r for r in linhas if r["confirmado_bh"] == "True"]


LIGAS_BRASIL = {648, 651}  # Série A, Série B — ver REGIOES_REGRA abaixo
LIGAS_NORDICAS = {573, 579, 447}  # Allsvenskan, Superettan, 1. Division


def _carregar_dados_pooled():
    """fixture_id -> {minuto: snapshot}, fixture_id -> resultados_alvo, fixture_id -> league_id
    (extraído do próprio nome do arquivo .checkpoint_<league_id>.json) — todas as ligas juntas.

    Só entram checkpoints cujos rótulos estão na versão ATUAL
    (buscar_sportmonks.VERSAO_ROTULO). Misturar versões aqui é silencioso e
    caro: uma regra de região "universal" recalibra sobre o pool inteiro
    (fixtures_desta_regiao = None em recalibrar_por_valor_atual), então
    checkpoints de ligas que não foram rebuscadas — ex.: 405/408, de
    explorações antigas, ~1.115 jogos — entrariam com rótulos da fonte velha
    (`trends`) no cálculo da probabilidade publicada, justamente a fonte que
    a correção de rótulo existe pra parar de usar."""
    snaps_por_fixture = {}
    resultados = {}
    liga_por_fixture = {}
    ignorados = []
    for caminho in glob.glob(f"{DADOS_DIR}/.checkpoint_*.json"):
        sufixo = os.path.basename(caminho).removeprefix(".checkpoint_").removesuffix(".json")
        if not sufixo.isdigit():
            continue  # não é checkpoint de liga (ex.: checkpoints dos scripts de backtest)
        league_id = int(sufixo)
        d = json.load(open(caminho, encoding="utf-8"))
        versao = d.get("versao_rotulo", 1)
        if versao != VERSAO_ROTULO:
            ignorados.append((league_id, versao, len(d["resultados_alvo"])))
            continue
        for fid_str, res in d["resultados_alvo"].items():
            resultados[int(fid_str)] = res
            liga_por_fixture[int(fid_str)] = league_id
        for snap in d["snapshots"]:
            snaps_por_fixture.setdefault(snap["fixture_id"], {})[snap["minuto"]] = snap
    if ignorados:
        for league_id, versao, n in sorted(ignorados):
            print(f"  [aviso] liga {league_id} ignorada no pool: rótulos na versão {versao}, "
                  f"a atual é {VERSAO_ROTULO} ({n} jogos fora)")
    print(f"  pool: {len(resultados)} jogos de {len(set(liga_por_fixture.values()))} ligas "
          f"(rótulos versão {VERSAO_ROTULO})")
    return snaps_por_fixture, resultados, liga_por_fixture


def _valor_stat_alvo(snap, stat_alvo):
    """
    Valor da estatística-ALVO (não das condições) num snapshot. Caso especial
    "cards" (cartões): o snapshot não tem esse campo direto, só
    "yellowcards"/"redcards" separados (mesmo motivo do fix em
    ligas_live_app/xg_pressure.py::extrair_stats_para_regras) — soma os dois
    aqui, do jeito que resultados_alvo[fid]["cartoes"] também soma pro
    resultado FINAL.
    """
    if stat_alvo == "cards":
        amarelos = snap.get("yellowcards")
        vermelhos = snap.get("redcards")
        if amarelos is None or vermelhos is None:
            return None
        return amarelos + vermelhos
    return snap.get(stat_alvo)


def _condicao_bate(condicoes, snap):
    for c in condicoes:
        v = snap.get(c["stat"])
        if v is None:
            return False
        if c["operador"] == ">=" and v < c["limite"]:
            return False
        if c["operador"] == "<=" and v > c["limite"]:
            return False
    return True


# Nunca deixa o fallback (regressão) devolver uma certeza absoluta — é uma
# EXTRAPOLAÇÃO fora do dado observado, não uma medição direta; publicar
# p=100% (ou 0%) tornaria odd_minima=1/p degenerada (1.00, sem espaço pra
# EV) e afirmaria uma certeza que os dados não sustentam.
P_MIN_FALLBACK = 0.02
P_MAX_FALLBACK = 0.98


def _tabela_com_fallback(casos_por_valor):
    """
    {valor_atual: [bateu, ...]} -> {valor_atual: {"n":.., "n_usado":.., "p":..}}.

    Pros valores com amostra própria suficiente (>=AMOSTRA_MINIMA_VALOR_ATUAL),
    usa a proporção observada direto. Pros demais, ANTES usava a proporção do
    valor_atual vizinho mais próximo por distância absoluta — bug real
    reportado (Norrby x Varberg BoIS, 14/09/2026): "mais de 11.5 escanteios"
    aos 30min com 9 escanteios já feitos mostrava 70.5% de probabilidade,
    idêntico ao que valeria pra só 7 escanteios — o vizinho mais próximo COM
    amostra suficiente era 7 (nada com amostra boa existe acima disso pra essa
    condição), e todo valor de 8 em diante ficava "empacado" nesse mesmo
    número, mesmo sendo estatisticamente óbvio que mais escanteios já feitos
    só pode aumentar (nunca diminuir) a chance de passar de uma linha fixa.

    Corrigido com uma regressão linear (ponderada pelo tamanho de amostra de
    cada ponto) sobre os valores QUE TÊM amostra suficiente — usada tanto pra
    INTERPOLAR (valor sem amostra própria entre dois pontos confiáveis) quanto
    pra EXTRAPOLAR (valor além do maior/menor ponto confiável, como o caso
    acima). Isso respeita a tendência real dos dados em vez de travar num
    platô artificial. Resultado clipado em [P_MIN_FALLBACK, P_MAX_FALLBACK] —
    é extrapolação, nunca uma medição direta, então nunca deveria virar 0%/100%.

    Com só 1 ponto de amostra suficiente (não dá pra ajustar reta), cai pro
    comportamento antigo (usa a proporção desse único ponto). Sem NENHUM
    ponto de amostra suficiente, último recurso: usa a própria amostra
    pequena (pode ser pouco confiável, mas não há nada melhor disponível).
    """
    com_amostra = sorted(v for v, casos in casos_por_valor.items() if len(casos) >= AMOSTRA_MINIMA_VALOR_ATUAL)

    slope = intercept = None
    if len(com_amostra) >= 2:
        pesos = [len(casos_por_valor[v]) for v in com_amostra]
        proporcoes = [sum(casos_por_valor[v]) / len(casos_por_valor[v]) for v in com_amostra]
        soma_pesos = sum(pesos)
        media_x = sum(w * x for w, x in zip(pesos, com_amostra)) / soma_pesos
        media_y = sum(w * y for w, y in zip(pesos, proporcoes)) / soma_pesos
        variancia_x = sum(w * (x - media_x) ** 2 for w, x in zip(pesos, com_amostra))
        if variancia_x > 0:
            covariancia = sum(w * (x - media_x) * (y - media_y) for w, x, y in zip(pesos, com_amostra, proporcoes))
            slope = covariancia / variancia_x
            intercept = media_y - slope * media_x

    tabela = {}
    for valor, casos in casos_por_valor.items():
        if len(casos) >= AMOSTRA_MINIMA_VALOR_ATUAL:
            tabela[valor] = {"n": len(casos), "n_usado": len(casos), "p": sum(casos) / len(casos)}
            continue
        if slope is not None:
            p = max(P_MIN_FALLBACK, min(P_MAX_FALLBACK, intercept + slope * valor))
            n_usado = sum(len(casos_por_valor[v]) for v in com_amostra)
        elif com_amostra:
            casos_uso = casos_por_valor[min(com_amostra, key=lambda v: abs(v - valor))]
            p, n_usado = sum(casos_uso) / len(casos_uso), len(casos_uso)
        else:
            p, n_usado = (sum(casos) / len(casos) if casos else 0.0), len(casos)
        tabela[valor] = {"n": len(casos), "n_usado": n_usado, "p": p}
    return tabela


def recalibrar_por_valor_atual(regras):
    """
    Recalcula p_condicao/p_base de cada regra CONDICIONADO ao valor atual
    exato da própria estatística-alvo (escanteios/chutes já ocorridos no
    momento do snapshot) — a versão original só condicionava em
    minuto+placar+condição, então duas partidas no mesmo minuto/placar com a
    mesma condição mas progressos bem diferentes do próprio alvo (1
    escanteio vs. 6 aos 45') recebiam a MESMA probabilidade. Caso real
    reportado: odd mínima de 1,33 mostrada quando a chance real (dado só 1
    escanteio até ali) era >95% — o jogo já tinha decidido o mercado sozinho.

    Usa as 5 ligas juntas (não só a Allsvenskan) — isso não é uma nova
    descoberta de condição (já feita e confirmada antes), é só uma
    reestimativa mais fina de uma condição já fixada, então usar mais dado
    aqui não tem o mesmo risco de vazamento que teria na descoberta original.

    Também recalcula a mesma coisa pras linhas VIZINHAS (ver OFFSETS_LINHAS_VIZINHAS,
    mesma direção) —
    caso real reportado: casa de apostas só tinha "mais de 10.5" disponível
    quando o sinal era calibrado pra "mais de 9.5"; sem isso, não dava pra
    saber a probabilidade real de bater a linha que realmente estava
    disponível pra apostar, só a da linha original. Guardado em
    "linhas_vizinhas" pra não mexer no formato já existente (linha original
    continua nas chaves de sempre, por compatibilidade).

    A probabilidade em si (p_condicao/p_base) é estimada agrupando por DELTA
    — "quanto falta pra bater a linha" (linha_off - valor_atual), não pelo
    valor_atual sozinho pra uma linha FIXA. Achado real (ver conversa,
    14/09/2026 — Norrby x Varberg BoIS): pra essa mesma regra, valor_atual=4
    faltando 5 (linha 8.5), valor_atual=5 faltando 5 (linha 9.5), valor=6
    faltando 5 (linha 10.5) e valor=7 faltando 5 (linha 11.5) — todos com
    amostra própria boa (n>=30) — deram 66%, 69%, 64% e 70% respectivamente:
    praticamente CONSTANTE. Ou seja, "quanto falta" prevê a probabilidade
    muito melhor do que o valor absoluto sozinho — faz sentido, já que o
    tempo restante até o fim do jogo é o mesmo pro checkpoint fixo (minuto da
    regra), então a distribuição de quantos escanteios ainda saem depende
    muito mais de "quantos faltam" do que de "quantos já saíram". Agrupar por
    delta (em vez de por valor, por linha fixa) junta a amostra de VÁRIOS
    (valor, linha vizinha) diferentes que head pro mesmo delta — muito mais
    dado por ponto, e generaliza de verdade pra valor_atual raros (extrapolar
    em cima do delta, que é estável, é muito mais seguro que extrapolar em
    cima do valor absoluto pra uma linha fixa, que decai rápido por pura
    escassez de amostra em cada linha isolada).
    """
    snaps_por_fixture, resultados, liga_por_fixture = _carregar_dados_pooled()

    for regra in regras:
        stat_alvo, linha, direcao = regra["mercado"]["stat"], regra["mercado"]["linha"], regra["mercado"]["direcao"]
        alvo = regra["alvo"]
        linhas_a_calcular = {0: linha}
        linhas_a_calcular.update({off: linha + off for off in OFFSETS_LINHAS_VIZINHAS})

        # Regra "brasil" só vale pra Série A/B; "nordicas" só vale pras 3
        # ligas nórdicas — nenhuma das duas foi confirmada (ou nem chegou a
        # amostra suficiente) na região oposta, então recalibrar com o pool
        # errado misturado diluiria/distorceria o efeito real com dado de uma
        # região onde ele nem se sustentou. Regra "universal" usa o pool
        # inteiro, como sempre (ver REGIOES_REGRA).
        if regra.get("regiao") == "brasil":
            fixtures_desta_regiao = {fid for fid, lid in liga_por_fixture.items() if lid in LIGAS_BRASIL}
        elif regra.get("regiao") == "nordicas":
            fixtures_desta_regiao = {fid for fid, lid in liga_por_fixture.items() if lid in LIGAS_NORDICAS}
        else:
            fixtures_desta_regiao = None

        # offset -> valor_atual -> [bateu, ...] — só pra "n" (transparência:
        # quantos jogos de referência tinham EXATAMENTE esse valor_atual e
        # bateram a condição), o formato de sempre.
        casos_condicao_por_valor = {off: {} for off in linhas_a_calcular}
        # delta (linha_off - valor_atual) -> [bateu, ...] — POOLED entre todos
        # os (offset, valor_atual) que caem no mesmo delta, usado pra estimar
        # p_condicao/p_base de verdade (ver docstring acima).
        casos_condicao_por_delta = {}
        casos_base_por_delta = {}
        # Complemento = "NAO cumpre a condicao" (subconjunto proprio da base,
        # que inclui a condicao) -- achado da auditoria de metodologia
        # (15/09/2026): medir impacto contra a base dilui o numero, porque a
        # base ja contem o grupo condicao dentro dela. Guardado so pra
        # transparencia (impacto_vs_complemento_pp abaixo); o portao ao vivo
        # (IMPACTO_MINIMO_PP_VALOR_ATUAL em live_monitor.py) continua
        # comparando contra impacto_pp (vs base), sem mudanca de comportamento.
        casos_complemento_por_delta = {}

        for fid, snaps in snaps_por_fixture.items():
            if fixtures_desta_regiao is not None and fid not in fixtures_desta_regiao:
                continue
            snap = snaps.get(regra["minuto"])
            if not snap or snap.get("gols_momento") != regra["gols_momento"]:
                continue
            res = resultados.get(fid)
            valor_stat_alvo = _valor_stat_alvo(snap, stat_alvo)
            if not res or res.get(alvo) is None or valor_stat_alvo is None:
                continue
            valor_atual = int(valor_stat_alvo)
            condicao_ok = _condicao_bate(regra["condicoes"], snap)
            for off, linha_off in linhas_a_calcular.items():
                bateu = (res[alvo] > linha_off) if direcao == "mais_de" else (res[alvo] < linha_off)
                delta = linha_off - valor_atual
                casos_base_por_delta.setdefault(delta, []).append(bateu)
                if condicao_ok:
                    casos_condicao_por_valor[off].setdefault(valor_atual, []).append(bateu)
                    casos_condicao_por_delta.setdefault(delta, []).append(bateu)
                else:
                    casos_complemento_por_delta.setdefault(delta, []).append(bateu)

        tabela_condicao_por_delta = _tabela_com_fallback(casos_condicao_por_delta)
        tabela_base_por_delta = _tabela_com_fallback(casos_base_por_delta)
        tabela_complemento_por_delta = _tabela_com_fallback(casos_complemento_por_delta)

        por_valor_atual = {}
        for valor, casos_deste_valor in casos_condicao_por_valor[0].items():
            delta_0 = linha - valor
            p_condicao = tabela_condicao_por_delta[delta_0]["p"]
            p_base = tabela_base_por_delta.get(delta_0, {"p": regra["prob_base_confirmacao"]})["p"]
            linhas_vizinhas = {}
            for off in OFFSETS_LINHAS_VIZINHAS:
                casos_off_deste_valor = casos_condicao_por_valor[off].get(valor)
                if casos_off_deste_valor is None:
                    continue
                delta_off = linhas_a_calcular[off] - valor
                entrada_delta = tabela_condicao_por_delta[delta_off]
                p_off = entrada_delta["p"]
                p_base_off = tabela_base_por_delta.get(delta_off, {"p": p_base})["p"]
                p_complemento_off = tabela_complemento_por_delta.get(delta_off, {"p": p_base_off})["p"]
                linhas_vizinhas[str(off)] = {
                    "linha": linhas_a_calcular[off],
                    "n": len(casos_off_deste_valor),
                    "n_usado": entrada_delta["n_usado"],
                    "p_condicao": round(p_off, 4),
                    "impacto_pp": round((p_off - p_base_off) * 100, 2),
                    "impacto_vs_complemento_pp": round((p_off - p_complemento_off) * 100, 2),
                    "odd_minima": round(1 / p_off, 2) if p_off > 0 else None,
                }
            p_complemento = tabela_complemento_por_delta.get(delta_0, {"p": p_base})["p"]
            por_valor_atual[str(valor)] = {
                "n": len(casos_deste_valor),
                "n_usado": tabela_condicao_por_delta[delta_0]["n_usado"],
                "p_condicao": round(p_condicao, 4),
                "p_base": round(p_base, 4),
                "impacto_pp": round((p_condicao - p_base) * 100, 2),
                # Transparencia (ver auditoria 15/09/2026): impacto contra quem
                # NAO cumpre a condicao, nao contra a base (que ja inclui a
                # condicao dentro dela e por isso dilui o numero). NAO e usado
                # em nenhum portao/selecao -- so pra leitura humana de quanto o
                # efeito realmente vale. p_base usado como fallback quando o
                # delta nao tem amostra propria de complemento.
                "p_complemento": round(p_complemento, 4),
                "impacto_vs_complemento_pp": round((p_condicao - p_complemento) * 100, 2),
                "odd_minima": round(1 / p_condicao, 2) if p_condicao > 0 else None,
                "linhas_vizinhas": linhas_vizinhas,
            }
        regra["por_valor_atual"] = por_valor_atual

    return regras


def _carregar_brutas(alvos_lista, sufixo="", origem=None):
    """
    Lê {alvo}_confirmacao{sufixo}_1stat.csv/_2stats.csv (confirmado_bh=True)
    pra cada alvo em alvos_lista. sufixo="" lê a confirmação nórdica de
    sempre; sufixo="_brasil" lê a confirmação HERDADA (condição descoberta na
    Allsvenskan, confirmada contra Série A/B); sufixo="_serieB" lê a
    confirmação NATIVA (condição descoberta na própria Série A, confirmada na
    Série B — ver descobrir_nativo_brasil.py). "origem" marca qual é qual,
    usado por _selecionar_brasil_por_confianca pra saber quando uma condição
    foi achada pelos DOIS caminhos independentes (ver conversa).
    """
    brutas = []
    for alvo_id in alvos_lista:
        for r in ler_csv(f"{BASE}/{alvo_id}_confirmacao{sufixo}_1stat.csv"):
            brutas.append({
                "alvo_id": alvo_id,
                "minuto": int(r["minuto"]),
                "gols_momento": int(r["gols_momento"]),
                "condicao_chave": (r["stat"], r["operador"], r["limite"]),
                "condicoes": [{"stat": r["stat"], "operador": r["operador"], "limite": float(r["limite"])}],
                "linha_mercado": float(r["mercado"][1:]),
                "sinal_mercado": r["mercado"][0],
                "amostra": int(r["amostra_outras_ligas"]),
                "p_base": float(r["p_base_outras_ligas"]),
                "p_condicao": float(r["p_final_outras_ligas"]),
                "impacto": float(r["impacto_outras_ligas_pp"]),
                # Transparencia (auditoria 15/09/2026) -- .get() com fallback
                # pro proprio impacto (vs base) protege contra CSV antigo
                # (gerado antes desta mudanca) sem a coluna nova.
                "impacto_vs_complemento": float(r["impacto_vs_complemento_outras_ligas_pp"]) if "impacto_vs_complemento_outras_ligas_pp" in r else float(r["impacto_outras_ligas_pp"]),
                "p_valor": float(r["p_valor_outras_ligas"]),
                "origem": origem,
            })
        for r in ler_csv(f"{BASE}/{alvo_id}_confirmacao{sufixo}_2stats.csv"):
            p_base = float(r["p_base_outras_ligas"])
            p_cond = float(r["p_conjunta_outras_ligas"])
            impacto = (p_cond - p_base) * 100
            brutas.append({
                "alvo_id": alvo_id,
                "minuto": int(r["minuto"]),
                "gols_momento": int(r["gols_momento"]),
                "condicao_chave": (r["stat1"], r["operador1"], r["limite1"], r["stat2"], r["operador2"], r["limite2"]),
                "condicoes": [
                    {"stat": r["stat1"], "operador": r["operador1"], "limite": float(r["limite1"])},
                    {"stat": r["stat2"], "operador": r["operador2"], "limite": float(r["limite2"])},
                ],
                "linha_mercado": float(r["mercado"][1:]),
                "sinal_mercado": r["mercado"][0],
                "amostra": int(r["amostra_outras_ligas"]),
                "p_base": p_base,
                "p_condicao": p_cond,
                "impacto": impacto,
                "impacto_vs_complemento": float(r["impacto_vs_complemento_outras_ligas_pp"]) if "impacto_vs_complemento_outras_ligas_pp" in r else impacto,
                "p_valor": float(r["p_valor_outras_ligas"]),
                "origem": origem,
            })
    return brutas


def _colapsar(brutas):
    """Colapsa cada par mais-de/menos-de da mesma linha, ficando só com o lado
    favorável — mesmo critério já usado no Excel "Sinais". Inclui "origem" na
    chave: uma condição herdada e uma nativa que caem exatamente no mesmo
    limite/linha NÃO se fundem aqui (perderia a informação de que vieram de
    dois processos de descoberta distintos) — só se fundem, se for o caso,
    na etapa de família (_selecionar_brasil_por_confianca)."""
    grupos = {}
    for item in brutas:
        chave = (
            item["alvo_id"], item["minuto"], item["gols_momento"],
            item["condicao_chave"], item["linha_mercado"], item["origem"],
        )
        grupos.setdefault(chave, []).append(item)
    return [max(itens, key=lambda x: x["impacto"]) for itens in grupos.values()]


def _ancoras_1stat(itens):
    """(alvo, minuto, gols_momento, stat, operador) de toda condição de 1 SÓ
    estatística que, sozinha, já passou no filtro de amostra/impacto — usado
    por _chave_familia pra achatar combinações de 2 estatísticas que usam uma
    dessas âncoras.

    Achado real (ver conversa): em escanteios-Brasil, "Cruzamentos >= N" sozinho
    já confirma em 192/246 das condições de 1 stat — e aparece em 680/1100 das
    condições de 2 stats, combinado com DEZENAS de parceiros diferentes
    (Ataques, Passes-chave, Duelos vencidos, Chutes, Defesas, Impedimentos...)
    que são todos, eles mesmos, correlacionados com o mesmo fenômeno de fundo
    (intensidade ofensiva) — não são 80 histórias novas, é 1 história (cruzamento
    prevê escanteio no Brasil) redescoberta 80 vezes com ruído de parceiro.
    Mesmo padrão em cartões: "Faltas >= N" sozinho é 100% das condições de 1
    stat e aparece em 70/72 das de 2 stats.
    """
    return {
        (it["alvo_id"], it["minuto"], it["gols_momento"], it["condicoes"][0]["stat"], it["condicoes"][0]["operador"])
        for it in itens if len(it["condicoes"]) == 1
    }


def _chave_familia(item, ancoras):
    """
    Agrupa por (alvo, minuto, gols_momento, conjunto de stat+direção usados) —
    ignora o limite exato de cada condição e a linha de mercado, que são
    exatamente o que mais explode em variações quase-idênticas da MESMA
    história (achado real, ver conversa: gerar 511 regras de escanteios pro
    Brasil, 167 só num checkpoint — quase todas eram "Cruzamentos>=6" ou
    "Ataques>=31 E Cruzamentos<=N" fatiado em 4-5 linhas de mercado x vários
    limites vizinhos de N, não histórias diferentes). _colapsar já junta o par
    mais/menos NA MESMA linha; isso aqui vai além, juntando linhas e limites
    diferentes da mesma combinação de estatísticas+direção.

    Além disso (ver _ancoras_1stat): se a condição é de 2 estatísticas e UMA
    delas já vale sozinha (é uma âncora) pro mesmo alvo/minuto/placar, a família
    é a da âncora sozinha, não a do par — assim "Cruzamentos>=6 E X" pra
    qualquer X cai na MESMA família que "Cruzamentos>=6" sozinho, em vez de
    cada parceiro X virar uma "descoberta" própria.
    """
    if len(item["condicoes"]) == 2:
        base = (item["alvo_id"], item["minuto"], item["gols_momento"])
        for c in item["condicoes"]:
            if (*base, c["stat"], c["operador"]) in ancoras:
                return (*base, frozenset({(c["stat"], c["operador"])}))
    condset = frozenset((c["stat"], c["operador"]) for c in item["condicoes"])
    return (item["alvo_id"], item["minuto"], item["gols_momento"], condset)


def _deduplicar_familia(itens):
    """Mantém só a variação de MAIOR impacto de cada família (ver _chave_familia) —
    aplicado DEPOIS do filtro de amostra/impacto mínimos (fortes/fortes_brasil),
    não antes: assim, se a variação de maior impacto não tivesse amostra
    suficiente mas uma vizinha tivesse, a família inteira já teria sido
    descartada de qualquer forma (o candidato a "melhor" já é sempre um que
    passou no filtro)."""
    ancoras = _ancoras_1stat(itens)
    grupos = {}
    for item in itens:
        grupos.setdefault(_chave_familia(item, ancoras), []).append(item)
    return [max(grupo, key=lambda x: x["impacto"]) for grupo in grupos.values()]


# Piso de confirmações independentes exigido para uma condição do Brasil
# entrar no painel. Calibrado por backtest retroativo contra odds reais de
# mercado (3.876 jogos, ver conversa): confirmacoes=1 rendeu ROI real de
# -12.3% (79 apostas), confirmacoes=2 rendeu -8.1% (821 apostas), e só
# confirmacoes=3 (as três fontes de descoberta independentes concordando —
# herdado, nativo A->B e nativo B->A) rendeu ROI real positivo, +5.6% (159
# apostas). Ou seja: 1 ou 2 fontes passam no teste estatístico interno mas
# não representam edge real contra o mercado; só a tripla confirmação
# sobrevive. Tudo que não bate esse piso fica de fora do painel mas
# registrado em CAMINHO_AUDITORIA_BRASIL (nada é descartado sem rastro).
CONFIRMACOES_MINIMAS_BRASIL = 3
CAMINHO_AUDITORIA_BRASIL = os.path.join(BASE, "brasil_candidatos_nao_incluidos.csv")


def _selecionar_brasil_por_confianca(itens_combinados):
    """
    Agrupa por família (ver _chave_familia) o pool JÁ COMBINADO de condições
    de até TRÊS processos de descoberta independentes do Brasil: herdado
    (Allsvenskan -> confirmado em Série A/B), nativo A->B (descoberto na
    Série A -> confirmado na Série B) e nativo B->A (descoberto na Série B ->
    confirmado na Série A). Dentro de cada família, só entra a melhor
    variação se as TRÊS origens sobreviveram nela (confirmacoes >= 3, ver
    CONFIRMACOES_MINIMAS_BRASIL) — famílias confirmadas por 1 ou 2 fontes
    ficam de fora do painel, mas registradas em CAMINHO_AUDITORIA_BRASIL
    (nada é descartado sem deixar rastro).
    """
    ancoras = _ancoras_1stat(itens_combinados)
    grupos = {}
    for item in itens_combinados:
        grupos.setdefault(_chave_familia(item, ancoras), []).append(item)

    selecionados, nao_incluidos = [], []
    for grupo in grupos.values():
        origens = {i["origem"] for i in grupo}
        melhor = max(grupo, key=lambda x: x["impacto"])
        melhor["confirmacoes"] = len(origens)
        if len(origens) >= CONFIRMACOES_MINIMAS_BRASIL:
            selecionados.append(melhor)
        else:
            nao_incluidos.append(melhor)
    return selecionados, nao_incluidos


def _remover_sobreposicoes(itens):
    """
    Remove contradições reais entre regras de 1 SÓ estatística que
    compartilham alvo/minuto/placar/linha de mercado: uma diz "stat >= X",
    outra "stat <= Y" — se X <= Y, um jogo com o valor nessa faixa
    ([X,Y]) dispara as duas ao mesmo tempo, com direções OPOSTAS do mesmo
    mercado (achado real, ver conversa: "Passes-chave" em chutes_no_alvo/
    chutes_totais — ex. Passes-chave=15 disparava tanto "Mais de 7.5"
    quanto "Menos de 7.5" chutes no alvo aos 75'). Mantém só a de maior
    impacto de cada par sobreposto; não mexe em condições de 2 estatísticas
    (nenhum caso encontrado lá) nem em pares que não se sobrepõem (ex.:
    "Mais de 8.5" com "Menos de 9.5" em linhas de mercado diferentes —
    isso é normal, as duas linhas podem bater ao mesmo tempo sem
    contradição).
    """
    grupos = defaultdict(list)
    passam_direto = []
    for item in itens:
        if len(item["condicoes"]) != 1:
            passam_direto.append(item)
            continue
        c = item["condicoes"][0]
        chave = (item["alvo_id"], item["minuto"], item["gols_momento"], item["linha_mercado"], c["stat"])
        grupos[chave].append(item)

    resultado = list(passam_direto)
    for grupo in grupos.values():
        maiores = [it for it in grupo if it["condicoes"][0]["operador"] == ">="]
        menores = [it for it in grupo if it["condicoes"][0]["operador"] == "<="]
        excluidos = set()
        for ma in maiores:
            for me in menores:
                if ma["condicoes"][0]["limite"] <= me["condicoes"][0]["limite"]:
                    pior = ma if ma["impacto"] < me["impacto"] else me
                    excluidos.add(id(pior))
        resultado.extend(it for it in grupo if id(it) not in excluidos)
    return resultado


def _salvar_nao_incluidos(itens, caminho):
    linhas = []
    for it in itens:
        cond_txt = " E ".join(f"{c['stat']}{c['operador']}{c['limite']:g}" for c in it["condicoes"])
        linhas.append({
            "alvo_id": it["alvo_id"], "minuto": it["minuto"], "gols_momento": it["gols_momento"],
            "condicoes": cond_txt, "mercado": f"{it['sinal_mercado']}{it['linha_mercado']:g}",
            "origem_melhor_variacao": it["origem"], "confirmacoes": it["confirmacoes"],
            "amostra": it["amostra"], "impacto_pp": round(it["impacto"], 2),
            "motivo": f"confirmado por só {it['confirmacoes']} de 3 processos de descoberta "
                      f"(exige {CONFIRMACOES_MINIMAS_BRASIL})",
        })
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        if not linhas:
            f.write("(nenhum candidato ficou de fora)\n")
            return
        writer = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        writer.writeheader()
        writer.writerows(linhas)


def _carregar_confirmadas_brasil():
    """
    (alvo_id, minuto, gols_momento, mercado '+/-N', frozenset de (stat,operador,limite))
    confirmadas contra Série A + Série B (pesquisa_gols/confirmar_brasil.py) — mesmo teste
    estatístico formal (duas proporções + Benjamini-Hochberg) usado na confirmação nórdica,
    só que rodado de novo contra o Brasil como dataset de confirmação. Exigir as duas
    (nórdicas E Brasil) garante que uma regra só entra no painel se já se provou fora de
    UMA amostra (nórdicas -> Allsvenskan) E de uma REGIÃO inteira diferente (Brasil), não só
    de mais jogos da mesma vizinhança de ligas.
    """
    chaves = set()
    for alvo_id in ALVOS:
        for r in ler_csv(f"{BASE}/{alvo_id}_confirmacao_brasil_1stat.csv"):
            condset = frozenset({(r["stat"], r["operador"], float(r["limite"]))})
            chaves.add((alvo_id, int(r["minuto"]), int(r["gols_momento"]), r["mercado"], condset))
        for r in ler_csv(f"{BASE}/{alvo_id}_confirmacao_brasil_2stats.csv"):
            condset = frozenset({
                (r["stat1"], r["operador1"], float(r["limite1"])),
                (r["stat2"], r["operador2"], float(r["limite2"])),
            })
            chaves.add((alvo_id, int(r["minuto"]), int(r["gols_momento"]), r["mercado"], condset))
    return chaves


def _chave_brasil(item):
    condset = frozenset((c["stat"], c["operador"], c["limite"]) for c in item["condicoes"])
    mercado = f"{item['sinal_mercado']}{item['linha_mercado']:g}"
    return (item["alvo_id"], item["minuto"], item["gols_momento"], mercado, condset)


def montar_regras(fortes):
    """
    (lista de "sinais" já filtrados/deduplicados, cada um com "regiao" e
    "confirmacoes" já setados) -> lista de regras no formato final do painel
    (com por_valor_atual calibrado). Extraído do pipeline principal pra ser
    reaproveitado por outros geradores de conjunto (ex.: o de candidatos
    sombra rejeitados só por falta de amostra, ver
    gerar_regras_sombra_baixa_amostra.py) sem duplicar a lógica de
    montagem/recalibração.
    """
    fortes = _remover_sobreposicoes(fortes)
    fortes = sorted(fortes, key=lambda x: (x["alvo_id"], -x["impacto"]))

    regras = []
    contador = {}
    for s in fortes:
        alvo_id = s["alvo_id"]
        contador[alvo_id] = contador.get(alvo_id, 0) + 1
        regra_id = f"{alvo_id}_{contador[alvo_id]:03d}"

        op_txt = {">=": "≥", "<=": "≤"}
        cond_txt = " E ".join(
            f"{nome(c['stat'])} {op_txt[c['operador']]} {c['limite']:g}" for c in s["condicoes"]
        )
        direcao = "mais_de" if s["sinal_mercado"] == "+" else "menos_de"
        stat_alvo = ALVO_STAT_BASE[alvo_id]
        mercado_curto = (
            f"{'Mais' if direcao == 'mais_de' else 'Menos'} de {s['linha_mercado']:g} {ALVO_TITULO[alvo_id].lower()}"
        )
        rotulo = f"{cond_txt} aos {s['minuto']}' ({s['gols_momento']} gol(s) no jogo) → {mercado_curto}"

        regras.append({
            "id": regra_id,
            "alvo": alvo_id,
            "alvo_nome": ALVO_TITULO[alvo_id],
            "minuto": s["minuto"],
            "gols_momento": s["gols_momento"],
            "condicoes": s["condicoes"],
            "mercado": {
                "stat": stat_alvo,
                "direcao": direcao,
                "linha": s["linha_mercado"],
            },
            "mercado_curto": mercado_curto,
            "amostra_confirmacao": s["amostra"],
            "prob_base_confirmacao": round(s["p_base"], 4),
            "prob_condicao_confirmacao": round(s["p_condicao"], 4),
            "impacto_pp": round(s["impacto"], 2),
            # Transparencia (auditoria 15/09/2026): impacto contra quem NAO
            # cumpre a condicao, nao contra a base (que ja inclui a condicao
            # e por isso dilui o numero -- medido ~1,85x menor em media).
            # NAO e usado em nenhum filtro/portao, so pra leitura humana.
            "impacto_vs_complemento_pp": round(s.get("impacto_vs_complemento", s["impacto"]), 2),
            "p_valor_confirmacao": s["p_valor"],
            "odd_minima_referencia": round(1 / s["p_condicao"], 2) if s["p_condicao"] > 0 else None,
            "rotulo": rotulo,
            # "universal" (confirmou nórdicas E Brasil), "nordicas" (só confirmou
            # nas ligas nórdicas — live_monitor.py só aplica a Allsvenskan/
            # Superettan/1.Division) ou "brasil" (só confirmou no Brasil — só
            # aplica a Série A/B). Ver live_monitor.py::_regra_vale_para_liga.
            "regiao": s["regiao"],
            # Quantos processos de descoberta independentes confirmaram esta
            # condição: 2 só é possível pra regiao=brasil (herdado da Allsvenskan
            # E descoberto nativamente na Série A, ver
            # _selecionar_brasil_por_confianca) — universal/nórdicas usam sempre
            # 1 processo de descoberta (Allsvenskan), então o campo aqui é só
            # informativo, default 1.
            "confirmacoes": s.get("confirmacoes", 1),
        })

    print("recalibrando cada regra por valor atual do próprio alvo (escanteios/chutes já ocorridos)...")
    regras = recalibrar_por_valor_atual(regras)
    coberturas = [len(r["por_valor_atual"]) for r in regras]
    amostras_min = [min(v["n_usado"] for v in r["por_valor_atual"].values()) for r in regras] if regras else [0]
    print(f"  cobertura: {sum(coberturas)/len(coberturas):.1f} valores distintos por regra em média "
          f"(min {min(coberturas)}, max {max(coberturas)})" if regras else "  (nenhuma regra)")
    if regras:
        print(f"  amostra usada por valor: pior caso = {min(amostras_min)} jogos (após fallback pro vizinho)")
    return regras


def gerar():
    sinais = _colapsar(_carregar_brutas(ALVOS))
    confirmadas_brasil = _carregar_confirmadas_brasil()

    # Pool nórdico inteiro (amostra/impacto ok), ANTES de saber se também bate no
    # Brasil — dividido em dois destinos abaixo. Antes desta correção, qualquer
    # condição que passasse aqui mas NÃO confirmasse no Brasil era descartada por
    # completo (nunca virava regra nem pras próprias ligas nórdicas onde already
    # se provou fora da amostra — achado real, ver conversa: 17 condições de
    # escanteios/chutes_totais estavam sendo jogadas fora assim).
    fortes_nordicas_bruto = [s for s in sinais if s["amostra"] >= AMOSTRA_MINIMA_NORDICAS and s["impacto"] >= IMPACTO_MINIMO_PP]

    fortes_universal_pre = [s for s in fortes_nordicas_bruto if _chave_brasil(s) in confirmadas_brasil]
    for s in fortes_universal_pre:
        s["regiao"] = "universal"
    fortes = _deduplicar_familia(fortes_universal_pre)

    # Confirmou nas outras ligas nórdicas mas NÃO no Brasil -> só vale pras
    # próprias ligas nórdicas (ver LIGAS_NORDICAS em recalibrar_por_valor_atual e
    # live_monitor.py::LIGAS_REGIAO_NORDICAS). Espelha exatamente o raciocínio já
    # usado pra "regiao=brasil": um efeito pode ser real e específico de uma
    # região sem generalizar pra outra.
    fortes_apenas_nordicas_pre = [s for s in fortes_nordicas_bruto if _chave_brasil(s) not in confirmadas_brasil]
    for s in fortes_apenas_nordicas_pre:
        s["regiao"] = "nordicas"
    fortes_nordicas = _deduplicar_familia(fortes_apenas_nordicas_pre)

    # Brasil: combina os TRÊS caminhos de descoberta independentes — herdado
    # (Allsvenskan -> confirmado em Série A/B, confirmar_brasil.py), nativo A->B
    # (descoberto na Série A -> confirmado na Série B, descobrir_nativo_brasil.py)
    # e nativo B->A (descoberto na Série B -> confirmado na Série A,
    # descobrir_nativo_serieB.py — espelho do anterior, adicionado depois de notar
    # que só deixar a Série A descobrir também deixava a Série B sem chance de
    # propor sua própria hipótese, ver conversa). Ver
    # _selecionar_brasil_por_confianca pro critério de quando um sinal de fonte
    # única ainda entra. Nunca duplica uma regra que já é "universal" (passou
    # nórdicas E Brasil pelo caminho herdado).
    chaves_universais = {_chave_brasil(s) for s in fortes}
    sinais_brasil_herdado = _colapsar(_carregar_brutas(ALVOS_REGIAO_BRASIL, sufixo="_brasil", origem="herdado"))
    sinais_brasil_nativo_AB = _colapsar(_carregar_brutas(ALVOS_REGIAO_BRASIL, sufixo="_serieB", origem="nativo_AB"))
    sinais_brasil_nativo_BA = _colapsar(_carregar_brutas(ALVOS_REGIAO_BRASIL, sufixo="_serieA", origem="nativo_BA"))
    candidatos_brasil = [
        s for s in (sinais_brasil_herdado + sinais_brasil_nativo_AB + sinais_brasil_nativo_BA)
        if s["amostra"] >= AMOSTRA_MINIMA and s["impacto"] >= IMPACTO_MINIMO_PP
        and _chave_brasil(s) not in chaves_universais
    ]
    fortes_brasil, brasil_nao_incluidos = _selecionar_brasil_por_confianca(candidatos_brasil)
    for s in fortes_brasil:
        s["regiao"] = "brasil"
    _salvar_nao_incluidos(brasil_nao_incluidos, CAMINHO_AUDITORIA_BRASIL)

    fortes = fortes + fortes_nordicas + fortes_brasil

    print(f"sinais totais: {len(sinais)} | subconjunto forte (amostra>={AMOSTRA_MINIMA}, impacto>={IMPACTO_MINIMO_PP}pp): {len(fortes)}")
    print(f"  ({len(brasil_nao_incluidos)} candidatos do Brasil de fonte única ficaram de fora, registrados em {CAMINHO_AUDITORIA_BRASIL})")
    for alvo_id in ALVOS:
        n_universal = sum(1 for s in fortes if s["alvo_id"] == alvo_id and s["regiao"] == "universal")
        n_nordicas = sum(1 for s in fortes if s["alvo_id"] == alvo_id and s["regiao"] == "nordicas")
        n_brasil = sum(1 for s in fortes if s["alvo_id"] == alvo_id and s["regiao"] == "brasil")
        if n_universal or n_nordicas or n_brasil:
            extras = []
            if n_nordicas:
                extras.append(f"{n_nordicas} só nórdicas")
            if n_brasil:
                extras.append(f"{n_brasil} só Brasil")
            sufixo_extra = f" (+ {', '.join(extras)})" if extras else ""
            print(f"  {ALVO_TITULO[alvo_id]}: {n_universal}{sufixo_extra}")

    campos_usados = set()
    for s in fortes:
        for c in s["condicoes"]:
            campos_usados.add(c["stat"])
        campos_usados.add(ALVO_STAT_BASE[s["alvo_id"]])
    print("campos crus necessários da API (condição + alvo):", sorted(campos_usados))

    regras = montar_regras(fortes)

    payload = {
        "criterio": f"amostra_confirmacao >= {AMOSTRA_MINIMA} e impacto_pp >= {IMPACTO_MINIMO_PP}; "
                    "regiao=universal confirmado nas nórdicas E no Brasil; regiao=nordicas confirmado só "
                    "nas ligas nórdicas (aplicadas só a Allsvenskan/Superettan/1.Division); regiao=brasil "
                    f"exige confirmacoes >= {CONFIRMACOES_MINIMAS_BRASIL} (as três fontes de descoberta "
                    "independentes do Brasil concordando: herdado da Allsvenskan, nativo Série A->B e "
                    "nativo Série B->A — piso calibrado por backtest retroativo contra odds reais de "
                    "mercado, ver CONFIRMACOES_MINIMAS_BRASIL) (alvos "
                    f"{ALVOS_REGIAO_BRASIL}, aplicadas só a jogos de Série A/B)",
        "fonte": "pesquisa_gols/resultados/*_confirmacao_*.csv (nórdicas) + *_confirmacao_brasil_*.csv "
                 "(herdado) + *_confirmacao_serieB_*.csv (nativo, descobrir_nativo_brasil.py) — todos "
                 "confirmado_bh=True — + recalibração por valor atual do alvo (universal: pool de todas "
                 "as ligas; nordicas: só as 3 ligas nórdicas; brasil: só Série A/B — ver "
                 "recalibrar_por_valor_atual em gerar_regras_sinais.py)",
        "total_regras": len(regras),
        "regras": regras,
    }

    os.makedirs(os.path.dirname(DESTINO), exist_ok=True)
    with open(DESTINO, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\nsalvo em {os.path.abspath(DESTINO)}")


if __name__ == "__main__":
    gerar()
