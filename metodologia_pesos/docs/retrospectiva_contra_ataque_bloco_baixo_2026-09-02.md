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

Confirmei ao vivo, direto na API, pedindo `markets:60` explicitamente —
a odd de escanteios **é retida normalmente** pra Série A/B, de 2024 até
jogos de 31/08/2026, inclusive via bet365 especificamente. Não é
limitação do Sportmonks — é só o pipeline de produção que parou de
pedir esse mercado, algo esperado já que não é usado hoje. Puxei um
snapshot à parte (`markets:1,80,14,60,255`), fora de `data/` (não é
produção, não versionado), com 1005/1005 (Série A) e 1010/1010
(Série B) fixtures, 1003 e — respectivamente — com odd de escanteios
real. Nenhuma mudança em `sportmonks_client.py`/produção feita aqui —
só documentando que a lacuna existe e por quê.

**Atualização (mesmo dia)**: achei o MESMO bug de pipeline nas ligas
nórdicas mais tarde hoje — o "0% de cobertura" que eu tinha reportado
antes lá também era esse gap do `MARKETS`, não limitação real do
Sportmonks (corrigido em `docs/retrospectiva_ligas_nordicas_2026-09-02.md`).

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

**ERRATA (mesmo dia)**: a tabela abaixo, na primeira versão deste doc,
tinha um SEGUNDO bug — `retrospectiva._valor_real` somava as colunas
de escanteios sem checar o sentinela `-1` (usado por
`sportmonks_adapter.flat_para_linha` quando falta estatística de
detalhe no jogo). Dois lados ausentes viravam `real_total = -2`, um
placar que nunca aconteceu — e qualquer aposta "Under" vencia
automaticamente contra ele, inflando o ROI de qualquer célula com
jogos de dado incompleto (mais comum em 2024, a temporada mais antiga
puxada). Achado ao investigar um resultado implausível (z>5) no
reteste das ligas nórdicas com esse mesmo motor. Corrigido em
`retrospectiva.py` (commit `bd23a5b`, `_valor_real` agora trata `-1`
como dado ausente, igual a coluna faltante/NaN). A tabela abaixo é a
versão CORRIGIDA (números antigos, errados: Série A filtro n=137
z=-0,28 / resto n=727 z=+1,64; Série B filtro n=134 z=-0,79 / resto
n=714 z=-1,42 — mantidos aqui só por rastreabilidade, não usar).

| Liga | Grupo | n | ROI | z | Ano a ano |
|---|---|---|---|---|---|
| Série A | Filtro (contra-ataque × bloco) | 120 | -12,1% | -1,42 | 2024 +0,8% \| 2025 -18,6% \| 2026 -11,1% |
| Série A | Resto | 637 | -3,0% | -0,81 | 2024 +4,1% \| 2025 +0,4% \| 2026 -15,0% |
| Série B | Filtro (contra-ataque × bloco) | 132 | -4,9% | -0,61 | 2024 +5,1% \| 2025 -4,1% \| 2026 -14,0% |
| Série B | Resto | 702 | -5,1% | -1,46 | 2024 -9,6% \| 2025 -4,2% \| 2026 -0,1% |

Com o dado corrigido, o quadro fica mais simples e mais limpo: **tudo
negativo ou perto de zero, nas duas ligas, dentro e fora do filtro.**
O "resto" da Série A, que antes parecia levemente positivo (z=+1,64,
já tratado com cautela na v1 deste doc), na verdade é negativo
(z=-0,81) — o sinal positivo aparente era, ele também, efeito do bug.
Hipótese rejeitada com ainda mais clareza que antes.

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

**ERRATA**: também refeito depois de corrigir o bug do sentinela `-1`
(seção anterior). Os números originais abaixo (`soma_pa≤mediana`
z=+2,12) vinham do mesmo dado contaminado — mantidos riscados por
rastreabilidade:

~~Nenhuma feature separa green de red de forma real — diferenças de
média minúsculas (0,015 a 0,098). Todo corte testado na Série A tem
2026 negativo, sem exceção — inclusive o "melhor" pelo agregado
(`soma_pa≤mediana`, z=+2,12, ROI+8,6%, mas 2026=-11,4%). Série B
ficou negativa em praticamente todos os cortes.~~

**Resultado corrigido**: continua nenhuma feature separando green de
red de forma real (diferenças de média igualmente pequenas com o dado
corrigido). Mas agora **nenhum corte fica positivo em nenhuma liga** —
o melhor da Série A cai pra `edge≤mediana` z=+0,31 (ROI+1,6%), longe
de qualquer limiar; Série B não tem nenhum cruzamento positivo. O
padrão "2026 pior que os outros anos" que eu tinha destacado antes
como pista genuína também enfraquece bastante com o dado corrigido —
2024 deixa de ser uniformemente ótimo (varia entre +0,8% e +25,2%
conforme o corte, não mais um bloco consistente) — então não vale mais
tratar isso como um sinal de mudança de regime; era, em boa parte,
também reflexo do bug.

Não achamos parâmetro nenhum que sustente uma entrada em escanteios,
nem no filtro original nem no complemento dele.

## Conclusão

Hipótese de futebol bem fundamentada, testada com disciplina (dado
real, ano a ano, os dois sentidos do confronto, mineração green/red no
complemento, e uma correção de bug de integridade de dado no meio do
caminho) — e não se sustenta em nenhuma camada. Escanteios em Série
A/B continua sem critério viável, mesma conclusão de antes
(`docs/retrospectiva_escanteios_cartoes_2026-08-27.md`), agora com o
resultado mais limpo e mais confiável que já tivemos pra esse mercado
(sem o viés de dado ausente que inflava resultados anteriores — inclui
possivelmente o teste original de 27/08, não revalidado aqui). Não
recomendo perseguir mais recortes de estilo pra escanteios sem uma
hipótese nova e concreta.
