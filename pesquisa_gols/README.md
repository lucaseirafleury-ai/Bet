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
5. **Pares de 2 estatísticas testados a partir de um pool amplo** — a busca
   de pares não exige que cada estatística já tenha validado sozinha (uma
   versão anterior deste pipeline fazia isso, e por causa disso deixava
   passar combinações reais só porque nenhuma das duas metades tinha efeito
   isolado — ver "Achados ao comparar com a planilha original" abaixo). Em
   vez disso, qualquer estatística com impacto individual acima de uma barra
   baixa (`config.IMPACTO_MINIMO_PAREAMENTO_PP`, bem menor que a barra de
   "achado individual") entra no pool de pareamento, e a validação (BH +
   fora da amostra) é aplicada ao efeito CONJUNTO, não a cada metade. Isso
   ainda reduz o espaço de busca de 544 mil para ~1.500 pares na base da
   Allsvenskan — só não exige que o efeito já apareça isoladamente.

## Achados ao comparar com a planilha original

Comparando resultado a resultado com duas combinações que você identificou na
planilha original como "Sinal forte":

1. **Bug de off-by-one nas colunas "-N" da planilha original.** Em toda linha
   testada, `P(-1) + P(+2) = 100%`, `P(-2) + P(+3) = 100%`, `P(-3) + P(+4) =
   100%` — ou seja, a coluna documentada como "-1: menos de 1 gol" foi na
   prática calculada como "menos de 2 gols" (complemento de "+2", não de
   "+1"). As colunas "+N" estão corretas; só as "-N" estão deslocadas em uma
   posição. Vale revisar/corrigir isso na planilha original antes de
   confiar nas leituras "-N" dela.
2. **Bug real no meu carregador de dados, já corrigido.** 14 jogos que
   terminaram 0-0 tinham `goals_casa`/`goals_fora` vazios em `Stats_Finais`
   (falha da fonte), mesmo com o placar certo disponível no snapshot `FT`.
   Meu código descartava esses jogos; agora usa o snapshot `FT` como
   fallback. Isso levou a amostra do bucket (minuto 15, 0 gols) de 168 para
   182 jogos — batendo exatamente com a amostra da planilha original.
3. **A poda por "cada metade já validada" (ver seção acima) escondia
   combinações reais.** Nenhuma das quatro estatísticas das suas duas
   combinações passa sozinha na minha barra de "achado individual" (impacto
   < 5 p.p., não significativa isoladamente) — por isso a busca de pares
   nunca chegava a testá-las juntas. Corrigido: agora o pool de pareamento
   usa uma barra bem mais baixa (item 5 acima).
4. **Mesmo assim, as duas combinações específicas que você mandou não
   validam com o critério rigoroso — e dá para mostrar exatamente por quê.**
   Usando o mercado equivalente correto (a "-1" da planilha = minha "-2",
   por causa do bug do item 1) e o split cronológico treino/teste:

   | Combinação | Treino (168 jogos) | Teste (72 jogos) |
   |---|---|---|
   | `goal_attempts<=0` & `big_chances_created<=0` | p=0,14 (n=62 vs 64) | p=0,08 (n=31 vs 25) |
   | `dangerous_attacks<=20` & `key_passes>=2` | p=0,06 (n=64 vs 62) | p=0,11 (n=24 vs 32) |

   Nenhum dos dois p-valores fica abaixo de 0,05 nem no treino nem no teste
   — e isso é *antes* até de aplicar a correção de Benjamini-Hochberg, que
   exigiria um p-valor ainda menor dado o volume de pares testados. A
   direção do efeito é consistente entre treino e teste (sinal de que pode
   ser real), mas a amostra de ~240 jogos, dividida em dois períodos, não é
   grande o suficiente para confirmar com rigor — a probabilidade "forte"
   vista na planilha original vinha de calcular e "confirmar" no mesmo
   conjunto de 240 jogos, sem separação treino/teste.

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
