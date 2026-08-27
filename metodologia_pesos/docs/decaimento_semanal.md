# Decaimento semanal — Over 2.5 / BTTS (Série A) + Cartões+Árbitro (Série B)

Checagem recorrente (rotina semanal) do ROI/z dos critérios campeões (`docs/protocolo.md`), acumulado vs. janela móvel dos últimos 90 dias — a janela recente é o que importa pra pegar decaimento cedo, o acumulado se move devagar demais pra isso. "Cartões+Árbitro (Série B)" é o 3º critério, adotado com stake reduzido (~1/3 do normal) por ainda não ter passado do limiar de significância z≈2 — só aparece quando `data/sportmonks_serieb_cartoes/fixtures.jsonl` está disponível (ver `sportmonks_pull_serieb_cartoes.py`).

| Data da checagem | Critério | Acumulado 2023-2026 | Últimos 90 dias |
|---|---|---|---|
| 2026-08-26 | Over 2.5 | n=278 ROI=+8.7% z=+1.37 | n=9 ROI=-30.2% z=-0.86 |
| 2026-08-26 | BTTS | n=256 ROI=+16.0% z=+2.62 | n=12 ROI=+7.3% z=+0.27 |
| 2026-08-27 | Over 2.5 | n=278 ROI=+8.7% z=+1.37 | n=9 ROI=-30.2% z=-0.86 |
| 2026-08-27 | BTTS | n=256 ROI=+16.0% z=+2.62 | n=12 ROI=+7.3% z=+0.27 |
| 2026-08-27 | Cartões+Árbitro (Série B, stake reduzido) | n=387 ROI=+8.1% z=+1.71 | n=105 ROI=+5.9% z=+0.64 |
