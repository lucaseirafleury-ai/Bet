# Metodologia de Pesos (Histórico + Estilo de Jogo)

Motor versionado e testado da metodologia de análise de jogos (pesos de
histórico e estilo, mercados Pró/Contra, ajuste de mando). Substitui a
reescrita manual de fórmula Excel array/LET a cada sessão — o mesmo cálculo
agora é código Python testado, e a planilha final recebe VALORES já
calculados, não fórmulas frágeis.

## Por que isso existe

Antes, a "fórmula robusta Pró/Contra" (média/desvio-padrão ponderados +
corte de outlier) e o ajuste de mando existiam só como instruções em texto
numa skill do Claude Code, reescritas em fórmula Excel LET/array a cada
planilha gerada. Isso já causou pelo menos uma planilha que "não calculava"
no Excel por erro de gravação de fórmula, e os parâmetros (decaimento de
recência, k do mando, corte de outlier) nunca foram calibrados
estatisticamente — só ajustados "no olho".

## Arquivos

```
pesos.py            → motor de pesos puro (sem Excel): aderência de estilo,
                       aderência de favoritismo, peso de recência, peso
                       final, ajuste de mando, média/desvio-padrão
                       ponderados, corte de outlier — tudo testável isolado.
test_pesos.py        → testes unitários do motor (35 casos).
excel_writer.py      → grava os valores calculados por pesos.py na planilha
                       (Times!AG:AK e os 12 indicadores Pró/Contra de
                       Jogos do Dia), rodando DEPOIS de build_workbook.
test_excel_writer.py → teste de integração: monta uma planilha real com
                       histórico fabricado e confere que os valores saem
                       numéricos e corretos, sem depender de LibreOffice/
                       Excel avaliar fórmula nenhuma.
estilo.py             → calcula as 5 notas de estilo (1-5) automaticamente a
                       partir dos últimos N jogos de um time (padrão 5),
                       usando parâmetros pré-definidos e documentados —
                       substitui a atribuição manual/qualitativa. Duas
                       dimensões (Posse, Bloco Baixo) usam dado direto do
                       CSV; as outras três (Pressão Alta, Transição, Bola
                       Parada) usam proxies estatísticos mais fracos,
                       documentados em cada função. `atualizar_banco_estilo`
                       recalcula e SOBRESCREVE o cache JSON (estilos_*.json)
                       a cada chamada.
test_estilo.py        → testes unitários do cálculo de estilo (21 casos).
retrospectiva.py       → validação walk-forward: para cada jogo do
                       histórico, monta o cenário só com dados anteriores a
                       ele (sem look-ahead), roda o motor de pesos e compara
                       a previsão com o placar real — nos 12 mercados
                       Pró/Contra (gols, cartões, escanteios, chutes,
                       chutes no gol, gols 1ºT), não só gols. Usado pra
                       calibrar os parâmetros livres (k do mando, corte de
                       outlier, `usar_estilo` pra ablação) sem depender do
                       Tips_telegram.xlsx. Inclui `grid_search` pra comparar
                       combinações de parâmetros; `rodar_retrospectiva`
                       retorna `mae_gols_total`/`acerto_over25`/`acerto_btts`
                       (mercado de gols) + `mercados` (MAE absoluto e
                       relativo dos 12 mercados). Cada jogo avaliado já
                       carrega `prob_modelo_over25`/`prob_modelo_btts`
                       (via `pesos.probabilidade_over`/`probabilidade_btts`)
                       e `prob_mercado_*`/`odd_*` — `simular_apostas`
                       aposta só quando o modelo supera a odd real por um
                       `limiar_edge`, retornando ROI/lucro de verdade (não
                       só acerto — ver "O que já foi feito" abaixo, os
                       dois NÃO são a mesma coisa).
test_retrospectiva.py  → teste de integração com dataset fabricado (não
                       depende dos CSVs reais, que só chegam com o upload).
planilha_lib.py      → mecânica de planilha (CSV, clonagem de fórmula,
                       build_workbook) — migrada de
                       ~/.claude/skills/synced/copa-planilha-dia/scripts/.
data/estilos_selecoes.json → cache de estilo tático por seleção/time,
                       sobrescrito a cada sessão por `atualizar_banco_estilo`.
templates/Copa_Template_Simplificado.xlsx → template-base das planilhas.
docs/                → protocolo e critérios de aposta persistentes
                       (antes viviam em pasta efêmera /mnt/user-data/outputs/).
```

## Uso típico (dentro de uma skill de planilha)

```python
import sys
sys.path.insert(0, "/home/user/Bet/metodologia_pesos")
from planilha_lib import build_workbook, get_historico, attach_estilo, load_all_matches
from excel_writer import aplicar_pesos_historico, aplicar_indicadores_pro_contra

# ... montar hist_A, hist_B, jdd_A, jdd_B, mercados_rows como sempre ...
build_workbook(games, template_path="metodologia_pesos/templates/Copa_Template_Simplificado.xlsx",
                output_path="SerieA_10ago.xlsx", data_jogo="10/08/2026")

# recalcula Times!AG:AK com o motor Python (substitui a fórmula Excel):
historico = aplicar_pesos_historico(
    "SerieA_10ago.xlsx",
    mando_alvo_por_time={"Ceará": "Casa"},  # opcional: ajuste de mando
    k_mando=0.35,
)

# recalcula os 12 indicadores Pró/Contra de Jogos do Dia:
aplicar_indicadores_pro_contra("SerieA_10ago.xlsx", historico_por_time=historico)
```

Como os dois passos gravam VALORES (não fórmula), o arquivo já sai correto
mesmo se aberto só com `recalc.py`/LibreOffice — elimina os avisos de
`#VALUE!`/fallback do LET que o protocolo antigo tinha que repetir a cada
entrega.

### Estilo automático + validação retrospectiva

