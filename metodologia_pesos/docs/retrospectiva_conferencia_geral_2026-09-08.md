# Conferência geral no motor (08/09/2026) — 2 bugs novos achados e corrigidos

## Contexto

Depois de achar e corrigir o bug do sentinela `-1` (escanteios/cartões
tratados como "0" quando a estatística de detalhe estava ausente —
`docs/retrospectiva_ligas_nordicas_2026-09-02.md` e
`docs/retrospectiva_contra_ataque_bloco_baixo_2026-09-02.md`), Lucas
pediu uma revisão geral no motor pra ver se havia mais bugs parecidos.
Revisei sistematicamente `pesos.py`, `retrospectiva.py`,
`cartoes_arbitro.py`, `previsao_dia.py`, `ledger_apostas.py`,
`gerar_painel_dia.py`, `checar_decaimento.py`, `sportmonks_client.py`,
`sportmonks_adapter.py`, `estilo.py`, `planilha_lib.py` — achei 2 bugs
reais, os dois corrigidos com testes de regressão.

## Bug 1 — médias de árbitro contornavam o fix do sentinela

`previsao_dia.py` e `checar_decaimento.py` tinham CADA UM sua própria
função pra reconstruir a média histórica de cartões por árbitro
(`_carregar_referees_cartoes`/`_carregar_referees_serieb_ordenado`) —
as duas liam o JSONL bruto DIRETO (`d.get("yellowcards_home") or 0`),
sem passar pelo `sportmonks_adapter.flat_para_linha`, que é onde o
sentinela `-1` de dado ausente foi corrigido. Ou seja: mesmo depois do
fix de ontem, um jogo com cartões ausentes continuava entrando no
HISTÓRICO DO ÁRBITRO como "0 cartões" reais — não só na resolução da
aposta individual (já corrigida), mas na média do árbitro em si, que
alimenta TODA previsão futura que usa aquele árbitro.

