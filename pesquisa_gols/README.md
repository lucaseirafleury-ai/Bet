# Pesquisa de probabilidades de gols (fase 1 — isolada do ligas_live_app)

Substitui a abordagem da planilha original (milhares/milhões de linhas
estáticas, uma por combinação de minuto × placar × estatística × operador ×
limite) por um pipeline em Python que calcula tudo sob demanda e só guarda os
resultados que realmente se sustentam fora da amostra.

## Por que a planilha ficava pesada

Inspecionando o `.xlsx` original: as abas de origem (`Jogos`, `Snapshots`,
`Stats_Finais`, `Matriz`, `Tempo`) são leves — 240 jogos, ~1.700 snapshots.
O peso vinha das abas derivadas (`Tabela_Probabilidades`,
`Probabilidades_2Stats`): cada uma das ~6 mil / ~544 mil linhas era um
**valor estático colado**, não uma fórmula — ou seja, o cálculo já tinha sido
feito fora do Excel (por código) e só o resultado bruto de *todas* as
combinações possíveis foi despejado na planilha. É por isso que replicar para
outra liga/temporada significava recomeçar do zero: a "grade" não era
reutilizável, só o resultado de uma rodada específica.

Aqui a grade virou uma função (`probabilidades.py`): dado
`(minuto, placar, estatística, operador, limite)`, ela filtra os snapshots em
memória e devolve P Final/P Base/Impacto/amostra em milissegundos. Só entram
num arquivo de saída as condições que passam pela validação abaixo — por isso
os resultados finais têm dezenas de linhas, não milhões.

## O que mudou em relação à planilha (além do peso)

A planilha testava ~6 mil condições individuais e ~544 mil combinações de
duas estatísticas em cima de ~240 jogos, sem separar dados de treino/teste.
Nesse volume de comparações, é esperado que muitas pareçam "fortes" só por
coincidência de amostra pequena — o mesmo risco que o `ligas_live_app` já
evita no modelo calibrado de Over/Under 2.5 (validação cronológica fora da
amostra, ver `ligas_live_app/LEIA-ME.md`, seção 9). Este pipeline aplica o
mesmo rigor aqui:

1. **Split cronológico por rodada** — treino = rodadas iniciais, teste = mais
   recentes. Uma condição só é aceita se valer nos dois períodos.
2. **Amostra mínima** por condição (`config.AMOSTRA_MINIMA`, tanto para quem
   cumpre a condição quanto para o complemento).
3. **Teste estatístico formal** (duas proporções) com **correção de
   Benjamini-Hochberg** para múltiplas comparações — não basta "amostra
   grande = confiável", como a coluna "Confiabilidade" da planilha original
   fazia.
4. **Revalidação fora da amostra**: a condição precisa repetir a mesma
   direção e reter uma fração mínima do impacto no conjunto de teste.
5. **Pares de 2 estatísticas só entre quem já validou individualmente** — em
   vez de testar todos os pares possíveis (o que gerava as 544 mil linhas),
   restringe a busca às combinações que já provaram ter algum efeito sozinhas.

**Resultado no dado atual (Allsvenskan 2025, o anexo que você me passou):
zero condições sobrevivem ao critério rigoroso.** Isso não é um bug — é o
resultado esperado ao aplicar validação de verdade a ~240 jogos testando
centenas de hipóteses. É a mesma amostra que gerava "achados fortes" na
planilha original; a diferença é que agora sabemos que a maioria não se
sustentaria fora da amostra em que foi encontrada. Para ter achados que
sobrevivam à correção, o caminho é mais jogos (temporadas adicionais da
mesma liga) e/ou afrouxar critérios conscientemente — ver `config.py`.

Enquanto isso, `resultados/exploratorio_1stat.csv` lista as 50 condições com
menor p-valor **sem** a correção/validação fora da amostra — só para
referência exploratória, claramente não confiável para decisão.

## Como rodar

```bash
cd pesquisa_gols
pip install -r requirements.txt
python buscar_condicoes.py
```

Saída em `resultados/`:
- `condicoes_1stat.csv` — condições de 1 estatística validadas fora da amostra.
- `condicoes_2stats.csv` — pares de 2 estatísticas com "melhora conjunta"
  confirmada em treino e teste.
- `exploratorio_1stat.csv` — top 50 por p-valor bruto, sem correção nem
  validação (não confiar para decisão, só para inspecionar candidatos).

Para trocar de arquivo de entrada (outra liga/temporada), edite
`config.ARQUIVO_ENTRADA` — o arquivo precisa ter as mesmas abas/colunas de
`Jogos`, `Snapshots`, `Stats_Finais` e `Matriz` do formato original.

## Ajustar o comportamento

Tudo fica em `config.py`:

| Parâmetro | O que controla |
|---|---|
| `FRACAO_TREINO` | fração das rodadas (cronológica) usada como treino |
| `AMOSTRA_MINIMA` | amostra mínima para uma condição ser considerada |
| `ALFA` | nível de significância aceito após Benjamini-Hochberg |
| `IMPACTO_MINIMO_PP` | impacto mínimo (p.p.) para reportar uma condição |
| `NUM_LIMITES_TESTADOS` | quantos limites testar por estatística |
| `FRACAO_MINIMA_IMPACTO_TESTE` | quanto do impacto do treino precisa se repetir no teste |
| `TOLERANCIA_EFEITO_CONJUNTO_PP` | tolerância de estabilidade da comparação de efeito conjunto |

## Fase 2 (não implementada ainda — só o gancho)

Quando alguma condição (ou combinação) se mostrar robusta o suficiente —
seja nesta liga com mais dados, seja em outra — o próximo passo é replicar o
padrão já usado para o Over/Under 2.5 calibrado: adicionar coeficientes por
liga em `MODELOS_CALIBRADOS_POR_LIGA` (`ligas_live_app/live_poisson.py`) e
expor um novo mercado calibrado no painel, seguindo a convenção descrita em
`ligas_live_app/LEIA-ME.md` (seção 9). Não é o escopo desta pasta.

## Estrutura

```
config.py             → parâmetros ajustáveis
carregar_dados.py      → lê Jogos/Snapshots/Stats_Finais/Matriz do .xlsx
probabilidades.py      → P Final / P Base / Impacto sob demanda
estatistica.py         → teste de duas proporções + correção Benjamini-Hochberg
buscar_condicoes.py    → orquestra a busca (1 e 2 estatísticas) com treino/teste
dados/                 → arquivo(s) de entrada
resultados/            → CSVs gerados (não versionados, exceto .gitkeep)
```
