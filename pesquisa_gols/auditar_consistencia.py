"""
Auditoria de robustez de TODAS as regras aprovadas em regras_sinais.json:
pra cada uma, recalcula o impacto separadamente por LIGA (dentro da própria
região de confirmação da regra) e por ANO (2024/2025/2026) — pra ver se o
efeito é consistente em todos os componentes, ou se uma liga/ano específico
está "puxando" o resultado sozinho (mascarando um efeito fraco/nulo nas
outras — o mesmo tipo de risco de paradoxo de Simpson já investigado nesta
sessão pra regiões inteiras, agora aplicado dentro de cada região).

Não formaliza um teste estatístico por fatia (a amostra de cada
liga×ano×condição costuria fica pequena demais pra isso ser confiável) — só
verifica CONSISTÊNCIA DE DIREÇÃO (o efeito aponta pro mesmo lado em toda
fatia com amostra mínima) e reporta a magnitude/amostra de cada fatia pra
inspeção. Não escreve em nenhum arquivo do painel — é só leitura.

Uso: python3 auditar_consistencia.py
"""
import glob
import json
import os

DADOS_DIR = os.path.join(os.path.dirname(__file__), "dados")
REGRAS_PATH = os.path.join(os.path.dirname(__file__), "..", "ligas_live_app", "regras_sinais.json")

AMOSTRA_MINIMA_FATIA = 20  # abaixo disso, não dá pra confiar nem na direção

LIGAS_NORDICAS = {579, 447}  # Superettan, 1.Division (Allsvenskan é descoberta, fica de fora)
LIGAS_BRASIL = {648, 651}    # Série A, Série B

NOME_LIGA = {573: "Allsvenskan", 579: "Superettan", 447: "1.Division", 648: "Série A", 651: "Série B"}


def _ligas_confirmadoras(regiao):
    if regiao == "nordicas":
        return LIGAS_NORDICAS
    if regiao == "brasil":
        return LIGAS_BRASIL
    return LIGAS_NORDICAS | LIGAS_BRASIL  # universal


def _carregar_tudo():
    """fixture_id -> liga, ano; fixture_id -> {minuto: snapshot}; fixture_id -> resultados_alvo."""
    liga_por_fixture, ano_por_fixture = {}, {}
    snaps_por_fixture, resultados = {}, {}
    for caminho in glob.glob(f"{DADOS_DIR}/.checkpoint_*.json"):
        lid = int(os.path.basename(caminho).removeprefix(".checkpoint_").removesuffix(".json"))
        d = json.load(open(caminho, encoding="utf-8"))
        for fid_str, jogo in d["jogos"].items():
            fid = int(fid_str)
            liga_por_fixture[fid] = lid
            data_hora = jogo.get("data_hora")
            if data_hora:
                ano_por_fixture[fid] = int(data_hora[:4])
        for fid_str, res in d["resultados_alvo"].items():
            resultados[int(fid_str)] = res
        for snap in d["snapshots"]:
            snaps_por_fixture.setdefault(snap["fixture_id"], {})[snap["minuto"]] = snap
    return liga_por_fixture, ano_por_fixture, snaps_por_fixture, resultados


def _valor_stat_alvo(snap, stat_alvo):
    if stat_alvo == "cards":
        a, v = snap.get("yellowcards"), snap.get("redcards")
        return None if a is None or v is None else a + v
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


def _impacto_no_subconjunto(regra, fixture_ids, snaps_por_fixture, resultados, liga_por_fixture, ano_por_fixture, filtro):
    """filtro(fid) -> bool decide quais fixtures entram nesta fatia (liga X, ano Y, etc)."""
    stat_alvo, linha, direcao = regra["mercado"]["stat"], regra["mercado"]["linha"], regra["mercado"]["direcao"]
    alvo = regra["alvo"]
    bateu_condicao, bateu_base = [], []
    for fid in fixture_ids:
        if not filtro(fid):
            continue
        snap = snaps_por_fixture.get(fid, {}).get(regra["minuto"])
        if not snap or snap.get("gols_momento") != regra["gols_momento"]:
            continue
        res = resultados.get(fid)
        valor_stat_alvo = _valor_stat_alvo(snap, stat_alvo)
        if not res or res.get(alvo) is None or valor_stat_alvo is None:
            continue
        bateu_mercado = (res[alvo] > linha) if direcao == "mais_de" else (res[alvo] < linha)
        bateu_base.append(bateu_mercado)
        if _condicao_bate(regra["condicoes"], snap):
            bateu_condicao.append(bateu_mercado)
    if len(bateu_condicao) < AMOSTRA_MINIMA_FATIA or len(bateu_base) < AMOSTRA_MINIMA_FATIA:
        return None
    p_condicao = sum(bateu_condicao) / len(bateu_condicao)
    p_base = sum(bateu_base) / len(bateu_base)
    return {"n_condicao": len(bateu_condicao), "n_base": len(bateu_base), "impacto_pp": (p_condicao - p_base) * 100}


