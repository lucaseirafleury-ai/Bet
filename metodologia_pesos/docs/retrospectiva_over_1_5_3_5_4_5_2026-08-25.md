# Over 1.5/3.5/4.5 não diversificam — edge fica só no 2.5

## Contexto

Depois de descobrir que cartões/escanteios/chutes não têm odd de
mercado real no CSV (só percentual estatístico do próprio FootyStats,
não o que a casa oferece), a alternativa de diversificação disponível
com dado real era usar as outras linhas de gols que o CSV já traz odd:
Over 1.5, Over 3.5, Over 4.5 (além do 2.5 já usado). Implementado em
`retrospectiva.py` (generaliza `_probabilidades_e_odds`/
`_MERCADOS_SIMULAVEIS` pra qualquer linha de Over, reaproveitando
`pesos.probabilidade_over`).

## Resultado — nenhuma das 3 linhas mostra edge, e 3.5/4.5 são

Simulação completa 2023-2026 (mesmo desenho da checagem "se tivéssemos
começado em 2023"), parâmetros neutros, liga:

| Liga | Mercado | Edge | n | ROI geral | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|
| Série A | Over 1.5 | 0-8% | 122-406 | −2% a −7% | sempre negativo | misto | misto | levemente positivo |
| Série A | Over 2.5 | 8% | 223 | −2,3% (mas +35,8% só em 2026) | −28,4% | +11,5% | −15,7% | +35,8% |
| Série A | Over 3.5 | 0-8% | 181-441 | **−11% a −20%** | sempre negativo | quase sempre negativo | misto | misto |
| Série A | Over 4.5 | 0-8% | 106-379 | **−9% a −40%** | sempre muito negativo | sempre muito negativo | misto | misto |
| Série B | Over 1.5 | 0-8% | 99-345 | −12% a −17% | sempre negativo | sempre negativo | misto | sempre negativo |
| Série B | Over 3.5 | 0-8% | 113-332 | **−26% a −37%** | sempre negativo | quase sempre negativo | sempre muito negativo | sempre muito negativo |
| Série B | Over 4.5 | 0-8% | 36-250 | **−61% a −81%** | sempre catastrófico | sempre muito negativo | sempre catastrófico | sempre catastrófico |

**Nenhuma das duas ligas mostra edge em Over 1.5/3.5/4.5, em nenhum
limiar de edge testado.** Pior: Over 3.5 e principalmente Over 4.5 têm
ROI fortemente negativo, de forma consistente ano a ano — não é ruído,
é prejuízo sistemático.

## Por que isso acontece (hipótese)

Over 4.5 é um evento raro (taxa de acerto real de 2-12% nas simulações
acima) — a cauda da distribuição de gols. O modelo de Poisson simples
usado (`probabilidade_over`) provavelmente calibra mal justamente nas
caudas (a soma de duas Poisson independentes é uma aproximação; na
prática times têm correlação/viés que muda o formato da cauda), e o
mercado — que precifica essas linhas raras com cuidado justamente por
serem mais fáceis de explorar com erro de modelo — não deixa passar
esse erro. Over 2.5 fica bem no meio da distribuição, onde a
aproximação de Poisson tende a funcionar melhor — possivelmente por
isso é a única linha com sinal (ainda que concentrado em 2026).

## Conclusão

**A tentativa de diversificar apostando em mais linhas de gols não
funciona** — o edge que existe (só na Série A, só em Over 2.5 e BTTS,
só robusto em `limiar_edge≥8%`) não se generaliza pras linhas
vizinhas. Continuamos sem uma segunda fonte de aposta genuinamente
independente pra reduzir a variância ano a ano documentada
anteriormente.

**Não apostar Over 1.5, Over 3.5 ou Over 4.5 com este modelo — ROI
negativo, e em Over 3.5/4.5 fortemente negativo, em toda a amostra.**

## Próximos passos possíveis (não implementados nesta rodada)

- Série B BTTS continua sendo o único outro sinal promissor encontrado
  (`docs/retrospectiva_roi_calibracao_2023_2025_holdout_2026-08-25.md`,
  z≈0,9-1,0) — ainda não comprovado, mas é a única alternativa real de
  diversificação disponível hoje.
- Buscar uma fonte de odds histórica pra cartões/escanteios seria a
  única forma de diversificar em mercados genuinamente diferentes (não
  testado — pode não existir de graça pro histórico 2023-2026).
- Gestão de banca (Kelly fracionário) segue como opção que não resolve
  a causa raiz, mas suaviza a curva de banca sem precisar de mercado
  novo.

Reprodução: `metodologia_pesos/retrospectiva.py`
(`simular_apostas(..., mercado="over15"/"over35"/"over45")`), mesmo
padrão dos relatórios anteriores.
