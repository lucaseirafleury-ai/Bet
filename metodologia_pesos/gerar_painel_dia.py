"""Gera o painel diário (HTML publicado como Artifact) — jogos
qualificados dos 3 critérios pros próximos dias, resultados recentes
(Green/Red) e o resumo de entradas/acerto/ROI na lateral.

Uso: `python3 gerar_painel_dia.py [caminho_saida]`
(default: `painel_dia.html` no diretório atual)

Mantém `data/ledger_sugestoes.json` — cada sugestão feita é registrada
lá (pendente) e resolvida (Green/Red) assim que o jogo aparece como
finalizado no histórico do Sportmonks já atualizado. Esse arquivo É
versionado no git (histórico real de apostas sugeridas, pequeno,
diferente dos JSONL de dado bruto).

Não publica sozinho — quem chama isso (a rotina diária) precisa
republicar o HTML gerado usando a ferramenta Artifact, passando a
mesma URL do painel já existente (pra manter o link fixo que o Lucas
salvou).
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

from ledger_apostas import calcular_resumo, carregar_ledger, registrar_novas_sugestoes, resolver_pendentes, salvar_ledger
from previsao_dia import CAMINHO_HIST, gerar_sugestoes_do_dia
from sportmonks_adapter import carregar_liga_sportmonks

FUSO_BRASIL = timezone(timedelta(hours=-3))
CAMINHO_LEDGER = "data/ledger_sugestoes.json"
DIAS_RESULTADOS_RECENTES = 14

CRITERIOS_INFO = [
    dict(nome="BTTS", stake="cheio", stake_label="stake normal", evidencia="Série A · bet365 z=+2,89 · sem ano negativo"),
    dict(nome="Over 2.5", stake="reduzido", stake_label="stake reduzido", evidencia="Série A · Sbo z=+2,00 · filtro União (odd/favoritismo) · sem ano negativo"),
    dict(nome="Cartões+Árbitro", stake="reduzido", stake_label="stake reduzido", evidencia="Série B · bet365 z=+2,61 · edge mín. 10% · positivo nos 3 anos"),
]

_NOME_LADO = {"btts": "BTTS · Sim", "over25": "Over 2.5"}

# Casa usada como base estatística de cada critério ("bet365" não leva
# nota — é a casa que o Lucas já usa direto). Sbo leva a nota de tentar a
# Betfair Exchange antes, na prática — a Exchange não está representada
# no dado do Sportmonks (só a Sportsbook deles, rala e com margem pior
# que o bet365), então isso não dá pra confirmar automaticamente aqui.
_NOTA_EXECUCAO = {"Sbo": "odd de referência: Sbo — tente a Betfair Exchange antes, se a linha existir"}


def _fmt_data_hora(data_iso):
    dt_utc = datetime.strptime(data_iso[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    dt_local = dt_utc.astimezone(FUSO_BRASIL)
    return dt_local.strftime("%d/%m, %H:%M")


def _card_pendente_html(s):
    lado = _NOME_LADO.get(s["lado"], s["lado"])
    stake_classe = "cheio" if s["stake"] == "normal" else "reduzido"
    stake_texto = "stake normal" if s["stake"] == "normal" else "stake reduzido"
    nota = _NOTA_EXECUCAO.get(s.get("casa_ref"))
    nota_html = f'\n      <div class="nota-execucao">{nota}</div>' if nota else ""
    return f"""
    <div class="jogo-card">
      <div class="confronto">{s['jogo']}</div>
      <div class="meta"><span class="liga-tag">{s['liga']}</span> {_fmt_data_hora(s['data_jogo'])} BRT</div>
      <div class="aposta">
        <span class="lado">{lado}</span>
        <span class="odd-edge"><span class="odd">{s['odd']:.2f}</span><span class="edge">+{s['edge']*100:.1f}% edge</span></span>
        <span class="stake-tag stake {stake_classe}">{stake_texto}</span>
      </div>{nota_html}
    </div>"""


def _card_resolvido_html(e):
    lado = _NOME_LADO.get(e["lado"], e["lado"])
    classe = "green" if e["resultado"] == "green" else "red"
    texto = "GREEN" if e["resultado"] == "green" else "RED"
    lucro_txt = f"{'+' if e['lucro'] >= 0 else ''}{e['lucro']:.2f}u"
    return f"""
    <div class="jogo-card resolvido {classe}">
      <div class="confronto">{e['jogo']}</div>
      <div class="meta"><span class="liga-tag">{e['liga']}</span> {_fmt_data_hora(e['data_jogo'])} BRT · {e['criterio']}</div>
      <div class="aposta">
        <span class="lado">{lado}</span>
        <span class="odd-edge"><span class="odd">{e['odd']:.2f}</span><span class="lucro {classe}">{lucro_txt}</span></span>
        <span class="resultado-pill {classe}">{texto}</span>
      </div>
    </div>"""


def _criterio_chip_html(c):
    return f"""
    <div class="criterio-chip">
      <div class="linha1"><span class="nome">{c['nome']}</span><span class="stake {c['stake']}">{c['stake_label']}</span></div>
      <div class="evidencia">{c['evidencia']}</div>
    </div>"""


def _linha_resumo_criterio_html(nome, dados):
    roi_txt = f"{dados['roi']*100:+.1f}%" if dados["roi"] is not None else "—"
    roi_classe = "pos" if (dados["roi"] or 0) >= 0 else "neg"
    return f"""
      <tr>
        <td>{nome}</td>
        <td class="num">{dados['n']}</td>
        <td class="num">{dados['n_green']}/{dados['n_red']}</td>
        <td class="num {roi_classe}">{roi_txt}</td>
      </tr>"""


TEMPLATE = """<title>Painel Brasileirão</title>

