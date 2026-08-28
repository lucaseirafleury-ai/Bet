# Filtro de favoritismo (1x2) no Over 2.5-Sbo: sinal real, adotado via regra "União"

**Atualização (mesmo dia)**: a seção "Recomendação" abaixo (não
empilhar) segue válida pra INTERSEÇÃO (exigir os dois sinais ao mesmo
tempo). Mas Lucas perguntou sobre a UNIÃO (bastar um dos dois) — testei
os 4 quadrantes completos e a União se mostrou a melhor opção de
todas testadas até aqui (mais volume E mais lucro absoluto que
qualquer filtro isolado, com os 3 anos bem representados). **Adotada
em produção** — ver `docs/protocolo.md` (seção "Filtro de
favoritismo... regra União") pra os números finais e
`previsao_dia.CRITERIOS_GOLS` (`limiar_favoritismo=0.7484`) pra a
implementação.

## Contexto

Primeira rodada da varredura pedida pelo Lucas (revisitar achados
antigos de amostra grande, não positivos ou fracamente positivos,
atrás de um filtro). Uma segmentação antiga (`docs/protocolo.md`,
"Segmentação do Over 2.5 por favoritismo — curiosidade, não
acionável") tinha achado um padrão em U (jogos equilibrados e
favoritos claros rendem mais que o meio-termo) nos parâmetros
FootyStats antigos — nunca testado no critério atual (Sbo, n=80).

## Resultado — mediana de `prob_mercado_favorito_dc`

| Grupo | n | Acerto | ROI | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| Equilibrado (≤ mediana) | 40 | 65,0% | +41,8% | +32,7% | +26,1% | +66,3% |
| Favorito claro (> mediana) | 40 | 52,5% | +5,4% | +31,8% | **−13,2%** | +9,4% |

Diferente do achado antigo (padrão em U) — aqui é mais uma queda
constante: quanto mais claro o favorito, pior. Todos os 3 anos
positivos do lado equilibrado; o lado de favorito claro tem 2025
negativo. Correlação com a odd de Over 2.5 é moderada (−0,44), não é a
mesma informação do teto de odd já adotado.

## Empilhado em cima do teto de odd já em produção (odd≤2,20, n=46)

| Subgrupo | n | Lucro (stake=1) |
|---|---|---|
| Equilibrado | 23 | +12,00u |
| Favorito claro | 23 | +6,07u |

Dobro de eficiência, mas o detalhamento por ano fica fino demais pra
confiar (2024 e 2025 caem pra `n=5` cada) — filtragem tripla (edge +
odd + favoritismo) amostra insuficiente pra validar.

## Recomendação

Favoritismo é um sinal real e sustenta sozinho (n=40/40, 3 anos limpos
do lado equilibrado). **Não empilhar** com o teto de odd já adotado —
amostra insuficiente pra essa combinação. Fica registrado como segundo
candidato independente, à espera de mais dado (2027) pra reavaliar a
versão combinada.

## Verificação

- `n=40` em cada lado do corte principal, acima do mínimo de 15.
- Checagem ano a ano feita; a versão empilhada com o teto de odd foi
  explicitamente REJEITADA por falhar essa checagem (`n=5` por ano).
- Reprodução: script ad-hoc rodado nesta sessão, mesmo dado
  (`data/sportmonks_seriea/fixtures.jsonl`, bookmaker Sbo) e critério
  Over 2.5 já em produção, usando o campo
  `prob_mercado_favorito_dc` já calculado por
  `retrospectiva._probabilidades_favorito_dc`.
