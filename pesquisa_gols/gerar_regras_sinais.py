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

BASE = os.path.join(os.path.dirname(__file__), "resultados")
DADOS_DIR = os.path.join(os.path.dirname(__file__), "dados")
DESTINO = os.path.join(os.path.dirname(__file__), "..", "ligas_live_app", "regras_sinais.json")

AMOSTRA_MINIMA_VALOR_ATUAL = 30  # abaixo disso, a proporção não é confiável — busca o valor_atual vizinho

AMOSTRA_MINIMA = 200
IMPACTO_MINIMO_PP = 5.0

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
    (extraído do próprio nome do arquivo .checkpoint_<league_id>.json) — todas as ligas juntas."""
    snaps_por_fixture = {}
    resultados = {}
    liga_por_fixture = {}
    for caminho in glob.glob(f"{DADOS_DIR}/.checkpoint_*.json"):
        league_id = int(os.path.basename(caminho).removeprefix(".checkpoint_").removesuffix(".json"))
        d = json.load(open(caminho, encoding="utf-8"))
        for fid_str, res in d["resultados_alvo"].items():
            resultados[int(fid_str)] = res
            liga_por_fixture[int(fid_str)] = league_id
        for snap in d["snapshots"]:
            snaps_por_fixture.setdefault(snap["fixture_id"], {})[snap["minuto"]] = snap
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


def _tabela_com_fallback(casos_por_valor):
    """{valor_atual: [bateu, ...]} -> {valor_atual: {"n":.., "p":..}}, usando o valor vizinho com amostra
    suficiente quando o valor exato tem poucos jogos (mesmo padrão de fallback do resto do projeto)."""
    com_amostra = sorted(v for v, casos in casos_por_valor.items() if len(casos) >= AMOSTRA_MINIMA_VALOR_ATUAL)
    tabela = {}
    for valor, casos in casos_por_valor.items():
        if len(casos) >= AMOSTRA_MINIMA_VALOR_ATUAL:
            casos_uso = casos
        elif com_amostra:
            casos_uso = casos_por_valor[min(com_amostra, key=lambda v: abs(v - valor))]
        else:
            casos_uso = casos  # último recurso — nenhum valor com amostra boa pra esse alvo/regra
        # n = jogos observados EXATAMENTE nesse valor (transparência); n_usado = amostra
        # de fato usada pra estimar "p" (pode vir de um valor vizinho, se n for pequeno).
        tabela[valor] = {"n": len(casos), "n_usado": len(casos_uso), "p": sum(casos_uso) / len(casos_uso)}
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

    Também recalcula a mesma coisa pras linhas VIZINHAS (±1, mesma direção) —
    caso real reportado: casa de apostas só tinha "mais de 10.5" disponível
    quando o sinal era calibrado pra "mais de 9.5"; sem isso, não dava pra
    saber a probabilidade real de bater a linha que realmente estava
    disponível pra apostar, só a da linha original. Guardado em
    "linhas_vizinhas" pra não mexer no formato já existente (linha original
    continua nas chaves de sempre, por compatibilidade).
    """
    snaps_por_fixture, resultados, liga_por_fixture = _carregar_dados_pooled()

    for regra in regras:
        stat_alvo, linha, direcao = regra["mercado"]["stat"], regra["mercado"]["linha"], regra["mercado"]["direcao"]
        alvo = regra["alvo"]
        linhas_a_calcular = {0: linha, -1: linha - 1, 1: linha + 1}

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

        # offset -> valor_atual -> [bateu, ...]
        casos_condicao = {off: {} for off in linhas_a_calcular}
        casos_base = {off: {} for off in linhas_a_calcular}
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
                casos_base[off].setdefault(valor_atual, []).append(bateu)
                if condicao_ok:
                    casos_condicao[off].setdefault(valor_atual, []).append(bateu)

        tabelas_condicao = {off: _tabela_com_fallback(casos_condicao[off]) for off in linhas_a_calcular}
        tabelas_base = {off: _tabela_com_fallback(casos_base[off]) for off in linhas_a_calcular}

        por_valor_atual = {}
        for valor, entrada in tabelas_condicao[0].items():
            p_condicao = entrada["p"]
            p_base = tabelas_base[0].get(valor, {"p": regra["prob_base_confirmacao"]})["p"]
            linhas_vizinhas = {}
            for off in (-1, 1):
                entrada_off = tabelas_condicao[off].get(valor)
                if entrada_off is None:
                    continue
                p_off = entrada_off["p"]
                p_base_off = tabelas_base[off].get(valor, {"p": p_base})["p"]
                linhas_vizinhas[str(off)] = {
                    "linha": linhas_a_calcular[off],
                    "n": entrada_off["n"],
                    "n_usado": entrada_off["n_usado"],
                    "p_condicao": round(p_off, 4),
                    "impacto_pp": round((p_off - p_base_off) * 100, 2),
                    "odd_minima": round(1 / p_off, 2) if p_off > 0 else None,
                }
            por_valor_atual[str(valor)] = {
                "n": entrada["n"],
                "n_usado": entrada["n_usado"],
                "p_condicao": round(p_condicao, 4),
                "p_base": round(p_base, 4),
                "impacto_pp": round((p_condicao - p_base) * 100, 2),
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
                "p_valor": float(r["p_valor_outras_ligas"]),
                "origem": origem,
            })
        for r in ler_csv(f"{BASE}/{alvo_id}_confirmacao{sufixo}_2stats.csv"):
            p_base = float(r["p_base_outras_ligas"])
            p_cond = float(r["p_conjunta_outras_ligas"])
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
                "impacto": (p_cond - p_base) * 100,
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


