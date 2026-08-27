# Restringir odds ao bet365: BTTS/Cartões melhoram, Over 2.5 recalibrado cai

## Contexto

Lucas reportou um problema real no painel: a sugestão "Under 5.5
cartões" (Goiás x São Bernardo) não existia em nenhuma casa que ele usa
(Betano, bet365) — só Betano/bet365 ofereciam a linha 4,5.

Investigando via API, confirmei duas coisas:

1. **Nesse jogo específico, só 1 casa (Unibet) cotava cartões**, em 3
   linhas (3,5/4,5/5,5) empatadas em "1 casa cada" —
   `linha_mais_liquida` escolheu 5,5 de forma arbitrária (não havia
   diferença real de liquidez entre as linhas), e a odd usada vinha de
   uma casa que o Lucas não tem acesso. Coincidentemente, **bet365 não
   cotou NENHUM mercado nesse jogo específico** (nem gols, nem 1x2) —
   uma exceção, não a regra.
2. **Betano não existe no catálogo do Sportmonks pro Brasil** — só uma
   "Betano.de" alemã, que nunca aparece nos nossos dados. bet365
   (bookmaker_id=2) é a única casa real do Lucas coberta de forma
   confiável: 999/999 jogos Série A e 998/1000 Série B têm alguma odd
   do bet365 em algum mercado; 904/1000 (90,4%) especificamente no
   mercado de Cartões da Série B.

**Decisão**: restringir toda odd usada nas sugestões (produção) ao
bet365 especificamente — nunca cair pra outra casa quando bet365 não
cotar. Implementado em `sportmonks_adapter.flat_para_linha`
(`bookmaker_id=2` por padrão; `bookmaker_id=None` reproduz o
comportamento antigo, usado só pra comparar aqui).

## Resultado — revalidação dos 3 critérios, bet365 vs. média de todas as casas

| Critério | Fonte da odd | n | ROI | z | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|
| BTTS (Série A) | Média (antigo) | 175 | +17,3% | +2,33 | +2,44 | −0,10 | +2,04 |
| BTTS (Série A) | **bet365** | 187 | +20,9% | **+2,89** | +2,63 | **+0,31** | +2,36 |
| Over 2.5 recalibrado (Série A) | Média (antigo) | 94 | +25,4% | +2,28 | +1,44 | +0,33 | +2,83 |
| Over 2.5 recalibrado (Série A) | **bet365** | 98 | +14,6% | **+1,31** | +1,65 | **−0,72** | +2,08 |
| Cartões+Árbitro (Série B) | Média (antigo) | 395 | +5,5% | +1,19 | +1,65 | −0,42 | +1,69 |
| Cartões+Árbitro (Série B) | **bet365** | 386 | +9,7% | **+2,08** | +1,87 | **+0,80** | +1,63 |

(A linha "Média (antigo)" de Cartões+Árbitro usa o pull de dado mais
recente, não o número original documentado em 27/08 mais cedo — pull
de dado diferente, não é o mesmo snapshot; a comparação bet365-vs-média
DENTRO desta tabela, mesmo pull, é a que importa.)

## Interpretação

- **BTTS melhora com bet365** — inclusive o ano fraco (2025) vira
  positivo. Confirma o critério com ainda mais confiança.
- **Cartões+Árbitro melhora com bet365** — cruza z=2, positivo nos 3
  anos com folga maior que antes.
- **Over 2.5 recalibrado PIORA com bet365 — 2025 vira negativo.** Esse
  critério só parecia "positivo todo ano" na média de todas as casas;
  contra a odd real que o Lucas consegue pegar, tem um ano genuinamente
  perdedor. Não passa mais nem no critério mais permissivo ("sem ano
  negativo") que usamos pra aceitar Cartões+Árbitro.

## Recomendação

**Remover Over 2.5 recalibrado do painel** — feito em `previsao_dia.py`
(`CRITERIOS_GOLS`). Painel agora roda só **BTTS (stake normal) e
Cartões+Árbitro (stake reduzido)**, ambos revalidados e mais fortes com
a odd real do bet365 do que estavam com a média de todas as casas.

**Lição mais ampla**: qualquer achado calibrado numa média de múltiplas
casas do Sportmonks precisa ser revalidado contra a casa REAL que o
Lucas usa antes de virar produção — a média pode mascarar tanto
sinais reais (Over 2.5 parecia melhor do que é) quanto esconder sinais
mais fortes (BTTS/Cartões eram mais fortes do que a média sugeria).

Reprodução: `/tmp/.../scratchpad/revalidar_bet365.py`,
`revalidar_cartoes_bet365.py` (ad-hoc, não versionados), usando
`sportmonks_adapter.carregar_liga_sportmonks(path, bookmaker_id=...)`.
