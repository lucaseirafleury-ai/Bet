# Decaimento mensal — critérios em produção (100% Sportmonks)

Checagem recorrente (rotina mensal) do ROI/z/acerto dos 3 critérios em produção (`docs/protocolo.md`), acumulado desde que o Sportmonks tem dado (2024+) vs. janela móvel dos últimos 90 dias — a janela recente é o que importa pra pegar decaimento cedo, o acumulado se move devagar demais pra isso. **Nunca reagir a uma checagem isolada** — o que importa é a tendência ao longo de várias checagens seguidas (foi assim que o "casa" Série B foi identificado como sinal morto: 2023/2024 ótimos, 2025 murchando, 2026 negativo — só visível olhando vários pontos).

| Data da checagem | Critério | Acumulado (2024+) | Últimos 90 dias |
|---|---|---|---|
| 2026-08-28 | BTTS | n=187 ROI=+20.9% z=+2.89 acerto=60% | n=12 ROI=+13.8% z=+0.47 acerto=58% |
| 2026-08-28 | Over 2.5 | n=70 ROI=+31.6% z=+2.56 acerto=63% | n=6 ROI=-36.0% z=-0.89 acerto=33% |
| 2026-08-28 | Cartões+Árbitro (Série B, stake reduzido) — **pré-correção `linha_mais_liquida`** | n=386 ROI=+9.7% z=+2.08 acerto=59% | n=107 ROI=+12.9% z=+1.48 acerto=62% |
| 2026-08-28 | BTTS (reexecução, não afetada pela correção abaixo) | n=187 ROI=+20.9% z=+2.89 acerto=60% | n=12 ROI=+13.8% z=+0.47 acerto=58% |
| 2026-08-28 | Over 2.5 (reexecução, não afetada pela correção abaixo) | n=70 ROI=+31.6% z=+2.56 acerto=63% | n=6 ROI=-36.0% z=-0.89 acerto=33% |
| 2026-08-28 | Cartões+Árbitro (Série B, stake reduzido) — **pós-correção `linha_mais_liquida`** (ver `docs/retrospectiva_linha_cartoes_bug_2026-08-28.md`) | n=386 ROI=+9.4% z=+2.01 acerto=59% | n=107 ROI=+13.8% z=+1.60 acerto=63% |
| 2026-08-28 | BTTS | n=187 ROI=+20.9% z=+2.89 acerto=60% | n=12 ROI=+13.8% z=+0.47 acerto=58% |
| 2026-08-28 | Over 2.5 | n=70 ROI=+31.6% z=+2.56 acerto=63% | n=6 ROI=-36.0% z=-0.89 acerto=33% |
| 2026-08-28 | Cartões+Árbitro (Série B, stake reduzido) — **pós-corte edge≥10%** (ver `docs/retrospectiva_edge_minimo_cartoes_2026-08-28.md`) | n=211 ROI=+16.2% z=+2.61 acerto=63% | n=59 ROI=+13.6% z=+1.17 acerto=63% |
| 2026-09-01 | BTTS | n=189 ROI=+21.6% z=+3.02 acerto=61% | n=13 ROI=+19.2% z=+0.70 acerto=62% |
| 2026-09-01 | Over 2.5 | n=71 ROI=+29.7% z=+2.42 acerto=62% | n=7 ROI=-45.1% z=-1.27 acerto=29% |
| 2026-09-01 | Cartões+Árbitro (Série B, stake reduzido) | n=215 ROI=+17.4% z=+2.85 acerto=64% | n=58 ROI=+22.4% z=+1.97 acerto=67% |
| 2026-09-02 | BTTS (reexecução pós-correção sentinela `-1`, ver abaixo — só confirma que não muda) | n=189 ROI=+21.6% z=+3.02 acerto=61% | n=13 ROI=+19.2% z=+0.70 acerto=62% |
| 2026-09-02 | Over 2.5 (reexecução pós-correção sentinela `-1` — só confirma que não muda) | n=71 ROI=+29.7% z=+2.42 acerto=62% | n=7 ROI=-45.1% z=-1.27 acerto=29% |
| 2026-09-02 | Cartões+Árbitro (Série B, stake reduzido) — **pós-correção sentinela `-1` em cartões** (`sportmonks_adapter.flat_para_linha` não sentinelava cartões/chutes ausentes, só corners — jogos com cartões faltando entravam como "0 cartões" de verdade; achado ao investigar o bug de escanteios, ver `docs/retrospectiva_ligas_nordicas_2026-09-02.md`) | n=212 ROI=+16.4% z=+2.66 acerto=63% | n=56 ROI=+20.3% z=+1.73 acerto=66% |