# Acima de quanto impacto uma condição do Brasil confirmada por SÓ UM dos dois
# caminhos (herdado OU nativo, não os dois) ainda entra no painel — o dobro do
# piso normal (5pp), calibrado pra preservar achados fortes como
# "Ataques perigosos" pra escanteios (achado só pela descoberta nativa, nunca
# passaria pelo caminho herdado porque a Allsvenskan nunca testou esse stat —
# ver conversa) e ainda assim cortar a maioria das ~275 condições de fonte
# única mais fracas, que ficam registradas em auditoria, não descartadas
# (ver _salvar_nao_incluidos).
IMPACTO_CURADORIA_UNICA_BRASIL = 10.0
CAMINHO_AUDITORIA_BRASIL = os.path.join(BASE, "brasil_candidatos_nao_incluidos.csv")


def _selecionar_brasil_por_confianca(itens_combinados):
    """
    Agrupa por família (ver _chave_familia) o pool JÁ COMBINADO de condições
    herdadas (Allsvenskan -> Brasil) e nativas (Série A -> Série B) do Brasil.
    Dentro de cada família:
      - se sobrevivem itens de origem "herdado" E "nativo" -> confirmado por
        DOIS processos de descoberta independentes, entra sempre
        (confirmacoes=2, a evidência mais forte que este pipeline produz pra
        região).
      - se só uma origem sobrevive -> só entra se o impacto da melhor
        variação bater IMPACTO_CURADORIA_UNICA_BRASIL (confirmacoes=1); caso
        contrário, fica de fora do painel mas registrada em
        CAMINHO_AUDITORIA_BRASIL (nada é descartado sem deixar rastro).
    """
    ancoras = _ancoras_1stat(itens_combinados)
    grupos = {}
    for item in itens_combinados:
        grupos.setdefault(_chave_familia(item, ancoras), []).append(item)

    selecionados, nao_incluidos = [], []
    for grupo in grupos.values():
        origens = {i["origem"] for i in grupo}
        melhor = max(grupo, key=lambda x: x["impacto"])
        if len(origens) > 1:
            melhor["confirmacoes"] = 2
            selecionados.append(melhor)
        elif melhor["impacto"] >= IMPACTO_CURADORIA_UNICA_BRASIL:
            melhor["confirmacoes"] = 1
            selecionados.append(melhor)
        else:
            nao_incluidos.append(melhor)
    return selecionados, nao_incluidos


def _salvar_nao_incluidos(itens, caminho):
    linhas = []
    for it in itens:
        cond_txt = " E ".join(f"{c['stat']}{c['operador']}{c['limite']:g}" for c in it["condicoes"])
        linhas.append({
            "alvo_id": it["alvo_id"], "minuto": it["minuto"], "gols_momento": it["gols_momento"],
            "condicoes": cond_txt, "mercado": f"{it['sinal_mercado']}{it['linha_mercado']:g}",
            "origem_unica": it["origem"], "amostra": it["amostra"], "impacto_pp": round(it["impacto"], 2),
            "motivo": f"confirmado por só 1 processo de descoberta e impacto < {IMPACTO_CURADORIA_UNICA_BRASIL}pp",
        })
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        if not linhas:
            f.write("(nenhum candidato ficou de fora)\n")
            return
        writer = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        writer.writeheader()
        writer.writerows(linhas)


sinais = _colapsar(_carregar_brutas(ALVOS))


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


CONFIRMADAS_BRASIL = _carregar_confirmadas_brasil()

