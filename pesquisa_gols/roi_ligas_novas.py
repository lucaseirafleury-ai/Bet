"""
Mede ROI REAL contra odds da bet365 das famílias que as 3 vias de descoberta
confirmaram nas ligas novas (ver descobrir_ligas_novas.py / cruzar_vias_
ligas_novas.py) — o passo que decide se o estudo rendeu regra apostável.

Por que ROI real e não o teste estatístico: as regras nórdicas passavam no
teste (duas proporções + Benjamini-Hochberg) e renderam -47,1% contra odds de
verdade. Significância não é o critério; dinheiro é.

Só roda alvo COM MERCADO AO VIVO (escanteios e cartões). Chutes fica de fora
de propósito: a bet365 congela a linha ~1min depois do apito e nunca
reprecifica, então não existe odd ao vivo pra apostar e qualquer ROI
calculado ali seria ficção (ver CLAUDE.md).

Reaproveita, sem reimplementar:
- cruzar_vias_ligas_novas.cruzar    -> as famílias com as 3 vias concordando
- gerar_regras_sinais.recalibrar_por_valor_atual -> a recalibração que a
  produção aplica; sem ela o impacto bruto engana (medido nesta sessão:
  total_crosses>=10 dá +19,2pp cru e +0,1pp controlado pelos escanteios já
  ocorridos)
- backtest_odds_reais_v2._tentativas_mercado/_achar_odd_real -> o casamento
  de linha .5 contra a linha INTEIRA 3-vias que a bet365 usa em escanteios
  (mais_de 8.5 -> Over 8; menos_de 8.5 -> Under 9). Os backtests antigos
  erravam isso e concluíam "0% de cobertura" onde havia mercado.

DUAS RESSALVAS que o número carrega, ditas aqui pra não serem esquecidas na
leitura:

1. É IN-SAMPLE. O backtest roda sobre as mesmas fixtures que produziram a
   descoberta. É teto otimista, não estimativa honesta de futuro. Serve
   porque a decisão é assimétrica: se nem o teto otimista for positivo, não
   há o que publicar. Foi assim que os números do Brasil foram produzidos
   também, então é comparável.
2. A recalibração usa o mesmo dado da liga. Mesma ressalva que a produção já
   aceita (ver docstring de recalibrar_por_valor_atual): não é descoberta
   nova, é reestimativa de condição já fixada.

RESULTADO DA PRIMEIRA EXECUÇÃO (18/09/2026) — LEIA ANTES DE CONFIAR NO NÚMERO:

O ROI que este script mede é INUTILIZÁVEL, e a causa não é bug: é o arquivo
de odds. A bet365 MOVE a linha conforme o jogo anda, e o histórico só guarda
a linha cotada em cada momento. Procurar retroativamente por uma linha FIXA
(a da regra) só acha match nos jogos onde ela já está no dinheiro.

Medido na regra mls_escanteios_002 (30', +8.5), sobre os 222 disparos:
  - 53 fixtures TÊM a linha "Over 8" cotada -> 5,6 escanteios aos 30',
    100,0% de acerto, odd média 1,35
  - 169 fixtures NÃO têm             -> 3,2 escanteios aos 30', 71,0%
E quando a linha 8 não está cotada, as que estão são 7, 6, 12, 13...

71% é a taxa real da regra (bate com a amostra de confirmação). Os 100% são
puro artefato de seleção. O mesmo vale pro consolidado de +25,9%.

Consequência que vai além deste script: os ROI históricos do projeto
(+17,8% Brasil confirmacoes=3, -47,1% nórdicas) saíram do mesmo arquivo com
o mesmo casamento de linha fixa, então carregam o mesmo viés. O viés é
ASSIMÉTRICO e inflaciona: um resultado muito negativo (nórdicas) continua
valendo — seria pior ainda sem o viés — mas um resultado positivo não é
evidência de nada.

Único caminho não enviesado pra medir ROI: para frente, capturando a odd ao
vivo no momento do sinal, que é o que ligas_live_app já faz em
historico_sinais.csv. Retroativo com este arquivo não tem conserto.

Uso: python3 roi_ligas_novas.py
"""
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta

