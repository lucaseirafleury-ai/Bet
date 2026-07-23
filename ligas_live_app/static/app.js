const $ = (sel) => document.querySelector(sel);

async function getJSON(url) {
  const r = await fetch(url);
  return r.json();
}

function renderPrelive(data) {
  const lista = $("#prelive-lista");
  const relatorios = data.relatorios || [];
  $("#prelive-gerado-em").textContent = data.gerado_em ? `— gerado em ${data.gerado_em}` : "";

  if (relatorios.length === 0) {
    lista.innerHTML = `<p class="empty-state">Nenhuma análise pré-live ainda.</p>`;
    return;
  }

  lista.innerHTML = relatorios.map((r) => `
    <div class="match-card">
      <div class="liga-tag">${r.liga}</div>
      <div class="times">${r.home} <span style="color:var(--muted)">x</span> ${r.away}</div>
      <div class="placar-modal">${r.placar_modal} <span style="font-size:12px;color:var(--muted);font-weight:400">(${r.placar_modal_prob_pct}%)</span></div>
      <div class="grid-info">
        <div class="label">Favorito posse</div><div class="value">${r.favorito_posse}</div>
        <div class="label">Favorito pressão</div><div class="value">${r.favorito_pressao}</div>
        <div class="label">Favorito xG</div><div class="value">${r.favorito_xg}</div>
        <div class="label">Início (UTC)</div><div class="value">${r.data_hora_utc || "?"}</div>
      </div>
    </div>
  `).join("");
}

function classeDivergencia(v) {
  if (v > 0.3) return "divergencia-pos";
  if (v < -0.3) return "divergencia-neg";
  return "divergencia-neutro";
}

function classeComparacao(oddDigitada, oddMinima) {
  if (isNaN(oddDigitada) || oddDigitada <= 1) return "";
  return oddDigitada >= oddMinima ? "comparacao-favoravel" : "comparacao-desfavoravel";
}

function compararOdd(fixtureId, mercado, oddMinima) {
  const input = document.getElementById(`odd-${fixtureId}-${mercado}`);
  const badge = document.getElementById(`badge-${fixtureId}-${mercado}`);
  const odd = parseFloat(input.value.replace(",", "."));
  if (!odd || odd <= 1) {
    badge.textContent = "";
    badge.className = "comparacao-badge";
    return;
  }
  if (odd >= oddMinima) {
    badge.textContent = "✓ vale a entrada";
    badge.className = "comparacao-badge comparacao-favoravel";
  } else {
    badge.textContent = "✗ abaixo do mínimo";
    badge.className = "comparacao-badge comparacao-desfavoravel";
  }
}

function rotuloOverUnder(fonte) {
  if (fonte === "calibrado_somente_minuto") {
    return { texto: " ⚠ só relógio — sem edge informacional", classe: "tag-sem-edge" };
  }
  if (fonte && fonte.startsWith("calibrado_")) {
    return { texto: " ✓ calibrado", classe: "tag-calibrado" };
  }
  return { texto: "", classe: "" };
}

function linhaValor(fixtureId, mercado, label, prob) {
  const margem = window.MARGEM_VALOR ?? 0.05;
  const oddMinima = prob > 0 ? ((1 + margem) / prob).toFixed(2) : "—";
  const probPct = (prob * 100).toFixed(1);
  return `
    <div class="valor-row">
      <div class="valor-info">
        <span class="valor-label">${label}</span>
        <span class="valor-prob">nosso modelo: ${probPct}%</span>
      </div>
      <div class="odd-minima">${oddMinima}</div>
      <input type="text" id="odd-${fixtureId}-${mercado}" class="odd-input" placeholder="odd real"
             oninput="compararOdd(${fixtureId}, '${mercado}', ${oddMinima})">
      <span id="badge-${fixtureId}-${mercado}" class="comparacao-badge"></span>
    </div>
  `;
}

