"""
Gera o painel-artefato de histórico de assertividade (green/red/ROI por tipo
de aposta) a partir de historico_sinais.csv — publicado como Artifact no
Claude, no mesmo espírito do "Painel Brasileirão" (docs/protocolo.md), só que
para os sinais AO VIVO deste painel (escanteios/chutes/gols), não os tips
pré-jogo.

Não substitui historico_sinais.csv nem a checagem diária das rotinas — é só
uma camada de apresentação agregada em cima do mesmo CSV. Rodar de novo e
republicar (mesma URL) sempre que o CSV ganhar linhas novas.

Uso: python3 gerar_painel_historico.py
Gera ligas_live_app/painel_historico.html — publique manualmente via Artifact
(action publish, mesma URL de antes pra atualizar em vez de criar outra).
"""
import csv
import os
from datetime import datetime, timezone

CAMINHO_CSV = os.path.join(os.path.dirname(__file__), "historico_sinais.csv")
CAMINHO_SAIDA = os.path.join(os.path.dirname(__file__), "painel_historico.html")

ALVO_NOME = {
    "escanteios": "Escanteios", "chutes_totais": "Chutes totais",
    "chutes_no_alvo": "Chutes no alvo", "gols": "Gols", "cartoes": "Cartões",
}
DIRECAO_NOME = {"mais_de": "Mais de", "menos_de": "Menos de"}


def carregar_linhas():
    with open(CAMINHO_CSV, newline="", encoding="utf-8") as fp:
        linhas = list(csv.DictReader(fp))
    processadas = []
    for r in linhas:
        if r["resultado"] not in ("green", "red"):
            continue
        odd_real = float(r["odd_real"]) if r.get("odd_real") else None
        odd_minima = float(r["odd_minima"]) if r.get("odd_minima") else None
        odd_usada = odd_real if odd_real else odd_minima
        if odd_usada is None:
            continue
        lucro = (odd_usada - 1) if r["resultado"] == "green" else -1.0
        processadas.append({
            **r,
            "odd_usada": odd_usada,
            "fonte_odd": "real" if odd_real else "sintética",
            "lucro": lucro,
            "tipo_aposta": f"{ALVO_NOME.get(r['alvo'], r['alvo'])} · {DIRECAO_NOME.get(r['direcao'], r['direcao'])}",
        })
    processadas.sort(key=lambda r: r["timestamp_sinal"])
    return processadas


def agrupar_por_tipo(linhas):
    grupos = {}
    for r in linhas:
        grupos.setdefault(r["tipo_aposta"], []).append(r)
    resumo = []
    for tipo, itens in grupos.items():
        n = len(itens)
        greens = sum(1 for i in itens if i["resultado"] == "green")
        reds = n - greens
        roi_pct = sum(i["lucro"] for i in itens) / n * 100
        resumo.append({
            "tipo": tipo, "n": n, "greens": greens, "reds": reds,
            "taxa_pct": greens / n * 100, "roi_pct": roi_pct,
        })
    resumo.sort(key=lambda g: -g["n"])
    return resumo


def curva_roi_acumulado(linhas):
    acumulado = 0.0
    pontos = []
    for r in linhas:
        acumulado += r["lucro"]
        pontos.append(acumulado)
    return pontos


