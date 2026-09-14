"""
Versão corrigida de medir_efeito_vermelho.py — a v1 tinha uma falha
metodológica real (achada revisando os números com o usuário, ver
conversa): media a taxa de acerto usando só o condicional bruto
(minuto+placar+condição, igual "prob_condicao_confirmacao" da etapa de
confirmação), sem recondicionar pelo VALOR ATUAL exato do próprio alvo
(escanteios/cartões/chutes já ocorridos) — que é o que o painel ao vivo
realmente usa pra decidir se publica (ver live_monitor.py::
_stats_para_valor_atual/PROBABILIDADE_MINIMA_VALOR_ATUAL=70%). Isso juntava
num único número médio tanto os estados de jogo onde o sinal teria disparado
de verdade (p_condicao≥70% pro valor atual específico) quanto estados onde
nunca dispararia (p_condicao bem abaixo de 70%) — por isso a v1 mostrava
taxas de acerto de 20-40% pra regras que o painel só publica quando a
condição no valor atual promete ≥70%. Também não filtrava por região
("regiao":"brasil"/"nordicas"), deixando regra brasileira ser avaliada
contra jogo nórdico.

Esta versão só conta uma instância como "sinal que dispararia de verdade"
quando passa EXATAMENTE pelos mesmos filtros de _candidatas_para_conjunto/
_consolidar_candidatas em produção: liga aceita pra região da regra,
condição bate, impacto_pp≥5, e p_condicao (recondicionado pelo valor atual)
≥70%. Só then compara com_vermelho x sem_vermelho.

Uso: python3 medir_efeito_vermelho_v2.py
"""
import json
import os
import sys
import types
from collections import defaultdict

# Stub de pywebpush pra poder importar live_monitor.py sem a dependência real
# (só precisamos das funções de matching, não do envio de push).
_fake = types.ModuleType("pywebpush")
_fake.webpush = lambda *a, **k: None
class _WebPushException(Exception):
    pass
_fake.WebPushException = _WebPushException
sys.modules["pywebpush"] = _fake

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ligas_live_app"))
import live_monitor as lm  # noqa: E402

DADOS_DIR = os.path.join(os.path.dirname(__file__), "dados")
REGRAS_PATH = os.environ.get(
    "REGRAS_PATH_OVERRIDE",
    os.path.join(os.path.dirname(__file__), "..", "ligas_live_app", "regras_sinais.json"),
)

# id numérico (Sportmonks) -> nome de liga como aparece de verdade em
# fixture.league.name (ver conversa: bug do acento corrigido em
# LIGAS_REGIAO_BRASIL) — usado só pra alimentar _regra_vale_para_liga com o
# nome de liga certo por fixture.
LIGA_NOME_REAL = {573: "Allsvenskan", 579: "Superettan", 447: "1. Division", 648: "Serie A", 651: "Serie B"}

ALVO_KEY = {
    "escanteios": "escanteios", "cartoes": "cartoes",
    "chutes_totais": "chutes_totais", "chutes_no_alvo": "chutes_no_alvo",
}
STAT_ALVO_PARA_VALOR_ATUAL = {
    "escanteios": "corners", "cartoes": None,  # cartoes tratado à parte (soma yellow+red)
    "chutes_totais": "shots_total", "chutes_no_alvo": "shots_on_target",
}

AMOSTRA_MINIMA_RELATO = 5


def carregar_pooled():
    snaps_por_fixture = defaultdict(dict)
    resultados = {}
    liga_por_fixture = {}
    for lid, nome in LIGA_NOME_REAL.items():
        caminho = os.path.join(DADOS_DIR, f".checkpoint_{lid}.json")
        d = json.load(open(caminho, encoding="utf-8"))
        for snap in d["snapshots"]:
            snaps_por_fixture[snap["fixture_id"]][snap["minuto"]] = snap
        for fid_str, res in d["resultados_alvo"].items():
            resultados[int(fid_str)] = res
            liga_por_fixture[int(fid_str)] = nome
    return snaps_por_fixture, resultados, liga_por_fixture


def _valor_atual_do_alvo(regra, snap):
    alvo = regra["alvo"]
    if alvo == "cartoes":
        amarelos, vermelhos = snap.get("yellowcards"), snap.get("redcards")
        if amarelos is None or vermelhos is None:
            return None
        return amarelos + vermelhos
    campo = STAT_ALVO_PARA_VALOR_ATUAL[alvo]
    return snap.get(campo)


