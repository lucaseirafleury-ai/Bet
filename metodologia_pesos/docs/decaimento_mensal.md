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
