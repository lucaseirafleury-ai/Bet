# Protocolo de Apostas — Regras Persistentes

**🔄 Migração concluída (27/08/2026) — saiu do FootyStats (upload manual
de CSV), foi pra 100% Sportmonks com painel automatizado.** Lucas
cancelou o FootyStats. Tudo abaixo desta nota que fala em "critério
campeão"/`k_mando`/etc. foi calibrado em cima do FootyStats — histórico
de como se chegou aos parâmetros atuais, não mais a fonte de dado em
produção. **3 critérios rodando no painel diário**:
- ✅ **BTTS (Série A)** — stake normal, odd bet365. z=+2,89 com odd real
  do bet365 (mais forte até que a média de todas as casas do
  Sportmonks, z=+2,33).
- ✅ **Over 2.5 recalibrado (Série A)** — stake reduzido, odd **Sbo**
  (bookmaker_id=34), não bet365. Foi removido em 27/08/2026 (com odd do
  bet365, 2025 vira negativo — z 2,28→1,31) e READICIONADO no mesmo dia
  depois de testar 12 bookmakers: Sbo é o único acima de z≈2 sem
  nenhum ano negativo (z=+2,00, n=80, ROI+23,6%; 2024 z=+1,38, 2025
  z=+0,28, 2026 z=+2,07). Execução real: tentar a Betfair Exchange
  primeiro (Lucas relata odd geralmente melhor nesse mercado — não
  validável no dado do Sportmonks, que só tem a Betfair Sportsbook
  cadastrada e com cobertura/margem piores que o bet365), caindo pra
  Sbo como preço já confirmado. Ver
  `docs/retrospectiva_over25_sbo_betfair_2026-08-27.md`.
- ✅ **Cartões+Árbitro (Série B)** — stake reduzido, odd bet365. z=+2,08
  com odd real do bet365 (também mais forte que a média, z=+1,19).
- Série B Over 2.5/BTTS seguem sem edge, confirmado de novo.

**⚠️ Odds restritas por critério a UMA casa específica (não mais média
de todas as casas do Sportmonks), desde 27/08/2026.** Lucas reportou
uma sugestão de cartões que não existia em nenhuma casa que ele usa —
investigando, o Sportmonks agrega dezenas de casas internacionais
(Unibet, Pinnacle, 10Bet...) que ele não tem acesso; Betano nem existe
no catálogo pro Brasil. bet365 é a casa padrão (única coberta de forma
confiável: 999/999 Série A, 998/1000 Série B) — usada em BTTS e
Cartões+Árbitro. Over 2.5 é a exceção: usa Sbo especificamente (ver
acima), porque é a única casa testada que passa na barra "sem ano
negativo" pra esse critério. Revalidação completa com bet365-só mudou a
recomendação original: BTTS e Cartões+Árbitro ficaram MAIS fortes,
Over 2.5 recalibrado ficou mais fraco com bet365 mas se recuperou com
Sbo. Ver `docs/retrospectiva_bookmaker_bet365_2026-08-27.md` e
`docs/retrospectiva_over25_sbo_betfair_2026-08-27.md`.

**Painel automatizado**: `metodologia_pesos/previsao_dia.py` (previsão
ao vivo, reaproveitando `retrospectiva.prever_jogo` via linha sintética
— ver `sportmonks_adapter.py`) + `gerar_painel_dia.py` (monta o HTML)
+ rotina diária (Claude Code Routine, 08h BRT, sem notificação
proativa) que republica o Artifact. Depende de `SPORTMONKS_TOKEN`
configurado como variável de ambiente persistente no ambiente do
Claude Code (não em arquivo/sessão — precisa sobreviver entre
disparos da rotina).

Ver `docs/retrospectiva_validacao_100_sportmonks_2026-08-27.md`,
`docs/retrospectiva_over25_sportmonks_2026-08-27.md` e
`docs/retrospectiva_bookmaker_bet365_2026-08-27.md`. O conteúdo
histórico abaixo (calibração em cima do FootyStats) fica preservado
como registro — não é mais o critério de aposta vigente pra produção
nova, mas explica o raciocínio que levou até aqui.

**⚠️ Leitura obrigatória antes de qualquer outra coisa neste arquivo —
seção "Grid completo: melhor achado da sessão (25/08/2026)" logo mais
abaixo.** Os parâmetros de `k_mando`/`usar_estilo`/`filtro_aderencia` da
tabela logo abaixo foram otimizados por ACERTO (Over/Under, BTTS) —
vantagem competitiva real (ROI contra odd de mercado) é outra métrica.
**Critério de aposta ATUAL (25/08/2026) pra Over 2.5 na Série A:
`k_mando=0.5, usar_estilo=False, filtro_aderencia=0.8,
multiplicador_dp=1.5, limite_unilateral=2, limiar_edge=5%`** — z=2,23
no período completo 2023-2026 (n=221), sem ano negativo real. Substitui
a recomendação anterior (neutro + `limiar_edge≥8%`).