<style>
  @import url('https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@600;700;800&family=Karla:ital,wght@0,400;0,500;0,700;1,400&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

  :root {{
    --bg: #f5f6f1; --surface: #ffffff; --surface-sunken: #edefe8; --border: #dbdfd3;
    --text: #131b16; --text-muted: #5c665e; --text-faint: #8b9389;
    --accent: #1f6f4a; --accent-tint: #e4f0e8; --accent-strong: #14512f;
    --amber: #a56312; --amber-tint: #f7ecdc;
    --red: #a3261e; --red-tint: #f8e6e4; --red-strong: #7d1c16;
    --shadow: 0 1px 2px rgba(19, 27, 22, 0.04), 0 6px 20px -8px rgba(19, 27, 22, 0.12);
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg: #0e1512; --surface: #161f1a; --surface-sunken: #101713; --border: #263229;
      --text: #e9ede7; --text-muted: #9aa79d; --text-faint: #6c766e;
      --accent: #45b17f; --accent-tint: #17281f; --accent-strong: #6fd6a3;
      --amber: #d99a3f; --amber-tint: #2a2214;
      --red: #e5776e; --red-tint: #2a1715; --red-strong: #f0968f;
      --shadow: 0 1px 2px rgba(0, 0, 0, 0.3), 0 6px 24px -8px rgba(0, 0, 0, 0.5);
    }}
  }}
  :root[data-theme="dark"] {{
    --bg: #0e1512; --surface: #161f1a; --surface-sunken: #101713; --border: #263229;
    --text: #e9ede7; --text-muted: #9aa79d; --text-faint: #6c766e;
    --accent: #45b17f; --accent-tint: #17281f; --accent-strong: #6fd6a3;
    --amber: #d99a3f; --amber-tint: #2a2214;
    --red: #e5776e; --red-tint: #2a1715; --red-strong: #f0968f;
    --shadow: 0 1px 2px rgba(0, 0, 0, 0.3), 0 6px 24px -8px rgba(0, 0, 0, 0.5);
  }}

  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--text); font-family: 'Karla', system-ui, -apple-system, sans-serif; -webkit-font-smoothing: antialiased; }}
  .page {{ max-width: 1180px; margin: 0 auto; padding: 2.5rem 1.5rem 4rem; }}
  h1, h2, h3 {{ text-wrap: balance; font-family: 'Big Shoulders Display', system-ui, sans-serif; margin: 0; }}

  .masthead {{ display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem; flex-wrap: wrap; border-bottom: 2px solid var(--text); padding-bottom: 1.1rem; margin-bottom: 1.75rem; }}
  .masthead h1 {{ font-size: clamp(2.1rem, 5vw, 2.9rem); font-weight: 800; letter-spacing: 0.01em; line-height: 0.95; }}
  .masthead .sub {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem; color: var(--text-muted); text-align: right; line-height: 1.5; }}
  .masthead .sub b {{ color: var(--text); font-weight: 600; }}

  .criterios {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.75rem; margin-bottom: 2.25rem; }}
  .criterio-chip {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 0.85rem 1rem; box-shadow: var(--shadow); }}
  .criterio-chip .linha1 {{ display: flex; justify-content: space-between; align-items: baseline; gap: 0.5rem; }}
  .criterio-chip .nome {{ font-weight: 700; font-size: 0.95rem; }}
  .criterio-chip .stake {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.65rem; letter-spacing: 0.04em; text-transform: uppercase; padding: 0.15rem 0.5rem; border-radius: 999px; white-space: nowrap; }}
  .stake.cheio {{ background: var(--accent-tint); color: var(--accent-strong); }}
  .stake.reduzido {{ background: var(--amber-tint); color: var(--amber); }}
  .criterio-chip .evidencia {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem; color: var(--text-muted); margin-top: 0.35rem; }}

  .layout {{ display: grid; grid-template-columns: 1fr 300px; gap: 2rem; align-items: start; }}

  .secao-titulo {{ display: flex; align-items: baseline; gap: 0.6rem; margin: 0 0 0.9rem; }}
  .secao-titulo:not(:first-child) {{ margin-top: 2.25rem; }}
  .secao-titulo h2 {{ font-size: 1.5rem; font-weight: 700; }}
  .secao-titulo .contagem {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.85rem; color: var(--text-faint); }}

  .jogos {{ display: flex; flex-direction: column; gap: 0.7rem; }}
  .jogo-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 1rem 1.15rem; box-shadow: var(--shadow); display: grid; grid-template-columns: 1fr auto; gap: 0.4rem 1rem; align-items: center; }}
  .jogo-card.resolvido.green {{ border-color: color-mix(in srgb, var(--accent) 45%, var(--border)); }}
  .jogo-card.resolvido.red {{ border-color: color-mix(in srgb, var(--red) 45%, var(--border)); }}
  .jogo-card .confronto {{ font-weight: 700; font-size: 1.05rem; }}
  .jogo-card .meta {{ grid-column: 1; display: flex; gap: 0.6rem; align-items: center; font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem; color: var(--text-muted); }}
  .liga-tag {{ background: var(--surface-sunken); border-radius: 5px; padding: 0.1rem 0.45rem; color: var(--text-muted); font-weight: 500; }}
  .aposta {{ grid-column: 2; grid-row: 1 / 3; text-align: right; display: flex; flex-direction: column; align-items: flex-end; gap: 0.25rem; min-width: 132px; }}
  .aposta .lado {{ font-weight: 700; font-size: 0.92rem; }}
  .aposta .odd-edge {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.82rem; display: flex; gap: 0.5rem; align-items: baseline; font-variant-numeric: tabular-nums; }}
  .aposta .odd {{ color: var(--text); font-weight: 600; }}
  .aposta .edge {{ color: var(--accent-strong); }}
  .aposta .lucro.green {{ color: var(--accent-strong); font-weight: 600; }}
  .aposta .lucro.red {{ color: var(--red-strong); font-weight: 600; }}
  .aposta .stake-tag {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.04em; padding: 0.1rem 0.4rem; border-radius: 999px; }}
  .resultado-pill {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem; font-weight: 700; letter-spacing: 0.04em; padding: 0.15rem 0.5rem; border-radius: 999px; }}
  .resultado-pill.green {{ background: var(--accent-tint); color: var(--accent-strong); }}
  .resultado-pill.red {{ background: var(--red-tint); color: var(--red-strong); }}

  .nota-execucao {{ grid-column: 1 / -1; font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem; color: var(--text-faint); border-top: 1px dashed var(--border); padding-top: 0.4rem; margin-top: 0.15rem; }}

  .vazio {{ background: var(--surface); border: 1px dashed var(--border); border-radius: 12px; padding: 1.5rem; text-align: center; color: var(--text-muted); font-size: 0.9rem; }}

  .sidebar {{ display: flex; flex-direction: column; gap: 1rem; position: sticky; top: 1.5rem; }}
  .resumo-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 1.25rem; box-shadow: var(--shadow); }}
  .resumo-card h3 {{ font-size: 1.1rem; font-weight: 700; margin-bottom: 0.9rem; }}
  .resumo-roi {{ font-family: 'IBM Plex Mono', monospace; font-size: 2.1rem; font-weight: 600; line-height: 1; font-variant-numeric: tabular-nums; }}
  .resumo-roi.pos {{ color: var(--accent-strong); }}
  .resumo-roi.neg {{ color: var(--red-strong); }}
  .resumo-roi-label {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.7rem; color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 0.3rem; }}
  .resumo-stats {{ display: flex; gap: 1.25rem; margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--border); }}
  .resumo-stat {{ display: flex; flex-direction: column; }}
  .resumo-stat .valor {{ font-family: 'IBM Plex Mono', monospace; font-size: 1.3rem; font-weight: 600; font-variant-numeric: tabular-nums; }}
  .resumo-stat .valor.green {{ color: var(--accent-strong); }}
  .resumo-stat .valor.red {{ color: var(--red-strong); }}
  .resumo-stat .label {{ font-size: 0.68rem; color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.03em; }}
  .resumo-stake-nota {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.65rem; color: var(--text-faint); margin-top: 0.85rem; line-height: 1.5; }}

  .tabela-criterios {{ width: 100%; border-collapse: collapse; font-size: 0.78rem; }}
  .tabela-criterios th {{ text-align: left; font-family: 'IBM Plex Mono', monospace; font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.03em; color: var(--text-faint); font-weight: 500; padding-bottom: 0.4rem; border-bottom: 1px solid var(--border); }}
  .tabela-criterios td {{ padding: 0.4rem 0; border-bottom: 1px solid var(--border); font-family: 'IBM Plex Mono', monospace; }}
  .tabela-criterios td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .tabela-criterios td.pos {{ color: var(--accent-strong); }}
  .tabela-criterios td.neg {{ color: var(--red-strong); }}
  .tabela-criterios tr:last-child td {{ border-bottom: none; }}

  footer {{ margin-top: 3rem; padding-top: 1.25rem; border-top: 1px solid var(--border); font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem; color: var(--text-faint); line-height: 1.7; }}

  @media (max-width: 760px) {{
    .layout {{ grid-template-columns: 1fr; }}
    .sidebar {{ position: static; }}
  }}
  @media (max-width: 520px) {{
    .masthead {{ flex-direction: column; align-items: flex-start; }}
    .masthead .sub {{ text-align: left; }}
    .jogo-card {{ grid-template-columns: 1fr; }}
    .aposta {{ grid-column: 1; grid-row: auto; align-items: flex-start; text-align: left; margin-top: 0.4rem; }}
  }}