```python
from estilo import atualizar_banco_estilo
from retrospectiva import rodar_retrospectiva, grid_search

# recalcula e sobrescreve o cache de estilo de vários times, últimos 5 jogos:
times = {t: get_historico(t, df, n=5) for t in nomes_dos_times}
atualizar_banco_estilo(times, estilo_db_path="data/estilos_seriea.json", n=5)

# valida o modelo contra os placares reais já presentes nos CSVs (walk-forward):
relatorio = rodar_retrospectiva(df, min_jogos_historico=10)
print(relatorio["n"], relatorio["mae_gols_total"], relatorio["acerto_over25"], relatorio["acerto_btts"])
for mercado, m in relatorio["mercados"].items():
    print(mercado, m["mae"], m["mae_relativo"])  # MAE de todos os 12 mercados Pró/Contra

# teste de ablação: o estilo está ajudando? (usar_estilo=False força aderência_estilo=1.0)
com_estilo = rodar_retrospectiva(df, params=dict(usar_estilo=True), min_jogos_historico=10)
sem_estilo = rodar_retrospectiva(df, params=dict(usar_estilo=False), min_jogos_historico=10)

# compara combinações de parâmetros pra achar a que mais acerta nesse histórico:
grade = dict(k_mando=[None, 0.2, 0.35, 0.5], limite_unilateral=[3, 4, 5], multiplicador_dp=[2, 2.5, 3])
melhores = grid_search(df, grade, min_jogos_historico=10)
print(melhores[0])  # (params, relatorio) com o menor mae_gols_total
```

### Vantagem real (ROI contra odd de mercado) — não confundir com acerto

```python
from retrospectiva import simular_apostas

# relatorio já vem com prob_modelo_*/odd_*/prob_mercado_* em cada jogo (rodar_retrospectiva acima)
r = simular_apostas(relatorio["jogos"], mercado="over25", limiar_edge=0.05, stake=1.0)
print(r["n_apostas"], r["taxa_acerto"], r["lucro_total"], r["roi"])
# só aposta quando prob_modelo - prob_mercado >= limiar_edge — mede vantagem
# de verdade, não só se o modelo "acertou" (ver docs/retrospectiva_roi_2026-08-24.md:
# os dois NÃO são a mesma coisa, uma config pode acertar mais e ter MENOS edge real)
```

## O que já foi feito (24/08/2026, ver `docs/protocolo.md` pro estado atual)

Resumo rápido, cronológico — o `docs/protocolo.md` tem a versão sempre
atualizada, esta lista aqui não é mantida em detalhe:

1. Motor de pesos + estilo automático viram código testado (não mais
   fórmula Excel/julgamento manual).
2. Primeira retrospectiva real (154-156 jogos, 2026 parcial) — achados
   que pareciam claros.
3. Amostra ampliada com 2025 completo (3,3× mais jogos) — parte dos
   achados da rodada 2 não se sustentou.
4. Validação fora-da-amostra (treino 2025 / holdout 2026) — resolve o
   problema de comparação múltipla; Série B generaliza bem, Série A não.
5. **Simulação de aposta contra odd real (ROI, não só acerto)** — mostra
   que acerto e vantagem competitiva NÃO são a mesma coisa: a config
   "vencedora" da Série B por acerto não tem edge nenhum contra o
   mercado; a Série A (parâmetros neutros) mostra edge real e crescente.
   Ver `docs/retrospectiva_roi_2026-08-24.md`.
6. **Recalibração por ROI (treino 2025/holdout 2026) não superou os
   parâmetros neutros** — grid de 48 combinações otimizado por ROI
   simulado (não acerto) repetiu o mesmo padrão de overfitting já visto
   com `k_mando`/`estilo_por_mando`; nenhum candidato bateu o neutro no
   critério que importa (z-score). Decisão: manter parâmetros neutros +
   `limiar_edge≥8%` como critério de aposta na Série A; Série B ainda
   sem edge defensável. Ver
   `docs/retrospectiva_roi_calibracao_holdout_2026-08-25.md`.
7. **Repetido com 3 temporadas de treino (2023+2024+2025 → holdout
   2026)** — Lucas subiu 2023/2024 completos. O achado da Série A se
   REFORÇOU (BTTS edge=8% subiu de z=2,72 pra z=2,91); o neutro da Série
   B Over 2.5 piorou (ficou claramente negativo com mais histórico); e
   pela primeira vez o grid achou algo pra Série B BTTS que bate o
   neutro (`k=0.2, estilo=True, filtro=0.65, edge=5%`, z≈0,9-1,0 — ainda
   não significativo, mas o sinal mais consistente que essa liga já
   mostrou). Ver
   `docs/retrospectiva_roi_calibracao_2023_2025_holdout_2026-08-25.md`.
8. **Tentativa de diversificar em Over 1.5/3.5/4.5 não funcionou** —
   cartões/escanteios não têm odd real no CSV (só percentual do próprio
   FootyStats), então a alternativa era as outras linhas de gols que já
   tinham odd real disponível. `simular_apostas` foi generalizado pra
   qualquer linha (`retrospectiva.py`); resultado: ROI negativo em
   TODOS os limiares/anos testados nas duas ligas, Over 3.5/4.5
   especialmente ruins (até −81%). O edge fica concentrado só em
   Over 2.5/BTTS, não generaliza. Ver
   `docs/retrospectiva_over_1_5_3_5_4_5_2026-08-25.md`.
9. **Simulação "desde 2023" revela que o z=2,24/2,91 é só o holdout
   2026, não o histórico completo** — apostando com neutro+edge≥8%
   desde 2023: Over 2.5 dá ROI acumulado **−2,3%** (2023/2025 foram
   anos de prejuízo, 2024/2026 de lucro); BTTS dá **+5,0%**, também com
   variação enorme ano a ano. Corrige a impressão de "edge comprovado"
   que os z-scores do holdout sozinhos passavam.
10. **Favorito DC (sozinho e combinado com Over/Under) não tem edge** —
   Lucas relatou que essa combinação funcionou pra ele no passado;
   implementamos `probabilidade_resultado` + `simular_apostas_combo`
   (múltipla genérica) pra testar. Resultado: sempre negativo sozinho,
   pior ainda combinado com Over 2.5, e combinado com BTTS não passa de
   z≈1 em nenhuma liga. Ver `docs/retrospectiva_favorito_dc_2026-08-25.md`.
11. **Corte de outlier mais apertado melhora Over 2.5 na Série A —
   primeira melhoria real sobre o neutro** — variando
   `multiplicador_dp`/`limite_unilateral` (nunca testados antes):
   `multiplicador_dp=1.5, limite_unilateral=2` dá z=+1,50 (ROI+16,2%)
   no período completo 2023-2026, contra z=−0,31 (ROI−2,3%) do padrão
   — confirmado como platô (não célula isolada) e com estabilidade ano
   a ano melhor. Ainda z<2, específico da Série A/Over 2.5. Ver
   `docs/retrospectiva_corte_outlier_2026-08-25.md`.