def _svg_sparkline(pontos, largura=560, altura=120, pad=14):
    if len(pontos) < 2:
        return ""
    minimo, maximo = min(pontos + [0]), max(pontos + [0])
    amplitude = (maximo - minimo) or 1
    n = len(pontos)

    def x_de(i):
        return pad + (i / (n - 1)) * (largura - 2 * pad)

    def y_de(v):
        return pad + (1 - (v - minimo) / amplitude) * (altura - 2 * pad)

    pts = " ".join(f"{x_de(i):.1f},{y_de(v):.1f}" for i, v in enumerate(pontos))
    y_zero = y_de(0)
    cor = "#35d68a" if pontos[-1] >= 0 else "#ff5c5c"
    area_pts = f"{x_de(0):.1f},{y_zero:.1f} {pts} {x_de(n-1):.1f},{y_zero:.1f}"
    return f'''<svg viewBox="0 0 {largura} {altura}" class="roi-spark" preserveAspectRatio="none" role="img" aria-label="ROI acumulado em unidades ao longo dos sinais fechados">
    <line x1="{pad}" y1="{y_zero:.1f}" x2="{largura-pad}" y2="{y_zero:.1f}" class="spark-zero" />
    <polygon points="{area_pts}" fill="{cor}" opacity="0.12" stroke="none" />
    <polyline points="{pts}" fill="none" stroke="{cor}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
    <circle cx="{x_de(n-1):.1f}" cy="{y_de(pontos[-1]):.1f}" r="4" fill="{cor}" />
  </svg>'''