function renderLive(snapshots) {
  const lista = $("#live-lista");
  const jogos = Object.values(snapshots || {});

  if (jogos.length === 0) {
    lista.innerHTML = `<p class="empty-state">Nenhum jogo ao vivo monitorado no momento.</p>`;
    return;
  }

  lista.innerHTML = jogos.map((j) => {
    const p = j.probabilidades || {};
    const sc = j.stats_completas_home || {};
    const sa = j.stats_completas_away || {};

    return `
    <div class="live-card">
      <div class="live-header">
        <span class="liga-tag">${j.liga}</span>
        <span class="minuto-tag">min ${j.minuto}</span>
      </div>
      <div class="placar-atual">${j.gols_home} - ${j.gols_away}</div>
      <div class="times-row"><span>${j.home} <span style="color:var(--muted)">x</span> ${j.away}</span><span style="color:var(--muted)">esperado pré-live: ${j.placar_modal_prelive}</span></div>

      <div class="momentum-wrap">
        <div class="momentum-label"><span>${j.momentum_home}%</span><span>MOMENTUM</span><span>${j.momentum_away}%</span></div>
        <div class="momentum-bar">
          <div class="momentum-fill-home" style="width:${j.momentum_home}%"></div>
          <div class="momentum-fill-away" style="width:${j.momentum_away}%"></div>
        </div>
      </div>

      <div class="ajuste-lambda-wrap">
        <span class="ajuste-item">lambda casa: <b class="${j.ajuste_lambda_home >= 1 ? 'ajuste-alta' : 'ajuste-baixa'}">×${j.ajuste_lambda_home}</b></span>
        <span class="ajuste-item">lambda fora: <b class="${j.ajuste_lambda_away >= 1 ? 'ajuste-alta' : 'ajuste-baixa'}">×${j.ajuste_lambda_away}</b></span>
      </div>

      <table class="stat-table">
        <tr><th class="label-col"></th><th>${j.home.slice(0,10)}</th><th>${j.away.slice(0,10)}</th></tr>
        <tr><td class="label-col">xG_proxy acumulado</td><td>${j.xg_proxy_home}</td><td>${j.xg_proxy_away}</td></tr>
        <tr>
          <td class="label-col">xG − Gols</td>
          <td class="${classeDivergencia(j.divergencia_xg_gols_home)}">${j.divergencia_xg_gols_home > 0 ? "+" : ""}${j.divergencia_xg_gols_home}</td>
          <td class="${classeDivergencia(j.divergencia_xg_gols_away)}">${j.divergencia_xg_gols_away > 0 ? "+" : ""}${j.divergencia_xg_gols_away}</td>
        </tr>
        <tr><td class="label-col">Posse</td><td>${sc.posse ?? "—"}%</td><td>${sa.posse ?? "—"}%</td></tr>
        <tr><td class="label-col">Finalizações (no alvo)</td><td>${sc.finalizacoes ?? "—"} (${sc.chutes_no_alvo ?? "—"})</td><td>${sa.finalizacoes ?? "—"} (${sa.chutes_no_alvo ?? "—"})</td></tr>
        <tr><td class="label-col">Escanteios</td><td>${j.escanteios_home}</td><td>${j.escanteios_away}</td></tr>
        <tr><td class="label-col">Faltas</td><td>${sc.faltas ?? "—"}</td><td>${sa.faltas ?? "—"}</td></tr>
        <tr><td class="label-col">Impedimentos</td><td>${sc.impedimentos ?? "—"}</td><td>${sa.impedimentos ?? "—"}</td></tr>
        <tr><td class="label-col">Cartões</td><td>${j.cartoes_home}</td><td>${j.cartoes_away}</td></tr>
        <tr><td class="label-col">Passes (%)</td><td>${sc.passes_totais ?? "—"} (${sc.passes_certos ?? "—"}%)</td><td>${sa.passes_totais ?? "—"} (${sa.passes_certos ?? "—"}%)</td></tr>
        <tr><td class="label-col">Defesas</td><td>${sc.defesas ?? "—"}</td><td>${sa.defesas ?? "—"}</td></tr>
        <tr><td class="label-col">Eficiência de finalização</td><td>${j.eficiencia_home != null ? j.eficiencia_home + "%" : "—"}</td><td>${j.eficiencia_away != null ? j.eficiencia_away + "%" : "—"}</td></tr>
      </table>

      <div class="valor-box">
        <div class="valor-titulo">Odd mínima para valer a entrada (margem ${((window.MARGEM_VALOR ?? 0.05) * 100).toFixed(0)}%)</div>
        ${linhaValor(j.fixture_id, "casa", `Vitória ${j.home}`, p.prob_casa)}
        ${linhaValor(j.fixture_id, "empate", "Empate", p.prob_empate)}
        ${linhaValor(j.fixture_id, "fora", `Vitória ${j.away}`, p.prob_fora)}
        ${linhaValor(j.fixture_id, "over25", `Over 2.5 gols<span class="${rotuloOverUnder(p.over_under_fonte).classe}">${rotuloOverUnder(p.over_under_fonte).texto}</span>`, p.prob_over25)}
        ${linhaValor(j.fixture_id, "under25", `Under 2.5 gols<span class="${rotuloOverUnder(p.over_under_fonte).classe}">${rotuloOverUnder(p.over_under_fonte).texto}</span>`, p.prob_under25)}
        ${linhaValor(j.fixture_id, "bttssim", "Ambas marcam - Sim", p.prob_btts_sim)}
        ${linhaValor(j.fixture_id, "bttsnao", "Ambas marcam - Não", p.prob_btts_nao)}
      </div>

      <div class="valor-box">
        <div class="valor-titulo">
          Escanteios — linha ${p.linha_escanteios ?? "9.5"}
          <span class="aviso-confianca">confiança menor, não calibrado ainda</span>
        </div>
        ${linhaValor(j.fixture_id, "over_esc", `Over ${p.linha_escanteios ?? "9.5"}`, p.prob_over_escanteios)}
        ${linhaValor(j.fixture_id, "under_esc", `Under ${p.linha_escanteios ?? "9.5"}`, p.prob_under_escanteios)}
      </div>
    </div>
  `;
  }).join("");
}