def rodar():
    snaps_por_fixture, resultados, liga_por_fixture = carregar_pooled()
    payload = json.load(open(REGRAS_PATH, encoding="utf-8"))
    regras = payload["regras"]
    print(f"{len(regras)} regras publicadas — replicando exatamente o gate de produção "
          f"(liga aceita p/ regiao, impacto_pp>={lm.IMPACTO_MINIMO_PP_VALOR_ATUAL}, "
          f"p_condicao>=piso por região da liga — ver lm._piso_probabilidade_para_liga)\n")

    agregados = defaultdict(lambda: {"com_vermelho": [], "sem_vermelho": []})
    por_regra = []

    for regra in regras:
        minuto = regra["minuto"]
        gols_momento = regra["gols_momento"]
        alvo = regra["alvo"]
        direcao = regra["mercado"]["direcao"]
        linha = regra["mercado"]["linha"]
        chave_grupo = (alvo, direcao)

        grupo = {"com_vermelho": [], "sem_vermelho": []}
        for fid, snaps in snaps_por_fixture.items():
            liga_nome = liga_por_fixture.get(fid)
            if not lm._regra_vale_para_liga(regra, liga_nome):
                continue
            snap = snaps.get(minuto)
            if not snap or snap.get("gols_momento") != gols_momento:
                continue
            if not lm._regra_bate(regra, snap):
                continue

            valor_atual = _valor_atual_do_alvo(regra, snap)
            if valor_atual is None:
                continue
            tabela = regra.get("por_valor_atual") or {}
            valor_int = int(round(valor_atual))
            entrada = tabela.get(str(valor_int))
            if entrada is None:
                if not tabela:
                    continue
                disponiveis = [int(v) for v in tabela.keys()]
                mais_proximo = min(disponiveis, key=lambda v: abs(v - valor_int))
                entrada = tabela[str(mais_proximo)]

            # MESMO gate de _candidatas_para_conjunto em produção.
            if entrada["impacto_pp"] < lm.IMPACTO_MINIMO_PP_VALOR_ATUAL:
                continue
            if entrada["p_condicao"] < lm._piso_probabilidade_para_liga(liga_nome):
                continue

            res = resultados.get(fid)
            if not res or res.get(ALVO_KEY[alvo]) is None:
                continue
            valor_final = res[ALVO_KEY[alvo]]
            bateu = (valor_final > linha) if direcao == "mais_de" else (valor_final < linha)
            chave = "com_vermelho" if (snap.get("redcards") or 0) > 0 else "sem_vermelho"
            grupo[chave].append(bateu)
            agregados[chave_grupo][chave].append(bateu)

        n_cv, n_sv = len(grupo["com_vermelho"]), len(grupo["sem_vermelho"])
        if n_cv >= AMOSTRA_MINIMA_RELATO:
            taxa_cv = 100 * sum(grupo["com_vermelho"]) / n_cv
            taxa_sv = 100 * sum(grupo["sem_vermelho"]) / n_sv if n_sv else None
            por_regra.append((regra["id"], regra.get("rotulo", "")[:55], n_cv, taxa_cv, n_sv, taxa_sv))

    print("=" * 78)
    print("AGREGADO POR (alvo, direção) — só instâncias que PASSARIAM no gate real de produção")
    print("=" * 78)
    print(f"{'alvo/direcao':28s} {'n_sv':>6s} {'acerto_sv':>10s} {'n_cv':>6s} {'acerto_cv':>10s} {'dif_pp':>8s}")
    for (alvo, direcao), g in sorted(agregados.items()):
        n_sv, n_cv = len(g["sem_vermelho"]), len(g["com_vermelho"])
        taxa_sv = 100 * sum(g["sem_vermelho"]) / n_sv if n_sv else 0.0
        taxa_cv = 100 * sum(g["com_vermelho"]) / n_cv if n_cv else 0.0
        print(f"{alvo+'/'+direcao:28s} {n_sv:6d} {taxa_sv:9.1f}% {n_cv:6d} {taxa_cv:9.1f}% {taxa_cv-taxa_sv:7.1f}pp")

    print(f"\n{'='*78}\nPOR REGRA (amostra >= {AMOSTRA_MINIMA_RELATO} em jogos com vermelho — {len(por_regra)} de {len(regras)})\n{'='*78}")
    print(f"{'id':18s} {'n_cv':>5s} {'acerto_cv':>10s} {'n_sv':>6s} {'acerto_sv':>10s}  rótulo")
    for id_, rotulo, n_cv, taxa_cv, n_sv, taxa_sv in sorted(por_regra, key=lambda x: -x[2]):
        taxa_sv_str = f"{taxa_sv:.1f}%" if taxa_sv is not None else "-"
        print(f"{id_:18s} {n_cv:5d} {taxa_cv:9.1f}% {n_sv:6d} {taxa_sv_str:>10s}  {rotulo}")
    if not por_regra:
        print("(nenhuma regra teve amostra suficiente em jogos com vermelho DENTRO do gate real de produção)")


if __name__ == "__main__":
    rodar()