**⚠️ n=221/z=2,23 é o número ORIGINAL (calculado quando só havia dado
de 2023-2026 disponível) — desatualizado.** Com o histórico 2016-2022
disponível, jogos do início de 2023 que antes eram pulados (sem
histórico suficiente) agora entram na avaliação, e o ROI deles puxa a
média pra baixo: recalculado com o histórico completo, o mesmo critério
dá **n=278, ROI+8,7%, z=+1,37** (26/08/2026, ver
`docs/retrospectiva_estabilidade_era_2026-08-26.md`, seção "Nota
técnica sobre a diferença de `n`"). Esse n=278/z=1,37 é o número que
`checar_decaimento.py` reporta a partir de agora — trate-o como o valor
de referência atual, não o n=221 antigo.

**⚠️ Atualização importante (26/08/2026) — os z-scores acima NÃO se
sustentam fora de 2023-2026.** Com histórico estendido pra 2016-2026 (11
anos), os dois critérios acima têm z≈0 no agregado completo — negativos
em 2016-2019 e 2020-2022, só positivos no bloco 2023-2026 (onde foram
calibrados). Isso não invalida o uso atual (2023-2026 continua sendo o
período relevante pra apostar agora), mas rebaixa a confiança de "forte"
pra "moderada, específica do período recente, com hipótese plausível de
causa" — ver seção "Estabilidade por era" mais abaixo para a análise
completa antes de tratar qualquer z-score deste documento como prova
definitiva.

**Segundo critério (25/08/2026) pra BTTS na Série A:
`k_mando=0.7, usar_estilo=True, filtro_estilo=0.8,
filtro_favoritismo=0.65, multiplicador_dp=1.5, limite_unilateral=2,
n_historico=10, limiar_edge=5%`** — z=2,65, n=207, ROI+17,9%, sem
nenhum ano negativo — ver seção "BTTS com parâmetros próprios" mais
abaixo.

**Nível de confiança extra**: quando um jogo aciona os DOIS critérios
acima ao mesmo tempo (113 jogos, ~32/ano), z=+3,40, ROI+22,7%, sem
nenhum ano nem perto de negativo — o resultado mais forte da sessão,
mas com ressalva de comparação múltipla empilhada (3 camadas de
seleção) — ver seção "Dupla confirmação" mais abaixo antes de tratar
como prova definitiva.

Não apostar na Série B por nenhum critério de PADRÃO ainda — ver a seção
nova pro raciocínio completo. **Exceção, com stake reduzido**: Cartões +
Árbitro (Série B) — ver seção "Terceiro critério (stake reduzido)" logo
abaixo.

## Terceiro critério (stake reduzido) — Cartões + Árbitro, Série B (27/08/2026)

Diferente dos dois critérios acima (Over 2.5/BTTS, ambos z>2, stake
normal), este NÃO passa do limiar de significância padrão do projeto
— é adotado com **stake reduzido (~1/3 do normal)** por decisão
explícita do Lucas, não porque a evidência estatística seja
equivalente. Ver `docs/retrospectiva_escanteios_cartoes_2026-08-27.md`
pra todo o histórico de como se chegou aqui (por que cartões/escanteios
"puros" não têm edge, por que o árbitro ajuda).

**Parâmetros**: modelo de times com o corte de outlier do BTTS
reescalado pra cartões (`k_mando=0.7, usar_estilo=True,
filtro_estilo=0.8, filtro_favoritismo=0.65, multiplicador_dp=1.5,
limite_unilateral=2, limite_unilateral_por_campo={cartoes_pro: 3.8,
cartoes_contra: 3.8}, n_historico=10`), combinado com a média histórica
de cartões do árbitro (walk-forward, mínimo de 10 jogos antes de
confiar nela) via `pred = pred_time×0,7 + media_arbitro×0,3`. Aposta no
mercado real "Number of Cards" (odds do Sportmonks, não do FootyStats)
sem limiar de edge mínimo (`limiar_edge=0.0` — os números abaixo foram
medidos assim, mudar isso exige revalidar).

**Evidência**: z≈1,73 combinado nos 2 anos mais recentes e menos
inflados (2025 z=+0,73 n=186; 2026 z=+1,75 n=167), positivo isoladamente
nos 3 anos com dado disponível (2024/2025/2026). O agregado completo
(incluindo 2024, que tem só n=28 e infla o z) chega a z≈2,3 — não tratar
esse número isolado como prova, o z≈1,73 é a leitura mais honesta.

**Implementação em produção**: `metodologia_pesos/cartoes_arbitro.py`
(funções puras, testadas em `test_cartoes_arbitro.py`) +
`sportmonks_pull_serieb_cartoes.py` (atualiza
`data/sportmonks_serieb_cartoes/fixtures.jsonl` — precisa de
`SPORTMONKS_TOKEN` no ambiente, rodar de novo periodicamente pra manter
o dado atualizado, mesmo esforço que já é feito com os CSVs do
FootyStats). `checar_decaimento.py` já inclui esse critério na checagem
semanal (pula com aviso se o arquivo do Sportmonks não existir).

**Acompanhamento**: a checagem semanal vai recalculando o z conforme
mais jogos de 2026 entram — se subir e se sustentar acima de z≈2 de
forma consistente (não só um ano isolado), promover pra stake normal;
se decair, reduzir mais ou descartar (mesmo tratamento que qualquer
outro critério deste documento).

## Quarto critério (stake reduzido) — Over 2.5 recalibrado, Série A (27/08/2026)

**✅ ATIVO no painel — odd de referência Sbo (bookmaker_id=34), não
bet365.** Histórico do mesmo dia: a seção abaixo foi validada com a
MÉDIA de todas as casas do Sportmonks. Ao restringir pra bet365 (a casa
padrão do painel — ver seção "Odds restritas" no topo deste arquivo),
2025 vira negativo (z=−0,72) e o agregado cai de z=+2,28 pra z=+1,31 —
critério foi removido do painel nesse ponto. Lucas pediu pra testar
outras casas antes de descartar; testando os mesmos parâmetros contra
12 bookmakers do catálogo Sportmonks, **Sbo é o único que fica acima de
z≈2 com os 3 anos genuinamente positivos** (z=+2,00 agregado, n=80,
ROI+23,6%; 2024 z=+1,38 n=21, 2025 z=+0,28 n=34, 2026 z=+2,07 n=25) —
readicionado ao painel usando Sbo como casa de referência. Ver
`docs/retrospectiva_bookmaker_bet365_2026-08-27.md` e
`docs/retrospectiva_over25_sbo_betfair_2026-08-27.md`.

**Nota de execução (Betfair Exchange)**: Lucas relata que, na prática,
a Betfair Exchange costuma pagar melhor que a Sbo nesse mercado (e
possivelmente nos outros). Investigamos a entrada "Betfair"
(bookmaker_id=9) no catálogo do Sportmonks — não é a Exchange: cobertura
rala (8,9-16,1% dos jogos, contra 98,7-98,9% da Sbo), margem MAIOR que
o bet365 (8,08% vs 5,80% em gols) e uma grade fixa de só 34 valores de
odd distintos — características de sportsbook tradicional fraco, não
de uma exchange peer-to-peer (que teria margem baixa e preços
contínuos). A Betfair Exchange simplesmente não está representada no
dado do Sportmonks — não dá pra validar estatisticamente a observação
do Lucas. Recomendação: a Sbo é a odd de referência pra validar o
critério (garante que o preço mínimo aceitável existe de verdade);
na execução real, tentar a Betfair Exchange primeiro (se a linha
existir e a odd for igual ou melhor), caindo pra Sbo como preço já
confirmado.

Os parâmetros antigos de Over 2.5 (calibrados em cima do FootyStats)
não se sustentam 100% em cima do Sportmonks (z caiu de +2,23 pra
+0,49) — ver `docs/retrospectiva_over25_sportmonks_2026-08-27.md`.
Recalibração dedicada achou um candidato novo, validado com a mesma
disciplina de treino/holdout usada no resto do projeto: **`k_mando=0.35,
usar_estilo=False, filtro_aderencia=0.65, multiplicador_dp=1.5,
limite_unilateral=4, limiar_edge=8%`**.

**Por que stake reduzido, não normal**: o parâmetro foi escolhido
olhando só 2024+2025 (honesto, sem espiar 2026) — nesse treino, o z
combinado é só +1,15, fraco sozinho. O que sustenta a decisão é o
holdout de 2026 (nunca usado na escolha): z=+2,83, mas com `n=23` —
amostra pequena, mesmo padrão de cautela do Cartões+Árbitro. Positivo
nos 3 anos disponíveis (2024/2025/2026), sem nenhum ano negativo —
critério real, ainda não comprovado ao nível dos dois primeiros.

**Acompanhamento**: mesmo tratamento do Cartões+Árbitro — reavaliar
conforme 2026 completa e 2027 começa a entrar na amostra.

## Painel automatizado (27/08/2026)

Substituiu a planilha manual. Roda 100% em cima do Sportmonks:
- `sportmonks_client.py` — pull de fixtures finalizados (histórico) e
  futuros (odds pré-jogo) das duas ligas.
- `sportmonks_adapter.py` — traduz fixture do Sportmonks pro formato
  que o motor já entende; fixtures futuros viram uma linha SINTÉTICA
  (placar placeholder nunca lido de verdade) — é assim que
  `retrospectiva.prever_jogo` (feito pra backtesting) prevê jogos que
  ainda não aconteceram, sem duplicar lógica em lugar nenhum.
- `previsao_dia.py` — gera as sugestões dos 3 critérios ativos (BTTS,
  Over 2.5 recalibrado, Cartões+Árbitro) pros próximos dias.
- `gerar_painel_dia.py` — monta o HTML publicado como Artifact.
- **Rotina diária** (Claude Code Routine, 08h BRT, sem notificação
  proativa — só o painel) republica o Artifact automaticamente todo
  dia. Depende de `SPORTMONKS_TOKEN` configurado como variável de
  ambiente PERSISTENTE no ambiente do Claude Code (precisa sobreviver
  entre disparos da rotina — diferente do token usado durante o
  desenvolvimento, que só existia na sessão).

## Acerto ≠ vantagem real (24/08/2026)

Toda calibração até aqui (`k_mando`, `usar_estilo`, `filtro_aderencia`,
`estilo_por_mando`) otimizou taxa de acerto de Over/Under 2.5 e BTTS.
Isso NÃO mede vantagem competitiva — uma taxa de acerto de 55% não vale
nada se a odd de mercado já embutia essa probabilidade ou mais. Vantagem
real é a probabilidade do modelo ser maior que a probabilidade implícita
na odd — só aí vale apostar. Ver
`docs/retrospectiva_roi_2026-08-24.md` para o relatório completo.

Implementado: `pesos.probabilidade_over`/`probabilidade_btts` (gols
esperados → probabilidade via Poisson), `pesos.probabilidade_implicita`/
`probabilidade_implicita_2vias` (odd real → probabilidade de mercado,
removendo margem quando os 2 lados do mercado estão disponíveis), e
`retrospectiva.simular_apostas` (só aposta quando o modelo supera o
mercado por um `limiar_edge`, com odd e resultado reais — ROI, lucro,
taxa de acerto DAS APOSTAS, não de todos os jogos).

**Achado — inverte o que a calibração por acerto sugeria:**
- **Série A** (parâmetros neutros, nunca "vencedores" de nenhum grid de
  acerto): mostra vantagem real e CRESCENTE com a exigência de edge —
  ROI de +9% (sem filtro de edge) até +35,8% (edge ≥8%), estatisticamente
  significativo nos limiares mais altos (z=2,24 em Over 2.5, z=2,72 em
  BTTS). Quanto mais o modelo discorda da odd, mais ele acerta — assinatura
  de probabilidade bem calibrada.
- **Série B** (`k=0.5, sem estilo, filtro=0.8` — o "vencedor" do holdout
  por acerto): **não mostra vantagem nenhuma contra odd real**, e piora
  conforme se exige mais edge em Over 2.5 (+6,8% → −5,7%). Provavelmente
  aprendeu a concordar com o consenso do mercado (acerta replicando a odd,
  não discordando dela) — acerto alto, edge baixo/negativo.

**Isso muda a prioridade**: o próximo passo de maior alavancagem é
recalibrar `k_mando`/`usar_estilo`/`filtro_aderencia` otimizando ROI
simulado (não mais `acerto_over25`) — a infraestrutura de grid/holdout já
existe, só falta trocar a métrica.

## Recalibração por ROI não superou o neutro (25/08/2026)

Feita a recalibração sugerida acima — grid de 48 combinações
(`k_mando × usar_estilo × filtro_aderencia`) treinado só em 2025,
ordenado por ROI simulado (não acerto), top candidatos revalidados em
holdout 2026. Ver `docs/retrospectiva_roi_calibracao_holdout_2026-08-25.md`
para o relatório completo.

**Resultado: nenhuma combinação encontrada bate o parâmetro neutro
(sem ajuste) no critério que importa — z-score/significância
estatística.** O mesmo padrão de overfitting que já tinha derrubado
`k_mando`(Série A) e `estilo_por_mando` se repetiu pra ROI: na Série B, o
"vencedor" de treino (ROI +22%) virou ROI −14% no holdout; na Série A, o
grid achou candidatos com ROI de holdout positivo mas mais fracos
(z≈1.0-1.5) que o que já estava documentado (z=2.24 Over 2.5, z=2.72
BTTS, ambos em `limiar_edge=8%`). O motivo: ranquear por ROI de treino
prefere limiares de edge baixos (mais apostas, ROI mais "estável" na
amostra pequena) — mas o sinal genuíno mora no limiar mais alto e
seletivo (8%), que fica sub-representado no treino.

**Decisão**: manter os parâmetros neutros (`k_mando=None,
usar_estilo=True, filtro_aderencia=0.65, estilo_por_mando=False`) —
não os "vencedores por acerto" da tabela abaixo — como critério de
APOSTA (não de acerto). Na prática:
- **Série A**: exigir `limiar_edge ≥ 8%` em Over 2.5/BTTS antes de
  apostar — único ponto com sinal estatisticamente defensável (z>2)
  encontrado até agora.
- **Série B**: não apostar por este critério ainda — nenhuma
  configuração testada passou de z≈0.9.

**⚠️ Atualizado 25/08/2026 — repetido com 3 temporadas de treino
(2023+2024+2025), ver `docs/retrospectiva_roi_calibracao_2023_2025_holdout_2026-08-25.md`:**
- Série A: achado se REFORÇOU com mais dado (BTTS edge=8% subiu de
  z=2,72 pra **z=2,91**) — mantém neutro + `limiar_edge≥8%`.
- **Série B Over 2.5**: piorou — mesmo o parâmetro neutro virou
  claramente negativo (ROI −7,9% a −21,4% conforme o limiar) com mais
  histórico. Reforça: não apostar aqui.
- **Série B BTTS**: primeira vez que o grid supera o neutro — considerar
  `k_mando=0.2, usar_estilo=True, filtro_aderencia=0.65, limiar_edge=5%`
  (z≈0,9-1,0, ROI +12-14%, n=53-54) em vez do neutro puro (z≈0). Ainda
  não é significativo (z<2) — promissor, não comprovado.

**❌ Reteste 27/08/2026 — Série B BTTS NÃO se sustenta, descartar.**
O n=53-54/z≈0,9-1,0 documentado acima era só o holdout de 2026 — ao
rodar o MESMO parâmetro (`k_mando=0.2, usar_estilo=True,
filtro_aderencia=0.65, limiar_edge=5%`) no período completo 2023-2026
(n=262), o quadro muda bastante: **não é consistente ano a ano**
(2023: ROI−6,7%/z=−0,40; 2024: ROI−1,8%/z=−0,15; 2025: ROI+14,8%/
z=+1,20; 2026: ROI+11,7%/z=+0,89) — 2 dos 4 anos são negativos, o
"platô robusto" descrito antes não existia no período inteiro, só
apareceu no recorte de holdout que foi olhado na época. Agregado
completo: z=+0,76 (mais fraco que o já modesto z≈0,9-1,0 original).

Testando também a troca de odds por Sportmonks (mesmo padrão usado em
Over 2.5/BTTS da Série A, jogos 2024-2026 pareados): o pouco sinal que
sobrava praticamente desaparece — FootyStats z=+1,04 (n=216) vs.
Sportmonks **z=+0,16** (n=213), caindo em todos os 3 anos
individualmente. Mesmo padrão já visto no Over 2.5 da Série A (odds
mais "afiadas" reduzem o edge medido), mas aqui o efeito é decisivo:
não sobra nada defensável.

**Conclusão: Série B BTTS não é um segundo caso de "cartões+árbitro"**
(que ao menos é positivo nos 3 anos isolados). Aqui 2 anos são
diretamente negativos e o sinal restante é odd-dependente. Não
incorporar como critério nem como pista em observação — item fechado,
removido do backlog do README.

**⚠️ Testado 25/08/2026 — Over 1.5/3.5/4.5 NÃO diversificam** (Lucas
perguntou como reduzir a variância ano a ano do Over 2.5; cartões/
escanteios não têm odd real no CSV, então a alternativa era mais linhas
de gols). Simulação 2023-2026 nas duas linhas mostra ROI negativo em
TODOS os limiares/anos — Over 3.5/4.5 especialmente ruins (ROI até
−81%). O edge que existe fica concentrado só em Over 2.5/BTTS, não
generaliza pras linhas vizinhas. **Não apostar Over 1.5/3.5/4.5.** Ver
`docs/retrospectiva_over_1_5_3_5_4_5_2026-08-25.md`.

**⚠️ IMPORTANTE — o z=2,24/2,91 da Série A é só o holdout de 2026, não
prova de vantagem no longo prazo.** Simulando "se tivéssemos apostado
desde 2023" com os parâmetros neutros + `limiar_edge≥8%` (walk-forward
2023-2026 inteiro, sem cortar só o holdout): **Over 2.5 dá ROI
acumulado −2,3%** (2023 −28,4%, 2024 +11,5%, 2025 −15,7%, 2026 +35,8% —
2026 foi o ano bom, não a média); **BTTS dá +5,0%** acumulado, mas
também com variação enorme ano a ano (−19,1% a +37,8%). Ou seja: **não
tratar Over 2.5/BTTS como "edge comprovado que sempre ganha dinheiro"**
— é um sinal estatisticamente distinguível de zero no holdout mais
recente, mas o histórico completo mostra metade dos anos no prejuízo.
Qualquer decisão de apostar dinheiro real precisa considerar essa
variância, não só o z-score do último ano.

