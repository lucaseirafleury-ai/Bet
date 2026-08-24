# Protocolo de Apostas — Regras Persistentes

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

| Parâmetro | Série A | Série B | Origem |
|---|---|---|---|
| Decaimento de recência | 100%/85%/70%/50%/30%/15%/0% em ≤10/20/30/45/90/180/>180 dias (as duas ligas) | | fórmula original do template — ainda não retestado |
| `k` (encolhimento de mando) | Sem ajuste (`None`) | **0.5** | **validado por holdout 2025→2026** — ver "Validação fora-da-amostra" abaixo |
| `usar_estilo` | `True` | **`False`** | idem |
| `filtro_aderencia` | 0.65 | **0.8** | idem — na Série B contraria o achado anterior baseado em MAE; aqui a evidência é de holdout real em Over/Under 2.5 |
| `estilo_por_mando` (estilo casa≠fora) | `True` (ligado) | `False` (desligado) | testado em amostra única (não holdout ainda) — ver "Estilo por mando" abaixo |
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
`estilo_por_mando` também não foi re-testado em holdout ainda (fica pro
próximo passo).

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

**Resultado: ajuda na Série A, atrapalha na Série B** (mesmo padrão de
divergência entre ligas já visto no `k_mando`):
- **Série A**: estilo por mando é a MELHOR das 3 opções (sem estilo /
  estilo misto / estilo por mando) tanto em Over/Under 2.5 (50.62% vs
  50.20% sem estilo vs 49.61% misto) quanto em BTTS. **Decisão: ligar
  `estilo_por_mando=True` na Série A.**
- **Série B**: estilo por mando é a PIOR opção em Over/Under 2.5 (55.02%
  vs 56.71% do estilo misto atual, que continua sendo o melhor aqui) —
  apesar de vencer em MAE de gols e BTTS. **Decisão: manter
  `estilo_por_mando=False` (estilo misto) na Série B.**

Custo: estilo por mando exige mais dado (5 jogos NAQUELE mando
específico) — avalia ~5-7% menos jogos. As amostras comparadas não são
idênticas entre os 3 cenários por causa disso (ver limitações no
relatório) — tratar como sinal real mas não definitivo.

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
- [ ] Re-testar `estilo_por_mando` com o mesmo desenho de holdout
      (treino 2025 / teste 2026) — foi decidido numa comparação única,
      sem holdout, mesmo risco de comparação múltipla que já derrubou o
      achado antigo de `k_mando`.
- [ ] Rodar o grid search de `k_mando`/outlier também pros outros 11
      mercados (hoje só gols foi calibrado, e só com holdout na Série B).
- [ ] Quando surgir mais uma temporada/rodada de dado (2024? mais de
      2026?), repetir o treino/holdout de novo — principalmente pra
      Série A, que precisa de mais dado antes de qualquer ajuste fino
      valer a pena, e pra confirmar se o achado da Série B se mantém
      numa 3ª temporada (1 holdout não é prova definitiva).
