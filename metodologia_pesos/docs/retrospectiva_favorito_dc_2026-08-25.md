# Favorito DC (sozinho e em múltipla) — sem edge encontrado

## Contexto

Lucas relatou que o que funcionou pra ele historicamente foi apostar em
combinação de Over/Under + Dupla Chance (DC) do favorito — pediu pra
buscarmos, sem restrição de mercado, uma metodologia com ROI positivo
sucessivo nos últimos anos. Implementado nesta rodada:
`pesos.probabilidade_resultado` (P(vitória/empate/derrota) via grade
conjunta de Poisson) e `retrospectiva.simular_apostas_combo` (múltipla
genérica, odd = produto das pernas, só ganha se todas baterem) — ver
commit `e5766e3`.

**Limitação de dado**: o CSV não tem odd real de Dupla Chance — só as 3
odds do 1x2. A "odd" usada aqui é a combinação bruta de duas pernas do
1x2 (favorito + empate), que subestima a odd real de DC (o mercado de
DC de verdade costuma ter margem menor que a soma de duas pernas do
1x2) — então o ROI simulado tende a ser conservador/pessimista em vez
de otimista.

## Resultado — simulação 2023-2026, parâmetros neutros, ano a ano

| Liga | Aposta | Edge | n | ROI geral | 2023 | 2024 | 2025 | 2026 | z-score |
|---|---|---|---|---|---|---|---|---|---|
| Série A | Favorito DC sozinho | 0-8% | 117-343 | **−6% a −17%** | sempre negativo | sempre negativo | sempre negativo | sempre negativo | — |
| Série A | Over 2.5 + Favorito DC | 0-8% | 101-301 | **−14% a −21%** | sempre muito negativo | quase neutro | sempre negativo | positivo | — |
| Série A | BTTS + Favorito DC | 0% | 316 | +4,1% | −6,4% | +12,9% | −8,7% | +21,6% | **+0,59** |
| Série B | Favorito DC sozinho | 0-8% | 130-321 | **−3% a −4%** | quase neutro | negativo | negativo | quase neutro | — |
| Série B | Over 2.5 + Favorito DC | 0-8% | 62-218 | **−28% a −34%** | misto | sempre negativo | sempre muito negativo | sempre muito negativo | — |
| Série B | BTTS + Favorito DC | 8% | 52 | +20,3% | +109,5%(!) | −6,7% | +7,3% | +15,8% | **+1,06** |

**Nenhuma combinação passa perto do limiar de significância (~z=2) que
usamos no resto do projeto.** Os dois candidatos "menos ruins" (BTTS +
Favorito DC nas duas ligas) têm z=0,59 e z=1,06 — muito abaixo do que já
temos documentado pra Over 2.5/BTTS sozinhos na Série A (z=2,24/2,91). O
resultado da Série B (z=1,06) é inflado por um único ano com amostra
minúscula (2023, n=8, ROI+109,5% — sinal clássico de outlier de amostra
pequena, não achado real).

## Achados

1. **Favorito DC sozinho não tem edge em nenhuma liga** — ROI
   consistentemente negativo em todos os anos e limiares testados. O
   mercado de resultado (1x2/DC) parece bem precificado pelo mercado —
   o modelo de Poisson pro resultado não vê nada que a odd não veja.
2. **Combinar com Over 2.5 piora ainda mais** (principalmente Série B,
   até −34%) — combinar duas pernas sem edge individual (ou pior, com
   edge negativo) NÃO cria edge positivo; o produto das probabilidades
   carrega o viés negativo de cada perna.
3. **Combinar com BTTS é o menos ruim, mas ainda não convence** — ROI
   levemente positivo no agregado da Série A, mas com a mesma
   inconsistência ano a ano que já vimos em outros mercados (2023 e
   2025 negativos, 2024 e 2026 positivos) e sem significância
   estatística.

## Por que a estratégia do Lucas pode ter funcionado no passado mesmo assim

Algumas hipóteses que este teste NÃO consegue confirmar nem descartar,
porque testamos um modelo específico (pesos ponderados + Poisson), não
o julgamento humano do Lucas:
- Escolha manual de QUAIS jogos entrar (não "todo jogo com edge≥X%") —
  o julgamento qualitativo de que jogos evitar pode ser o que gerava
  ROI, não a combinação de mercados em si.
- Período específico em que funcionou pode ter sido favorável (como
  2024/2026 aqui) sem ser representativo do longo prazo — mesmo padrão
  de variância ano a ano que já apareceu em Over 2.5/BTTS.
- A "Dupla Chance do favorito" real do Lucas pode ter usado um
  favoritismo diferente do puramente "odd mais baixa" (ex.: favorito
  por julgamento de fontes, não só a odd).

## Recomendação

Não incorporar Favorito DC (sozinho ou combinado) como critério de
aposta — nenhuma variação testada mostra edge estatisticamente
defensável. Os únicos critérios com sinal real seguem sendo os já
documentados: Série A Over 2.5/BTTS com `limiar_edge≥8%` (z>2), e Série
B BTTS como candidato fraco (z≈1) ainda não comprovado.

## Limitações

- Mesma ressalva de sempre: 2023-2026, `n` de 52-343 por linha.
- Odd de DC é aproximada (soma bruta de duas pernas do 1x2, sem
  remover margem adicional) — o ROI real de apostar DC de verdade
  (com a odd real do mercado) pode ser um pouco diferente, mas a
  direção do resultado (sem edge) provavelmente não muda.
- Combo assume independência entre pernas (produto de probabilidades)
  — simplificação que pode subestimar ou superestimar o edge real
  dependendo da correlação verdadeira entre os mercados.

Reprodução: `metodologia_pesos/retrospectiva.py`
(`simular_apostas(mercado="favorito_dc")`,
`simular_apostas_combo(pernas=["over25"/"btts", "favorito_dc"])`).