12. **Grid completo (parâmetros + corte de outlier + todas as linhas de
   Over): melhor achado da sessão** — combinando `k_mando × usar_estilo
   × filtro_aderencia` com o corte de outlier apertado, achou
   `k=0.5, sem estilo, filtro=0.8, mult_dp=1.5, uni=2, edge=5%` pra
   Over 2.5 na Série A: **z=+2,23, ROI+16,0%, n=221** no período
   completo 2023-2026 — primeiro candidato do projeto a passar de z=2
   sem depender só do holdout, e SEM nenhum ano negativo real (pior ano:
   2025, −1,0%, essencialmente zero). BTTS também tem candidato forte
   (z=+2,13) mas com pior consistência ano a ano. Série B segue sem
   configuração defensável. **Este é agora o critério de aposta
   recomendado pra Over 2.5 na Série A** — substitui o critério anterior
   (neutro + edge≥8%). **Achado mais importante da sessão até agora** —
   ver `docs/retrospectiva_grid_completo_2026-08-25.md`.
13. **Teto de odd máxima por mercado — não muda o critério campeão de
   Over 2.5** — testado teto (Over1.5≤1,5/Over2.5≤3/Over3.5≤6/
   Over4.5≤7/BTTS≤2) em cima do combo campeão: pra Over 2.5 o teto não
   filtra nenhuma aposta (resultado idêntico com/sem, `n=221,
   ROI+16,0%, z=+2,23`). Parecia ajudar o BTTS também, mas isso usava
   os parâmetros de modelo do combo de Over 2.5, não os de BTTS — ver
   item 16 (com os parâmetros certos, o teto piora). Ver
   `docs/retrospectiva_odd_maxima_2026-08-25.md`.
14. **Under com odd aproximada (a partir da odd de Over) — testado e
   DESCARTADO, não é edge real** — o CSV não tem odd real de Under, só
   de Over; construímos uma aproximação (`pesos.odd_e_prob_under_aproximada`)
   documentada desde antes do teste como tendencialmente otimista. O
   resultado confirmou isso: **ROI positivo em 24 de 24 combinações**
   testadas (4 linhas × 2 ligas × 3 edges), com z-scores implausíveis
   (até z=+6,18) — assinatura clássica de viés sistemático da fórmula,
   não de vantagem real (nenhum mercado líquido deixaria essa
   "ineficiência" aberta em todas as linhas, nas duas ligas, por 4 anos).
   Ver `docs/retrospectiva_under_aproximado_2026-08-25.md`.
15. **Under com margem de casa assumida (~7-8%) — viés corrigido, mas
   ainda sem edge** — estendemos `odd_e_prob_under_aproximada` com um
   parâmetro `margem_total` (medimos a margem real desta fonte de dado
   nos mercados 1x2/BTTS: ~7% Série A, ~8% Série B) em vez de assumir
   margem zero. **O viés sistemático desaparece** (só 5/24 combinações
   positivas, contra 24/24 antes), confirmando que a correção é
   sensata — mas **continua sem edge real**: os mercados com amostra
   confiável (Under 1.5/2.5) ficam consistentemente NEGATIVOS nas duas
   ligas (z até −3,35). **Não usar nenhum critério de Under pra apostar
   dinheiro real** — agora por duas razões independentes, não só viés
   de fórmula. Ver `docs/retrospectiva_under_margem_2026-08-25.md`.
16. **BTTS com parâmetros próprios + teto de odd — confirma z=+2,13,
   mas teto piora (não ajuda como o item 13 sugeria)** — testado o
   candidato de BTTS (`k=0.7, usar_estilo=True, filtro_aderencia=0`)
   com o teto (≤2,0) usando SEUS PRÓPRIOS parâmetros de modelo: o teto
   reduz o z de +2,13 pra +1,18 — descartar teto pra BTTS. **Sem teto,
   confirma z=+2,13, ROI+21,5%, n=95** no período completo, com
   consistência ano a ano mais fraca que o Over 2.5: **2 dos 4 anos com
   queda real** (2023: −7,7%, 2025: −6,7%). **Superado pelo item 17
   abaixo.** Ver `docs/retrospectiva_btts_final_2026-08-25.md`.
17. **Janela de histórico + filtros separados: novo candidato de BTTS,
   mais forte que o anterior e tão consistente quanto o Over 2.5** —
   nunca tínhamos variado `n_historico` (sempre 15) nem separado o
   filtro de aderência de estilo do de favoritismo (implementados nesta
   sessão). Grid de 48 combinações × 3 edges achou, pra BTTS:
   `k=0.7, usar_estilo=True, filtro_estilo=0.8, filtro_favoritismo=0.65,
   n_historico=10, edge=5%` → **n=207, ROI+17,9%, z=+2,65, SEM nenhum
   ano negativo** (2023 +18,3%, 2024 +19,0%, 2025 +1,9%, 2026 +37,2%) —
   mais amostra e mais consistente que o candidato anterior. **Agora é
   o segundo critério de aposta recomendado** (volume combinado com
   Over 2.5: ~122 apostas/ano). Pro Over 2.5, o mesmo grid confirmou o
   critério já vigente sem melhorá-lo (o filtro de estilo nunca
   filtrava nada nesse mercado). Série B continua sem qualquer
   candidato viável mesmo com esses eixos novos. Também testamos
   segmentar o Over 2.5 por nível de favoritismo (tercis): achado
   curioso em U (extremos melhores que o meio-termo), mas não acionável
   — amostra pequena por tercil e risco alto de comparação múltipla.
   Ver `docs/retrospectiva_novos_eixos_2026-08-25.md`.
18. **Dupla confirmação (Over 2.5 + BTTS no mesmo jogo) — resultado mais
   forte da sessão, com ressalva de comparação múltipla** — segmentando
   os 113 jogos onde os dois critérios acima coincidem (apostando as
   duas pernas separadamente, não é combo/parlay): **n=226, ROI+22,7%,
   z=+3,40, SEM nenhum ano nem perto de negativo** (2025, o ano mais
   fraco histórico, fica em +8,2% — o melhor resultado de 2025 em
   qualquer critério da sessão). Maior z de todo o projeto. **Ressalva
   importante**: empilha uma terceira camada de seleção (grid do Over
   2.5 + grid do BTTS + interseção dos dois), e as duas apostas do mesmo
   jogo são correlacionadas — tratar como sinal de maior confiança, não
   como prova mais forte que os dois critérios-pai. Os jogos que NÃO
   coincidem continuam positivos sozinhos em cada mercado (BTTS
   +9,9%, Over2.5 +11,0%) — não é motivo pra parar de apostar fora da
   interseção. Ver `docs/retrospectiva_dupla_confirmacao_2026-08-25.md`.
