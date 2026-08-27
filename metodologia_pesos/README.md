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

## O que ainda falta
- Série B Over 2.5 e as linhas Over 1.5/3.5/4.5 (as duas ligas) seguem
  sem qualquer edge defensável — não apostar por este critério.
- Cartões+Árbitro (Série B, item 28) está em stake reduzido porque
  ainda não passa de z≈2 de forma robusta — acompanhar semanalmente
  (`checar_decaimento.py`) e promover pra stake normal só se o z se
  sustentar acima de 2 com mais dado de 2026/2027, não com um ano
  isolado.
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
- Aplicar os parâmetros validados nas planilhas reais (skills de
  Copa/Série A/B) — ainda pendente de confirmação com o Lucas.
- Re-rodar tudo quando as temporadas avançarem mais (amostra maior).
- Acompanhar se o ROI dos critérios calibrados em 2023-2026 decai
  conforme mais dado de 2026/2027 entra — confirmaria a hipótese de
  janela de ineficiência temporária (item 23) em vez de propriedade
  permanente do futebol brasileiro.