**⚠️ Testado 25/08/2026 — Favorito DC (sozinho e combinado) NÃO tem
edge** (Lucas relatou que combinar Over/Under + Dupla Chance do
favorito funcionou pra ele no passado; pediu pra buscarmos qualquer
metodologia com ROI positivo sucessivo). Implementado
`pesos.probabilidade_resultado` + `retrospectiva.simular_apostas_combo`
(múltipla genérica). Resultado: Favorito DC sozinho é sempre negativo
nas duas ligas (ROI −3% a −17%); combinado com Over 2.5 piora ainda
mais (até −34% na Série B); combinado com BTTS é o menos ruim mas sem
significância (z=0,59 Série A, z=1,06 Série B — e esse último inflado
por 1 ano de amostra minúscula, n=8). **Não incorporar Favorito DC como
critério de aposta.** Ver `docs/retrospectiva_favorito_dc_2026-08-25.md`.

**⚠️ Testado 25/08/2026 — Corte de outlier mais apertado melhora
Over 2.5 na Série A (primeira melhoria real sobre o neutro)** — Lucas
pediu pra variar `multiplicador_dp`/`limite_unilateral` (nunca tinham
sido testados). Comparando ROI/z-score do período completo 2023-2026
(não só o holdout): `multiplicador_dp=1.5, limite_unilateral=2` dá
Over 2.5 com z=+1,50 (ROI+16,2%, n=99) contra z=−0,31 (ROI−2,3%) do
padrão (`2.5, 4`) — melhoria confirmada como platô (1,25 e 1,5 dão
resultado parecido, não é célula isolada de sorte) e com estabilidade
ano a ano melhor (só 1 ano negativo, era 2). Ainda z<2 (não
"comprovado"), e Série B não mostrou o mesmo padrão. **Considerar
`multiplicador_dp=1.5, limite_unilateral=2` pra Over 2.5 na Série A**
em vez do padrão. Ver
`docs/retrospectiva_corte_outlier_2026-08-25.md`.

