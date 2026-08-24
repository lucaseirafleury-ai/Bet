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

| Parâmetro | Valor atual | Origem |
|---|---|---|
| Decaimento de recência | 100%/85%/70%/50%/30%/15%/0% em ≤10/20/30/45/90/180/>180 dias | fórmula original do template (Times!AI) — ainda não retestado |
| `k` (encolhimento de mando) — **Série A** | **Sem valor "validado"** — mantido sem ajuste (k=1.0) por ser razoável dentro do platô, não porque vença claramente | ver "Recalibração com amostra ampliada" abaixo — a versão anterior desta linha (k=1.0 "vencedor claro") não se sustentou com mais dado |
| `k` (encolhimento de mando) — **Série B** | **Sem valor "validado"** — mantido em 0.35 por ser razoável dentro do platô, não porque vença claramente | idem — ver abaixo |
| `k` (encolhimento de mando) — Copa | 0.35 | ainda "no olho" — Copa é torneio neutro, sem mando; parâmetro pouco relevante lá |
| `limite_unilateral` (corte outlier) | 4 | testado (3/4/5) na Série A e B, sem diferença mensurável no mercado de gols — ver retrospectivas |
| `multiplicador_dp` (corte outlier) | 2.5 | testado (2/2.5/3) na Série A e B, diferença dentro do ruído — ver retrospectivas |
| Filtro de validade (aderência estilo/favoritismo) | ≥65% nos dois | testado (0/0.5/0.65/0.8) em 2 rodadas (154-156 jogos e depois 492-508) — único achado que se REPLICOU com força: 0.8 é ruim, resto é parecido. Mantido em 65% |

**⚠️ Recalibração com amostra ampliada (24/08/2026, mesmo dia) — ver
`docs/retrospectiva_2025_2026_recalibracao.md`.** A primeira rodada de
calibração (contra só 154-156 jogos de 2026 parcial) tinha concluído que
"zerar o mando na Série A vence nas 3 métricas de forma clara". Depois de
Lucas subir a temporada 2025 completa (380 jogos/liga), a mesma
recalibração rodou contra 492-508 jogos (3.3x mais dado) — **e essa
conclusão não se sustentou**: com mais dado, a diferença entre k=0.5/0.7/
None fica dentro de 1-2% (ruído), nas duas ligas, e MAE de gols aponta
numa direção enquanto acerto de Over/Under 2.5 aponta na oposta. Ou seja,
a conclusão "confiante" da rodada anterior era, em boa parte, artefato de
amostra pequena. **Lição prática**: tratar qualquer achado baseado em
\<200 jogos como preliminar até re-testar com mais dado — o que já
aconteceu aqui uma vez.

O `k_mando`/ablação de estilo foram recalibrados olhando só o mercado de
gols — os outros 11 mercados (ver seção de ablação abaixo) têm MAE
calculado mas não passaram por esse mesmo grid search ainda.

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
  avaliáveis combinados. `k=0.35` mantido, sem ser "vencedor claro" (ver
  recalibração acima).
- **Série A**: dados reais em `data/footystats_seriea/` (2026 parcial) +
  `data/footystats_seriea_2025/` (temporada completa) — 508 jogos
  avaliáveis combinados. `k` sem ajuste mantido, sem ser "vencedor claro"
  (ver recalibração acima).

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
- [ ] Não tratar `k_mando` como resolvido em nenhuma liga — se quiser
      decidir um valor único (em vez de manter os atuais "razoáveis
      dentro do platô"), definir com Lucas se prioriza MAE de gols ou
      acerto de Over/Under 2.5 (apontam em direções opostas).
- [ ] Rodar o grid search de `k_mando`/outlier também pros outros 11
      mercados (hoje só gols foi calibrado com grid; os outros só têm MAE
      baseline + ablação de estilo).
- [ ] Quando surgir mais uma temporada/rodada de dado, repetir de novo —
      o padrão "achado muda com mais dado" já se confirmou uma vez, vale
      manter a guarda alta antes de fixar qualquer parâmetro de vez.