19. **1x2 e Dupla Chance de mandante/visitante — testado, NÃO USAR** —
   implementados `pesos.probabilidades_implicitas_nvias` (de-vig de N
   vias) e `retrospectiva._probabilidades_1x2_e_dc` (casa/empate/fora
   com odd REAL de mercado, mais Dupla Chance de lado fixo). Grid
   completo (96 combos × 2 ligas): Série A sem sinal em nenhum mercado
   (melhor z=+0,27). Série B: "casa" parecia forte (z=+2,71, n=354,
   robusto a vizinhança de parâmetros), **mas é um sinal morto** — ano a
   ano mostra deterioração progressiva (2023 +35,8%→2024 +38,6%→2025
   +2,3%→2026 **−9,9%**); só os 2 anos mais recentes juntos já dão
   ROI≈−2,8%. O z agregado alto vinha só dos anos antigos. **Não usar.**
   Ver `docs/retrospectiva_1x2_dc_2026-08-25.md`.
20. **1x2/DC com n_historico + filtros separados — confirma, não muda
   nada** — mesmo eixo que melhorou o BTTS, aplicado aos mercados de
   1x2/DC (rodado em paralelo, 4 processos, pra acelerar): o "casa" da
   Série B mantém a mesma deterioração ano a ano em toda a vizinhança
   testada — não é problema de calibração fina, é tendência temporal
   que nenhum corte de amostra reverte. Série A continua sem sinal em
   nenhum mercado. Ver `docs/retrospectiva_1x2_dc_novos_eixos_2026-08-25.md`.
21. **Planilha de testes visuais ganha botão "Recalcular" no Excel** —
   `gerar_planilha_testes.py` refatorado (`computar_jogos`/`gerar_workbook`
   reutilizáveis) e todos os parâmetros já validados na sessão
   (`filtro_estilo`, `filtro_favoritismo`, `n_historico`, além dos já
   existentes) agora editáveis na aba Parâmetros. Novo
   `SerieA_testes_visuais.py` (script pareado do xlwings) permite clicar
   "Run main" no Excel e recalcular a aba Jogos inteira sem terminal —
   setup de uma vez em `docs/planilha_botao_recalcular.md`. Validado bit
   a bit o cálculo/round-trip de parâmetros (bate exatamente com
   `simular_apostas`); a interação de clique dentro do Excel não pôde
   ser testada neste ambiente (sem Excel disponível).
22. **Estabilidade por era (2016-2026) — critérios campeões NÃO são
   duráveis em 10 anos** — Lucas conseguiu 7 temporadas adicionais da
   Série A (2016-2022), estendendo a cobertura de 4 pra 11 anos. Os
   critérios de Over 2.5 (z=2,23) e BTTS (z=2,65), calibrados só em
   2023-2026, caem pra z≈0 (+0,12/+0,46) no agregado de 11 anos —
   negativos em 2016-2019 e 2020-2022, só positivos em 2023-2026 (a
   janela de calibração). Duas hipóteses não excludentes: overfitting
   dos parâmetros ao período de treino, ou mudança real de regime de
   mercado (regulamentação de apostas no Brasil, Lei 14.790/2023, casas
   licenciadas desde 2024). Não invalida o uso atual (2023-2026 segue
   positivo e é o período relevante pra apostar agora), mas rebaixa a
   confiança de "forte" pra "moderada, específica do período recente".
   Ver `docs/retrospectiva_estabilidade_era_2026-08-26.md`.
23. **Recalibração 2016-2022 → holdout 2023-2026 — não existe parâmetro
   durável** — grid de 208 combinações (`k_mando`, corte de outlier,
   `n_historico`, filtros de estilo/favoritismo) rodado inteiramente em
   2016-2022, selecionando só por ROI de treino. Nenhuma configuração
   tem edge defensável: a melhor de Over 2.5 tem ROI **negativo**
   (-2,7%, z=-0,36); a melhor de BTTS chega a z=+0,37 (ruído, não
   sinal). Não é problema de calibração fina — em 832 avaliações,
   nenhuma combinação mostrou edge por acaso, o que pesa contra
   "overfitting simples" e a favor de mudança real de regime de mercado
   (regulamentação de apostas no Brasil). Confirma: não existe um
   conjunto de parâmetros durável nas 3 eras — mantém a recomendação de
   usar os critérios calibrados em 2023-2026 pra apostar agora, com
   confiança moderada. Ver
   `docs/retrospectiva_recalibracao_holdout_2026-08-26.md`.
24. **Rotina semanal de checagem de decaimento** — `checar_decaimento.py`
   roda os dois critérios campeões (Over 2.5, BTTS) contra o dado
   disponível, mede ROI/z no acumulado 2023-2026 e numa janela móvel dos
   últimos 90 dias (a janela recente é o que pega decaimento cedo — o
   acumulado se move devagar demais), e registra em
   `docs/decaimento_semanal.md` (uma linha por checagem, pra dar pra
   acompanhar a tendência ao longo de várias semanas). Rotina agendada
   (toda segunda) pergunta se há export novo do FootyStats pra
   atualizar — não busca dado sozinha, depende do Lucas subir o CSV.
25. **Início de temporada não explica a queda de ROI ao estender o
   histórico** — separamos as apostas 2023-2026 por rodada (`Game
   Week`, cortes de 5/10) pra testar se jogos de início de temporada
   saem sistematicamente piores. Sem padrão consistente: o resultado
   inverte de sinal dependendo do corte, nos dois mercados. A queda de
   ROI observada (n=221→278 no Over 2.5) provavelmente é um efeito único
   de bootstrap do dataset (só o início de 2023, quando faltava
   histórico anterior), não um padrão recorrente a cada temporada. Não
   muda nenhuma recomendação. Ver
   `docs/retrospectiva_inicio_temporada_2026-08-26.md`.