## Grid completo: melhor achado da sessão (25/08/2026)

Combinando tudo — `k_mando × usar_estilo × filtro_aderencia` × corte de
outlier (apertado vs. padrão), reincluindo Over 1.5/3.5/4.5 na busca —
encontrou o candidato mais forte de toda a sessão:

**Over 2.5, Série A: `k_mando=0.5, usar_estilo=False,
filtro_aderencia=0.8, multiplicador_dp=1.5, limite_unilateral=2,
limiar_edge=5%` → z=+2,23, ROI+16,0%, n=221 (período completo
2023-2026), SEM ano realmente negativo** (2023 +10,2%, 2024 +35,8%,
2025 −1,0%, 2026 +25,4%). É o primeiro candidato do projeto todo que
passa de z=2 no período completo (não só no holdout isolado) com
amostra grande (n=221, mais que o dobro de qualquer achado anterior).

BTTS também tem candidatos fortes (`k=0.7, usar_estilo=True,
filtro_aderencia=0`, mesmo corte, edge=8%: z=+2,13, ROI+21,5%, n=95),
mas com pior consistência ano a ano (2025 sempre fraco nos candidatos
testados) — considerar validado com mais cautela que Over 2.5.

Série B continua sem qualquer configuração defensável — os melhores
candidatos do mesmo grid deram ROI negativo ou catastrófico
(Over 3.5/4.5 até −100%, amostra minúscula).

**Este é agora o critério de aposta recomendado pra Over 2.5 na Série
A** — substitui o critério anterior (neutro + `limiar_edge≥8%`). Ver
`docs/retrospectiva_grid_completo_2026-08-25.md` pro raciocínio
completo, incluindo por que o combo dos 3 parâmetros funciona melhor
que qualquer um isolado, e as ressalvas (risco residual de comparação
múltipla ao testar 96 combinações).

Versão inicial, consolidada a partir do que estava espalhado nas skills
`copa-planilha-dia`/`serie-b-planilha-dia` (que citavam um
`briefing_*.md`/`PROTOCOLO_BETS_LUCAS.md` vivendo só em pasta efêmera de
sessão, não versionado). **Este arquivo existe pra parar de se perder entre
sessões — complete/corrija o que estiver incompleto ou desatualizado.**

## Teto de odd máxima por mercado (25/08/2026)

Testado um teto de odd máxima na entrada (Over1.5≤1,5 / Over2.5≤3 /
Over3.5≤6 / Over4.5≤7 / BTTS≤2) em cima do critério campeão acima.
**Não muda o critério de Over 2.5**: o teto de 3,0 não filtra nenhuma
aposta desse critério (com/sem teto dão exatamente `n=221, ROI+16,0%,
z=+2,23`) — não precisa adicionar. Pra BTTS o teto (≤2,0) parecia
melhorar (z subia), mas isso usava os parâmetros de modelo do combo de
Over 2.5, não os de BTTS — **testado depois com os parâmetros certos de
BTTS e o teto PIORA** (ver seção seguinte). Ver
`docs/retrospectiva_odd_maxima_2026-08-25.md` pro detalhamento completo
por mercado/liga/edge (mantido como registro histórico do teste, já
corrigido pela seção abaixo).

## BTTS com parâmetros próprios — segundo critério de aposta (25/08/2026, atualizado)

Testado o candidato de BTTS (`k_mando=0.7, usar_estilo=True,
filtro_aderencia=0, multiplicador_dp=1.5, limite_unilateral=2,
limiar_edge=8%`) com seus PRÓPRIOS parâmetros de modelo (não os de Over
2.5) e o teto de odd (≤2,0): **o teto PIORA o resultado** (z cai de
+2,13 pra +1,18) — descartar essa ideia pra BTTS.

**Sem teto, esse candidato confirmava z=+2,13, ROI+21,5%, n=95**
(período completo), com 2 dos 4 anos negativos (2023: −7,7%, 2025:
−6,7%) — mais fraco que o Over 2.5. Ver
`docs/retrospectiva_btts_final_2026-08-25.md`.

**Superado por um candidato melhor** (variando `n_historico` e
separando os filtros de estilo/favoritismo, nunca testados antes):
`k_mando=0.7, usar_estilo=True, filtro_estilo=0.8,
filtro_favoritismo=0.65, multiplicador_dp=1.5, limite_unilateral=2,
n_historico=10, limiar_edge=5%` → **n=207, ROI+17,9%, z=+2,65, SEM
nenhum ano negativo** (2023 +18,3%, 2024 +19,0%, 2025 +1,9%, 2026
+37,2%). Ver `docs/retrospectiva_novos_eixos_2026-08-25.md`.

**Este é agora o segundo critério de aposta recomendado, em paralelo
ao Over 2.5** — substitui o candidato anterior. Volume combinado:
Over 2.5 (~63/ano) + BTTS (~59/ano) ≈ 122 apostas/ano.

## Dupla confirmação (Over 2.5 + BTTS no mesmo jogo) — resultado mais forte, com ressalva (25/08/2026)

