# BTTS com parâmetros próprios + teto de odd — confirma z=2,13, mas teto piora

## Contexto

O candidato de BTTS (`k_mando=0.7, usar_estilo=True, filtro_aderencia=0,
multiplicador_dp=1.5, limite_unilateral=2`, z=+2,13 no grid completo,
`docs/retrospectiva_grid_completo_2026-08-25.md`) nunca tinha sido
testado com o teto de odd (≤2,0) usando SEUS PRÓPRIOS parâmetros de
modelo — o teste de teto anterior (`docs/retrospectiva_odd_maxima_2026-08-25.md`)
usou os parâmetros do combo de Over 2.5 (`k=0.5, sem estilo, filtro=0.8`),
não os de BTTS. Lucas pediu pra fechar essa lacuna, buscando mais volume
de apostas (segundo critério rodando em paralelo ao Over 2.5).

## Resultado — o teto PIORA o BTTS com os parâmetros certos

| Edge | COM teto (≤2,0) | SEM teto |
|---|---|---|
| 0% | n=175, ROI+6,1%, z=+0,86 | n=275, ROI+2,2%, z=+0,37 |
| 5% | n=110, ROI+4,7%, z=+0,52 | n=166, ROI+8,4%, z=+1,09 |
| **8%** | n=63, ROI+13,8%, **z=+1,18** | **n=95, ROI+21,5%, z=+2,13** |

**Ao contrário do que o teste anterior sugeria** (usando os parâmetros
errados de modelo), aqui o teto de odd **reduz** o z-score em todos os
limiares de edge — de z=+2,13 pra z=+1,18 no melhor caso. **Conclusão:
descartar a ideia do teto pra BTTS** — a "pista promissora" registrada
antes não se confirma com os parâmetros certos. Isso é o motivo exato
de sempre testar a combinação completa antes de recomendar algo (mesma
lição do resto da sessão).

## O candidato em si (SEM teto, edge=8%) — confirma z=2,13, mas ano a ano é mais fraco que o Over 2.5

| Ano | n | ROI |
|---|---|---|
| 2023 | 12 | **−21,0%** |
| 2024 | 18 | +27,3% |
| 2025 | 15 | **−9,1%** |
| 2026 | 18 | +42,8% |

**2 dos 4 anos são negativos** (2023 e 2025), não só "levemente"
negativos como no Over 2.5 (que tinha só 2025 em −1,0%, essencialmente
zero) — aqui são quedas reais de −21% e −9%. O z=+2,13 do período
completo é puxado por 2024 e 2026 serem excepcionalmente bons (+27% e
+43%), compensando dois anos ruins. **Isso é uma consistência ano a
ano nitidamente mais fraca que o Over 2.5**, mesmo cruzando o mesmo
limiar de z.

Série B: sem sinal nenhum com esses parâmetros (Série A-otimizados) —
z negativo em todos os limiares de edge, ROI negativo na maioria dos
anos. Não é surpresa (já esperado, parâmetros não foram calibrados pra
Série B).

## Recomendação — candidato válido pra mais volume, mas com risco maior que o Over 2.5

- **Descartar o teto de odd pra BTTS** — não ajuda, piora.
- **BTTS (`k=0.7, usar_estilo=True, filtro_aderencia=0`, edge=8%, SEM
  teto) pode ser adotado como SEGUNDO critério** de aposta, em paralelo
  ao Over 2.5, adicionando ~n=95/3,5 anos (~27 apostas/ano) ao volume
  total — mas com uma ressalva que precisa ficar clara: **sua
  consistência ano a ano é mais fraca** (2 de 4 anos com queda real,
  não só zero) que o critério de Over 2.5. Decisão de usar ou não fica
  com Lucas, ciente desse risco maior.
- Continua sem qualquer critério defensável na Série B.

## Limitações

- Mesma ressalva de sempre: 4 anos de dado, `n=95` no melhor caso —
  ainda abaixo do `n=221` do critério de Over 2.5.
- z=2,13 cruza o limiar de significância, mas por pouco, e com padrão
  ano a ano menos estável — merece mais cautela que o critério
  principal, não o mesmo nível de confiança.

Reprodução: `metodologia_pesos/retrospectiva.py`
(`rodar_retrospectiva`/`simular_apostas`, mercado `"btts"`), script de
orquestração ad-hoc (não versionado).