26. **Escanteios e cartões via odds reais do Sportmonks — testado, NÃO
   USAR ainda** — Lucas queria diversificar além de Over 2.5/BTTS;
   validamos que o Sportmonks tem odds reais de escanteios/cartões
   (cobertura confirmada, dado consistente com FootyStats) e testamos
   reaproveitando o motor de gols atual. Escanteios: sinal **negativo**
   forte e consistente nas duas ligas (Série A z=-2,38, Série B
   z=-2,80, todos os anos) — não é calibração, é viés sistemático.
   Cartões: sem edge, mas ruído (não viés) — provavelmente precisa do
   fator árbitro (Sportmonks expõe `referee_id`, mas não estatística
   agregada pronta) pra sair do zero. **Confirmado também com os
   parâmetros campeões de Over 2.5 e BTTS** (não só neutro) —
   escanteios negativo nas 6 combinações testadas (2 ligas × 3
   configs), cartões perto de zero e inconsistente nas 6. **Testamos
   também reescalar `limite_unilateral`** (corte de outlier calibrado
   pra escala de gols, ~1,4/time, nunca reescalado pra escanteios
   ~5/time ou cartões ~2,6/time): não ajuda escanteios (continua
   negativo), mas ajuda cartões (Série B passa a ter os 3 anos
   positivos com o corte do BTTS, ainda abaixo de z≈2). **Testamos
   também combinar cartões com dado de árbitro** (`referee_id` via
   Sportmonks): Série A piora com mais peso no árbitro (não usar);
   Série B melhora e cruza z≈2 no agregado (ROI+9,8-10,9%, positivo
   nos 3 anos), mas o z está inflado por uma amostra de só n=28 em
   2024 — não é prova definitiva, vale continuar acompanhando. Mantém
   recomendação de usar só Over 2.5/BTTS. Ver
   `docs/retrospectiva_escanteios_cartoes_2026-08-27.md`.
27. **Série B BTTS (k=0.2/estilo/filtro=0.65) reavaliado no período
   completo — NÃO se sustenta, item fechado.** O z≈0,9-1,0 documentado
   no item 7 era só o holdout 2026; rodando o mesmo parâmetro em
   2023-2026 inteiro (n=262), o resultado deixa de ser um "platô
   robusto": 2023 e 2024 são negativos (z=-0,40 e -0,15), só 2025/2026
   são positivos, agregado cai pra z=+0,76. Testando também com odds
   Sportmonks (2024-2026 pareado, mesmo método usado no item 26): o
   pouco sinal que sobrava quase desaparece (z=+1,04 FootyStats →
   z=+0,16 Sportmonks). Diferente de cartões+árbitro (item 26, positivo
   nos 3 anos isolados), aqui 2 dos 4 anos são diretamente negativos —
   não é o mesmo tipo de caso, não vale manter em observação. Ver nota
   "Reteste 27/08/2026" em `docs/protocolo.md`.
28. **Cartões+Árbitro (Série B) formalizado como 3º critério, stake
   reduzido** — o achado do item 26 (z≈1,73 combinado 2025+2026, positivo
   isoladamente nos 3 anos) virou produção de verdade: novo módulo
   `metodologia_pesos/cartoes_arbitro.py` (testado, `test_cartoes_arbitro.py`),
   `sportmonks_pull_serieb_cartoes.py` (atualiza
   `data/sportmonks_serieb_cartoes/fixtures.jsonl` com odds de Cartões +
   `referee_id` da Série B) e `checar_decaimento.py` estendido pra
   monitorar esse critério toda semana junto com Over 2.5/BTTS. Rodado
   de ponta a ponta pela primeira vez: n=387, ROI+8,1%, z=+1,71
   acumulado — consistente com o número original. Adotado com stake
   ~1/3 do normal (não paridade com Over 2.5/BTTS) — ver seção
   "Terceiro critério (stake reduzido)" em `docs/protocolo.md`.

29. **Under retestado com odd REAL do Sportmonks — confirma, fecha a
   questão** — usando os 2 conjuntos de params já campeões (Over 2.5 e
   BTTS) × 2 ligas × 4 linhas (1.5/2.5/3.5/4.5) = 16 células, **todas
   as 16 deram negativo**, e 47 dos 48 recortes ano-a-ano dentro delas
   também (a única exceção é ruído, nem a célula agregada é positiva).
   Diferente das rodadas anteriores (item 14/15, que usavam odd
   aproximada), aqui a odd é real de mercado — confirma que o problema
   não é a fonte de dado, é o mercado de Under mesmo. Ver
   `docs/retrospectiva_under_odds_reais_2026-08-27.md`.
30. **Migração pra 100% Sportmonks iniciada — BTTS confirma, Over 2.5
   não.** Lucas decidiu cancelar o FootyStats e automatizar tudo numa
   rotina + painel (sem planilha manual). Construído
   `sportmonks_adapter.py` (traduz fixture do Sportmonks pro formato que
   o motor já entende, sem tocar em `pesos.py`/`retrospectiva.py`/
   `estilo.py`) — resolveu 2 problemas reais: xG não existe nessas ligas
   no Sportmonks (usa gols reais como proxy) e ~5-16% dos jogos têm
   estatística de detalhe faltando (reaproveita o sentinela de dado
   ausente já existente). Rodando os 2 critérios campeões 100% em cima
   do Sportmonks: **BTTS (Série A) confirma** (z=+2,33, quase igual ao
   original) — vai pro painel com stake normal. **Over 2.5 (Série A)
   não se sustenta** (z caiu pra +0,49) com os parâmetros antigos —
   recalibração dedicada (grid de 192 combinações) achou um candidato
   novo (`k=0.35, sem estilo, filtro=0.65, mult_dp=1.5, uni=4,
   edge=8%`). Ver `docs/retrospectiva_validacao_100_sportmonks_2026-08-27.md`
   e `docs/retrospectiva_over25_sportmonks_2026-08-27.md`.
31. **Over 2.5 recalibrado validado com treino/holdout honesto — entra
   no painel com stake reduzido.** Lucas questionou o descarte do item
   30 (positivo nos 3 anos, "ganha na média"). Reavaliação correta:
   escolher o parâmetro usando SÓ 2024+2025 (sem espiar 2026) dá
   z_treino=+1,15 (fraco sozinho); o holdout real em 2026 (nunca visto
   na escolha) dá z=+2,83 (n=23, pequeno mas honesto). Mesmo padrão do
   Cartões+Árbitro — adotado com stake reduzido, não descartado.
   Auditoria de todos os outros achados rejeitados da sessão sob essa
   mesma régua ("sem ano negativo, mesmo que z<2") não revelou nenhum
   outro candidato — todos os demais têm pelo menos um ano
   genuinamente negativo (Série B BTTS, Favorito DC, "casa" 1x2 Série
   B) ou tendência de deterioração, o que os desqualifica mesmo sob a
   régua mais permissiva.
32. **Painel automatizado substitui a planilha manual** —
   `sportmonks_client.py` (pull de fixtures finalizados e futuros,
   odds pré-jogo incluídas) + `sportmonks_adapter.py` (traduz fixture
   do Sportmonks pro formato do motor; fixture futuro vira uma linha
   SINTÉTICA — placar placeholder nunca lido de verdade — pra
   reaproveitar `retrospectiva.prever_jogo`, feito pra backtesting, sem
   duplicar lógica de previsão) + `previsao_dia.py` (gera as sugestões
   dos 3 critérios ativos) + `gerar_painel_dia.py` (monta o HTML).
   Testado de ponta a ponta com dado real: 5 sugestões geradas pros
   próximos jogos das duas ligas. Publicado como Artifact, atualizado
   por uma Claude Code Routine diária (08h BRT, sem notificação
   proativa) — depende de `SPORTMONKS_TOKEN` como variável de ambiente
   persistente no ambiente do Claude Code (configuração pendente do
   Lucas, fora do que dá pra fazer via ferramentas desta sessão).