function renderInsights(lista) {
  const feed = $("#insights-feed");
  if (!lista || lista.length === 0) {
    feed.innerHTML = `<p class="empty-state">Nenhum sinal gerado ainda.</p>`;
    return;
  }
  feed.innerHTML = lista.map((i) => {
    const dirClass = i.delta_pct >= 0 ? "delta-up" : "delta-down";
    const seta = i.delta_pct >= 0 ? "▲" : "▼";
    return `
      <div class="insight-item ${dirClass}">
        <div class="jogo">${i.jogo} <span style="color:var(--muted);font-weight:400">— ${i.liga}</span></div>
        <div class="msg"><span class="delta-tag">${seta} ${Math.abs(i.delta_pct)}%</span>${i.mensagem}</div>
      </div>
    `;
  }).join("");
}

function renderStatus(status) {
  const pill = $("#relogio-status");
  if (status.monitor_ativo) {
    pill.textContent = "monitor: ativo";
    pill.className = "status-pill status-on";
  } else {
    pill.textContent = "monitor: parado";
    pill.className = "status-pill status-off";
  }
}

async function atualizarTudo() {
  const [prelive, insights, status, liveSnapshots] = await Promise.all([
    getJSON("/api/prelive"),
    getJSON("/api/insights"),
    getJSON("/api/status"),
    getJSON("/api/live-snapshots"),
  ]);
  renderPrelive(prelive);
  renderInsights(insights);
  renderStatus(status);
  renderLive(liveSnapshots);
}

atualizarTudo();
setInterval(atualizarTudo, 15000); // atualiza a cada 15s
