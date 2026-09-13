"""
Mede se jogos que já tiveram cartão vermelho (expulsão) até o checkpoint da
regra se comportam diferente o suficiente pra precisar de tratamento especial
no painel ao vivo — pedido do usuário (ver conversa): antes de suprimir ou
marcar sinais em jogos com vermelho, medir o efeito real nos dados pooled em
vez de assumir.

Usa os mesmos checkpoints pooled de 5 ligas já baixados em
dados/.checkpoint_*.json (mesma fonte que gerar_regras_sinais.py usa pra
calibrar as regras) — "redcards" no snapshot é CUMULATIVO até aquele minuto
(confirmado: 0 aos 45', 1 aos 60' num jogo real onde a expulsão aconteceu
entre os dois checkpoints), então dá pra saber com certeza se o jogo já
tinha expulsão no momento em que cada regra seria avaliada.

Uso: python3 medir_efeito_vermelho.py
"""
import json
import os
from collections import defaultdict

DADOS_DIR = os.path.join(os.path.dirname(__file__), "dados")
REGRAS_PATH = os.environ.get(
    "REGRAS_PATH_OVERRIDE",
    os.path.join(os.path.dirname(__file__), "..", "ligas_live_app", "regras_sinais.json"),
)

LIGAS = {573: "Allsvenskan", 579: "Superettan", 447: "1. Division", 648: "Serie A", 651: "Serie B"}

ALVO_KEY = {
    "escanteios": "escanteios", "cartoes": "cartoes",
    "chutes_totais": "chutes_totais", "chutes_no_alvo": "chutes_no_alvo",
}

AMOSTRA_MINIMA_RELATO = 5  # só reporta regra a regra quando tem alguma amostra em jogo com vermelho


def carregar_pooled():
    snaps_por_fixture = defaultdict(dict)
    resultados = {}
    for lid in LIGAS:
        caminho = os.path.join(DADOS_DIR, f".checkpoint_{lid}.json")
        d = json.load(open(caminho, encoding="utf-8"))
        for snap in d["snapshots"]:
            snaps_por_fixture[snap["fixture_id"]][snap["minuto"]] = snap
        for fid_str, res in d["resultados_alvo"].items():
            resultados[int(fid_str)] = res
    return snaps_por_fixture, resultados


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


def rodar():
    snaps_por_fixture, resultados = carregar_pooled()
    payload = json.load(open(REGRAS_PATH, encoding="utf-8"))
    regras = payload["regras"]
    print(f"{len(regras)} regras publicadas (produção) — {sum(len(s) for s in snaps_por_fixture.values())} snapshots pooled em {len(snaps_por_fixture)} jogos\n")

    agregados = {"com_vermelho": [], "sem_vermelho": []}
    por_regra = []

    for regra in regras:
        minuto = regra["minuto"]
        gols_momento = regra["gols_momento"]
        condicoes = regra["condicoes"]
        alvo = regra["alvo"]
        linha = regra["mercado"]["linha"]
        direcao = regra["mercado"]["direcao"]

        grupo = {"com_vermelho": [], "sem_vermelho": []}
        for fid, snaps in snaps_por_fixture.items():
            snap = snaps.get(minuto)
            if not snap or snap.get("gols_momento") != gols_momento:
                continue
            if not _condicao_bate(condicoes, snap):
                continue
            res = resultados.get(fid)
            if not res or res.get(ALVO_KEY[alvo]) is None:
                continue
            valor_final = res[ALVO_KEY[alvo]]
            bateu = (valor_final > linha) if direcao == "mais_de" else (valor_final < linha)
            chave = "com_vermelho" if (snap.get("redcards") or 0) > 0 else "sem_vermelho"
            grupo[chave].append(bateu)
            agregados[chave].append(bateu)

        n_cv = len(grupo["com_vermelho"])
        n_sv = len(grupo["sem_vermelho"])
        if n_cv >= AMOSTRA_MINIMA_RELATO:
            taxa_cv = 100 * sum(grupo["com_vermelho"]) / n_cv
            taxa_sv = 100 * sum(grupo["sem_vermelho"]) / n_sv if n_sv else None
            por_regra.append((regra["id"], regra.get("rotulo", "")[:60], n_cv, taxa_cv, n_sv, taxa_sv, regra["prob_condicao_confirmacao"] * 100))

    print("=" * 78)
    print("AGREGADO GERAL (todas as regras publicadas somadas)")
    print("=" * 78)
    for chave in ("sem_vermelho", "com_vermelho"):
        itens = agregados[chave]
        n = len(itens)
        taxa = 100 * sum(itens) / n if n else 0.0
        print(f"  {chave:14s}  n={n:5d}   taxa_acerto={taxa:5.1f}%")

    print(f"\n{'='*78}\nPOR REGRA (só as com amostra >= {AMOSTRA_MINIMA_RELATO} em jogos com vermelho — {len(por_regra)} de {len(regras)})\n{'='*78}")
    print(f"{'id':18s} {'n_cv':>5s} {'acerto_cv':>10s} {'n_sv':>6s} {'acerto_sv':>10s} {'prometido':>10s}  rótulo")
    for id_, rotulo, n_cv, taxa_cv, n_sv, taxa_sv, prometido in sorted(por_regra, key=lambda x: -x[2]):
        taxa_sv_str = f"{taxa_sv:.1f}%" if taxa_sv is not None else "-"
        print(f"{id_:18s} {n_cv:5d} {taxa_cv:9.1f}% {n_sv:6d} {taxa_sv_str:>10s} {prometido:9.1f}%  {rotulo}")

    if not por_regra:
        print("(nenhuma regra publicada teve amostra suficiente em jogos com vermelho ainda)")


if __name__ == "__main__":
    rodar()
