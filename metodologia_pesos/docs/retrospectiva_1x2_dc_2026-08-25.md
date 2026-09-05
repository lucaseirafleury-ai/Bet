# 1x2 e Dupla Chance (mandante/visitante) — Série A sem sinal, Série B com "edge" que já morreu

## Contexto

Lucas sugeriu testar 1x2 (casa/empate/fora) e Dupla Chance de lado fixo
(mandante/visitante, diferente de Favorito DC) como mercados próprios —
motivado corretamente pelo fato de termos as 3 odds REAIS desses
mercados no CSV (ao contrário de Under, que precisa de aproximação).
Implementado `pesos.probabilidades_implicitas_nvias` (de-vig de N vias,
generaliza `probabilidade_implicita_2vias`) e
`retrospectiva._probabilidades_1x2_e_dc` (commit `d7b464b`).

Grid completo: `k_mando × usar_estilo × filtro_aderencia × corte de
outlier` (96 combinações por liga, mesma estrutura do grid vencedor de
Over 2.5), avaliado nos 5 mercados novos (`casa`, `empate`, `fora`,
`mandante_dc`, `visitante_dc`), 3 limiares de edge, período completo
2023-2026.

## Série A — nenhum mercado tem sinal

Nenhum dos 5 mercados passa perto de z=2 em nenhuma combinação. Melhor
caso: `casa`, z=+0,27 (ruído puro). `empate`/`visitante_dc` até
chegam a ficar moderadamente negativos (z≈−1,2 a −1,6) em alguns
cantos do grid, mas nada que passe o limiar de significância pra
qualquer direção. **1x2/DC não acrescenta nada à Série A** — o sinal
real ali continua concentrado em Over 2.5/BTTS.

## Série B — "casa" parecia forte (z=+2,71), mas é um sinal morto

O grid encontrou, pro mercado **casa** (mandante vence) na Série B:
`k_mando=0.5, usar_estilo=True, filtro_aderencia=0, mult_dp=1.5, uni=2,
edge=0%` → **n=354, ROI+17,5%, z=+2,71** — maior z de qualquer
candidato já achado na Série B em toda a sessão, e por uma margem
grande.

**Confirmamos que não é célula isolada de sorte** — testamos a
vizinhança de `k_mando` (0,35/0,5/0,7) e de `filtro_aderencia`/`usar_estilo`:
todos ficam num platô de z=2,1-2,7, robusto. O problema não é esse.

### O problema é a tendência ano a ano — e ela é decisiva

| Ano | n | Acerto | ROI |
|---|---|---|---|
| 2023 | 77 | 59,7% | **+35,8%** |
| 2024 | 102 | 59,8% | **+38,6%** |
| 2025 | 102 | 48,0% | +2,3% (quase zero) |
| 2026 | 73 | 42,5% | **−9,9%** |

**Esse mesmo padrão se repete em TODAS as 5 configurações testadas na
vizinhança** — não é ruído de uma célula, é uma tendência sistemática:
2023 e 2024 foram excelentes, 2025 já murchou pra quase zero, e **2026
(o ano mais recente, o que mais importa pra apostar hoje) já é
negativo**. Somando só 2025+2026 (os dois anos mais recentes): n=175,
lucro≈−4,88u, **ROI≈−2,8%** — o "edge" já não existe nos dados mais
recentes, só sobrevive no agregado por causa de 2023-2024 puxarem a
média pra cima.

Isso é diferente dos "um ano fraco, resto forte" que vimos no Over 2.5
(2025 quase zero, mas nenhuma tendência de piora) — aqui é uma
**deterioração progressiva e consistente ano após ano**, o padrão
clássico de uma ineficiência de mercado que existia e foi arbitrada
(a casa de apostas ajustou a odd de "casa vence" na Série B ao longo do
tempo), ou de um regime que mudou. De qualquer forma, apostar nisso
hoje seria apostar contra a tendência mais recente e mais forte dos
dados, não a favor dela.

## Recomendação

**Não adotar `casa` (nem `mandante_dc`, que tem o mesmo problema
atenuado) como critério de aposta na Série B.** O z-score agregado de
+2,71 é real, mas enganoso — mascarava uma tendência de deterioração
que só aparece ao olhar ano a ano. Mesma disciplina de sempre: nunca
confiar só no z do período completo sem checar a consistência temporal,
e aqui a checagem reprovou o achado claramente.

`fora` e `visitante_dc` seguem negativos em toda a Série B, sem
candidato promissor. `empate` também sem sinal defensável nas duas
ligas.

## Limitações

- O platô de robustez confirma que o "achado" é real nos dados
  históricos — só não é útil pra apostar PRA FRENTE, porque a tendência
  já é de queda.
- Mesma ressalva de sempre: 4 anos de dado, e aqui especificamente
  vimos o quanto o "z do período completo" pode enganar sem o
  detalhamento ano a ano — reforça por que essa checagem é obrigatória
  em toda descoberta.

Reprodução: `metodologia_pesos/retrospectiva.py`
(`_probabilidades_1x2_e_dc`, mercados `casa/empate/fora/mandante_dc/visitante_dc`),
scripts de orquestração ad-hoc (não versionados).
