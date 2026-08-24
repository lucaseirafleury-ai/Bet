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
                       a previsão com o placar real. Usado pra calibrar os
                       parâmetros livres (k do mando, corte de outlier) sem
                       depender do Tips_telegram.xlsx. Inclui `grid_search`
                       pra comparar combinações de parâmetros pelo erro
                       médio (MAE) de gols e acerto de Over/Under 2.5 e BTTS.
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

# compara combinações de parâmetros pra achar a que mais acerta nesse histórico:
grade = dict(k_mando=[None, 0.2, 0.35, 0.5], limite_unilateral=[3, 4, 5], multiplicador_dp=[2, 2.5, 3])
melhores = grid_search(df, grade, min_jogos_historico=10)
print(melhores[0])  # (params, relatorio) com o menor mae_gols_total
```

## O que ainda falta

- **Rodar a retrospectiva com os CSVs reais** do Lucas (Série A/B) — o
  pipeline está pronto e testado com dataset fabricado, mas a validação/
  calibração de verdade só acontece com o upload dos CSVs do FootyStats.
- Os proxies de Pressão Alta/Transição/Bola Parada em `estilo.py` são
  heurísticas limitadas ao que o CSV padrão do FootyStats traz — podem ser
  refinadas depois com dado mais rico (PPDA, passes no terço final etc.) ou
  recalibradas com o próprio `grid_search` da retrospectiva.