33. **Painel ganha registro de resultados (Green/Red) e resumo de
   ROI na lateral** — novo `ledger_apostas.py`: cada sugestão vira uma
   entrada `pendente` (persistida em `data/ledger_sugestoes.json`,
   versionado no git), resolvida pra Green/Red assim que o jogo aparece
   como finalizado no histórico já atualizado do Sportmonks. Stake fixo
   de gestão de banca (BTTS=1u, os outros=0,5u — diferente do "stake
   normal/reduzido" de confiança estatística). Painel ganha uma seção
   "Resultados recentes" (últimos 14 dias) e uma barra lateral com
   entradas/green/red/ROI, geral e por critério.
34. **Bug real reportado pelo Lucas: sugestão de cartões numa linha que
   não existia em nenhuma casa que ele usa — corrigido restringindo
   tudo ao bet365.** Investigação encontrou 2 causas: (1)
   `linha_mais_liquida` escolhia a linha com mais casas cotando, mas o
   Sportmonks agrega dezenas de casas internacionais (Unibet, Pinnacle
   etc.) que o Lucas não tem acesso — um empate entre linhas de 1 casa
   cada foi resolvido de forma arbitrária; (2) Betano não existe no
   catálogo do Sportmonks pro Brasil. bet365 é a única casa real dele
   coberta de forma confiável (999/999 Série A, 998/1000 Série B).
   Revalidação completa com bet365-só (não mais a média de todas as
   casas) mudou a recomendação: **BTTS (z=+2,89) e Cartões+Árbitro
   (z=+2,08) ficaram MAIS fortes; Over 2.5 recalibrado (item 31) ficou
   mais fraco e teve 2025 virar negativo (z=−0,72 nesse ano) — removido
   do painel.** Ver `docs/retrospectiva_bookmaker_bet365_2026-08-27.md`.
35. **Over 2.5 recalibrado READICIONADO ao painel usando odd da Sbo
   (bookmaker_id=34), não bet365** — Lucas pediu pra testar outras casas
   antes de descartar (item 34). Testando os mesmos parâmetros contra
   12 bookmakers do catálogo Sportmonks, **Sbo é o único acima de z≈2
   sem nenhum ano negativo** (z=+2,00, n=80, ROI+23,6%; 2024 z=+1,38,
   2025 z=+0,28, 2026 z=+2,07) — ranking bruto por z era enganoso
   (Pinnacle no topo, z=+2,31, mas 2025 negativo, mesmo problema do
   bet365). Investigamos também se a entrada "Betfair" do Sportmonks
   (bookmaker_id=9) é a Betfair Exchange (Lucas relata odd melhor lá
   pra esse mercado) — não é: cobertura rala (8,9-16,1% vs 98,7-98,9%
   da Sbo), margem MAIOR que o bet365, e grade de preço fixa (34
   valores distintos) — características de sportsbook tradicional, não
   de exchange peer-to-peer. A Betfair Exchange não está representada
   no dado do Sportmonks; painel documenta a Sbo como odd de referência
   e recomenda tentar a Betfair Exchange primeiro na execução real. Ver
   `docs/retrospectiva_over25_sbo_betfair_2026-08-27.md`.
36. **Análise exploratória green/red do Over 2.5-Sbo (item 35), à
   procura de um filtro adicional** — separando as 80 apostas em
   green/red e comparando 11 features (odd, edge, probabilidades,
   `gf_pred`/`ga_pred`/`total_pred` do modelo, e pela primeira vez o
   `predictions` do próprio Sportmonks, `type_id=235`, confirmado
   disponível retroativo com cobertura completa). Dois candidatos reais
   (consistentes nos 3 anos, `n≥27`, força quase idêntica entre os
   dois): **odd mais baixa** (odd≤2,20: 69,6% acerto/ROI+39,3% vs
   odd>2,20: 44,1%/+2,4%, monotônico em todo limiar testado) e
   **concordância com o `predictions` do Sportmonks** (67,5%/+39,2%
   vs 50,0%/+8,0%) — combinar os dois NÃO ajuda (interseção fica com
   ROI+30,6%, pior que qualquer um isolado — sinais correlacionados,
   não independentes); o grupo "nem odd baixa nem Sportmonks concorda"
   é o único com ROI NEGATIVO da análise (n=27, −6,1%). Também um
   alerta: edge mais alto teve acerto E ROI PIORES nesta amostra, com o
   padrão invertendo de sinal entre 2024 e 2025/2026 — não usar como
   filtro, é ruído. (Nota: a primeira versão desta análise reportava
   ROI em dobro por um bug de stake inconsistente no script ad-hoc,
   corrigido no mesmo dia — taxas de acerto e `n` não foram afetados.)
37. **Teto de odd 2,20 adotado pro Over 2.5-Sbo (item 36), em
   produção** — antes de decidir, comparei o lucro ABSOLUTO com stake=1
   pros dois grupos (mesmos 80 jogos): praticamente empatado em $
   (+18,88u sem teto vs +18,07u com teto) — o teto atinge quase o mesmo
   retorno com 43% menos capital exposto (46 apostas em vez de 80) e
   taxa de acerto bem maior (69,6% vs 58,8%). Lucas decidiu adotar por
   isso. Implementado em `previsao_dia.CRITERIOS_GOLS`
   (`odd_maxima=2.20` no critério de Over 2.5) — `avaliar_criterio_gols`
   pula a sugestão se a odd real do dia vier acima disso.
38. **Varredura de achados antigos de amostra grande, não positivos ou
   fracos, atrás de filtro (pedido do Lucas)** — primeira rodada:
   **favoritismo (1x2) no Over 2.5-Sbo** — jogos equilibrados rendem
   muito mais que favoritos claros (65,0%/ROI+41,8% vs 52,5%/+5,4%, 3
   anos limpos do lado equilibrado). Sinal real, mas NÃO empilhado com
   o teto de odd (item 37) — a combinação tripla teria `n=5`/ano,
   insuficiente. Ver
   `docs/retrospectiva_filtro_favoritismo_over25_2026-08-27.md`.
   Segunda rodada: **1x2 "casa" Série B** (o maior z já achado na
   Série B, mas já sabido "morto" por decaimento — item 20/21)
   revalidado com dado atual (Sportmonks/bet365): mesmo decaimento
   (2024 ROI+31,0% → 2025 +4,1% → 2026 −18,3%). Testei 7 características
   restringindo só a 2025+2026 (o período já morto) — **nenhum corte
   resgata o sinal, 2026 fica negativo em todo subgrupo testado**.
   Confirma eficiência de mercado genuína, não ruído — não vale
   reabrir sem mudança estrutural no motor. Ver
   `docs/retrospectiva_filtro_casa_serieb_2026-08-27.md`.
   Terceira e quarta rodadas (mesmo dia): **1x2 casa Série A** (z=+0,27
   original) e **mandante_dc Série B** (z=+0,09) — os "menos ruins"
   restantes na família 1x2/DC, escolhidos por não serem correlacionados
   com o Over Série A. Diferença chave: esses partem de z≈0 (nunca
   tiveram edge real), não de um sinal que decaiu — filtro-mineração
   com as mesmas 7 features não produziu NENHUM subgrupo com os 3 anos
   positivos em nenhum dos dois. Fecha a família 1x2/DC inteira como
   "sem edge, mesmo com filtro" — os demais (empate/fora/visitante_dc,
   já negativos de forma mais clara) não valem retestar. Ver
   `docs/retrospectiva_filtro_1x2_ruido_2026-08-27.md`. Restante da
   varredura (Escanteios, Under, Over1.5/3.5/4.5, Favorito DC) agendado
   numa rotina semanal (quartas-feiras, 3 candidatos por vez) — ver
   `docs/varredura_filtros_checklist.md`.
39. **Regra "União" substitui o teto de odd sozinho (item 37) no
   Over 2.5-Sbo, em produção** — Lucas perguntou como ficaria juntar o
   teto de odd com o favoritismo (item 38) de forma menos restritiva
   (bastar UM dos dois sinais, não os dois). Cruzando os 80 jogos em 4
   quadrantes (odd baixa/alta × equilibrado/favorito claro): só "odd
   alta E favorito claro" (n=10) é ruim (ROI−32,3%) — os outros 3
   quadrantes (n=70) são todos positivos. A União (pular só quando os
   DOIS sinais forem desfavoráveis) gera mais volume E mais lucro
   absoluto que o teto sozinho (n=70 ROI+31,6%/lucro+22,11u vs n=46
   ROI+39,3%/+18,07u, stake=1), com os 3 anos bem representados (n=18,
   29, 23). A interseção (exigir os dois ao mesmo tempo, n=16) tem ROI
   ainda maior no papel (+79,3%) mas fica fina demais por ano (`n=3`
   em 2024/2025) pra confiar — não adotada. Implementado em
   `previsao_dia.CRITERIOS_GOLS` (`odd_maxima=2.20` +
   `limiar_favoritismo=0.7484`).
40. **Testei se o mesmo filtro rende edge no Under 2.5 Série A —
   não rende** — Lucas notou que favorito claro/odd alta de Over
   "fecham" o jogo (menos gols) e perguntou se isso também dá edge pro
   lado Under (mercado já descartado antes, item 29). Rodei o motor
   com os parâmetros de produção do Over 2.5 e odd REAL de Under 2.5
   (bet365, 999/999 fixtures) — negativo em toda a amostra (n=497,
   ROI−12,6%) e em todo corte testado, inclusive o quadrante exato da
   hipótese (favorito claro E Over-odd alta, n=77, ROI−15,1% — PIOR
   que a base). Nuance explicada: "Over foi pior nesses jogos" ≠
   "existe edge pra Under" — a odd real de Under já precifica essa
   tendência, não sobra vantagem pro modelo capturar. Fechado. Ver
   `docs/retrospectiva_filtro_under25_favoritismo_2026-08-27.md`.
41. **`checar_decaimento.py` reconstruído — mensal, 100% Sportmonks,
   cobre os 3 critérios de produção** — Lucas pediu um processo de
   revalidação periódica. Decisão: NÃO re-rodar treino/holdout todo mês
   (reintroduziria o mesmo risco de comparação múltipla do dia inteiro,
   e o incremento de dado mensal é pequeno demais pra re-derivar
   parâmetro com confiança) — em vez disso, virou monitoramento de
   decaimento com os parâmetros FIXOS já em produção, reaproveitando
   `previsao_dia.CRITERIOS_GOLS`/`PARAMS_CARTOES_TIME`/
   `passa_filtros_gols` diretamente (extraído de `avaliar_criterio_gols`
   pra nunca duplicar a lógica do filtro União em dois lugares).
   Descontinuado `sportmonks_pull_serieb_cartoes.py` e
   `data/sportmonks_serieb_cartoes/` (pull estreito separado, obsoleto)
   — cartões agora lê `referee_id`/odds direto de
   `data/sportmonks_serieb/fixtures.jsonl`, o mesmo arquivo do painel.
   Rodado de ponta a ponta: os 3 números batem exatamente com o já
   documentado (BTTS z=+2,89, Over 2.5 n=70/ROI+31,6% igual ao filtro
   União, Cartões+Árbitro z=+2,08) — confirma que a reconstrução está
   fiel à produção real. Log novo em `docs/decaimento_mensal.md`
   (substitui `docs/decaimento_semanal.md`, mantido como registro
   histórico da era FootyStats).

42. **Bug real: painel sugeria linha de cartões que não existia na casa
   do Lucas (Goiás, "Under 4,5" vs. a casa só tinha "Under 3,5")** —
   causa raiz: `cartoes_arbitro.linha_mais_liquida` escolhia a linha
   quotada por mais bookmakers distintos, o que fazia sentido antes da
   restrição a bet365 (item anterior/`docs/retrospectiva_bookmaker_bet365_2026-08-27.md`)
   mas depois dela `jogo['odds']` sempre tem 1 bookmaker só — toda linha
   alternativa que o bet365 cota (cartões tem várias: 3,5/4,5/5,5...)
   empatava em "1 bookmaker", e o desempate caía pra ordem arbitrária de
   serialização do Sportmonks, não pra linha relevante. Confirmado com
   exemplo real (Cuiabá x Goiás, 22/08: 4,5 e 5,5 empatados, ordem bruta
   favorecia 5,5). Sportmonks não expõe campo de "linha principal" nos
   dados — corrigido com heurística: em empate, escolhe a linha com odd
   Over/Under mais próxima da paridade (proxy padrão de mercado pra
   linha destacada). Revalidação (`checar_decaimento.py`, que reusa a
   mesma função): z=+2,08→+2,01 acumulado, z=+1,48→+1,60 últimos 90
   dias — edge se sustenta, correção não inverteu o sinal. BTTS/Over 2.5
   não usam essa função, não afetados. Ver
   `docs/retrospectiva_linha_cartoes_bug_2026-08-28.md`. **Ressalva
   permanente**: é heurística, não garantia — sempre conferir a linha
   exata na casa antes de apostar em cartões.

43. **2º bug no mesmo caso: o painel ficava "preso" mostrando a
   sugestão antiga mesmo depois da correção acima** — Lucas confirmou
   que o Goiás x São Bernardo continuava com "Under 4,5" mesmo depois
   de rodar a rotina de novo com o código já corrigido. Causa raiz
   diferente: `sportmonks_client.puxar_fixtures_futuros` decidia "jogo
   ainda não jogado" checando `home_goals is None` — mas o Sportmonks
   publica um placeholder `CURRENT` 0-0 pouco antes do jogo começar
   (confirmado: `state_id` continuava 1/NS quando isso aconteceu), o
   que faz `home_goals` virar 0 (não `None`) e o jogo simplesmente
   desaparecer da lista de jogos futuros — o painel para de reavaliar
   esse jogo, ficando preso na última sugestão computada antes do
   placeholder aparecer. Risco mais sério (não confirmado como já
   tendo ocorrido): a mesma lógica em `puxar_fixtures_finalizados`/
   `atualizar_fixtures_finalizados` (histórico do motor) podia gravar
   esse placar fantasma 0-0 PERMANENTEMENTE no histórico (o pull
   incremental só adiciona `fixture_id` novo, nunca corrige um
   existente). Corrigido: `flatten_fixture` agora extrai `state_id`
   (campo sempre presente, confirmado via `/states` da própria API:
   1=NS, 5=FT, 7=AET, 8=FT_PEN), e as 3 funções passam a decidir
   "ainda não jogado"/"finalizado" por `state_id`, nunca mais por
   presença de gols. Testes novos cobrindo o caso exato (fixture NS
   com placeholder 0-0) em `test_sportmonks_client.py`. Verificado ao
   vivo: com a correção, `puxar_fixtures_futuros` volta a trazer o
   jogo do Goiás (9 fixtures em vez de 8), e a linha de cartões
   escolhida bate com a bet365 real (3,5, odd 1,83/1,83). Ver
   `docs/retrospectiva_estado_fixture_bug_2026-08-28.md`.

44. **3º achado no mesmo caso: painel não recalcula sugestão já
   registrada** — mesmo com as 2 correções acima, o painel continuou
   preso mostrando "Goiás Under 4,5" por 3 execuções seguidas. Causa:
   `ledger_apostas.registrar_novas_sugestoes` nunca sobrescreve uma
   entrada `(fixture_id, critério)` já registrada — a do Goiás tinha
   sido gravada em 27/08, antes de qualquer correção existir, e ficou
   congelada com o valor errado pra sempre (design correto em geral —
   evita mudar a odd de uma aposta já feita — só falhou porque o
   valor original nasceu errado). Corrigi manualmente essa UMA entrada
   no `data/ledger_sugestoes.json` (Under 3,5, odd 1,83, edge 3,08% —
   caiu de 19,9% porque a linha errada tinha odd mais generosa por ser
   desequilibrada). Recomputei as outras 4 entradas de Cartões
   pendentes pra checar se tinham o mesmo problema — não tinham (só
   odd/edge com movimento normal de mercado, não bug), não mexi
   nelas. Ver `docs/retrospectiva_estado_fixture_bug_2026-08-28.md`.

## O que ainda falta
- Série B Over 2.5 e as linhas Over 1.5/3.5/4.5 (as duas ligas) seguem
  sem qualquer edge defensável — não apostar por este critério.
- Cartões+Árbitro (Série B, item 28) está em stake reduzido — mesmo com
  bet365 (z=+2,08, item 34) ainda vale acompanhar
  (`checar_decaimento.py`, precisa migrar pra ler odds só do bet365
  também) antes de promover pra stake normal.
- Over 2.5 (Série A, item 35) está em stake reduzido com odd da Sbo e
  filtro "União" (odd/favoritismo, item 39) — testar 12 bookmakers é
  uma comparação múltipla em menor escala; reavaliar conforme mais
  dado (2027) entra na amostra, mesmo tratamento do Cartões+Árbitro.
  Concordância com o `predictions` do Sportmonks (item 36) NÃO foi
  adotada — força quase idêntica ao teto de odd sozinho, mas
  dependeria de manter um pull novo rodando. A interseção do filtro
  União (exigir odd baixa E favoritismo ao mesmo tempo, item 39) tem
  amostra fina demais por ano — reavaliar quando 2027 entrar.
- `SPORTMONKS_TOKEN` já configurado como variável de ambiente
  persistente (resolvido em 27/08/2026, após 3 tentativas — aspas
  curvas do teclado do iPhone corrompendo o valor) — rotina diária do
  painel (item 32) rodando sozinha.
- Escanteios (Série A + Série B) seguem sem qualquer edge com o motor
  atual, mesmo com odd real do Sportmonks (item 26) — não vale
  insistir sem repensar o motor de previsão desse mercado especificamente.
- Under: encerrado (item 29) — testado com odd aproximada, com margem
  corrigida e com odd real, sempre sem edge. Não reabrir sem uma
  mudança de motor de verdade.
- Os proxies de Pressão Alta/Transição/Bola Parada em `estilo.py` não
  estão se mostrando úteis em nenhum mercado testado — candidatos a
  redesenho (dado mais rico) antes de reavaliar a contribuição do estilo.
- `k_mando`/`limite_unilateral`/`multiplicador_dp` só foram calibrados
  olhando o mercado de gols — os outros 11 mercados têm MAE calculado mas
  não passaram pelo mesmo grid search ainda.
- Planilhas manuais (skills de Série A/B) foram substituídas pelo painel
  automatizado (item 32) pra Série A BTTS/Over 2.5 e Série B
  Cartões+Árbitro — ainda valem pra qualquer mercado/liga fora desses 3
  critérios, se o Lucas quiser.
- Re-rodar tudo quando as temporadas avançarem mais (amostra maior).
- Acompanhar se o ROI dos critérios calibrados em 2023-2026 decai
  conforme mais dado de 2026/2027 entra — confirmaria a hipótese de
  janela de ineficiência temporária (item 23) em vez de propriedade
  permanente do futebol brasileiro.
