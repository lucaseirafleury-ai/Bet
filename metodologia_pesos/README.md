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
13. **Teto de odd máxima por mercado — não muda o critério campeão,
   ajuda BTTS** — testado teto (Over1.5≤1,5/Over2.5≤3/Over3.5≤6/
   Over4.5≤7/BTTS≤2) em cima do combo campeão: pra Over 2.5 o teto não
   filtra nenhuma aposta (resultado idêntico com/sem, `n=221,
   ROI+16,0%, z=+2,23`); pra BTTS o teto (≤2,0) melhora o z de forma
   consistente, mas ainda não testado com os parâmetros de modelo
   específicos de BTTS — pista pra próxima rodada. Ver
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
   **Não usar nenhum critério de Under pra apostar dinheiro real.** Ver
   `docs/retrospectiva_under_aproximado_2026-08-25.md`.

## O que ainda falta

- Confirmar o sinal de Série B BTTS (z≈0,9-1,0, ainda não passa do
  limiar de significância ~2) com mais holdout conforme a temporada de
  2026 avança.
- Série B Over 2.5 e as linhas Over 1.5/3.5/4.5 (as duas ligas) seguem
  sem qualquer edge defensável — não apostar por este critério.
- Diversificação de mercado ainda não resolvida: cartões/escanteios não
  têm odd real na fonte de dado atual; buscar outra fonte de odds
  histórica seria o próximo passo, se existir de graça.
- Under (1.5/2.5/3.5/4.5) segue sem odd real na fonte de dado atual — a
  aproximação testada foi descartada por viés (item 14 acima); só dá
  pra testar Under de verdade com uma fonte que traga a odd real desse
  lado.
- Os proxies de Pressão Alta/Transição/Bola Parada em `estilo.py` não
  estão se mostrando úteis em nenhum mercado testado — candidatos a
  redesenho (dado mais rico) antes de reavaliar a contribuição do estilo.
- `k_mando`/`limite_unilateral`/`multiplicador_dp` só foram calibrados
  olhando o mercado de gols — os outros 11 mercados têm MAE calculado mas
  não passaram pelo mesmo grid search ainda.
- Aplicar os parâmetros validados nas planilhas reais (skills de
  Copa/Série A/B) — ainda pendente de confirmação com o Lucas.
- Re-rodar tudo quando as temporadas avançarem mais (amostra maior).
