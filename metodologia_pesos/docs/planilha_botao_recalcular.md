# Botão "Recalcular" na planilha de testes (Série A) — setup

## O que isso resolve

Antes: mudar um parâmetro do modelo (k_mando, usar_estilo,
filtro_aderencia, filtro_estilo, filtro_favoritismo, multiplicador_dp,
limite_unilateral, n_historico) na aba **Parâmetros** exigia pedir pra
mim (ou rodar `python3 gerar_planilha_testes.py` manualmente) pra
reprocessar a aba **Jogos**. Só `limiar_edge` recalculava sozinho.

Agora: com o **xlwings** instalado (uma vez só), a planilha ganha um
botão **"Run main"** na faixa de opções do Excel — clicar nele lê os
valores que você deixou na aba Parâmetros, roda o motor de pesos de
novo (mesmo `retrospectiva.py` de sempre) e recarrega a planilha já
atualizada. Sem terminal, sem me chamar.

## Por que precisa instalar algo (não dá 100% nativo no Excel)

O motor (histórico ponderado por time, recência, corte de outlier,
Poisson pra Over/BTTS) é complexo demais pra reimplementar em fórmula
de Excel sem reintroduzir os bugs que motivaram construir esse motor em
Python pra começo de conversa. O xlwings é a ponte: deixa o Excel
chamar o Python que já existe e funciona, com um clique.

## Setup (uma vez só)

1. **Instale o Python** (se ainda não tiver) — [python.org](https://python.org),
   versão 3.10 ou mais recente. No instalador do Windows, marque "Add
   python.exe to PATH".
2. **Abra um terminal** (PowerShell no Windows, Terminal no Mac) e instale
   as bibliotecas:
   ```
   pip install xlwings pandas openpyxl
   ```
3. **Instale o add-in do Excel** (adiciona a aba/faixa de opções
   "xlwings" no Excel):
   ```
   xlwings addin install
   ```
   Feche e abra o Excel depois — deve aparecer uma aba "xlwings" na
   faixa de opções, com botões tipo "Run main", "Import Functions" etc.
4. **Garanta que estes arquivos ficam na MESMA pasta**:
   - `SerieA_testes_visuais.xlsx` (a planilha)
   - `SerieA_testes_visuais.py` (o script que o botão roda — nome tem
     que ser IDÊNTICO ao da planilha, é assim que o xlwings decide qual
     script rodar)
   - `gerar_planilha_testes.py`, `retrospectiva.py`, `pesos.py`,
     `estilo.py`, `planilha_lib.py` (o motor)
   - a pasta `data/` com os CSVs da Série A (`footystats_seriea*`)

   Mais simples: coloque `SerieA_testes_visuais.xlsx` dentro da pasta
   `metodologia_pesos/` do seu clone local do repositório — todo o
   resto já está lá.

## Uso do dia a dia

1. Abra `SerieA_testes_visuais.xlsx` no Excel.
2. Na aba **Parâmetros**, edite os valores que quiser testar.
3. Clique **"Run main"** na aba xlwings da faixa de opções.
4. Aguarde (o recálculo do modelo pode levar de alguns segundos a
   1-2 minutos, dependendo dos parâmetros — a planilha fecha e reabre
   sozinha quando termina).
5. Confira a aba **Resumo** — já atualizada com o novo modelo.

`limiar_edge` continua não precisando de botão nenhum — muda e a aba
Resumo recalcula na hora, é só fórmula.

## Limitações e o que eu não consegui testar

- **Windows/Mac com Excel de verdade**: eu rodo num ambiente Linux sem
  Excel — testei e validei toda a parte de CÁLCULO (o motor
  `retrospectiva.py`, a geração do arquivo `.xlsx`, a leitura/escrita
  dos parâmetros, o "round-trip" de editar um parâmetro e reprocessar)
  bit a bit contra os números já conhecidos (ex.: o critério campeão de
  Over 2.5 bate exatamente com `n=221, ROI+16,0%`). **Não consegui
  testar o clique do botão dentro do Excel de verdade** — essa parte
  depende da sua máquina. Se der algum erro na hora de clicar "Run
  main", me manda a mensagem de erro que eu ajusto.
- Recalcular pode demorar (o motor reprocessa ~1200+ jogos da Série A
  toda vez) — não é instantâneo como o `limiar_edge`, mas evita ter que
  usar terminal ou me chamar a cada teste.
- Se você mudar o NOME ou a ORDEM das linhas da aba Parâmetros, o botão
  vai dar erro (`_ler_parametros_da_planilha` espera exatamente
  `k_mando, usar_estilo, filtro_aderencia, filtro_estilo,
  filtro_favoritismo, multiplicador_dp, limite_unilateral, n_historico,
  limiar_edge`, nessa ordem, começando na linha 3) — só edite a COLUNA
  de valor (coluna C), não a estrutura da aba.

## Se não quiser instalar nada

Sem problema — pode continuar como antes: edite a aba Parâmetros e me
peça pra rodar `gerar_planilha_testes.py` de novo, ou rode você mesmo
se já tiver Python:
```
python3 gerar_planilha_testes.py SerieA_testes_visuais.xlsx
```
