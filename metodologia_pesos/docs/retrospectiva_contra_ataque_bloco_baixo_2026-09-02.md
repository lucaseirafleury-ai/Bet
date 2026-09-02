# Escanteios: contra-ataque × bloco baixo (hipótese testada, não confirma)

## Contexto

Lucas propôs uma hipótese de futebol concreta: time em transição
(contra-ataque) contra time em bloco baixo tende a gerar mais
escanteios (mais bolas na área/faltas laterais, defesa mais compacta
forçando cruzamentos). `estilo.py` já calcula, walk-forward, as notas
`tr` (transição rápida) e `bb` (bloco baixo) por time — não precisou
construir nada novo pra representar a hipótese.

## Bug descoberto no caminho: escanteios sumiu do dado local, não é limitação do Sportmonks

Ao tentar rodar o teste, os dois lados (dentro e fora do filtro) deram
`n=0` nas duas ligas — sinal de bug, não de "sem jogos qualificados".
Investigando: `sportmonks_client.MARKETS = "1,80,14,255"` (1x2, gols,
BTTS, cartões) **não inclui o mercado 60 (escanteios)** — como
escanteios nunca virou critério de produção, o mercado foi tirado do
filtro da rotina diária em algum momento (economiza payload), e a
atualização incremental (`atualizar_fixtures_finalizados`) foi
progressivamente sobrescrevendo o arquivo local sem essa odd.

Diferente do achado de hoje mais cedo nas ligas nórdicas (Sportmonks
não retém odd de escanteios em NENHUM jogo finalizado, limitação real
do dado), aqui é diferente: confirmei ao vivo, direto na API, pedindo
`markets:60` explicitamente — a odd de escanteios **é retida
normalmente** pra Série A/B, de 2024 até jogos de 31/08/2026, inclusive
via bet365 especificamente. Não é limitação do Sportmonks — é só o
pipeline de produção que parou de pedir esse mercado, algo esperado já
que não é usado hoje. Puxei um snapshot à parte (`markets:1,80,14,60,255`),
fora de `data/` (não é produção, não versionado), com 1005/1005 (Série A)
e 1010/1010 (Série B) fixtures, 1003 e — respectivamente — com odd de
escanteios real. Nenhuma mudança em `sportmonks_client.py`/produção
feita aqui — só documentando que a lacuna existe e por quê.

## Teste

Motor: mesmo perfil de parâmetros já usado antes pra escanteios
(BTTS: `k_mando=0.7, usar_estilo=True, filtro_estilo=0.8,
filtro_favoritismo=0.65, multiplicador_dp=1.5, limite_unilateral=2,
n_historico=10` — não existe parâmetro campeão específico pra
escanteios). Pra cada jogo, calculei a nota de estilo de cada time
ANTES da partida (últimos 5 jogos, mesma janela padrão de `estilo.py`,
sem lookahead) e separei em dois grupos:

- **Filtro** ("Contra-ataque × Bloco baixo"): um time com `tr≥4` E o
  outro com `bb≥4` — testados os dois sentidos (mandante contra-ataca
  × visitante se fecha, e o inverso).
- **Resto**: todo o restante dos jogos.

Aposta simulada de escanteios contra odd real (bet365, mercado 60,
linha mais líquida) — mesma função já usada antes
(`cartoes_arbitro.simular_aposta_linha`).

## Resultado — hipótese NÃO se confirma

| Liga | Grupo | n | ROI | z | Ano a ano |
|---|---|---|---|---|---|
| Série A | Filtro (contra-ataque × bloco) | 137 | -2,2% | -0,28 | 2024 +23,9% \| 2025 -16,8% \| 2026 -8,1% |
| Série A | Resto | 727 | +5,6% | +1,64 | 2024 +24,8% \| 2025 +0,4% \| 2026 -13,3% |
| Série B | Filtro (contra-ataque × bloco) | 134 | -6,3% | -0,79 | 2024 +2,7% \| 2025 -6,4% \| 2026 -14,0% |
| Série B | Resto | 714 | -4,9% | -1,42 | 2024 -9,6% \| 2025 -3,6% \| 2026 -0,2% |

**Na Série A, o filtro tem ROI PIOR que o resto do jogo** — o oposto
do que a hipótese previa. Na Série B, os dois lados são negativos, sem
diferença que sustente a hipótese. Em nenhuma liga o subconjunto
filtrado passa perto de z≈2, e o próprio "resto" da Série A (z=+1,64)
**não deve ser tratado como candidato** — não foi uma hipótese
pré-registrada (é só o complemento de um filtro que falhou), e 2026
sozinho já é negativo (-13,3%), o que já reprova a barra de "sem ano
negativo" usada em todo o resto do projeto.

## Atualização (mesmo dia) — mineração green/red no "resto", nada se sustenta

Lucas propôs (corretamente, mesmo raciocínio que já funcionou pro
Over 2.5 antes): já que "resto" é o complemento de um filtro que
falhou, vale separar esses jogos em green/red e procurar parâmetros
que diferenciem os dois grupos, em vez de descartar de cara.

Testados 5 candidatos com razão de futebol (não é busca cega): `edge`,
soma de pressão alta dos dois times (`soma_pa`), soma de transição
(`soma_tr`), soma de bloco baixo (`soma_bb`), total de escanteios
previsto pelo modelo (`pred_total`) — médias green vs red e cortes por
mediana, nas duas ligas.

**Nenhuma feature separa green de red de forma real** — todas as
diferenças de média são minúsculas (0,015 a 0,098), dentro do ruído.
E mais revelador: **todo corte testado na Série A tem 2026 negativo,
sem exceção** — inclusive o "melhor" pelo agregado (`soma_pa≤mediana`,
z=+2,12, ROI+8,6%, mas 2026=-11,4%). Isso não é sinal de que falta
achar o corte certo — é o oposto: o padrão comum a TODOS os cortes é
"2024 ótimo, 2026 ruim", **independente de qualquer feature testada**,
o que sugere mudança de regime no mercado/dado de escanteios em 2026,
não um filtro escondido. Série B ficou negativa em praticamente todos
os cortes, sem nem um candidato de agregado positivo.

Não achamos parâmetro nenhum que sustente uma entrada em escanteios,
nem no filtro original nem no complemento dele.

## Conclusão

Hipótese de futebol bem fundamentada, testada com disciplina (dado
real, ano a ano, os dois sentidos do confronto, e depois mineração
green/red no complemento) — e não se sustenta em nenhuma camada.
Escanteios em Série A/B continua sem critério viável, mesma conclusão
de antes (`docs/retrospectiva_escanteios_cartoes_2026-08-27.md`), mas
agora testada especificamente contra esse ângulo tático e seu
complemento, não só no agregado. Não recomendo perseguir mais recortes
de estilo pra escanteios sem uma hipótese nova e concreta — cada teste
novo gasta comparação múltipla em cima de um mercado que já mostrou
sinal negativo/nulo em toda tentativa até aqui. O padrão "2026 pior que
2024 em qualquer recorte" é uma pista genuína, mas é uma investigação
diferente (mudança de regime no mercado de escanteios, não um filtro
de entrada) — não perseguida aqui.