import backtest_odds_reais_v2 as bt
import config
import cruzar_vias_ligas_novas as cz
import gerar_regras_sinais as g
from descobrir_ligas_novas import LIGAS_NOVAS

# Só alvos com mercado ao vivo de verdade (ver docstring).
ALVOS_COM_MERCADO = ["escanteios", "cartoes"]

# Portões de produção, replicados de ligas_live_app/live_monitor.py. Não
# inventar limiar aqui: o ponto da medição é saber o que a produção mostraria.
IMPACTO_MINIMO_PP_VALOR_ATUAL = 5.0
PROBABILIDADE_MINIMA = 0.70   # PROBABILIDADE_MINIMA_VALOR_ATUAL_PADRAO (liga não mapeada)
TETO_EV_PCT_ODD_REAL = 15.0

PREFIXO_POR_LIGA = LIGAS_NOVAS                      # {779: "mls", ...}
LIGA_POR_PREFIXO = {v: k for k, v in LIGAS_NOVAS.items()}


def familias_da_liga(prefixo):
    """As famílias com as 3 vias concordando, já colapsadas, viradas em regra
    no mesmo formato que regras_sinais.json usa (é o que recalibrar_por_valor_
    atual e o backtest esperam)."""
    regras = []
    for alvo_id in ALVOS_COM_MERCADO:
        _niveis, triplas, _por_via = cz.cruzar(alvo_id, prefixo)
        for i, t in enumerate(triplas, 1):
            regras.append({
                "id": f"{prefixo}_{alvo_id}_{i:03d}",
                "alvo": alvo_id,
                "minuto": t["minuto"],
                "gols_momento": t["gols_momento"],
                "condicoes": t["condicoes"],
                "mercado": {
                    "stat": g.ALVO_STAT_BASE[alvo_id],
                    "direcao": "mais_de" if t["sinal_mercado"] == "+" else "menos_de",
                    "linha": t["linha_mercado"],
                },
                "regiao": prefixo,
                "amostra_confirmacao": t["amostra"],
                "prob_condicao_confirmacao": t["p_condicao"],
                # recalibrar_por_valor_atual usa como fallback quando um delta
                # nao tem amostra propria de base (ver gerar_regras_sinais.py).
                "prob_base_confirmacao": t["p_base"],
                "impacto_pp": round(t["impacto"], 2),
            })
    return regras



def _achar_odd_sem_stopped(odds_historico, tentativas, timestamp_checkpoint):
    """Igual backtest_odds_reais_v2._achar_odd_real, MENOS o filtro de
    `stopped`.

    Por que remover: no arquivo histórico, 96,2% das entradas de escanteios
    vêm com stopped=True, o que seria implausível se significasse "mercado
    suspenso naquele instante". Teste decisivo com dado de verdade — a
    fixture 19667165, onde a produção capturou AO VIVO uma odd bet365 de 1,40
    aos 18' (ligas_live_app/historico_sinais.csv), tem ZERO entradas
    não-stopped de escanteios no arquivo. Ou seja, o flag reflete o estado do
    registro no fim da partida, não o estado no momento da odd: aplicá-lo
    retroativamente descarta odd que era real e apostável.

    O filtro CONTINUA certo ao vivo (odds_ao_vivo.py), onde stopped é lido no
    presente — é só retroativamente que ele mente. backtest_odds_reais_v2.py
    herdou o filtro de odds_ao_vivo.py sem notar essa diferença.

    O corte por timestamp continua valendo: a odd tem que ter sido conhecida
    até o checkpoint + 5min, senão é informação do futuro.
    """
    candidatas = []
    for market_id, label, total_alvo in tentativas:
        for d in odds_historico:
            if d.get("market_id") != market_id or d.get("label") != label:
                continue
            total = d.get("total")
            if total is None:
                continue
            try:
                if float(total) != float(total_alvo):
                    continue
                valor = float(d["value"])
            except (TypeError, ValueError):
                continue
            try:
                ts = datetime.strptime(d["latest_bookmaker_update"], "%Y-%m-%d %H:%M:%S")
            except (TypeError, ValueError):
                continue
            if ts > timestamp_checkpoint + timedelta(minutes=5):
                continue
            candidatas.append((ts, valor))
    if not candidatas:
        return None
    candidatas.sort(key=lambda x: x[0])
    return candidatas[-1][1]


