"""Gera `painel.html` (o painel diário publicado como Artifact) a
partir das sugestões do dia (`previsao_dia.gerar_sugestoes_do_dia`).

Uso: `python3 gerar_painel_dia.py [caminho_saida]`
(default: `painel_dia.html` no diretório atual)

Não publica sozinho — quem chama isso (a rotina diária) precisa
republicar o HTML gerado usando a ferramenta Artifact, passando a
mesma URL do painel já existente (pra manter o link fixo que o Lucas
salvou).
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

from previsao_dia import gerar_sugestoes_do_dia

FUSO_BRASIL = timezone(timedelta(hours=-3))

CRITERIOS_INFO = [
    dict(nome="BTTS", stake="cheio", stake_label="stake normal", evidencia="Série A · z=+2,33 · sem ano negativo"),
    dict(nome="Over 2.5", stake="reduzido", stake_label="stake reduzido", evidencia="Série A · holdout 2026 z=+2,83 (n=23)"),
    dict(nome="Cartões + Árbitro", stake="reduzido", stake_label="stake reduzido", evidencia="Série B · z≈+1,73 · positivo nos 3 anos"),
]

_NOME_LADO = {"btts": "BTTS · Sim", "over25": "Over 2.5"}


def _fmt_data_hora(data_iso):
    dt_utc = datetime.strptime(data_iso[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    dt_local = dt_utc.astimezone(FUSO_BRASIL)
    return dt_local.strftime("%d/%m, %H:%M")


def _card_html(s):
    lado = _NOME_LADO.get(s["lado"], s["lado"])
    stake_classe = "cheio" if s["stake"] == "normal" else "reduzido"
    stake_texto = "stake normal" if s["stake"] == "normal" else "stake reduzido"
    return f"""
    <div class="jogo-card">
      <div class="confronto">{s['jogo']}</div>
      <div class="meta"><span class="liga-tag">{s['liga']}</span> {_fmt_data_hora(s['data'])} BRT</div>
      <div class="aposta">
        <span class="lado">{lado}</span>
        <span class="odd-edge"><span class="odd">{s['odd']:.2f}</span><span class="edge">+{s['edge']*100:.1f}% edge</span></span>
        <span class="stake-tag stake {stake_classe}">{stake_texto}</span>
      </div>
    </div>"""


def _criterio_chip_html(c):
    return f"""
    <div class="criterio-chip">
      <div class="linha1"><span class="nome">{c['nome']}</span><span class="stake {c['stake']}">{c['stake_label']}</span></div>
      <div class="evidencia">{c['evidencia']}</div>
    </div>"""


TEMPLATE = """<title>Painel Brasileirão</title>

