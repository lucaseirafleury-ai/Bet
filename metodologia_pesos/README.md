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
planilha_lib.py      → mecânica de planilha (CSV, clonagem de fórmula,
                       build_workbook) — migrada de
                       ~/.claude/skills/synced/copa-planilha-dia/scripts/.
data/estilos_selecoes.json → banco de estilo tático por seleção (Copa).
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

## O que ainda falta (ver plano da sessão que criou isto)

- **Calibração estatística dos parâmetros** (decaimento de recência, `k`
  do mando, corte de outlier) contra resultado real — depende de acesso a
  `Tips_telegram.xlsx` (hoje só existe localmente no Windows do Lucas, fora
  desta sessão).
- **Banco de estilo da Série A** (`data/estilos_seriea.json`) — ainda não
  existe, precisa ser criado/preenchido incrementalmente como os outros.
- **Skill `serie-a-planilha-dia`** apontando para este motor em vez da
  fórmula em prosa.