def auditar_regra(regra, liga_por_fixture, ano_por_fixture, snaps_por_fixture, resultados):
    ligas = _ligas_confirmadoras(regra["regiao"])
    todas_fixtures = list(snaps_por_fixture.keys())

    por_liga = {}
    for lid in ligas:
        fixtures_da_liga = [fid for fid in todas_fixtures if liga_por_fixture.get(fid) == lid]
        r = _impacto_no_subconjunto(regra, fixtures_da_liga, snaps_por_fixture, resultados, liga_por_fixture, ano_por_fixture, lambda fid: True)
        if r:
            por_liga[lid] = r

    por_ano = {}
    for lid in ligas:
        fixtures_da_liga = [fid for fid in todas_fixtures if liga_por_fixture.get(fid) == lid]
        for ano in (2024, 2025, 2026):
            fixtures_do_ano = [fid for fid in fixtures_da_liga if ano_por_fixture.get(fid) == ano]
            r = _impacto_no_subconjunto(regra, fixtures_do_ano, snaps_por_fixture, resultados, liga_por_fixture, ano_por_fixture, lambda fid: True)
            if r:
                por_ano[(lid, ano)] = r

    sinais_liga = {lid: (1 if v["impacto_pp"] > 0 else -1) for lid, v in por_liga.items()}
    sinais_ano = {k: (1 if v["impacto_pp"] > 0 else -1) for k, v in por_ano.items()}

    liga_consistente = len(set(sinais_liga.values())) <= 1
    ano_consistente = len(set(sinais_ano.values())) <= 1

    return {
        "por_liga": por_liga, "por_ano": por_ano,
        "liga_consistente": liga_consistente, "ano_consistente": ano_consistente,
        "n_ligas_avaliadas": len(por_liga), "n_anos_avaliados": len(por_ano),
    }


def rodar():
    payload = json.load(open(REGRAS_PATH, encoding="utf-8"))
    regras = payload["regras"]
    print(f"Carregando dados de todas as ligas...")
    liga_por_fixture, ano_por_fixture, snaps_por_fixture, resultados = _carregar_tudo()
    print(f"  {len(snaps_por_fixture)} fixtures com snapshot, {len(resultados)} com resultado\n")

    resultado_auditoria = []
    for i, regra in enumerate(regras):
        aud = auditar_regra(regra, liga_por_fixture, ano_por_fixture, snaps_por_fixture, resultados)
        resultado_auditoria.append({"regra": regra, "auditoria": aud})
        if (i + 1) % 40 == 0:
            print(f"  ... {i+1}/{len(regras)} regras auditadas")

    json.dump(
        [{"id": r["regra"]["id"], "regiao": r["regra"]["regiao"], "rotulo": r["regra"]["rotulo"],
          "por_liga": {NOME_LIGA[k]: v for k, v in r["auditoria"]["por_liga"].items()},
          "por_ano": {f"{NOME_LIGA[k[0]]}_{k[1]}": v for k, v in r["auditoria"]["por_ano"].items()},
          "liga_consistente": r["auditoria"]["liga_consistente"], "ano_consistente": r["auditoria"]["ano_consistente"]}
         for r in resultado_auditoria],
        open("/tmp/auditoria_consistencia.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2,
    )

    n_total = len(resultado_auditoria)
    n_liga_inconsistente = sum(1 for r in resultado_auditoria if not r["auditoria"]["liga_consistente"])
    n_ano_inconsistente = sum(1 for r in resultado_auditoria if not r["auditoria"]["ano_consistente"])
    print(f"\n{'='*70}\nResumo geral ({n_total} regras)\n{'='*70}")
    print(f"Direção inconsistente entre ligas: {n_liga_inconsistente}")
    print(f"Direção inconsistente entre anos:  {n_ano_inconsistente}")
    print(f"\nSalvo detalhado em /tmp/auditoria_consistencia.json")


if __name__ == "__main__":
    rodar()