<style>
  @import url('https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@600;700;800&family=Karla:ital,wght@0,400;0,500;0,700;1,400&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

  :root {{
    --bg: #f5f6f1; --surface: #ffffff; --surface-sunken: #edefe8; --border: #dbdfd3;
    --text: #131b16; --text-muted: #5c665e; --text-faint: #8b9389;
    --accent: #1f6f4a; --accent-tint: #e4f0e8; --accent-strong: #14512f;
    --amber: #a56312; --amber-tint: #f7ecdc;
    --shadow: 0 1px 2px rgba(19, 27, 22, 0.04), 0 6px 20px -8px rgba(19, 27, 22, 0.12);
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg: #0e1512; --surface: #161f1a; --surface-sunken: #101713; --border: #263229;
      --text: #e9ede7; --text-muted: #9aa79d; --text-faint: #6c766e;
      --accent: #45b17f; --accent-tint: #17281f; --accent-strong: #6fd6a3;
      --amber: #d99a3f; --amber-tint: #2a2214;
      --shadow: 0 1px 2px rgba(0, 0, 0, 0.3), 0 6px 24px -8px rgba(0, 0, 0, 0.5);
    }}
  }}
  :root[data-theme="dark"] {{
    --bg: #0e1512; --surface: #161f1a; --surface-sunken: #101713; --border: #263229;
    --text: #e9ede7; --text-muted: #9aa79d; --text-faint: #6c766e;
    --accent: #45b17f; --accent-tint: #17281f; --accent-strong: #6fd6a3;
    --amber: #d99a3f; --amber-tint: #2a2214;
    --shadow: 0 1px 2px rgba(0, 0, 0, 0.3), 0 6px 24px -8px rgba(0, 0, 0, 0.5);
  }}

  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--text); font-family: 'Karla', system-ui, -apple-system, sans-serif; -webkit-font-smoothing: antialiased; }}
  .page {{ max-width: 900px; margin: 0 auto; padding: 2.5rem 1.5rem 4rem; }}
  h1, h2 {{ text-wrap: balance; font-family: 'Big Shoulders Display', system-ui, sans-serif; margin: 0; }}

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

  .secao-titulo {{ display: flex; align-items: baseline; gap: 0.6rem; margin: 2.25rem 0 0.9rem; }}
  .secao-titulo h2 {{ font-size: 1.5rem; font-weight: 700; }}
  .secao-titulo .contagem {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.85rem; color: var(--text-faint); }}

  .jogos {{ display: flex; flex-direction: column; gap: 0.7rem; }}
  .jogo-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 1rem 1.15rem; box-shadow: var(--shadow); display: grid; grid-template-columns: 1fr auto; gap: 0.4rem 1rem; align-items: center; }}
  .jogo-card .confronto {{ font-weight: 700; font-size: 1.05rem; }}
  .jogo-card .meta {{ grid-column: 1; display: flex; gap: 0.6rem; align-items: center; font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem; color: var(--text-muted); }}
  .liga-tag {{ background: var(--surface-sunken); border-radius: 5px; padding: 0.1rem 0.45rem; color: var(--text-muted); font-weight: 500; }}
  .aposta {{ grid-column: 2; grid-row: 1 / 3; text-align: right; display: flex; flex-direction: column; align-items: flex-end; gap: 0.25rem; min-width: 132px; }}
  .aposta .lado {{ font-weight: 700; font-size: 0.92rem; }}
  .aposta .odd-edge {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.82rem; display: flex; gap: 0.5rem; align-items: baseline; font-variant-numeric: tabular-nums; }}
  .aposta .odd {{ color: var(--text); font-weight: 600; }}
  .aposta .edge {{ color: var(--accent-strong); }}
  .aposta .stake-tag {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.04em; padding: 0.1rem 0.4rem; border-radius: 999px; }}

  .vazio {{ background: var(--surface); border: 1px dashed var(--border); border-radius: 12px; padding: 1.5rem; text-align: center; color: var(--text-muted); font-size: 0.9rem; }}

  footer {{ margin-top: 3rem; padding-top: 1.25rem; border-top: 1px solid var(--border); font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem; color: var(--text-faint); line-height: 1.7; }}

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

  <div class="secao-titulo">
    <h2>Jogos qualificados</h2>
    <span class="contagem">{n_sugestoes} sugest{plural_sugestao}</span>
  </div>

  <div class="jogos">{jogos_html}
  </div>

  <footer>
    Odd = odd real média do mercado (Sportmonks) no momento da checagem · Edge = probabilidade do modelo − probabilidade implícita do mercado.<br>
    Metodologia validada em <code>docs/protocolo.md</code> (repo Bet) · dado 100% Sportmonks, sem FootyStats.
  </footer>
</div>
"""


def gerar_html(sugestoes, dias_a_frente):
    agora_brt = datetime.now(timezone.utc).astimezone(FUSO_BRASIL)
    if sugestoes:
        sugestoes_ordenadas = sorted(sugestoes, key=lambda s: s["data"])
        jogos_html = "".join(_card_html(s) for s in sugestoes_ordenadas)
    else:
        jogos_html = '\n    <div class="vazio">Nenhum jogo qualificado nos próximos dias — normal, os critérios são seletivos por design.</div>'
    return TEMPLATE.format(
        atualizado_em=agora_brt.strftime("%d/%m/%Y, %H:%M"),
        dias_a_frente=dias_a_frente,
        criterios_html="".join(_criterio_chip_html(c) for c in CRITERIOS_INFO),
        n_sugestoes=len(sugestoes),
        plural_sugestao="ão" if len(sugestoes) == 1 else "ões",
        jogos_html=jogos_html,
    )


if __name__ == "__main__":
    caminho_saida = sys.argv[1] if len(sys.argv) > 1 else "painel_dia.html"
    dias_a_frente = 3
    sugestoes = gerar_sugestoes_do_dia(dias_a_frente=dias_a_frente)
    html = gerar_html(sugestoes, dias_a_frente)
    with open(caminho_saida, "w") as f:
        f.write(html)
    print(f"{len(sugestoes)} sugestões — painel salvo em {caminho_saida}", flush=True)