</style>

<div class="page">
  <div class="masthead">
    <h1>Painel do dia</h1>
    <div class="sub">Atualizado <b>{atualizado_em}</b> (BRT)<br>Série A + Série B · próximos {dias_a_frente} dias</div>
  </div>

  <div class="criterios">{criterios_html}
  </div>

  <div class="layout">
    <div class="conteudo">
      <div class="secao-titulo">
        <h2>Jogos qualificados</h2>
        <span class="contagem">{n_sugestoes} sugest{plural_sugestao}</span>
      </div>
      <div class="jogos">{jogos_html}
      </div>

      <div class="secao-titulo">
        <h2>Resultados recentes</h2>
        <span class="contagem">últimos {dias_resultados} dias</span>
      </div>
      <div class="jogos">{resolvidos_html}
      </div>
    </div>

    <aside class="sidebar">
      <div class="resumo-card">
        <h3>Resumo geral</h3>
        <div class="resumo-roi-label">ROI (stake fixo)</div>
        <div class="resumo-roi {roi_classe}">{roi_txt}</div>
        <div class="resumo-stats">
          <div class="resumo-stat"><span class="valor">{resumo_n}</span><span class="label">Entradas</span></div>
          <div class="resumo-stat"><span class="valor green">{resumo_green}</span><span class="label">Green</span></div>
          <div class="resumo-stat"><span class="valor red">{resumo_red}</span><span class="label">Red</span></div>
        </div>
        <table class="tabela-criterios" style="margin-top: 1rem;">
          <thead><tr><th>Critério</th><th class="num">N</th><th class="num">G/R</th><th class="num">ROI</th></tr></thead>
          <tbody>{tabela_criterios_html}
          </tbody>
        </table>
        <div class="resumo-stake-nota">Stake fixo: BTTS = 1u, Over 2.5 e Cartões+Árbitro = 0,5u. ROI já pondera pelo stake de cada critério.</div>
      </div>
    </aside>
  </div>

  <footer>
    Odd = odd real média do mercado (Sportmonks) no momento da checagem · Edge = probabilidade do modelo − probabilidade implícita do mercado.<br>
    Metodologia validada em <code>docs/protocolo.md</code> (repo Bet) · dado 100% Sportmonks, sem FootyStats.
  </footer>