Quando os dois critérios acima disparam no MESMO jogo (113 jogos, ~32/ano),
apostando as duas pernas separadamente (2 stakes por jogo, não é
combo/parlay): **n=226, ROI+22,7%, z=+3,40 — SEM nenhum ano nem perto de
negativo** (2023 +12,0%, 2024 +37,6%, 2025 +8,2% — o melhor resultado
que 2025 teve em qualquer critério da sessão, 2026 +34,1%).

**Ressalva importante**: isso empilha uma TERCEIRA camada de seleção em
cima das duas já feitas (grid do Over 2.5 + grid do BTTS) — é esperado
que a interseção de dois sinais positivos performe melhor, não é
necessariamente uma vantagem nova e independente. As duas apostas do
mesmo jogo também são correlacionadas (jogo de muito gol tende a
favorecer os dois mercados juntos), o que provavelmente infla um pouco
o z-score. Tratar como o critério de MAIOR confiança dentro do que já
temos, não como prova estatística mais forte que os outros dois. Ver
`docs/retrospectiva_dupla_confirmacao_2026-08-25.md` — inclui também a
assertividade separada dos jogos que NÃO coincidem (ambos os critérios
continuam positivos sozinhos: BTTS não-coincide ROI+9,9%, Over2.5
não-coincide ROI+11,0% — não descartar apostar fora da interseção).

## Segmentação do Over 2.5 por favoritismo — curiosidade, não acionável (25/08/2026)

Dividindo as 221 apostas do critério campeão de Over 2.5 em tercis por
`prob_mercado_favorito_dc` (o quão favorito é o time da odd 1x2):
jogos equilibrados (tercil 1) e favoritos claros (tercil 3) rendem mais
(ROI +24,0% e +20,5%) que o meio-termo (tercil 2, ROI+3,4%) — um
padrão em U, não monotônico. **Não é acionável ainda**: é uma
segmentação post-hoc de um `n` já pequeno (n≈73-75 por tercil), alto
risco de comparação múltipla (poderíamos ter cortado em quartis,
quintis etc. e visto outro padrão). Registrado como curiosidade a
investigar com mais dado, não como regra de aposta.

## Under com odd aproximada — NÃO USAR (25/08/2026)

Testamos Under 1.5/2.5/3.5/4.5 usando uma odd aproximada, construída a
partir da odd real de Over (o CSV não traz odd real de Under). **O
resultado deu ROI positivo em 24 de 24 combinações testadas** (4
mercados × 2 ligas × 3 edges), com z-scores absurdos (até z=+6,18) —
isso é a assinatura de viés sistemático da fórmula (a aproximação é
propositalmente otimista, documentado antes do teste rodar), não uma
descoberta de edge real. Nenhum mercado líquido como Over/Under gols
deixaria essa ineficiência aberta em todas as linhas, nas duas ligas,
por 4 anos seguidos. Ver `docs/retrospectiva_under_aproximado_2026-08-25.md`.

**Correção testada (margem de casa ~7-8%, em vez de 0%)**: refeito com
`margem_under=0.07` (Série A) / `0.08` (Série B) — margem real medida
nos mercados 1x2/BTTS desta fonte de dado. **O viés desapareceu** (só
5/24 combinações positivas, contra 24/24 antes), mas **continua sem
edge real** — os mercados com amostra confiável (Under 1.5/2.5) ficam
consistentemente NEGATIVOS (z até −3,35) nas duas ligas. Duas
conclusões independentes na mesma direção: **não usar nenhum critério
de Under pra apostar dinheiro real**, até conseguirmos uma fonte com
odd REAL desse lado. Ver `docs/retrospectiva_under_margem_2026-08-25.md`.

**✅ Reteste 27/08/2026 com odd REAL do Sportmonks — CONFIRMA, fecha a
dúvida.** Agora com odd real de mercado (não mais aproximação), testado
com os 2 conjuntos de params já campeões (Over 2.5 e BTTS) × 2 ligas ×
4 linhas (1.5/2.5/3.5/4.5) = 16 células: **as 16 são negativas**, e 47
dos 48 recortes ano-a-ano dentro delas também são negativos (a única
exceção, Série A/BTTS/Under 3.5/2024, é ruído — nem a célula agregada é
positiva). Fecha a questão: não é limitação da fonte de dado nem da
aproximação de margem, é o mercado de Under mesmo que não deixa edge
pro nosso modelo, com odd de qualquer fonte testada até aqui. Ver
`docs/retrospectiva_under_odds_reais_2026-08-27.md`.

## 1x2 e Dupla Chance de mandante/visitante — testado, NÃO USAR (25/08/2026)

Testamos casa/empate/fora (1x2, odd REAL, margem removida via
`probabilidades_implicitas_nvias`) e Dupla Chance de lado FIXO
(`mandante_dc`/`visitante_dc`, diferente de Favorito DC) — motivado por
termos as 3 odds reais desse mercado. **Série A: nenhum sinal em
nenhum dos 5 mercados** (melhor z=+0,27, ruído). **Série B: "casa"
parecia forte** (z=+2,71, n=354, ROI+17,5%, robusto a vizinhança de
parâmetros) **mas é um sinal morto**: ano a ano mostra deterioração
progressiva (2023 +35,8%, 2024 +38,6%, 2025 +2,3%, 2026 **−9,9%**) —
somando só os 2 anos mais recentes (2025+2026), ROI≈−2,8%. O z agregado
alto vinha só de 2023-2024; o mercado já foi arbitrado ou o regime
mudou. **Não usar `casa`/`mandante_dc` pra apostar** — apostar nisso
hoje seria ir contra a tendência mais recente dos dados. Ver
`docs/retrospectiva_1x2_dc_2026-08-25.md`.

**Testado também com `n_historico`/filtros separados** (mesmo eixo que
melhorou o BTTS): não muda nada — o "casa" da Série B mantém a mesma
deterioração ano a ano em toda a vizinhança testada (não é problema de
calibração, é tendência temporal, que nenhum corte de amostra reverte).
Confirma a decisão acima. Ver
`docs/retrospectiva_1x2_dc_novos_eixos_2026-08-25.md`.

## Estabilidade por era (2016-2026) — os critérios campeões NÃO são duráveis em 10 anos (26/08/2026)

Lucas conseguiu 7 temporadas adicionais da Série A (2016-2022),
estendendo a cobertura de 4 pra 11 anos seguidos (2016-2026). Testamos
os dois critérios campeões (Over 2.5 e BTTS, parâmetros já validados)
divididos em 3 blocos de era, em vez de uma média só — pra evitar o
mesmo problema já visto no "casa" da Série B (agregado escondendo
decadência).

**Resultado: os dois critérios têm z≈0 no agregado de 11 anos.** São
claramente negativos em 2016-2019 e 2020-2022 (7 dos 11 anos) e só
ficam positivos no bloco 2023-2026 — justamente o único período usado
pra calibrar TODOS os parâmetros já validados nesta sessão.

| Critério | Agregado 2016-2026 | 2016-2019 | 2020-2022 | 2023-2026 |
|---|---|---|---|---|
| Over 2.5 | z=+0,12 (n=578) | z=−1,18 | z=−0,47 | z=+1,37 (n=278) |
| BTTS | z=+0,46 (n=540) | z=−1,11 | z=−1,27 | z=+2,62 (n=256) |

Duas explicações não excludentes: (1) todo o grid search desta sessão
foi calibrado exclusivamente em 2023-2026 — é esperado que uma
configuração otimizada pra um período específico performe pior fora
dele; (2) mudança real de regime de mercado — o Brasil regulamentou
apostas esportivas (Lei 14.790/2023), com casas licenciadas operando a
partir de 2024, o que coincide com a janela onde o edge aparece
(hipótese concreta de ineficiência temporária de mercado novo, não
garantida durar).