def _snaps_e_jogos(league_id):
    d = json.load(open(os.path.join(config.DIR_DADOS, f".checkpoint_{league_id}.json"), encoding="utf-8"))
    snaps = defaultdict(dict)
    for s in d["snapshots"]:
        snaps[s["fixture_id"]][s["minuto"]] = s
    return d, snaps


def backtest(regras, league_id):
    """Percorre as fixtures da liga e simula cada regra, com e sem os portões
    de produção. Devolve (linhas_detalhe, resumo_por_regra)."""
    d, snaps_por_fixture = _snaps_e_jogos(league_id)
    detalhe = []

    for fid_str, jogo in d["jogos"].items():
        fid = int(fid_str)
        if not jogo.get("finalizado") or fid_str not in d["resultados_alvo"]:
            continue
        caminho = os.path.join(bt.CACHE_ODDS_DIR, f"{fid}.json")
        if not os.path.exists(caminho):
            continue
        try:
            odds_historico = json.load(open(caminho, encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not odds_historico:
            continue

        kickoff = datetime.strptime(jogo["data_hora"], "%Y-%m-%d %H:%M:%S")
        resultado_final = d["resultados_alvo"][fid_str]
        snaps = snaps_por_fixture.get(fid, {})

        for regra in regras:
            snap = snaps.get(regra["minuto"])
            if not snap or snap.get("gols_momento") != regra["gols_momento"]:
                continue
            if not bt._condicao_bate(regra["condicoes"], snap):
                continue

            alvo = regra["alvo"]
            direcao = regra["mercado"]["direcao"]
            linha = regra["mercado"]["linha"]
            valor_final = resultado_final.get(alvo)
            if valor_final is None:
                continue

            tentativas = bt._tentativas_mercado(alvo, direcao, linha)
            odd = _achar_odd_sem_stopped(odds_historico, tentativas, kickoff + timedelta(minutes=regra["minuto"]))
            if odd is None:
                continue

            # Portão de produção: probabilidade condicionada ao valor ATUAL do
            # próprio alvo, não a probabilidade bruta da regra.
            stats = None
            tabela = regra.get("por_valor_atual") or {}
            # _valor_stat_alvo e nao snap.get(): "cards" nao existe no
            # snapshot (so yellowcards/redcards separados) e o helper soma os
            # dois, do mesmo jeito que a producao faz.
            valor_atual = g._valor_stat_alvo(snap, regra["mercado"]["stat"])
            if tabela and valor_atual is not None:
                chave = str(int(round(valor_atual)))
                stats = tabela.get(chave)
                if stats is None:
                    disp = [int(v) for v in tabela]
                    stats = tabela[str(min(disp, key=lambda v: abs(v - int(round(valor_atual)))))]

            p_bruta = regra["prob_condicao_confirmacao"]
            p_ctrl = stats["p_condicao"] if stats else None
            imp_ctrl = stats["impacto_pp"] if stats else None
            ev_bruto = (p_bruta * odd - 1) * 100
            ev_ctrl = (p_ctrl * odd - 1) * 100 if p_ctrl is not None else None

            bateu = (valor_final > linha) if direcao == "mais_de" else (valor_final < linha)
            passa_portao = (
                stats is not None
                and imp_ctrl >= IMPACTO_MINIMO_PP_VALOR_ATUAL
                and p_ctrl >= PROBABILIDADE_MINIMA
                and ev_ctrl is not None and 0 < ev_ctrl <= TETO_EV_PCT_ODD_REAL
            )
            detalhe.append({
                "fixture_id": fid, "regra_id": regra["id"], "alvo": alvo,
                "direcao": direcao, "linha": linha, "minuto": regra["minuto"],
                "valor_atual": valor_atual, "odd": odd,
                "p_bruta": p_bruta, "p_ctrl": p_ctrl, "impacto_ctrl_pp": imp_ctrl,
                "ev_bruto_pct": ev_bruto, "ev_ctrl_pct": ev_ctrl,
                "passa_portao": passa_portao,
                "bateu": int(bateu),
                "retorno": (odd - 1) if bateu else -1.0,
            })
    return detalhe


def _resumir(linhas, rotulo):
    if not linhas:
        print(f"  {rotulo:34s} sem apostas")
        return
    n = len(linhas)
    green = sum(x["bateu"] for x in linhas)
    ret = sum(x["retorno"] for x in linhas)
    print(f"  {rotulo:34s} {n:5d} apostas | acerto {green/n*100:5.1f}% | ROI {ret/n*100:+7.1f}% | odd media {sum(x['odd'] for x in linhas)/n:.2f}")


def rodar():
    todas_linhas = []
    for prefixo, league_id in LIGA_POR_PREFIXO.items():
        regras = familias_da_liga(prefixo)
        print(f"\n{'='*78}\n{prefixo.upper()} (liga {league_id}) — {len(regras)} famílias com as 3 vias\n{'='*78}", flush=True)
        if not regras:
            print("  nenhuma família — nada a medir")
            continue

        for r in regras:
            cond = " E ".join(f"{c['stat']}{c['operador']}{c['limite']:g}" for c in r["condicoes"])
            print(f"  {r['id']}  {r['minuto']:3d}' g={r['gols_momento']} | {cond} -> "
                  f"{r['mercado']['direcao']} {r['mercado']['linha']:g} | bruto {r['impacto_pp']:+.1f}pp n={r['amostra_confirmacao']}", flush=True)

        print("\n  recalibrando por valor atual do alvo (pool só desta liga)...", flush=True)
        g.recalibrar_por_valor_atual(regras)

        linhas = backtest(regras, league_id)
        for x in linhas:
            x["liga"] = prefixo
        todas_linhas.extend(linhas)

        print(f"\n  --- {prefixo}: {len(linhas)} disparos com odd real encontrada ---")
        _resumir(linhas, "TODOS (sem portão)")
        _resumir([x for x in linhas if x["passa_portao"]], "com portão de produção")
        print()
        for r in regras:
            do_id = [x for x in linhas if x["regra_id"] == r["id"]]
            com_portao = [x for x in do_id if x["passa_portao"]]
            _resumir(do_id, f"{r['id']} (bruto)")
            _resumir(com_portao, f"{r['id']} (portão)")

    if todas_linhas:
        caminho = os.path.join(config.DIR_DADOS, "roi_ligas_novas_detalhe.csv")
        import csv
        with open(caminho, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(todas_linhas[0].keys()))
            w.writeheader()
            w.writerows(todas_linhas)
        print(f"\n{'='*78}\nCONSOLIDADO ({len(todas_linhas)} disparos, detalhe em {caminho})\n{'='*78}")
        _resumir(todas_linhas, "TODAS AS LIGAS (sem portão)")
        _resumir([x for x in todas_linhas if x["passa_portao"]], "TODAS AS LIGAS (com portão)")
    else:
        print("\nNenhum disparo com odd real em liga nenhuma.")


if __name__ == "__main__":
    rodar()