</div>
"""


def gerar_html(sugestoes_pendentes, resolvidos_recentes, resumo, dias_a_frente):
    agora_brt = datetime.now(timezone.utc).astimezone(FUSO_BRASIL)

    if sugestoes_pendentes:
        jogos_html = "".join(_card_pendente_html(s) for s in sorted(sugestoes_pendentes, key=lambda s: s["data_jogo"]))
    else:
        jogos_html = '\n    <div class="vazio">Nenhum jogo qualificado nos próximos dias — normal, os critérios são seletivos por design.</div>'

    if resolvidos_recentes:
        resolvidos_html = "".join(_card_resolvido_html(e) for e in sorted(resolvidos_recentes, key=lambda e: e["data_jogo"], reverse=True))
    else:
        resolvidos_html = '\n    <div class="vazio">Nenhum resultado resolvido ainda nesta janela.</div>'

    roi = resumo["roi"]
    roi_txt = f"{roi*100:+.1f}%" if roi is not None else "—"
    tabela_criterios_html = "".join(_linha_resumo_criterio_html(nome, dados) for nome, dados in resumo["por_criterio"].items())
    if not tabela_criterios_html:
        tabela_criterios_html = '<tr><td colspan="4" style="color: var(--text-faint); text-align: center;">sem dado ainda</td></tr>'

    return TEMPLATE.format(
        atualizado_em=agora_brt.strftime("%d/%m/%Y, %H:%M"),
        dias_a_frente=dias_a_frente,
        dias_resultados=DIAS_RESULTADOS_RECENTES,
        criterios_html="".join(_criterio_chip_html(c) for c in CRITERIOS_INFO),
        n_sugestoes=len(sugestoes_pendentes),
        plural_sugestao="ão" if len(sugestoes_pendentes) == 1 else "ões",
        jogos_html=jogos_html,
        resolvidos_html=resolvidos_html,
        roi_txt=roi_txt,
        roi_classe="pos" if (roi or 0) >= 0 else "neg",
        resumo_n=resumo["n"], resumo_green=resumo["n_green"], resumo_red=resumo["n_red"],
        tabela_criterios_html=tabela_criterios_html,
    )


def atualizar_painel(caminho_ledger=CAMINHO_LEDGER, dias_a_frente=3):
    ledger = carregar_ledger(caminho_ledger)

    dfs_por_liga = {liga: carregar_liga_sportmonks(caminho) for liga, caminho in CAMINHO_HIST.items()}
    ledger = resolver_pendentes(ledger, dfs_por_liga)

    sugestoes = gerar_sugestoes_do_dia(dias_a_frente=dias_a_frente)
    hoje = datetime.now(timezone.utc).date().isoformat()
    ledger = registrar_novas_sugestoes(ledger, sugestoes, data_registro=hoje)

    salvar_ledger(caminho_ledger, ledger)

    pendentes = [e for e in ledger if e["resultado"] == "pendente"]
    corte_recente = (datetime.now(timezone.utc) - timedelta(days=DIAS_RESULTADOS_RECENTES)).strftime("%Y-%m-%d %H:%M:%S")
    resolvidos_recentes = [
        e for e in ledger
        if e["resultado"] != "pendente" and e["data_jogo"] >= corte_recente
    ]
    resumo = calcular_resumo(ledger)

    return pendentes, resolvidos_recentes, resumo


if __name__ == "__main__":
    caminho_saida = sys.argv[1] if len(sys.argv) > 1 else "painel_dia.html"
    dias_a_frente = 3
    pendentes, resolvidos_recentes, resumo = atualizar_painel(dias_a_frente=dias_a_frente)
    html = gerar_html(pendentes, resolvidos_recentes, resumo, dias_a_frente)
    with open(caminho_saida, "w") as f:
        f.write(html)
    print(
        f"{len(pendentes)} pendentes, {len(resolvidos_recentes)} resolvidos recentes, "
        f"resumo geral n={resumo['n']} roi={resumo['roi']} — painel salvo em {caminho_saida}",
        flush=True,
    )