**Isso NÃO significa abandonar os critérios atuais** — pro que
interessa agora (apostar em 2026), 2023-2026 continua sendo o período
relevante e nele os dois critérios continuam positivos. **Mas rebaixa a
confiança estatística de "forte" pra "moderada, específica do período
recente, com hipótese plausível de causa"** — os z=2,23/z=2,65
documentados antes não se sustentam fora da janela onde foram
calibrados.

Próximo passo natural (ainda não feito): recalibrar o grid completo
usando 2016-2022 como treino e 2023-2026 como holdout de verdade
(inverso do que foi feito até agora), pra testar se ALGUM conjunto de
parâmetros é durável através das eras. Ver
`docs/retrospectiva_estabilidade_era_2026-08-26.md`.

## Recalibração 2016-2022 → holdout 2023-2026 — não existe parâmetro durável (26/08/2026)

Fizemos o próximo passo acima: grid de 208 combinações (`k_mando` ×
corte de outlier × `n_historico` × variantes de estilo/filtro) rodado
inteiramente sobre 2016-2022 (treino), selecionando só por ROI de
treino. **Resultado: nenhuma configuração tem edge defensável no
treino.** Over 2.5 — a MELHOR das 416 combinações qualificadas tem ROI
**negativo** (-2,7%, z=-0,36). BTTS — a melhor chega a z=+0,37, bem
abaixo de qualquer limiar de significância usado no projeto (z≈2).

Isso não é problema de calibração fina — é ausência de edge real em
2016-2022 pra este modelo, em qualquer configuração testada (832
avaliações no total). Se fosse overfitting puro ao acaso, seria
esperado que alguma combinação aparecesse com z alto por comparação
múltipla; nenhuma apareceu. Reforça a hipótese de mudança real de
regime de mercado (regulamentação de apostas no Brasil, 2023/2024) em
vez de simples ajuste fino errado. **Não existe um conjunto de
parâmetros "santo graal" durável nas 3 eras** — não vale insistir nessa
busca. Mantém a recomendação prática: usar os critérios calibrados em
2023-2026 pra apostar agora, com confiança "moderada, específica do
período recente". Ver
`docs/retrospectiva_recalibracao_holdout_2026-08-26.md`.

## Início de temporada não explica a queda de ROI (26/08/2026)

Lucas perguntou se a queda de ROI do Over 2.5 (n=221→278 ao estender o
histórico) é explicada por "jogos de início de temporada saem piores"
— testamos separando as apostas 2023-2026 por número de rodada (`Game
Week`), cortes de 5 e 10 rodadas. **Resultado: sem padrão consistente**
— o resultado inverte de sinal dependendo do corte (às vezes início
parece melhor que o resto, às vezes pior) nos dois mercados, e o ano a
ano dentro do grupo "início" não mostra nenhuma consistência (n
pequeno, 11-56 por bloco). Não é "início de temporada é
sistematicamente pior" — a queda de ROI observada provavelmente reflete
um efeito único de bootstrap do dataset (jogos de início de 2023
especificamente, o único momento em que faltava histórico anterior a
2016-2022), não um padrão recorrente. Não muda nenhuma recomendação —
ver `docs/retrospectiva_inicio_temporada_2026-08-26.md`.

## Escanteios e cartões (Sportmonks) — testado, NÃO USAR ainda (27/08/2026)

Buscando diversificar além de Over 2.5/BTTS (que dependem de um mesmo
motor), testamos escanteios e cartões com odds reais do Sportmonks
(2024-2026, cobertura confirmada nas duas ligas). **Escanteios: sinal
NEGATIVO forte e consistente** (Série A z=-2,38, Série B z=-2,80,
negativo em TODOS os anos) — não é falta de calibração, é viés
sistemático do motor de gols reaproveitado; não vale insistir com
grid. **Cartões: sem edge, mas por ruído** (agregado perto de zero,
z cai conforme sobe o limiar de edge exigido — assinatura de ruído,
não de sinal real) — provavelmente precisa do fator árbitro (não
incorporado ainda) pra sair do ruído. **Confirmado também com os
combos campeões de Over 2.5 e BTTS** (não só neutro) — escanteios
negativo nas 6 combinações testadas (2 ligas × 3 configs), cartões
perto de zero e inconsistente nas 6. **Testamos também se
`limite_unilateral` (corte de outlier) mal escalado pra gols estava
prejudicando escanteios/cartões** (calibrado pra média de ~1,4 gols/
time, aplicado sem reescalar pra escanteios ~5/time e cartões
~2,6/time): reescalar proporcionalmente NÃO ajuda escanteios (continua
negativo, às vezes pior), mas AJUDA cartões (Série B com corte do BTTS
passa a ter os 3 anos positivos pela primeira vez, ainda abaixo de
z≈2). **Testamos também combinar cartões com dado de árbitro**
(`referee_id` via Sportmonks, média histórica walk-forward): Série A
piora monotonicamente com mais peso no árbitro (não usar); **Série B
melhora e cruza z≈2 no agregado (ROI+9,8-10,9%), positivo nos 3 anos —
mas o z está inflado por uma amostra de só n=28 em 2024**, não é prova
definitiva ainda, vale continuar acompanhando conforme mais dado
entrar. Mantém a recomendação de usar só Over 2.5/BTTS por enquanto. Ver
`docs/retrospectiva_escanteios_cartoes_2026-08-27.md`.

## Regras que nunca mudam

1. **Não usar odds de memória** — sempre pesquisar odds reais (Betano e
   outras casas) antes de confirmar qualquer entrada.
2. **Sinalizar em vez de inventar** quando faltar dado no CSV/fonte — nunca
   preencher um número plausível sem avisar que é estimativa.
3. **P.Font reflete julgamento qualitativo das fontes**, não é só a odd de
   mercado normalizada — tem que agregar visão de tipsters/analistas.
4. **Não alterar fórmulas do template** — só clonar/redimensionar (hoje
   feito por `planilha_lib.build_workbook`; o motor de pesos em
   `pesos.py`/`excel_writer.py` grava valor calculado, não fórmula nova).
5. Máximo 2 apostas por jogo; mínimo 3 jogos diferentes por dia quando
   houver jogos suficientes.

## Critérios de aposta (faixas de ROI)

- **Alta Certeza**: piso de odd 1.40, teto 1.80. ROI histórico reportado:
  +38.8%, ~89% de acerto (revalidar periodicamente contra resultado real).
- Faixa "Referência" (menor confiança): ROI histórico reportado -41% — ou
  seja, evitar como base de decisão isolada.
- Gestão de banca: máximo 47% da banca por jogo.

## Parâmetros do motor de pesos (ver `metodologia_pesos/pesos.py`)

**Esta tabela é a validação por ACERTO — pra decisão de aposta (ROI),
usar o critério da seção "Grid completo: melhor achado da sessão"
acima (Over 2.5 na Série A: `k=0.5, sem estilo, filtro=0.8,
multiplicador_dp=1.5, limite_unilateral=2, edge=5%`), não
necessariamente os valores desta tabela.**