def gerar_html():
    linhas = carregar_linhas()
    resumo_tipos = agrupar_por_tipo(linhas)
    n_total = len(linhas)
    greens_total = sum(1 for r in linhas if r["resultado"] == "green")
    reds_total = n_total - greens_total
    roi_total_pct = (sum(r["lucro"] for r in linhas) / n_total * 100) if n_total else 0.0
    lucro_total_un = sum(r["lucro"] for r in linhas)
    pontos_roi = curva_roi_acumulado(linhas)
    agora = datetime.now(timezone.utc).strftime("%d/%m/%Y, %H:%M UTC")

    linhas_tipo_html = "".join(f"""
    <tr>
      <td>{g['tipo']}</td>
      <td class="num">{g['n']}</td>
      <td class="num"><span class="pill-mini green">{g['greens']}G</span> <span class="pill-mini red">{g['reds']}R</span></td>
      <td class="num">{g['taxa_pct']:.1f}%</td>
      <td class="num {'pos' if g['roi_pct'] >= 0 else 'neg'}">{g['roi_pct']:+.1f}%</td>
    </tr>""" for g in resumo_tipos) or '<tr><td colspan="5" class="vazio-linha">sem sinais fechados ainda</td></tr>'

    linhas_historico_html = "".join(f"""
    <tr>
      <td class="mono">{r['data_jogo']}</td>
      <td>{r['jogo']}<span class="liga-inline">{r['liga']}</span></td>
      <td>{r['tipo_aposta']} {float(r['linha']):g}</td>
      <td class="num">{float(r['probabilidade_estimada']):.1f}%</td>
      <td class="num mono">{r['odd_usada']:.2f}<span class="fonte-odd">{r['fonte_odd']}</span></td>
      <td class="num"><span class="pill-mini {r['resultado']}">{r['resultado']}</span></td>
      <td class="num {'pos' if r['lucro'] >= 0 else 'neg'}">{r['lucro']:+.2f}u</td>
    </tr>""" for r in reversed(linhas)) or '<tr><td colspan="7" class="vazio-linha">sem sinais fechados ainda</td></tr>'

    sparkline_html = _svg_sparkline(pontos_roi) if len(pontos_roi) >= 2 else '<div class="spark-vazio">precisa de 2+ sinais fechados pra desenhar a curva</div>'

    return f"""<title>Assertividade ao Vivo</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap');

  :root {{
    --bg: #0a0c0f; --surface: #12151a; --surface-alt: #161a20; --border: #232a33;
    --text: #e4e7eb; --muted: #7c8592; --faint: #4d5560;
    --brand: #4f8cff; --brand-tint: rgba(79,140,255,0.12);
    --good: #35d68a; --good-tint: rgba(53,214,138,0.12);
    --bad: #ff5c5c; --bad-tint: rgba(255,92,92,0.12);
    --neutral: #f0a93b;
    --mono: 'IBM Plex Mono', ui-monospace, monospace;
    --sans: 'Inter', system-ui, sans-serif;
    --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 8px 24px -10px rgba(0,0,0,0.55);
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--text); font-family: var(--sans); -webkit-font-smoothing: antialiased; }}
  .page {{ max-width: 1080px; margin: 0 auto; padding: 2.25rem 1.5rem 4rem; }}

  .masthead {{ display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem; flex-wrap: wrap; border-bottom: 1px solid var(--border); padding-bottom: 1.1rem; margin-bottom: 1.75rem; }}
  .masthead h1 {{ font-size: clamp(1.7rem, 4vw, 2.3rem); font-weight: 800; letter-spacing: -0.01em; margin: 0; text-wrap: balance; }}
  .masthead .brand-dot {{ color: var(--brand); }}
  .masthead .sub {{ font-family: var(--mono); font-size: 0.78rem; color: var(--muted); text-align: right; line-height: 1.6; }}
  .masthead .sub b {{ color: var(--text); font-weight: 600; }}

  .kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 0.9rem; margin-bottom: 1.75rem; }}
  .kpi {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 1rem 1.1rem; box-shadow: var(--shadow); }}
  .kpi .label {{ font-family: var(--mono); font-size: 0.66rem; color: var(--faint); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem; }}
  .kpi .valor {{ font-family: var(--mono); font-size: 1.6rem; font-weight: 600; font-variant-numeric: tabular-nums; line-height: 1; }}
  .kpi .valor.pos {{ color: var(--good); }}
  .kpi .valor.neg {{ color: var(--bad); }}
  .kpi .nota {{ font-size: 0.72rem; color: var(--faint); margin-top: 0.35rem; }}

  .painel-spark {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 1.1rem 1.25rem; box-shadow: var(--shadow); margin-bottom: 2.25rem; }}
  .painel-spark .titulo {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 0.6rem; }}
  .painel-spark h3 {{ font-size: 0.92rem; font-weight: 600; margin: 0; }}
  .painel-spark .valor-final {{ font-family: var(--mono); font-size: 0.85rem; font-weight: 600; }}
  .roi-spark {{ width: 100%; height: 100px; display: block; }}
  .spark-zero {{ stroke: var(--border); stroke-width: 1; stroke-dasharray: 3 3; }}
  .spark-vazio {{ color: var(--faint); font-size: 0.82rem; padding: 1.5rem 0; text-align: center; }}

  .secao-titulo {{ display: flex; align-items: baseline; gap: 0.6rem; margin: 0 0 0.9rem; }}
  .secao-titulo:not(:first-of-type) {{ margin-top: 2.25rem; }}
  .secao-titulo h2 {{ font-size: 1.15rem; font-weight: 700; margin: 0; }}
  .secao-titulo .contagem {{ font-family: var(--mono); font-size: 0.78rem; color: var(--faint); }}

  .tabela-wrap {{ overflow-x: auto; background: var(--surface); border: 1px solid var(--border); border-radius: 10px; box-shadow: var(--shadow); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; min-width: 560px; }}
  th {{ text-align: left; font-family: var(--mono); font-size: 0.64rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--faint); font-weight: 500; padding: 0.7rem 0.9rem; border-bottom: 1px solid var(--border); background: var(--surface-alt); position: sticky; top: 0; }}
  td {{ padding: 0.65rem 0.9rem; border-bottom: 1px solid var(--border); vertical-align: middle; }}
  tr:last-child td {{ border-bottom: none; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  td.mono {{ font-family: var(--mono); color: var(--muted); }}
  td.pos {{ color: var(--good); font-family: var(--mono); font-weight: 600; }}
  td.neg {{ color: var(--bad); font-family: var(--mono); font-weight: 600; }}
  .liga-inline {{ display: block; font-size: 0.72rem; color: var(--faint); margin-top: 0.15rem; }}
  .fonte-odd {{ display: block; font-size: 0.62rem; color: var(--faint); text-transform: uppercase; letter-spacing: 0.03em; }}
  .vazio-linha {{ text-align: center; color: var(--faint); padding: 1.5rem; }}

  .pill-mini {{ font-family: var(--mono); font-size: 0.68rem; font-weight: 700; letter-spacing: 0.02em; padding: 0.12rem 0.45rem; border-radius: 999px; white-space: nowrap; }}
  .pill-mini.green {{ background: var(--good-tint); color: var(--good); }}
  .pill-mini.red {{ background: var(--bad-tint); color: var(--bad); }}

  footer {{ margin-top: 3rem; padding-top: 1.25rem; border-top: 1px solid var(--border); font-family: var(--mono); font-size: 0.72rem; color: var(--faint); line-height: 1.8; }}

  @media (max-width: 560px) {{
    .masthead {{ flex-direction: column; align-items: flex-start; }}
    .masthead .sub {{ text-align: left; }}
  }}
</style>

<div class="page">
  <div class="masthead">
    <h1>Assertividade <span class="brand-dot">ao vivo</span></h1>
    <div class="sub">Atualizado <b>{agora}</b><br>Escanteios · Chutes totais · Chutes no alvo · Gols — todas as ligas monitoradas</div>
  </div>

  <div class="kpis">
    <div class="kpi">
      <div class="label">ROI (stake fixo 1u)</div>
      <div class="valor {'pos' if roi_total_pct >= 0 else 'neg'}">{roi_total_pct:+.1f}%</div>
      <div class="nota">{lucro_total_un:+.2f}u em {n_total} entrada{'s' if n_total != 1 else ''}</div>
    </div>
    <div class="kpi">
      <div class="label">Entradas fechadas</div>
      <div class="valor">{n_total}</div>
    </div>
    <div class="kpi">
      <div class="label">Green</div>
      <div class="valor pos">{greens_total}</div>
    </div>
    <div class="kpi">
      <div class="label">Red</div>
      <div class="valor neg">{reds_total}</div>
    </div>
  </div>

  <div class="painel-spark">
    <div class="titulo">
      <h3>ROI acumulado (unidades, ordem cronológica)</h3>
      <span class="valor-final {'pos' if lucro_total_un >= 0 else 'neg'}">{lucro_total_un:+.2f}u</span>
    </div>
    {sparkline_html}
  </div>

  <div class="secao-titulo">
    <h2>Por tipo de aposta</h2>
    <span class="contagem">{len(resumo_tipos)} tipos</span>
  </div>
  <div class="tabela-wrap">
    <table>
      <thead><tr><th>Tipo</th><th class="num">N</th><th class="num">G / R</th><th class="num">Taxa</th><th class="num">ROI</th></tr></thead>
      <tbody>{linhas_tipo_html}</tbody>
    </table>
  </div>

  <div class="secao-titulo">
    <h2>Histórico completo</h2>
    <span class="contagem">{n_total} sinal{'is' if n_total != 1 else ''} fechado{'s' if n_total != 1 else ''}, mais recente primeiro</span>
  </div>
  <div class="tabela-wrap">
    <table>
      <thead><tr><th>Data</th><th>Jogo</th><th>Mercado</th><th class="num">Prob. est.</th><th class="num">Odd usada</th><th class="num">Resultado</th><th class="num">Lucro</th></tr></thead>
      <tbody>{linhas_historico_html}</tbody>
    </table>
  </div>

  <footer>
    Stake fixo de 1 unidade em toda entrada · Odd usada = odd real ao vivo da casa de apostas quando encontrada no momento do sinal, senão odd mínima sintética (1 / probabilidade estimada da amostra histórica) — a origem de cada odd aparece embaixo dela na tabela.<br>
    Fonte: ligas_live_app/historico_sinais.csv, atualizado diariamente pela rotina de checagem de sinais. Este painel é só uma camada de leitura agregada — o histórico linha a linha completo continua sendo mantido no CSV pelas rotinas, independente deste painel existir.
  </footer>
</div>
"""


if __name__ == "__main__":
    html = gerar_html()
    with open(CAMINHO_SAIDA, "w", encoding="utf-8") as fp:
        fp.write(html)
    print(f"gerado em {CAMINHO_SAIDA}")
