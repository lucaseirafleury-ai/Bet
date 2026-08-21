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

## Atualização: juntando a temporada 2026

Ao receber `Allsvenskan_2026_snapshots.xlsx` (temporada em andamento — 135 de
240 jogos disputados até agora), três ajustes:

1. **A aba `Matriz` agora é opcional.** O arquivo de 2026 não trouxe essa
   aba (faz sentido — é conhecimento fixo sobre os indicadores, não dado da
   temporada). O padrão passou a viver em `matriz_padrao.py` e é usado
   sempre que o arquivo de entrada não tem sua própria `Matriz`.
2. **`config.ARQUIVOS_ENTRADA` agora é uma lista** — dá pra juntar várias
   temporadas/ligas num único dataset (`carregar_dados.carregar_tudo` aceita
   um caminho só ou vários). `dividir_treino_teste` passou a ordenar as
   rodadas pela data do primeiro jogo, não pelo ID bruto de rodada, porque
   IDs de rodada de competições diferentes não têm relação entre si.
3. **Bug de verdade encontrado ao juntar:** o split treino/teste original
   olhava para todas as rodadas cadastradas em `Jogos`, incluindo rodadas
   futuras de uma temporada em andamento (a 2026 tem jogos agendados para
   depois da data de hoje, ainda sem resultado). Isso empurrava o corte
   70/30 para dentro de rodadas majoritariamente não disputadas, e o
   conjunto de teste desabava para ~40 jogos em vez de ~110. Corrigido:
   o corte agora só considera rodadas com pelo menos um jogo já com gols
   finais conhecidos.

**Com 2025+2026 juntos (375 jogos disputados, 256 treino / 119 teste),
as duas combinações que você apontou ficaram mais fracas, não mais fortes:**
o p-valor no treino melhorou um pouco (0,10 e 0,06), mas a direção do efeito
**se inverteu** no teste para as duas — o grupo que "deveria" ter mais jogos
de poucos gols passou a ter proporcionalmente menos. Isso é consistente com
a hipótese original: o que parecia forte na planilha era, ao menos em parte,
ruído específico da amostra 2025. Ainda zero condições (individuais ou em
par) sobrevivem ao critério rigoroso com os dois anos juntos.

## Buscar direto da API (sem exportar/subir .xlsx)

Alternativa ao fluxo manual acima: `buscar_sportmonks.py` busca os mesmos
dados direto da API da Sportmonks, usando o include `trends` (o mesmo que
`ligas_live_app/backtest.py` já usa para reconstruir estatísticas minuto a
minuto de jogos passados) — não depende de exportar planilha nenhuma.

```bash
cd pesquisa_gols
pip install -r requirements.txt
export SPORTMONKS_TOKEN=...   # nunca cole o token dentro de um arquivo do repo
python buscar_sportmonks.py
```

Isso busca a Allsvenskan inteira (liga 573, mesmo id de
`ligas_live_app/config.py`) e já roda `buscar_condicoes.rodar()` em cima do
resultado, sem passar por `dados/*.xlsx`. Para usar num script próprio:

```python
import buscar_sportmonks, buscar_condicoes
dados = buscar_sportmonks.buscar(date_from="2025-01-01", date_to="2026-12-31")
buscar_condicoes.rodar(dados=dados)
```

Detalhes que valem saber:
- **Nomes de estatística não confirmados contra a API real ficam de fora,
  com aviso** (`sportmonks.py`/`buscar_sportmonks.py`), em vez de assumir um
  nome errado e cair em 0.0 silenciosamente — esse bug específico já
  aconteceu neste repo antes (ver o comentário no topo de
  `ligas_live_app/xg_pressure.py`), e prefiro perder uma estatística com
  aviso do que envenenar o dataset sem perceber.
- **Cobertura de `trends` não é garantida em toda fixture** — quando falta,
  o jogo é pulado com aviso (`[sem trends]`), igual `backtest.py` já faz.
- **O token nunca é escrito em nenhum arquivo deste repo** — só existe como
  variável de ambiente durante a execução.

## Busca multi-liga: descobrir na Allsvenskan, confirmar nas outras 4 ligas

`buscar_multiliga.py` busca a Allsvenskan (2024-2026, ~615 jogos disputados)
para descobrir condições com o mesmo rigor de sempre (treino/teste
cronológico + Benjamini-Hochberg), e depois testa cada uma nas outras 4
ligas já monitoradas pelo `ligas_live_app` (Superettan, A Lyga, 1. Lyga,
1. Division — 2.363 jogos disputados) como confirmação independente. Cada
liga individualmente só tem 3 temporadas disponíveis neste plano da
Sportmonks (2024/2025/2026) — pouco pra validar sozinha — mas ligas
diferentes têm médias de gols diferentes, então elas só entram como
holdout de confirmação, nunca misturadas com a Allsvenskan na descoberta.

```bash
export SPORTMONKS_TOKEN=...
python buscar_multiliga.py
```

Cada liga fica em cache permanente (`dados/.checkpoint_<id>.json`, nunca
apagado) — rodar de novo só busca fixtures novos, não a liga inteira. O
cache é invalidado automaticamente se o conjunto de campos buscados mudar
(ver seção seguinte), pra nunca reaproveitar snapshots incompletos.