| Parâmetro | Série A | Série B | Origem |
|---|---|---|---|
| Decaimento de recência | 100%/85%/70%/50%/30%/15%/0% em ≤10/20/30/45/90/180/>180 dias (as duas ligas) | | fórmula original do template — ainda não retestado |
| `k` (encolhimento de mando) | Sem ajuste (`None`) | **0.5** | **validado por holdout 2025→2026** — ver "Validação fora-da-amostra" abaixo |
| `usar_estilo` | `True` | **`False`** | idem |
| `filtro_aderencia` | 0.65 | **0.8** | idem — na Série B contraria o achado anterior baseado em MAE; aqui a evidência é de holdout real em Over/Under 2.5 |
| `estilo_por_mando` (estilo casa≠fora) | `False` (revertido — era `True`) | `False` (desligado, confirmado) | validado por holdout 2025→2026 (24/08/2026) — achado anterior não se sustentou. Ver "Estilo por mando" abaixo |
| `limite_unilateral` (corte outlier) | **2** (Over 2.5) / 4 (outros mercados) | 4 | ver "Corte de desvio padrão" abaixo — testado só pra Over 2.5 na Série A até agora |
| `multiplicador_dp` (corte outlier) | **1.5** (Over 2.5) / 2.5 (outros mercados) | 2.5 | idem |
| `k` (Copa) | 0.35 | | ainda "no olho" — torneio neutro, parâmetro pouco relevante |

**⚠️ Validação fora-da-amostra (24/08/2026) — ver
`docs/retrospectiva_holdout_2026-08-24.md`, é a evidência mais forte que
temos até agora, supera as rodadas anteriores.** Metodologia: escolher
parâmetros olhando só pra 2025 (treino) e medir o resultado real numa
temporada que a escolha nunca viu, 2026 (holdout) — resolve o problema de
comparação múltipla das rodadas anteriores (pegar o "vencedor" de um
grid grande na MESMA amostra onde foi medido não prova nada).

**Achado principal: as duas ligas se comportam de forma oposta.**
- **Série A**: o melhor resultado no TREINO (52.7% de acerto Over/Under
  2.5) virou o PIOR no HOLDOUT (44.0%, pior que cara-ou-coroa). Não há
  correlação confiável entre "ganhar no treino" e "generalizar" — com o
  volume de dado atual (~300 jogos de treino), ajuste fino de parâmetro
  nesta liga é mais perto de adivinhação do que calibração. **Por isso os
  valores da Série A continuam "neutros"/sem ajuste — não porque sejam
  comprovadamente ótimos, mas porque nada testado se provou melhor de
  forma confiável.**
- **Série B**: os 8 melhores candidatos do treino generalizam bem no
  holdout (todos entre 54.7-59.2%, vários até melhoram). O melhor
  resultado do HOLDOUT (`k=0.5, sem estilo, filtro=0.8` → 59.2%) é
  próximo do topo do treino — sinal real, não sorte de amostra. **Por
  isso a Série B teve os 3 parâmetros acima efetivamente alterados.**

Isso não significa que a Série B "resolveu" o problema pra sempre — é a
melhor estimativa disponível com 1 temporada de treino, não uma prova
definitiva. E não significa que a Série A é "pior" — pode ser só menos
previsível mesmo (mais zebra), ou precisar de mais dado ainda.

O `k_mando`/ablação de estilo foram recalibrados olhando só o mercado de
gols — os outros 11 mercados (ver seção de ablação abaixo) têm MAE
calculado mas não passaram por esse mesmo processo de treino/holdout.
`estilo_por_mando` FOI retestado com o mesmo desenho (ver seção
"Estilo por mando" abaixo, atualizada em 24/08/2026) — o achado anterior
não se sustentou, mesmo padrão do `k_mando` da Série A.

## Teste de ablação do estilo (24/08/2026)

Pergunta: o filtro/peso de aderência de estilo (≥65% nos dois, multiplica
em `peso_final`) está realmente ajudando a prever gols, ou é peso morto?
Testado isolando o efeito do estilo (`pesos.calcular_pesos_historico(usar_estilo=False)`)
contra o comportamento padrão, nas duas ligas, variando o limiar do
filtro — ver `docs/retrospectiva_estilo_2026-08-24.md` para o relatório
completo.

**Achado: no filtro atual (65%), o estilo é essencialmente indiferente**
(diferença de ~0.001-0.002 de MAE e 0-0.6pp de acerto, dentro do ruído) —
nas duas ligas. **Em filtro estrito (80%), o estilo ATRAPALHA**
(principalmente Série A: MAE piora 0.029, acerto de Over/Under 2.5 cai
6.5pp). Interpretação: não é que "estilo não importa" — é que os proxies
atuais (3 das 5 dimensões são proxies mais fracos, ver seção abaixo) não
estão discriminando bem o suficiente pra fazer diferença nesta amostra.
**Decisão**: manter `filtro_aderencia=0.65` (sem motivo pra trocar) e
manter o estilo ativado (não prejudica no filtro usual, só em 80%) — mas
não tratar como pilar comprovado do modelo até os proxies melhorarem.

**Atualização 24/08/2026 (mesmo dia) — testado nos outros 11 mercados
também**: estendi `retrospectiva.py` pra calcular os 12 indicadores
Pró/Contra completos (não só gols) e refiz a ablação em todos eles,
inclusive escanteios (onde o protocolo original mais ligava estilo a
resultado, "Princípio 5"). **Resultado: escanteios não é diferente** — em
todos os 12 mercados, nas duas ligas, a diferença com/sem estilo fica
abaixo de meio ponto percentual de MAE relativo. Não existe mercado onde
o estilo (do jeito que é calculado hoje) se destaque como relevante — ver
`docs/retrospectiva_mercados_2026-08-24.md`. Confirma que o problema é o
que os proxies medem, não o peso que recebem.

**Atualização com amostra ampliada (2025+2026)**: com 3.3x mais dado, o
sinal deixou de ser "indiferente" (diferença <0.1%) e passou a "levemente
negativo, mas consistente" (SEM estilo é ~0.1-0.4% melhor, nas duas
ligas) — ver `docs/retrospectiva_2025_2026_recalibracao.md`. Ainda pequeno
demais pra justificar desligar o estilo, mas a direção do efeito ficou
mais confiável (era ruído puro antes; agora é um viés fraco e replicado).

## Estilo por mando — casa ≠ fora (24/08/2026)

Antes de desistir do estilo, testei a hipótese do Lucas: muitos times
jogam diferente em casa vs fora — misturar os últimos 5 jogos (qualquer
mando) pode estar diluindo um sinal real. Implementado
`_estilo_por_mando()` em `retrospectiva.py` (parâmetro
`estilo_por_mando=True`): calcula o estilo de cada time só com os
últimos 5 jogos NAQUELE mando específico (o alvo de hoje e cada
adversário do histórico, respeitando o mando que tinham em cada
confronto). Métrica priorizada pelo Lucas: **acerto de Over/Under 2.5**
(não MAE). Ver `docs/retrospectiva_estilo_por_mando_2026-08-24.md`.

**Resultado inicial (comparação única, 24/08): ajuda na Série A,
atrapalha na Série B.** Série A: estilo por mando era a melhor das 3
opções em Over/Under 2.5 (50.62% vs 50.20% sem estilo vs 49.61% misto).
Série B: era a pior (55.02% vs 56.71% do estilo misto).

**⚠️ Atualização com validação fora-da-amostra (24/08/2026, mesmo dia) —
o achado da Série A NÃO se sustentou.** Mesmo problema que já tinha
derrubado o `k_mando` original: essa comparação foi feita numa amostra
única, sem holdout. Retestado com o mesmo desenho treino(2025)/
holdout(2026) — ver `docs/retrospectiva_holdout_estilo_por_mando_2026-08-24.md`:
- **Série A**: a diferença entre `estilo_por_mando=True` e `False` fica
  dentro de 0.1-0.7pp em pares comparáveis no holdout — ruído, não sinal.
  **Decisão revisada: `estilo_por_mando=False`** (revertido).