# Pool nórdico inteiro (amostra/impacto ok), ANTES de saber se também bate no
# Brasil — dividido em dois destinos abaixo. Antes desta correção, qualquer
# condição que passasse aqui mas NÃO confirmasse no Brasil era descartada por
# completo (nunca virava regra nem pras próprias ligas nórdicas onde already
# se provou fora da amostra — achado real, ver conversa: 17 condições de
# escanteios/chutes_totais estavam sendo jogadas fora assim).
fortes_nordicas_bruto = [s for s in sinais if s["amostra"] >= AMOSTRA_MINIMA and s["impacto"] >= IMPACTO_MINIMO_PP]

fortes_universal_pre = [s for s in fortes_nordicas_bruto if _chave_brasil(s) in CONFIRMADAS_BRASIL]
for s in fortes_universal_pre:
    s["regiao"] = "universal"
fortes = _deduplicar_familia(fortes_universal_pre)

# Confirmou nas outras ligas nórdicas mas NÃO no Brasil -> só vale pras
# próprias ligas nórdicas (ver LIGAS_NORDICAS em recalibrar_por_valor_atual e
# live_monitor.py::LIGAS_REGIAO_NORDICAS). Espelha exatamente o raciocínio já
# usado pra "regiao=brasil": um efeito pode ser real e específico de uma
# região sem generalizar pra outra.
fortes_apenas_nordicas_pre = [s for s in fortes_nordicas_bruto if _chave_brasil(s) not in CONFIRMADAS_BRASIL]
for s in fortes_apenas_nordicas_pre:
    s["regiao"] = "nordicas"
fortes_nordicas = _deduplicar_familia(fortes_apenas_nordicas_pre)

# Brasil: combina os dois caminhos de descoberta independentes — herdado
# (Allsvenskan -> confirmado em Série A/B, confirmar_brasil.py) e nativo
# (descoberto na própria Série A -> confirmado na Série B,
# descobrir_nativo_brasil.py) — ver _selecionar_brasil_por_confianca pro
# critério de quando um sinal de fonte única ainda entra. Nunca duplica uma
# regra que já é "universal" (passou nórdicas E Brasil pelo caminho herdado).
chaves_universais = {_chave_brasil(s) for s in fortes}
sinais_brasil_herdado = _colapsar(_carregar_brutas(ALVOS_REGIAO_BRASIL, sufixo="_brasil", origem="herdado"))
sinais_brasil_nativo = _colapsar(_carregar_brutas(ALVOS_REGIAO_BRASIL, sufixo="_serieB", origem="nativo"))
candidatos_brasil = [
    s for s in (sinais_brasil_herdado + sinais_brasil_nativo)
    if s["amostra"] >= AMOSTRA_MINIMA and s["impacto"] >= IMPACTO_MINIMO_PP
    and _chave_brasil(s) not in chaves_universais
]
fortes_brasil, brasil_nao_incluidos = _selecionar_brasil_por_confianca(candidatos_brasil)
for s in fortes_brasil:
    s["regiao"] = "brasil"
_salvar_nao_incluidos(brasil_nao_incluidos, CAMINHO_AUDITORIA_BRASIL)

fortes = fortes + fortes_nordicas + fortes_brasil
fortes.sort(key=lambda x: (x["alvo_id"], -x["impacto"]))

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

print("\nrecalibrando cada regra por valor atual do próprio alvo (escanteios/chutes já ocorridos)...")
regras = recalibrar_por_valor_atual(regras)
coberturas = [len(r["por_valor_atual"]) for r in regras]
amostras_min = [min(v["n_usado"] for v in r["por_valor_atual"].values()) for r in regras]
print(f"  cobertura: {sum(coberturas)/len(coberturas):.1f} valores distintos por regra em média "
      f"(min {min(coberturas)}, max {max(coberturas)})")
print(f"  amostra usada por valor: pior caso = {min(amostras_min)} jogos (após fallback pro vizinho)")

payload = {
    "criterio": f"amostra_confirmacao >= {AMOSTRA_MINIMA} e impacto_pp >= {IMPACTO_MINIMO_PP}; "
                "regiao=universal confirmado nas nórdicas E no Brasil; regiao=nordicas confirmado só "
                "nas ligas nórdicas (aplicadas só a Allsvenskan/Superettan/1.Division); regiao=brasil "
                f"confirmado no Brasil por descoberta herdada (Allsvenskan) OU nativa (Série A), "
                f"exigindo impacto_pp >= {IMPACTO_CURADORIA_UNICA_BRASIL} quando confirmado por só um "
                "dos dois processos (alvos "
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
