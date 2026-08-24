const $ = (sel) => document.querySelector(sel);

async function getJSON(url) {
  const r = await fetch(url);
  return r.json();
}

function dataHoraBrasilia(dataHoraUtc) {
  if (!dataHoraUtc) return "?";
  const iso = dataHoraUtc.replace(" ", "T") + "Z";
  const d = new Date(iso);
  if (isNaN(d)) return "?";
  return d.toLocaleString("pt-BR", {
    timeZone: "America/Sao_Paulo",
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
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
      <div class="horario-jogo">${dataHoraBrasilia(r.data_hora_utc)} (Brasília)</div>
    </div>
  `).join("");
}

function classeDivergencia(v) {
  if (v > 0.3) return "divergencia-pos";
  if (v < -0.3) return "divergencia-neg";
  return "divergencia-neutro";
}

function classeSituacao(comp) {
  if (!comp || comp.situacao === "equilibrado") return "situacao-equilibrado";
  const base = comp.situacao === "acima" ? "situacao-acima" : "situacao-abaixo";
  return comp.forte ? `${base} situacao-forte` : base;
}

function rotuloSituacao(comp) {
  if (!comp || comp.situacao === "equilibrado") return "≈ equilibrado";
  const seta = comp.situacao === "acima" ? "▲" : "▼";
  return `${seta} ${comp.situacao} do esperado`;
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

function linhaValor(label, prob, comp) {
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
      <span class="situacao-badge ${classeSituacao(comp)}">${rotuloSituacao(comp)}</span>
    </div>
  `;
}

const cardsExpandidos = new Set();

function toggleCard(fixtureId) {
  const estavaExpandido = cardsExpandidos.has(fixtureId);
  if (estavaExpandido) {
    cardsExpandidos.delete(fixtureId);
  } else {
    cardsExpandidos.add(fixtureId);
  }
  const detalhes = document.getElementById(`detalhes-${fixtureId}`);
  const chevron = document.getElementById(`chevron-${fixtureId}`);
  if (detalhes) detalhes.style.display = estavaExpandido ? "none" : "block";
  if (chevron) chevron.textContent = estavaExpandido ? "▼ expandir" : "▲ recolher";
}

const sinaisExpandidos = new Set();

function toggleSinal(chave) {
  const estavaExpandido = sinaisExpandidos.has(chave);
  if (estavaExpandido) {
    sinaisExpandidos.delete(chave);
  } else {
    sinaisExpandidos.add(chave);
  }
  const detalhe = document.getElementById(`sinal-detalhe-${chave}`);
  const chevron = document.getElementById(`sinal-chevron-${chave}`);
  if (detalhe) detalhe.style.display = estavaExpandido ? "none" : "block";
  if (chevron) chevron.textContent = estavaExpandido ? "▼ detalhes" : "▲ ocultar";
}

// Sinais confirmados por pesquisa cross-liga (tipo "regra_*") vêm com
// resumo/odd_minima próprios — mostra só isso fechado, com o texto completo
// (condição, amostra, p-valor) atrás de um "▼ detalhes". Os demais sinais
// (ex: ritmo de gols) continuam com o texto completo sempre visível, como já
// era antes de existir esse tipo de sinal.
function htmlSinalItem(i, { mostrarJogo }) {
  const dirClass = i.delta_pct >= 0 ? "delta-up" : "delta-down";
  const seta = i.delta_pct >= 0 ? "▲" : "▼";
  const jogoHtml = mostrarJogo
    ? `<div class="jogo">${i.jogo} <span style="color:var(--muted);font-weight:400">— ${i.liga}</span><span class="horario-emissao">${horarioBrasilia(i.timestamp)} (Brasília)</span></div>`
    : "";

  const ehSinalConfirmado = i.resumo != null;
  if (!ehSinalConfirmado) {
    return `
      <div class="insight-item ${dirClass}">
        ${jogoHtml}
        <div class="msg"><span class="delta-tag">${seta} ${Math.abs(i.delta_pct)}${unidadeDelta(i)}</span>${i.mensagem}</div>
      </div>
    `;
  }

  const chave = `${i.fixture_id}-${i.tipo}`;
  const expandido = sinaisExpandidos.has(chave);
  return `
    <div class="insight-item ${dirClass} sinal-compacto">
      ${jogoHtml}
      <div class="sinal-resumo-row" onclick="toggleSinal('${chave}')">
        <span class="delta-tag">${seta} ${i.resumo}</span>
        ${i.probabilidade != null ? `<span class="odd-min-tag">${i.probabilidade.toFixed(1)}%</span>` : ""}
        ${i.odd_minima != null ? `<span class="odd-min-tag">odd mín. ${i.odd_minima.toFixed(2)}</span>` : ""}
        <span id="sinal-chevron-${chave}" class="chevron-link">${expandido ? "▲ ocultar" : "▼ detalhes"}</span>
      </div>
      <div id="sinal-detalhe-${chave}" class="msg" style="display:${expandido ? "block" : "none"}">${i.mensagem}</div>
    </div>
  `;
}

function unidadeDelta(insight) {
  // Sinais confirmados por pesquisa cross-liga (identificados pelo campo
  // "resumo", que só eles têm) reportam impacto em pontos percentuais
  // (p.p.), não desvio percentual relativo como o sinal de ritmo de gols —
  // unidades diferentes, rótulo diferente. Checa o campo em si, não um
  // prefixo de "tipo" (que já mudou uma vez — regra_* virou sinal_*).
  return insight.resumo != null ? "p.p." : "%";
}

function badgeSinalCard(fixtureId, insights) {
  const doJogo = (insights || []).filter((i) => i.fixture_id === fixtureId);
  if (doJogo.length === 0) return "";
  const temPositivo = doJogo.some((i) => i.delta_pct >= 0);
  const temNegativo = doJogo.some((i) => i.delta_pct < 0);
  let classe = "badge-sinal-neutro";
  let seta = "⚡";
  if (temPositivo && !temNegativo) { classe = "badge-sinal-pos"; seta = "▲"; }
  else if (temNegativo && !temPositivo) { classe = "badge-sinal-neg"; seta = "▼"; }
  const plural = doJogo.length > 1 ? "is" : "";
  return `<span class="badge-sinal-card ${classe}">${seta} ${doJogo.length} sinal${plural}</span>`;
}

function renderLive(snapshots, insights) {
  const lista = $("#live-lista");
  const jogos = Object.values(snapshots || {});

  if (jogos.length === 0) {
    lista.innerHTML = `<p class="empty-state">Nenhum jogo ao vivo monitorado no momento.</p>`;
    return;
  }

  lista.innerHTML = jogos.map((j) => {
    const p = j.probabilidades || {};
    const comp = p.comparacao || {};
    const sc = j.stats_completas_home || {};
    const sa = j.stats_completas_away || {};
    const expandido = cardsExpandidos.has(j.fixture_id);

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

      <div class="live-card-toggle" onclick="toggleCard(${j.fixture_id})">
        ${badgeSinalCard(j.fixture_id, insights)}
        <span id="chevron-${j.fixture_id}" class="chevron-link">${expandido ? "▲ recolher" : "▼ expandir"}</span>
      </div>

      <div id="detalhes-${j.fixture_id}" class="live-card-detalhes" style="display:${expandido ? "block" : "none"}">
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
          ${linhaValor(`Vitória ${j.home}`, p.prob_casa, comp.prob_casa)}
          ${linhaValor("Empate", p.prob_empate, comp.prob_empate)}
          ${linhaValor(`Vitória ${j.away}`, p.prob_fora, comp.prob_fora)}
          ${linhaValor(`Over 2.5 gols<span class="${rotuloOverUnder(p.over_under_fonte).classe}">${rotuloOverUnder(p.over_under_fonte).texto}</span>`, p.prob_over25, comp.prob_over25)}
          ${linhaValor(`Under 2.5 gols<span class="${rotuloOverUnder(p.over_under_fonte).classe}">${rotuloOverUnder(p.over_under_fonte).texto}</span>`, p.prob_under25, comp.prob_under25)}
          ${linhaValor("Ambas marcam - Sim", p.prob_btts_sim, comp.prob_btts_sim)}
          ${linhaValor("Ambas marcam - Não", p.prob_btts_nao, comp.prob_btts_nao)}
        </div>

        <div class="valor-box">
          <div class="valor-titulo">
            Escanteios — linha ${p.linha_escanteios ?? "9.5"}
            <span class="aviso-confianca">confiança menor, não calibrado ainda</span>
          </div>
          ${linhaValor(`Over ${p.linha_escanteios ?? "9.5"}`, p.prob_over_escanteios, comp.prob_over_escanteios)}
          ${linhaValor(`Under ${p.linha_escanteios ?? "9.5"}`, p.prob_under_escanteios, comp.prob_under_escanteios)}
        </div>
      </div>
    </div>
  `;
  }).join("");
}

function horarioBrasilia(isoString) {
  if (!isoString) return "";
  return new Date(isoString).toLocaleTimeString("pt-BR", {
    timeZone: "America/Sao_Paulo",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function dataHoraBrasiliaCompleta(isoString) {
  if (!isoString) return "";
  return new Date(isoString).toLocaleString("pt-BR", {
    timeZone: "America/Sao_Paulo",
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function renderJogosAnteriores(lista) {
  const container = $("#jogos-anteriores-lista");
  if (!lista || lista.length === 0) {
    container.innerHTML = `<p class="empty-state">Nenhum jogo encerrado ainda.</p>`;
    return;
  }

  container.innerHTML = lista.map((j) => {
    const sc = j.stats_completas_home || {};
    const sa = j.stats_completas_away || {};
    const chave = `ant-${j.fixture_id}`;
    const expandido = cardsExpandidos.has(chave);
    const sinais = j.sinais || [];
    const gols = (j.eventos_gols || []).length
      ? j.eventos_gols.map((g) => `${g.minuto_texto}' ${g.time}`).join(", ")
      : "sem gols";
    const sinaisHtml = sinais.length
      ? sinais.map((i) => htmlSinalItem(i, { mostrarJogo: false })).join("")
      : `<p class="empty-state">Nenhum sinal gerado nesse jogo.</p>`;

    return `
    <div class="live-card">
      <div class="live-header">
        <span class="liga-tag">${j.liga}</span>
        <span class="minuto-tag">encerrado — ${dataHoraBrasiliaCompleta(j.arquivado_em)}</span>
      </div>
      <div class="placar-atual">${j.gols_home} - ${j.gols_away}</div>
      <div class="times-row"><span>${j.home} <span style="color:var(--muted)">x</span> ${j.away}</span><span style="color:var(--muted)">esperado pré-live: ${j.placar_modal_prelive ?? "?"}</span></div>

      <div class="momentum-wrap">
        <div class="momentum-label"><span>${j.momentum_home}%</span><span>MOMENTUM</span><span>${j.momentum_away}%</span></div>
        <div class="momentum-bar">
          <div class="momentum-fill-home" style="width:${j.momentum_home}%"></div>
          <div class="momentum-fill-away" style="width:${j.momentum_away}%"></div>
        </div>
      </div>

      <div class="live-card-toggle" onclick="toggleCard('${chave}')">
        ${badgeSinalCard(j.fixture_id, sinais)}
        <span id="chevron-${chave}" class="chevron-link">${expandido ? "▲ recolher" : "▼ expandir"}</span>
      </div>

      <div id="detalhes-${chave}" class="live-card-detalhes" style="display:${expandido ? "block" : "none"}">
        <div class="valor-titulo" style="margin-top:4px">Gols</div>
        <div class="gols-lista">${gols}</div>

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

        <div class="valor-titulo" style="margin-top:12px">Sinais que dispararam nesse jogo</div>
        ${sinaisHtml}
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
  feed.innerHTML = lista.map((i) => htmlSinalItem(i, { mostrarJogo: true })).join("");
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
  const [prelive, insights, status, liveSnapshots, jogosAnteriores] = await Promise.all([
    getJSON("/api/prelive"),
    getJSON("/api/insights"),
    getJSON("/api/status"),
    getJSON("/api/live-snapshots"),
    getJSON("/api/jogos-anteriores"),
  ]);
  renderPrelive(prelive);
  renderInsights(insights);
  renderStatus(status);
  renderLive(liveSnapshots, insights);
  renderJogosAnteriores(jogosAnteriores);
}

atualizarTudo();
setInterval(atualizarTudo, 15000); // atualiza a cada 15s

// ── Notificações push (Web Push) ──────────────────────────────

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)));
}

function mostrarHintPush(msg) {
  const hint = $("#push-hint");
  hint.textContent = msg;
  hint.style.display = "block";
}

const emStandalone = window.navigator.standalone === true || window.matchMedia("(display-mode: standalone)").matches;

async function ativarPush() {
  const btn = $("#btn-ativar-push");

  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    mostrarHintPush("Este navegador não suporta notificações push. No iPhone, adicione o site à Tela de Início (compartilhar → \"Adicionar à Tela de Início\") e abra por lá antes de ativar.");
    return;
  }
  if (!emStandalone && /iP(hone|ad|od)/.test(navigator.userAgent)) {
    mostrarHintPush("No iPhone, primeiro adicione este site à Tela de Início (compartilhar → \"Adicionar à Tela de Início\"), abra o app por lá, e só então clique em Ativar notificações.");
    return;
  }

  try {
    const reg = await navigator.serviceWorker.register("/static/sw.js");
    const permissao = await Notification.requestPermission();
    if (permissao !== "granted") {
      mostrarHintPush("Permissão de notificação negada. Ative nas configurações do navegador/app pra receber os sinais.");
      return;
    }
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(window.VAPID_PUBLIC_KEY),
    });
    await fetch("/api/push-subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(sub),
    });
    btn.textContent = "🔔 Notificações ativas";
    btn.disabled = true;
  } catch (e) {
    mostrarHintPush("Não deu pra ativar as notificações: " + e.message);
  }
}

$("#btn-ativar-push").addEventListener("click", ativarPush);