**Primeiro resultado, só com gols (rodado até o fim, sem cair, em
21/08/2026):** 4 condições de 1 estatística e 6 combinações de 2
estatísticas validadas dentro da Allsvenskan; nenhuma sobreviveu à
confirmação nas outras ligas com o teste estatístico formal (a mais
próxima, `accurate_crosses<=2 & saves>=1`, teve p=0,023 nas outras ligas —
pareceria significativa isolada, mas não sobrevive à correção de
Benjamini-Hochberg sobre as 8 combinações testadas nessa etapa, que exigia
p≤0,006). Ver seção seguinte pra como isso generalizou pra outros alvos.

## Outros alvos além de gols: escanteios, cartões, chutes

`alvos.py` generaliza o pipeline pra prever qualquer alvo, não só gols —
hoje: **escanteios**, **cartões** (amarelos + vermelhos), **chutes totais**
e **chutes no alvo**, além de gols. Mesmo motor estatístico (treino/teste
cronológico + Benjamini-Hochberg + confirmação entre ligas), só muda:

- **Resultado final da partida**: soma casa+fora do(s) campo(s) daquele
  alvo (`campos_base` em `alvos.py`), em vez de gols. Cartões é a soma de
  dois campos (amarelos + vermelhos).
- **Linhas de mercado**: cada alvo tem sua própria escala — gols usa linhas
  inteiras (+1..+4, convenção já estabelecida); os demais usam linhas
  `.5` (estilo linha de aposta real, nunca empata exatamente em cima do
  corte): escanteios 7.5–11.5, cartões 1.5–5.5, chutes totais 18.5–28.5,
  chutes no alvo 6.5–10.5.
- **Candidatas**: mesmo pool de ~26 estatísticas usado para gols (mais
  faltas/desarmes/interceptações/duelos, úteis principalmente pra cartões),
  excluindo sempre o(s) campo(s) do próprio alvo (não testa "escanteios
  prevê escanteios").

`buscar_multiliga.py` agora roda todos os alvos numa única execução (busca
os dados uma vez, com o superset de ~28 campos que qualquer alvo precisa;
a análise em si é só reaproveitar o mesmo `snapshots` com um resultado
final e uma lista de candidatas diferente por alvo). Saída:
`resultados/<alvo>_allsvenskan_condicoes_*.csv` e
`resultados/<alvo>_confirmacao_*.csv` pra cada alvo.

**Achado ao adicionar cartões: contagem por evento é mais confiável que
`trends` para esse alvo.** Um jogo real testado deu 7 cartões por `trends`
(o último ponto acumulado) mas 8 por contagem de eventos de cartão —
batendo com o total oficial. Dois cartões no mesmo minuto parecem fazer o
feed de trends perder um incremento. `resultados_finais_dos_alvos` usa
contagem de eventos (`ALVOS_POR_EVENTO`) para cartões, igual já era feito
pra gols — mais confiável que ler o trend acumulado.

**Limitação conhecida, menor:** chutes totais/no alvo não têm um "evento"
discreto pra contar (diferente de gol/cartão), então usam o último ponto
dos `trends` — em 1 de 2 jogos conferidos manualmente, o total ficou 1
unidade abaixo do valor oficial (~4% de erro relativo). Não é sistemático
(não aconteceu com escanteios, nem com o outro jogo testado) — tratado como
ruído de medição aceitável dado o volume de jogos da análise, não como bug
a corrigir agora.

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

Para trocar ou somar arquivos de entrada (outra liga/temporada), edite a
lista `config.ARQUIVOS_ENTRADA` — cada arquivo precisa ter as abas `Jogos`,
`Snapshots` e `Stats_Finais` no formato original (a `Matriz` é opcional, ver
seção acima).

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
config.py             → parâmetros ajustáveis (inclui a lista de arquivos de entrada)
matriz_padrao.py       → correlação indicador→Gols padrão, usada quando o arquivo não tem aba Matriz
alvos.py                → define os alvos além de gols (escanteios/cartões/chutes): campos,
                          linhas de mercado e candidatas por alvo
carregar_dados.py      → lê Jogos/Snapshots/Stats_Finais (+ Matriz opcional) de um ou vários .xlsx
sportmonks.py           → cliente mínimo da API Sportmonks (token via env var)
buscar_sportmonks.py    → monta o dataset direto da API (todos os alvos de uma vez), sem .xlsx
probabilidades.py      → P Final / P Base / Impacto sob demanda
estatistica.py         → teste de duas proporções + correção Benjamini-Hochberg
buscar_condicoes.py    → orquestra a busca (1 e 2 estatísticas) com treino/teste — aceita
                          dados de carregar_dados.py OU de buscar_sportmonks.py
buscar_multiliga.py    → roda descoberta (Allsvenskan) + confirmação (outras 4 ligas),
                          pra cada alvo em alvos.py
dados/                 → arquivo(s) de entrada (fluxo manual via .xlsx)
resultados/            → CSVs gerados (não versionados, exceto .gitkeep)
```