- **Série B**: o achado se CONFIRMA — o melhor resultado geral do
  holdout (59.16% de Over/Under 2.5) continua usando `False`, e a maioria
  do top-10 favorece `False`. **Mantido `estilo_por_mando=False`.**

**Estilo por mando fica desligado nas duas ligas agora** — nem `usar_estilo`
nem `estilo_por_mando` mostraram efeito forte o bastante pra justificar
tratamento diferenciado. O código (`_estilo_por_mando` em
`retrospectiva.py`) fica mantido, testado mas não usado por ora.

Custo (contexto): estilo por mando exige mais dado (5 jogos NAQUELE mando
específico) — avalia ~5-7% menos jogos que o estilo misto.

## Notas de estilo — agora automáticas (últimos 5 jogos)

Desde a consolidação em `estilo.py`, as 5 notas de estilo por time
(Bloco Baixo, Pressão Alta, Transição, Posse, Bola Parada) deixaram de ser
julgamento qualitativo e passaram a ser calculadas a partir dos últimos 5
jogos de cada time, com parâmetros pré-definidos e documentados no próprio
arquivo. Duas dimensões (Posse, Bloco Baixo) usam dado direto do CSV do
FootyStats; as outras três (Pressão Alta, Transição, Bola Parada) usam
proxies estatísticos mais fracos (não há métrica direta de pressão/
transição/bola parada no CSV padrão) — sinalizar essa diferença de
confiança sempre que relevante. O banco JSON (`data/estilos_*.json`) virou
um cache sobrescrito a cada sessão, não mais editado à mão.

## Ligas cobertas hoje

- **Copa 2026**: torneio neutro, sem mando de campo.
- **Série B 2026**: mando de campo conta, média de gols mais baixa
  (2.3/jogo), liga mais faltosa (5.37 cartões/jogo), tem props de jogador.
  Dados reais em `data/footystats_serieb/` (2026 parcial) +
  `data/footystats_serieb_2025/` (temporada completa) — 492 jogos
  avaliáveis combinados. `k=0.5, usar_estilo=False, filtro=0.8`,
  validado por holdout 2025→2026 (ver "Validação fora-da-amostra" acima).
- **Série A**: dados reais em `data/footystats_seriea/` (2026 parcial) +
  `data/footystats_seriea_2025/` (temporada completa) — 508 jogos
  avaliáveis combinados. Mantida em valores neutros (sem ajuste de mando,
  `filtro=0.65`) — o holdout mostrou que ajuste fino aqui não generaliza
  ainda (ver acima).

## TODO (preencher com Lucas)

- [x] Simular apostas de verdade contra odd real (24/08/2026) —
      `simular_apostas`, achado principal: acerto e vantagem real (ROI)
      não são a mesma coisa, Série B "vencedora" por acerto não tem edge
      nenhum contra o mercado. Ver "Acerto ≠ vantagem real" acima.
- [x] Recalibrar `k_mando`/`usar_estilo`/`filtro_aderencia` otimizando
      ROI simulado em vez de acerto (25/08/2026) — nenhuma combinação
      encontrada bateu o parâmetro neutro (ver "Recalibração por ROI não
      superou o neutro" acima e
      `docs/retrospectiva_roi_calibracao_holdout_2026-08-25.md`).
      Decisão: manter neutro + `limiar_edge≥8%` na Série A pra apostar;
      não apostar na Série B por este critério ainda.
- [ ] Conseguir odd do lado "Under 2.5" (hoje só "Over") pra poder simular
      apostar contra o modelo também, não só a favor.
- [ ] Completar critérios de ROI por faixa de odd (só temos "Alta Certeza"
      e "Referência" documentados — havia mais faixas mencionadas em
      sessões anteriores que não foram recuperadas nesta consolidação).
- [ ] Confirmar se as regras "não usar odds de memória" / "máx 47% da
      banca" valem igual pra Série A ou se há ajuste por liga.
- [x] Rodar `retrospectiva.rodar_retrospectiva`/`grid_search` com os CSVs
      reais da Série A (24/08/2026) — ver relatório e resultado acima.
- [x] Rodar a mesma retrospectiva pra Série B (24/08/2026) — sinal misto,
      `k=0.35` mantido (ver relatório acima). Confirmado: não dava pra
      assumir que o achado da Série A valeria lá.
- [x] Teste de ablação do estilo (24/08/2026) — filtro de 65% mantido,
      estilo é indiferente nesse nível, atrapalha em 80% (ver acima).
- [x] Estender `retrospectiva.py` pra validar os outros 10 indicadores
      Pró/Contra (24/08/2026) — `rodar_retrospectiva` já retorna MAE por
      mercado automaticamente. Reavaliei a ablação do estilo em todos: sem
      diferença em nenhum, nem escanteios (ver acima e relatório).
      MAE relativo por mercado sugere mais confiança em chutes/escanteios/
      cartões do que em gols e principalmente "Gols 1ºT" (MAE > 100% da
      média — pouco melhor que chutar a média da liga nesse mercado).
- [x] Re-rodar as duas retrospectivas com mais dado (24/08/2026, Lucas
      subiu 2025 completo) — 3.3x mais jogos avaliados. O achado "zerar
      k na Série A" NÃO se sustentou; virou platô raso sem vencedor claro
      nas duas ligas. Ver `docs/retrospectiva_2025_2026_recalibracao.md`.
- [x] Lucas definiu: **prioridade é acerto de Over/Under**, não MAE de
      gols (24/08/2026) — `grid_search` ganhou `ordenar_por` pra refletir
      isso. Ainda não re-rodei o grid completo de `k_mando` já ordenando
      por Over/Under 2.5 (só a comparação de estilo por mando usou essa
      prioridade até agora) — próximo passo natural.
- [x] Testado "estilo por mando" (casa≠fora) antes de descartar estilo de
      vez (24/08/2026, pedido do Lucas) — ajuda a Série A, atrapalha a
      Série B. `estilo_por_mando=True` ligado na Série A, `False` mantido
      na Série B. Ver "Estilo por mando" acima.
- [x] Rodar validação fora-da-amostra (treino 2025 / holdout 2026) pra
      resolver o problema de comparação múltipla (24/08/2026) —
      `timestamp_minimo` em `rodar_retrospectiva`. Achado: Série A não
      generaliza (melhor do treino virou pior do holdout), Série B
      generaliza bem. Parâmetros da Série B atualizados com base nisso
      (`k=0.5, usar_estilo=False, filtro=0.8`); Série A mantida neutra.
      Ver `docs/retrospectiva_holdout_2026-08-24.md`.
- [x] Re-testar `estilo_por_mando` com o mesmo desenho de holdout
      (treino 2025 / teste 2026), 24/08/2026 — o achado da Série A NÃO se
      sustentou (revertido pra `False`); o da Série B se confirmou
      (mantido `False`). `estilo_por_mando` fica desligado nas duas ligas
      agora. Ver `docs/retrospectiva_holdout_estilo_por_mando_2026-08-24.md`.
- [ ] Rodar o grid search de `k_mando`/outlier também pros outros 11
      mercados (hoje só gols foi calibrado, e só com holdout na Série B).
- [ ] Quando surgir mais uma temporada/rodada de dado (2024? mais de
      2026?), repetir o treino/holdout de novo — principalmente pra
      Série A, que precisa de mais dado antes de qualquer ajuste fino
      valer a pena, e pra confirmar se o achado da Série B se mantém
      numa 3ª temporada (1 holdout não é prova definitiva). Lucas
      confirmou (25/08/2026) que pode subir 2024 se pedirmos — vale a
      pena principalmente pra Série B (nenhum candidato passou de z≈0.9
      em ROI ainda, mais dado de treino pode ajudar a separar sinal de
      ruído).
