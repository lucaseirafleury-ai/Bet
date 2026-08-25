# Protocolo de Apostas — Regras Persistentes

**⚠️ Leitura obrigatória antes de qualquer outra coisa neste arquivo —
seções "Acerto ≠ vantagem real (24/08/2026)" e "Recalibração por ROI não
superou o neutro (25/08/2026)" logo abaixo.** Os parâmetros de
`k_mando`/`usar_estilo`/`filtro_aderencia` da tabela abaixo foram
otimizados por ACERTO (Over/Under, BTTS) — vantagem competitiva real
(ROI contra odd de mercado) é outra métrica, e a recalibração feita por
ROI (25/08/2026) **não encontrou nada melhor que os parâmetros neutros**
(sem ajuste nenhum). **Pra decisão de aposta, usar os parâmetros neutros
com `limiar_edge ≥ 8%` na Série A (único ponto com sinal
estatisticamente defensável até agora); não apostar na Série B por este
critério ainda** — ver a seção nova pro raciocínio completo.

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

**⚠️ Testado 25/08/2026 — Over 1.5/3.5/4.5 NÃO diversificam** (Lucas
perguntou como reduzir a variância ano a ano do Over 2.5; cartões/
escanteios não têm odd real no CSV, então a alternativa era mais linhas
de gols). Simulação 2023-2026 nas duas linhas mostra ROI negativo em
TODOS os limiares/anos — Over 3.5/4.5 especialmente ruins (ROI até
−81%). O edge que existe fica concentrado só em Over 2.5/BTTS, não
generaliza pras linhas vizinhas. **Não apostar Over 1.5/3.5/4.5.** Ver
`docs/retrospectiva_over_1_5_3_5_4_5_2026-08-25.md`.

Versão inicial, consolidada a partir do que estava espalhado nas skills
`copa-planilha-dia`/`serie-b-planilha-dia` (que citavam um
`briefing_*.md`/`PROTOCOLO_BETS_LUCAS.md` vivendo só em pasta efêmera de
sessão, não versionado). **Este arquivo existe pra parar de se perder entre
sessões — complete/corrija o que estiver incompleto ou desatualizado.**

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
usar os parâmetros neutros com `limiar_edge` conforme a seção
"Recalibração por ROI" acima, não necessariamente os valores aqui.**

| Parâmetro | Série A | Série B | Origem |
|---|---|---|---|
| Decaimento de recência | 100%/85%/70%/50%/30%/15%/0% em ≤10/20/30/45/90/180/>180 dias (as duas ligas) | | fórmula original do template — ainda não retestado |
| `k` (encolhimento de mando) | Sem ajuste (`None`) | **0.5** | **validado por holdout 2025→2026** — ver "Validação fora-da-amostra" abaixo |
| `usar_estilo` | `True` | **`False`** | idem |
| `filtro_aderencia` | 0.65 | **0.8** | idem — na Série B contraria o achado anterior baseado em MAE; aqui a evidência é de holdout real em Over/Under 2.5 |
| `estilo_por_mando` (estilo casa≠fora) | `False` (revertido — era `True`) | `False` (desligado, confirmado) | validado por holdout 2025→2026 (24/08/2026) — achado anterior não se sustentou. Ver "Estilo por mando" abaixo |
| `limite_unilateral` (corte outlier) | 4 | 4 | sem diferença mensurável, não testado em holdout |
| `multiplicador_dp` (corte outlier) | 2.5 | 2.5 | idem |
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