Consolidado numa única função (`cartoes_arbitro.carregar_referees_cartoes`,
reaproveita `flat_para_linha`) — princípio já enunciado no próprio
código (`previsao_dia.passa_filtros_gols`: "nunca duplicar essa lógica
em dois lugares, senão os dois processos podem divergir silenciosamente
do que está realmente em produção") que não tinha sido seguido aqui.
`previsao_dia.py` (previsão ao vivo) e `checar_decaimento.py`
(monitoramento mensal) agora usam a mesma função. 2 testes novos em
`test_cartoes_arbitro.py`.

## Bug 2 — `atualizar_fixtures_finalizados` nunca recapturava dado incompleto

A própria docstring da função dizia que `margem_dias` existia pra
"recapturar jogos cuja odd/estatística ainda não estava completa na
última passada" — mas o código só ADICIONAVA `fixture_id` novo,
nunca sobrescrevia um já existente. Ou seja: um jogo capturado pouco
depois de terminar, com estatística/odd ainda incompleta no Sportmonks
naquele momento, ficava incompleto PRA SEMPRE no cache local — mesmo
que a reconsulta da janela (`margem_dias`) trouxesse dado mais
completo depois, o código descartava silenciosamente porque o
`fixture_id` "já existia". Um teste já existente
(`test_atualizar_fixtures_finalizados_incremental_pula_existente_e_adiciona_novo`)
até codificava esse comportamento errado como esperado ("não duplicou
nem alterou a fixture já existente").

Corrigido: qualquer fixture finalizado devolvido pela reconsulta agora
SOBRESCREVE a versão local (preserva só o rótulo cosmético de
temporada, `season`, quando já conhecido) — `novos` continua contando
só `fixture_id` genuinamente novo. Teste antigo reescrito pra refletir
o comportamento certo + 1 teste novo confirmando que a reconsulta
sobrescreve dado desatualizado.

## Impacto no critério em produção

Rechecagem de Cartões+Árbitro (Série B) depois dos dois fixes de hoje
(cumulativo com o fix de ontem):

| Estágio | n | ROI | z |
|---|---|---|---|
| Antes de qualquer fix (documentado, 01/09) | 215 | +17,4% | +2,85 |
| Pós-fix sentinela em cartões/chutes (ontem) | 212 | +16,4% | +2,66 |
| Pós-fix carregador de árbitro (hoje) | 206 | +17,1% | +2,74 |

Continua folgadamente acima do limiar z≈2, positivo nos 3 anos.
`gerar_painel_dia.CRITERIOS_INFO` atualizado com o z mais recente
(+2,74). Nenhuma mudança de comportamento em BTTS/Over 2.5 (não
dependem de dado de árbitro nem do `atualizar_fixtures_finalizados`
incremental de forma que o Bug 2 afetasse os números já revalidados
ontem).

## O que mais foi revisado, sem achado

`pesos.py` (fórmulas de peso/probabilidade), `retrospectiva.py`
(look-ahead do walk-forward, simulação de apostas — `df_antes =
df[df["timestamp"] < ts_corte]`, corte estrito confirmado correto em
todo lugar), `ledger_apostas.calcular_resumo` (agregação de
ROI/lucro), `gerar_painel_dia.py` (geração de HTML, filtro de
resultados recentes) — nada de suspeito encontrado nessas partes.

## Auditoria de fechamento (mesmo dia) — smoke test de ponta a ponta + cross-check por formato diferente

Depois dos 2 bugs acima, três verificações adicionais, cada uma um
ângulo diferente do "reler o código de novo":

**1. Auditoria do ledger real** (10 apostas resolvidas em produção):
nenhuma pendente travada, nenhuma inconsistência de lucro/stake/odd
contra a fórmula. 2 "edges abaixo do limiar atual" investigados —
ambos são registros de 27/08/2026, um dia antes do limiar de edge≥10%
entrar em vigor (28/08) — registro histórico correto, não bug ativo.

**2. Smoke test real de ponta a ponta**: rodei
`previsao_dia.gerar_sugestoes_do_dia()` e
`checar_decaimento.rodar_checagem()` de verdade, com API ao vivo e
`data/sportmonks_{seriea,serieb}` atualizado (11 jogos novos/liga via
`atualizar_fixtures_finalizados`, testando o Bug 2 na prática). Pipeline
inteiro roda sem erro. BTTS e Over 2.5 reproduzem EXATAMENTE o número
já documentado; Cartões+Árbitro sobe de n=206→208 (2 jogos novos reais
entraram na amostra — decaimento normal), mantendo z=+2,56.

**3. Cross-check por formato de cálculo diferente** (pedido do Lucas —
mais forte que só rodar o mesmo código de novo, que sempre concorda
consigo mesmo mesmo se tiver um erro sistemático):
- `pesos.probabilidade_over`/`probabilidade_btts`/`probabilidade_resultado`
  (fórmula fechada, soma de Poisson analítica) comparadas contra
  **simulação Monte Carlo** (`numpy`, 2 milhões de sorteios por ponto,
  7 valores de λ × 5 linhas pra `over`, 6 combinações pra BTTS, 5 pra
  1x2) — maior diferença encontrada: 0,00065, dentro do ruído esperado
  de Monte Carlo (~1/√N ≈ 0,0007). Fórmula fechada confirmada correta
  por um caminho de cálculo totalmente diferente (simulação numérica,
  não a mesma álgebra).
- `checar_decaimento.zscore()` (fórmula escrita à mão) comparado contra
  `scipy.stats.ttest_1samp` (biblioteca estatística padrão, testada por
  terceiros) nos lucros REAIS dos 3 critérios em produção — diferença
  na ordem de 1e-15/1e-16 (ruído de ponto flutuante, essencialmente
  idêntico). Confirma que o z-score do projeto é matematicamente
  equivalente ao t-statistic padrão de uma amostra.

Nenhum dos dois cross-checks achou divergência — reforça que os 3
bugs já corrigidos hoje eram os problemas reais, não sintoma de um
erro matemático mais profundo nas fórmulas centrais do motor.

## Verificação

`pytest metodologia_pesos/` — 208 testes passando (4 novos: 2 em
`test_cartoes_arbitro.py`, 1 reescrito + 1 novo em
`test_sportmonks_client.py`).
