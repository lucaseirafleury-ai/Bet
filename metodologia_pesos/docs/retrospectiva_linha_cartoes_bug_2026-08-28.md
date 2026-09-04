# Retrospectiva — bug de seleção de linha em Cartões (28/08/2026)

## O relato

Lucas foi apostar num jogo do Goiás (Cartões+Árbitro, Série B) e viu que
o painel sugeria "Under 4,5", mas a casa dele só oferecia a linha
"Under 3,5" pra esse jogo — a sugestão simplesmente não existia na
prática. Pergunta: como garantir que o painel só sugira linhas que
realmente existem na casa de aposta?

## Investigação (só leitura, 3 rodadas)

**1. Onde a linha é escolhida.** `previsao_dia.py::avaliar_cartoes_arbitro`
chama `cartoes_arbitro.linha_mais_liquida(jogo_odds, MARKET_NUMBER_OF_CARDS)`
pra decidir QUAL total (3,5? 4,5? 5,5?) usar, e só depois
`odd_media_na_linha` busca a odd Over/Under nessa linha escolhida. As
odds que chegam em `jogo_odds` já vêm filtradas a bet365
(`sportmonks_adapter.flat_para_linha`, `bookmaker_id=BOOKMAKER_BET365`)
— confirmando que a restrição a bet365 (`docs/retrospectiva_bookmaker_bet365_2026-08-27.md`)
está em vigor tanto pra gols/BTTS quanto pra cartões.

**2. O defeito.** `linha_mais_liquida` foi desenhada pra escolher a
linha cotada pelo MAIOR número de bookmakers distintos — fazia sentido
quando `jogo['odds']` reunia cotações de várias casas ao mesmo tempo.
Depois da restrição a bet365, `jogo['odds']` sempre chega com **um
bookmaker só** — e cartões costuma ter várias linhas alternativas
cotadas pelo mesmo bookmaker (3,5/4,5/5,5...). Toda linha que o bet365
cota empata em "1 bookmaker distinto", e o `max()` do Python, diante de
um empate, devolve a primeira chave na ordem de inserção do dict — que
é a ordem arbitrária em que o Sportmonks serializou o array de odds,
não a linha que a casa realmente destaca. Esse empate não é uma
exceção rara: é o caso normal desde que a restrição a bet365 entrou em
vigor.

Confirmado com um exemplo real dos dados (Cuiabá x Goiás, 22/08/2026):
bet365 cotava cartões em 4,5 (1,72/2,00) e 5,5 (2,20/1,61), ambos
empatados em 1 bookmaker; a ordem bruta de inserção favorecia 5,5 —
prova de que a escolha dependia de ordem de serialização, não de
relevância.

**3. Não é staleness de dado.** O snapshot local
(`data/sportmonks_serieb/fixtures.jsonl`) só vai até 25/08 e não tinha
o jogo específico do Goiás de 28/08 — mas confirmei que isso não é o
problema: `previsao_dia.gerar_sugestoes_do_dia` usa
`sportmonks_client.puxar_fixtures_futuros`, que busca fixtures futuros
**direto na API a cada execução** (nunca grava em arquivo, sempre
fresco) — o snapshot estático desatualizado é irrelevante pro bug
relatado.

**4. Sem campo de "linha principal" nos dados.** Verifiquei se o
Sportmonks expõe algum campo (ex.: `sort_order`, `original_label`,
flag de linha em destaque) que identificasse a linha "oficial" — não
existe: os dados salvos (e o que `sportmonks_client.flatten_fixture`
extrai da resposta bruta da API) só têm `{bookmaker_id, label, total,
value}`. Não dá pra confiar num campo que não existe — a correção
precisou ser uma heurística de código, não um dado disponível.

## A correção

Em `cartoes_arbitro.linha_mais_liquida`: quando mais de uma linha
empata no número de bookmakers distintos (o caso normal hoje), o
desempate agora escolhe a linha com odd Over/Under mais próxima da
**paridade** (`min(abs(odd_over_médio - odd_under_médio))`) — proxy
padrão de mercado pra "linha principal": a linha que a casa destaca
tende a ser a mais equilibrada, enquanto linhas alternativas se afastam
da paridade conforme se distanciam da linha central. Quando NÃO há
empate, o comportamento não muda (a contagem de bookmakers decide
sozinha, como antes).

**Limite explícito, importante de entender**: essa é uma heurística,
não uma garantia. O Sportmonks não expõe qual linha a casa realmente
destaca — a proximidade de paridade é a melhor aproximação disponível
com o dado que temos, mas pode errar em casos raros (ex.: um jogo onde
a linha "certa" por algum motivo não é a mais equilibrada). **Lucas
deve sempre conferir a linha exata na casa antes de apostar**,
especialmente em cartões — mercado com várias linhas alternativas —
mesmo depois desta correção.

## Revalidação

Como `checar_decaimento.py` reusa a mesma `linha_mais_liquida` da
produção (nunca duplica número), rodei a checagem mensal de novo com a
correção aplicada, comparando com o baseline gravado mais cedo hoje
(pré-correção):

| | Acumulado (2024+, n=386) | Últimos 90 dias (n=107) |
|---|---|---|
| Pré-correção | ROI+9,7% z=+2,08 acerto=59% | ROI+12,9% z=+1,48 acerto=62% |
| Pós-correção | ROI+9,4% z=+2,01 acerto=59% | ROI+13,8% z=+1,60 acerto=63% |

A mudança é pequena e nos dois casos o critério continua acima do
limiar de significância (z≈2) no acumulado, com a janela recente até
ligeiramente melhor — a correção reordenou escolhas de linha em uma
fração dos jogos, mas não inverteu o sinal nem revelou que o edge
dependia da escolha errada. BTTS e Over 2.5 (Série A) não usam
`linha_mais_liquida` — não são afetados por este bug, confirmado pela
reexecução (números idênticos ao baseline).

## Recomendação final

Correção aplicada em produção (`cartoes_arbitro.py`), testes novos
cobrindo o caso de empate (`test_cartoes_arbitro.py`), critério
revalidado e mantido em stake reduzido — nenhuma mudança de status.
Ressalva permanente: sempre conferir a linha exata na casa de aposta
antes de apostar em cartões, já que a escolha automática é uma
heurística sem garantia absoluta de bater 100% com o que a casa exibe.
