# Over 2.5 recalibrado: readicionado com odd da Sbo, Betfair investigada

## Contexto

Over 2.5 recalibrado (Série A) tinha sido removido do painel mais cedo
neste mesmo dia (`docs/retrospectiva_bookmaker_bet365_2026-08-27.md`):
com odd só do bet365, 2025 vira negativo (z=−0,72) e o agregado cai de
z=+2,28 (média de todas as casas) pra z=+1,31.

Lucas pediu pra testar outras casas antes de descartar de vez ("não
tenho amor por casa de aposta"). Rodei os mesmos parâmetros já
homologados (`k_mando=0.35, usar_estilo=False, filtro_aderencia=0.65,
multiplicador_dp=1.5, limite_unilateral=4, n_historico=15,
limiar_edge=8%`) contra 12 bookmakers do catálogo do Sportmonks,
mesma disciplina de sempre (checar ano a ano, nunca só o agregado):
`/tmp/.../scratchpad/melhor_casa_over25.py`.

## Resultado — 12 bookmakers, ranking por z (n≥15)

| Bookmaker | n | ROI | z agregado | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| Pinnacle | — | — | **+2,31** | positivo | **−0,31** | positivo |
| **Sbo** | 80 | +23,6% | **+2,00** | +1,38 (n=21) | +0,28 (n=34) | +2,07 (n=25) |
| 188Bet | 19 | — | +2,22 | — | — | falta 1 ano inteiro |
| bet365 | 98 | +14,6% | +1,31 | +1,65 | −0,72 | +2,08 |
| (demais 8 bookmakers) | — | — | < 1,3 ou negativo | — | — | — |

(Tabela completa com os 12 bookmakers está no log do script ad-hoc; só
os relevantes pra decisão estão acima.)

## Interpretação — mesma barra "sem ano negativo" do Cartões+Árbitro

Ranking bruto por z é enganoso: **Pinnacle** lidera (z=+2,31), mas tem
2025 genuinamente negativo (z=−0,31) — mesmo problema estrutural que
derrubou o bet365. **188Bet** tem z alto (2,22) mas `n=19` e falta um
ano inteiro de dado — não conclusivo (amostra insuficiente pra
confiar, mesma cautela de sempre com `n` pequeno).

**Sbo (SBOBET, bookmaker_id=34)** é o único bookmaker testado que fica
acima de z≈2 com os **3 anos genuinamente positivos**: 2024 z=+1,38
(n=21), 2025 z=+0,28 (n=34), 2026 z=+2,07 (n=25). Aplicando a mesma
disciplina usada pra aceitar Cartões+Árbitro (evidência real mas não
tão forte quanto BTTS — trata como stake reduzido, não normal), Sbo é
o candidato correto, não o de maior z bruto.

**Ressalva explícita**: testar 12 bookmakers pra achar "o melhor z" é,
em menor escala, o mesmo risco de comparação múltipla dos grid
searches de parâmetro já feitos no projeto — por isso o critério
continua com stake REDUZIDO (mesmo tratamento do Cartões+Árbitro), não
promovido a stake normal.

## Investigação — "Betfair" no Sportmonks é a Exchange?

Lucas confirmou ter conta na Sbo, mas levantou que a **Betfair
Exchange** normalmente paga melhor que a Sbo nesse mercado (e possivelmente
nos outros), propondo usar Sbo como base estatística mas executar
sempre na Exchange na prática. Investigamos a entrada "Betfair"
(bookmaker_id=9) no catálogo do Sportmonks pra checar se é de fato a
Exchange ou a Sportsbook (produto fixo tradicional) deles — 4
evidências, todas na mesma direção:

| Evidência | Betfair (id=9) | bet365 (id=2) | Sbo (id=34) |
|---|---|---|---|
| Cobertura gols (mercado 80) | 8,9% (Série A) / 16,1% (Série B) | ~100% | 98,7-98,9% |
| Cobertura BTTS (mercado 14) | 8,9% / 16,0% | ~100% | **0%** |
| Cobertura cartões (mercado 255) | **0%** | 90,4-99,2% | 0% |
| Margem média (gols, amostra pareada n=20) | 8,08% | 5,80% | — |
| Margem média (BTTS, amostra pareada n=20) | 9,02% | 6,93% | — |
| Grade de odds (500 cotações O/U 2.5) | só 34 valores distintos, arredondados (2.20, 1.95, 1.85, 4.00, 8.00...) | grade similar | — |

Uma exchange peer-to-peer teria cobertura ampla (qualquer jogo com
liquidez mínima), margem baixa (1-3%, às vezes negativa pro "book" já
que quem cobra é o layer) e preços contínuos (não uma grade fixa de só
~34 valores). O que o Sportmonks tem cadastrado como "Betfair" tem
cobertura rala, margem MAIOR que o bet365, nunca aparece no mercado de
cartões, e usa uma grade de preço fixa — características de sportsbook
tradicional fraco, não de exchange.

**Conclusão**: a Betfair Exchange não está representada nos dados do
Sportmonks (só a Sportsbook deles, pior e mais rala que bet365/Sbo) —
não dá pra confirmar ou refutar estatisticamente a observação do Lucas
sobre ela pagar melhor. É experiência real de mercado dele, não algo
que o pipeline consegue validar.

## Decisão

- **Over 2.5 recalibrado READICIONADO ao painel** (`previsao_dia.py`,
  `CRITERIOS_GOLS`), stake reduzido, odd de referência **Sbo**
  (bookmaker_id=34) — não bet365.
- BTTS e Cartões+Árbitro continuam com bet365 (Sbo tem 0% de cobertura
  em BTTS e cartões — não pode virar base ali).
- **Nota de execução no painel**: cada sugestão de Over 2.5 mostra
  "odd de referência: Sbo — tente a Betfair Exchange antes, se a linha
  existir" — a Sbo garante que o preço mínimo aceitável existe de
  verdade; a Betfair Exchange, quando disponível e com odd igual ou
  melhor, é a escolha de execução na prática.

## Verificação

- `pytest metodologia_pesos/` — 184 testes passando (nenhuma mudança
  estrutural em `sportmonks_adapter.py`, que já suportava
  `bookmaker_id` desde a correção anterior).
- `gerar_painel_dia.gerar_html` testado manualmente com uma sugestão
  fabricada de Over 2.5/Sbo — nota de execução aparece corretamente no
  card.
- Reprodução: `/tmp/.../scratchpad/melhor_casa_over25.py` (ranking dos
  12 bookmakers, não versionado, mesmo padrão de todo script ad-hoc de
  validação do projeto).
