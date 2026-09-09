# Retrospectiva — ligas nórdicas (Noruega 1.Division, Suécia Allsvenskan/Superettan)

## Contexto

Lucas já tem 3 ligas nórdicas configuradas no plano Sportmonks (não
vai trocar por outras) — pediu pra investigar se dá pra achar edge
nelas, já que o dado está pago/disponível de qualquer forma.

Antes de rodar backtest, checamos cobertura de odds do bet365 (a casa
que o Lucas usa) nas 3 ligas: 1x2/Gols/BTTS 100%, Cartões 0% (em
qualquer bookmaker do catálogo, não só bet365), Escanteios aparentando
100%. Ver seção "Correção" abaixo — a checagem de escanteios estava
enganosa.

## Correção: escanteios não é testável historicamente — ERRADO, corrigido abaixo

**Esta seção estava errada — ver "Correção #2" mais abaixo pra a
versão certa.** Mantida aqui, riscada, por transparência (mesmo padrão
de todo erro corrigido neste projeto: nunca apagar, sempre mostrar o
que aconteceu).

~~A checagem inicial de cobertura de escanteios (mercado 60, "2-Way
Corners") usou `/fixtures` ordenado por `-starting_at` sem filtro de
data — isso pegou por acidente jogos FUTUROS/em aberto (com odd
pré-jogo ainda viva), não o histórico de jogos já encerrados.~~

~~Ao puxar o histórico real (`puxar_fixtures_finalizados`, 648 jogos na
Noruega 2024-2026) e checar `_odds_escanteios`: **0 de 648 jogos têm
odd de escanteios salva** — mesmo jogos de 30/08/2026 (bem recentes).
As estatísticas reais de escanteios (`corners_home`/`corners_away`)
existem normalmente (645/648) — só a ODD não fica retida depois que o
jogo termina. bet365 cota escanteios ao vivo/pré-jogo nessas ligas,
mas o Sportmonks não preserva essa odd no registro histórico
finalizado. **Não dá pra validar edge sem odd histórica real — mercado
descartado por limitação de dado, não por falta de sinal.**~~

Código de extração (`sportmonks_adapter.flat_para_linha`, campo
`_odds_escanteios`, mesmo padrão de `_odds_cartoes`) foi mantido —
capacidade genérica e reutilizável, mesmo sem uso imediato aqui.

## Correção #2 (02/09/2026, mesmo dia) — escanteios TEM odd histórica; o "0 de 648" era outro bug de pipeline

A "Correção" acima usou `puxar_fixtures_finalizados`, que por sua vez
usa `sportmonks_client.MARKETS = "1,80,14,255"` — **esse filtro nunca
pediu o mercado 60 (escanteios)**, porque escanteios nunca virou
critério de produção. O "0 de 648" não era o Sportmonks recusando
reter a odd — era o nosso próprio pull nunca tendo pedido essa odd em
primeiro lugar. Confirmado ao vivo na API, pedindo `markets:60`
explicitamente: a odd de escanteios **é retida normalmente** nas 3
ligas nórdicas, de 2024 até jogos de 30/08/2026, bet365 incluído
(>99% de cobertura nas 3 ligas). Mesmo bug (e mesma correção) achados
hoje mais cedo pra Série A/B — ver
`docs/retrospectiva_contra_ataque_bloco_baixo_2026-09-02.md`.

Puxei um snapshot à parte (fora de `data/`, não versionado, mercado 60
incluído) e testei escanteios de verdade nas 3 ligas — motor genérico
(perfil de parâmetros do BTTS, já usado antes pra escanteios),
`n_historico=10`, odd real bet365, mercado 60.

**Primeira rodada (com um SEGUNDO bug, também corrigido — ver
`docs/retrospectiva_contra_ataque_bloco_baixo_2026-09-02.md` pro
detalhe técnico)**: resultados implausíveis (Noruega z=+5,93, Superettan
z=+3,61) — grande demais pra ser real, investigado e achado um bug de
integridade de dado (`_valor_real` tratava o sentinela `-1`, usado
quando falta estatística de detalhe, como se fosse um placar real de
-2 escanteios — o que faz qualquer aposta "Under" vencer sozinha
contra um total que nunca aconteceu). Corrigido em `retrospectiva.py`
(commit `bd23a5b`).

**Resultado final, com o dado E o motor corretos**:

| Liga | n | ROI | z | Ano a ano |
|---|---|---|---|---|
| Noruega 1.Division | 361 | +2,2% | +0,45 | 2024 -4,5% (n=29) \| 2025 -0,6% \| 2026 +8,0% |
| Suécia Allsvenskan | 517 | -3,4% | -0,85 | 2024 -1,6% \| 2025 -8,6% \| 2026 +2,4% |
| Suécia Superettan | 361 | -11,4% | -2,33 | 2024 -26,3% (n=30) \| 2025 -11,6% \| 2026 -7,5% |

**Sem sinal em nenhuma das 3 ligas** — Noruega fica praticamente em
zero, Allsvenskan levemente negativa (mudou pouco com a correção,
esperado — é a liga com menos jogo de estatística faltando), Superettan
claramente negativa. A conclusão prática de antes ("não apostar
escanteios nas nórdicas") continua certa — só que agora testada de
verdade, não por falta de dado.

## BTTS / Over gols / 1x2-Dupla Chance — resultado negativo, limpo

Reaproveitado 100% o motor existente (`retrospectiva.rodar_retrospectiva`/
`simular_apostas`), com os parâmetros JÁ VALIDADOS pro Brasil (BTTS:
`k_mando=0.7, usar_estilo=True, filtro_estilo=0.8,
filtro_favoritismo=0.65, multiplicador_dp=1.5, limite_unilateral=2,
n_historico=10`; Over/1x2-DC: `k_mando=0.35, usar_estilo=False,
filtro_aderencia=0.65, multiplicador_dp=1.5, limite_unilateral=4,
n_historico=15`), sem recalibração nova — mesmo padrão usado quando
testamos a troca FootyStats→Sportmonks (reconfirma com o que já
funciona antes de cogitar grid novo).

| Liga | Mercado | n | ROI | z | Ano a ano |
|---|---|---|---|---|---|
| Noruega, 1.Division | BTTS | 101 | -14,9% | -1,97 | 2024 -35,3% \| 2025 -29,4% \| 2026 +9,5% |
| Noruega, 1.Division | Over 2.5 | 46 | -16,4% | -1,35 | 2024 -21,5% \| 2025 -31,6% \| 2026 -2,3% |
| Noruega, 1.Division | Casa | 172 | -19,0% | -2,27 | 2024 -26,1% \| 2025 -40,2% \| 2026 +8,7% |
| Noruega, 1.Division | Empate | 83 | -16,7% | -0,86 | 2024 -17,8% \| 2025 +6,1% \| 2026 -100,0% (n=10) |
| Noruega, 1.Division | Fora | 242 | -10,8% | -1,22 | 2024 +4,1% \| 2025 -28,9% \| 2026 -3,8% |
| Noruega, 1.Division | Mandante DC | 170 | -12,2% | -2,23 | 2024 -9,4% \| 2025 -18,4% \| 2026 -7,8% |
| Noruega, 1.Division | Visitante DC | 255 | -14,0% | -2,56 | 2024 -10,8% \| 2025 -10,9% \| 2026 -22,9% |
| Suécia, Allsvenskan | BTTS | 99 | -3,9% | -0,46 | 2024 +13,6% \| 2025 -10,1% \| 2026 -10,8% |
| Suécia, Allsvenskan | Over 2.5 | 69 | -15,3% | -1,44 | 2024 -33,6% \| 2025 -11,3% \| 2026 -10,7% |
| Suécia, Allsvenskan | Casa | 183 | -5,8% | -0,62 | 2024 -6,8% \| 2025 -2,6% \| 2026 -8,8% |
| Suécia, Allsvenskan | Empate | 101 | -12,7% | -0,75 | 2024 -10,2% \| 2025 -10,4% \| 2026 -23,2% |
| Suécia, Allsvenskan | Fora | 239 | +1,4% | +0,14 | 2024 -8,4% \| 2025 +18,0% \| 2026 -15,0% |
| Suécia, Allsvenskan | Mandante DC | 189 | -6,7% | -1,24 | 2024 -3,2% \| 2025 -13,7% \| 2026 -0,2% |
| Suécia, Allsvenskan | Visitante DC | 253 | -4,1% | -0,70 | 2024 -10,8% \| 2025 +5,7% \| 2026 -14,6% |
| Suécia, Superettan | BTTS | 95 | +8,4% | +0,99 | 2024 -19,1% \| 2025 +2,8% \| 2026 +31,4% |
| Suécia, Superettan | Over 2.5 | 57 | +2,2% | +0,18 | 2024 -27,8% (n=5) \| 2025 -15,0% \| 2026 +26,8% |
| Suécia, Superettan | Casa | 163 | -15,1% | -1,65 | 2024 -18,4% \| 2025 -2,2% \| 2026 -33,8% |
| Suécia, Superettan | Empate | 94 | -35,8% | -2,30 | 2024 -49,3% \| 2025 -0,1% \| 2026 -100,0% (n=8) |
| Suécia, Superettan | Fora | 241 | -9,1% | -0,96 | 2024 -13,5% \| 2025 -5,0% \| 2026 -9,0% |
| Suécia, Superettan | Mandante DC | 158 | -13,9% | -2,53 | 2024 -17,3% \| 2025 -4,7% \| 2026 -26,8% |
| Suécia, Superettan | Visitante DC | 263 | -7,8% | -1,46 | 2024 -12,7% \| 2025 -3,9% \| 2026 -6,5% |

(Over 1.5 e Over 3.5: n=0 nas 3 ligas — o combo de parâmetros usado
nunca qualificou nenhuma aposta nessas linhas com o `limiar_edge`
aplicado.)

**Nenhum mercado chega perto de z≈2.** A maioria é claramente negativa,
vários abaixo de z=-2 (Casa/Mandante DC/Visitante DC na Noruega,
Empate/Mandante DC na Superettan). O "melhor" resultado (BTTS
Superettan, z=+0,99) tem uma tendência de melhora ano a ano (2024
muito negativo → 2026 fortemente positivo) que parece mais ruído de
amostra recente pequena do que sinal real — não passa nem perto da
barra "3 anos positivos" exigida em todo o resto do projeto.

## Atualização (mesmo dia) — grid pooled nas 3 ligas juntas

Lucas propôs uma ideia genuinamente boa (não é "continuar procurando
até achar" — é aumentar potência estatística de verdade): já que as 3
ligas são "próximas" (mesma região, calendário parecido), testar os
parâmetros com as apostas das 3 ligas JUNTAS (como se fossem ~9
temporadas), em vez de cada liga isolada com pouca amostra.

**Como foi feito certo**: o walk-forward de cada time continua rodando
DENTRO da própria liga (não faz sentido histórico de time norueguês
incluir jogos suecos) — só as APOSTAS resultantes de cada parâmetro
testado foram agregadas (pooled) na hora de medir ROI/z. Grid: `k_mando
∈ {None,0.2,0.35,0.5,0.7,1.0} × usar_estilo ∈ {True,False} ×
filtro_aderencia ∈ {0,0.5,0.65,0.8}` (48 combos), `multiplicador_dp=1.5,
limite_unilateral=2` fixos — mesmo grid usado historicamente pra
calibrar Over 2.5 no Brasil. Rodado pra BTTS e Over 2.5 (os 2 mercados
mais centrais do motor).

**Salvaguarda pré-declarada**: não aceitar um candidato só pelo z
pooled — exigir a MESMA direção em cada liga individualmente (senão é
a armadilha clássica de "agregado bom escondendo que só 1 liga está
carregando tudo", já vista antes neste projeto).

| Mercado | Melhor z pooled | ROI pooled (n) | Por liga |
|---|---|---|---|
| BTTS | -0,38 | -1,8% (n=305) | Noruega -13,8% \| Allsvenskan -3,4% \| Superettan +11,2% |
| Over 2.5 | +0,72 | +3,3% (n=328) | Noruega -4,9% \| Allsvenskan +0,8% \| Superettan +16,1% |

**Os dois "melhores" candidatos falham a salvaguarda**: em ambos, é a
Superettan sozinha carregando o resultado — Noruega fica claramente
negativa, Allsvenskan fica em torno de zero. Não é sinal
compartilhado, é uma liga isolada dentro do pool. Nem com mais amostra
(pooling) nem testando 48 parâmetros apareceu algo que passasse nem
perto da barra z≈2 usada em todo o resto do projeto.

## Atualização (mesmo dia) — hipótese de mecanismo: vantagem de mando mais fraca

Pesquisa acadêmica (Pollard & Gómez, 157 ligas / 169.752 jogos,
2006-2012) mostra que a Escandinávia tem vantagem de mando
estruturalmente mais fraca que a média mundial — achado robusto (um
modelo de regressão com geografia/torcida/viagem explica 76,7% da
variância entre países), não uma hipótese solta. Isso bate com o
padrão mais feio visto acima: os mercados que mais foram mal são
justamente os ligados a mando (Casa, Mandante DC, Visitante DC).

**Mecanismo testável**: `k_mando` (`pesos.ajuste_mando`) controla o
quanto o modelo separa o histórico de casa/fora do time-alvo — `k`
baixo = separação forte (mais "vantagem de mando" embutida), `k=1.0`
ou `k=None` = sem separação nenhuma. Os testes anteriores nesta liga
usaram `k_mando=0.35` (herdado do campeão Over 2.5 do Brasil) nos
mercados de mando — nunca tinha sido testado um `k_mando` mais alto
especificamente aí. Testei `k_mando ∈ {None, 0.35, 0.5, 0.7, 1.0}` nos
5 mercados de mando, nas 3 ligas (mesma base de parâmetros de antes,
`limiar_edge=5%`) — teste estreito, com hipótese declarada antes de
rodar, não um grid novo às cegas. (Confirmação técnica: `k_mando=None`
e `k_mando=1.0` deram exatamente os mesmos números em toda a tabela —
esperado, já que os dois equivalem a "sem ajuste de mando".)

**Resultado: hipótese parcialmente confirmada, mas sem abrir edge em
lugar nenhum.**

| Mercado | k=0.35 (baseline) | Melhor k testado | Interpretação |
|---|---|---|---|
| Casa — Noruega | z=-2,27 | z=-0,96 (k=0,5) | melhora real e grande |
| Casa — Superettan | z=-1,65 | z=-0,35 (k=1,0) | melhora real, monotônica |
| Casa — Allsvenskan | z=-0,62 | z=-0,41 (k=0,5) | melhora pequena |
| Mandante DC — Noruega | z=-2,23 | z=-1,94 (k=0,7) | melhora pequena, segue negativo forte |
| Mandante DC — Superettan | z=-2,53 | z=-2,53 (o próprio baseline) | não melhora |
| Mandante DC — Allsvenskan | z=-1,24 | — | **piora** com menos mando (z=-1,89 em k=1,0) |
| Visitante DC — Noruega | z=-2,56 | — | **piora** com menos mando (z=-3,01 em k=0,5) |
| Visitante DC — Superettan | z=-1,46 | z=-1,13 (k=1,0) | melhora pequena |
| Visitante DC — Allsvenskan | z=-0,70 | z=-0,38 (k=0,5) | melhora pequena |

O mercado "Casa" (o mais diretamente ligado à magnitude de vantagem de
mando) melhora de forma consistente e às vezes grande nas 3 ligas
conforme reduzimos a separação casa/fora — confirma que parte do viés
negativo original era mesmo o modelo importando uma vantagem de mando
forte demais para essas ligas, exatamente como a pesquisa sugeria.
Mas Mandante DC/Visitante DC não seguem o mesmo padrão de forma limpa
(Allsvenskan e Noruega chegam a piorar em algum ponto do grid) — o
mecanismo não é a explicação completa do que está errado nesses
mercados.

**O ponto decisivo**: mesmo no melhor `k_mando` de cada combinação,
NENHUM resultado chega perto de positivo — o menos ruim ainda é
claramente negativo (z entre -0,35 e -3,01). Ou seja: corrigir a
calibração de mando reduz o tamanho do erro, mas não revela edge
nenhum — o mercado (bookmaker) já precifica corretamente essa vantagem
de mando mais fraca, então mesmo com o modelo "certo" nesse aspecto
específico, não sobra vantagem para apostar. Confirma, com um
mecanismo real e não só amostra pequena, que o motor atual (mesmo
recalibrado neste eixo) não tem o que oferecer nessas 3 ligas.

## Atualização (mesmo dia) — outros 3 mecanismos investigados, nenhum passa no filtro inicial

Além do mando, pesquisei mais 3 mecanismos de futebol específicos da
região que poderiam abrir uma pista nova:

- **Turfe sintético**: descartado pela própria literatura — o estudo
  mundial mais robusto (times que trocaram de grama natural pra
  sintética, antes/depois do mesmo time) não achou diferença
  significativa de vantagem de mando (p=0,85). Sem base pra testar.
- **Congestionamento de jogos europeus** (fadiga pós-competição
  continental): só a Allsvenskan (1ª divisão) tem uns poucos clubes
  disputando competição europeia — amostra baixa demais pra valer o
  esforço de testar nessas 3 ligas.
- **Sazonalidade/temperatura nos gols** (há respaldo acadêmico real —
  Mišák 2026, Kyklos: clima frio reduz produtividade ofensiva —
  plausível aqui, já que o Nórdico joga março-novembro com bordas de
  temporada frias, diferente do Brasil que não tem essa sazonalidade
  estrutural). Testei de forma barata ANTES de qualquer backtest:
  gols reais por mês x probabilidade implícita da odd de Over 2.5, nas
  3 ligas. Resultado: Noruega e Superettan mostram MAIS gols em
  novembro (o mês mais frio) que em setembro/outubro — o oposto da
  hipótese. Só a Allsvenskan bate com "frio = menos gol" (2,31
  gols/jogo em novembro, o mais baixo do ano), mas com `n=32` — e é a
  mesma armadilha já vista hoje com o pooling (1 de 3 ligas carregando
  um padrão que as outras duas contradizem). Não passa no filtro
  inicial — não vale investir num backtest completo.

Nenhum dos 3 sobrevive nem ao teste inicial mais barato. O mando
segue sendo o único mecanismo real encontrado nessa pesquisa mais
profunda — e mesmo ele, como já visto acima, não abre edge de
verdade.

## Recomendação final (revista)

**Não seguir com nenhum critério nessas 3 ligas.** Testamos 3
hipóteses diferentes hoje — parâmetros isolados, pooling com mais
amostra, e agora um mecanismo de futebol real (vantagem de mando mais
fraca na Escandinávia, com respaldo acadêmico) — nenhuma abriu edge.
A última é a mais informativa: confirma que o motor está capturando
corretamente o mecanismo (o viés de Casa melhora como esperado), mas
mesmo corrigido não sobra vantagem contra a odd — não é falta de
calibração, é o mercado já precificando bem. Não vejo mais nada
razoável a tentar aqui sem esperar mais temporadas de dado acumularem
(2027+), ou sem um mecanismo de futebol novo e diferente deste (vantagem
de mando) para investigar.

