---
name: planilha-liga-dia
description: >
  Use esta skill SEMPRE que o usuário (Lucas) pedir análise de apostas de um
  dia/rodada de futebol nas 3 competições cobertas — Copa do Mundo 2026,
  Brasileirão Série A 2026 ou Série B 2026 — seja como (a) o RELATÓRIO do dia
  em texto/Python direto (o modo padrão: "quais entram hoje", "lista de
  apostas do dia", "roda a análise do jogo X", "quero a shortlist de hoje")
  ou (b) a PLANILHA Excel completa de 4-5 abas (Times, Jogos do Dia,
  Mercados, Fontes, Padrões): Copa_Xjul.xlsx / SerieA_Xjul.xlsx /
  SerieB_Xjul.xlsx — só quando pedido EXPLICITAMENTE ("gera a planilha",
  "quero em Excel", "manda o arquivo .xlsx", "quero rever os parâmetros
  visualmente"). É a skill PADRÃO e ÚNICA para esse fluxo nas 3 competições —
  substitui as antigas copa-planilha-dia, serie-a-planilha-dia e
  serie-b-planilha-dia (unificadas aqui, parametrizado por liga, ver
  docs/MIGRACAO.md).
---

# Skill: Planilha Diária de Apostas (Times / Jogos do Dia / Mercados / Fontes / Padrões)

Monta a planilha multi-abas de um dia/rodada a partir de um template
compartilhado, preenchendo dados históricos reais dos CSVs do FootyStats,
odds pesquisadas na web, e o julgamento qualitativo de estilo/contexto —
mantendo fórmulas e estrutura do template intocadas (só redimensiona as 3
tabelas Excel para o número de jogos do dia).

Cobre 3 competições através de um parâmetro `liga`:

| `liga`     | Competição                    | Arquivo de saída  | Mando real | CSVs de liga/jogador |
|------------|--------------------------------|-------------------|:----------:|:---------------------:|
| `copa`     | Copa do Mundo 2026 (seleções)  | `Copa_Xjul.xlsx`  | ❌ neutro  | ❌ não tem            |
| `seriea`   | Brasileirão Série A 2026       | `SerieA_Xjul.xlsx`| ✅         | ✅                    |
| `serieb`   | Brasileirão Série B 2026       | `SerieB_Xjul.xlsx`| ✅         | ✅                    |

A Copa (mata-mata de seleções, ciclo já encerrado — banca final ~R$49) não
tem CSVs agregados de liga/time/jogador nem mandante real; `league_stats`,
`team_corner_profile`, `corner_matchup`, `player_props` e
`aplicar_ajuste_mando` levantam erro explícito se chamados com `liga="copa"`.

## Dois modos de uso — Python (padrão) vs. Excel (sob pedido)

Desde 23/07/2026 existem DOIS caminhos, e o padrão mudou:

- **Modo Python (`scripts/analise.py`) — PADRÃO para o dia a dia.** Reimplementa
  em Python puro (sem abrir Excel/LibreOffice) toda a matemática que antes só
  existia como fórmula na planilha: aderência/peso/recência, a fórmula
  Pró/Contra V2 (parametrizável — é o "trocar o desvio-padrão de 2.5 para
  1.25" que Lucas fazia manualmente em `Parâmetros!B11`), λ de Poisson,
  P.Plan/P.Comb/Edge/Veredito/Critérios pros 20 mercados, e o cruzamento de
  "Padrões em comum" entre os dois times. `gerar_shortlist()`/`relatorio_dia()`
  já automatizam o pós-processamento manual completo que Lucas fazia:
  filtrar P.Comb ≥ 65%, reavaliar com desvio-padrão 1.25 e descartar quem cai
  abaixo do piso nessa reavaliação, cortar odd de mercado > 2.0, e listar os
  padrões em comum com stake sugerido 1.0. **Use este modo por padrão** —
  não precisa gerar planilha nenhuma para responder "quais entram hoje".
- **Modo Excel (pipeline antigo, `build_workbook` + ... + `recalc.py`) — SÓ
  quando Lucas pedir explicitamente** ("quero em Excel", "gera a planilha",
  "quero rever os parâmetros visualmente"). Serve pra ele mexer visualmente
  nos parâmetros e reformular conceitos — não é mais o caminho padrão de
  consumo diário.

⚠️ **Sobre a fidelidade do modo Python:** `analise.py` foi escrito por leitura
cuidadosa das fórmulas do template e validado com testes de consistência
interna (Poisson normalizado, Over/Under complementares, simetria,
handicap coerente, robustez do corte de outlier) — ver
`scripts/test_analise.py` referenciado em `docs/MIGRACAO.md`. Em 23/07/2026
foi cross-validado de verdade contra um `SerieA_21a23jul.xlsx` real que
Lucas gerou no Project antigo: achou e corrigiu uma lacuna real (o ajuste de
mando, `mando_A`/`mando_B`/`mando_k` — **é obrigatório passar em toda
chamada de `analisar_jogo`/`gerar_shortlist` na Série A/B**, senão o λ fica
sistematicamente errado, sem aviso). Depois da correção, P.Plan bateu bem
próximo (~1-2pp) do Excel real nos jogos onde o banco de estilo não mudou
entre as duas versões; a atenção agora é: **sempre que `estilos_seriea.json`/
`estilos_serieb.json` for atualizado (pesquisa nova, correção manual), os
números de qualquer análise anterior àquela atualização ficam desatualizados
— isso é esperado, não é bug.** Ver `docs/MIGRACAO.md` para o relato completo
da comparação.

## Arquivos desta skill

```
scripts/planilha_lib.py  → motor 100% compartilhado entre as 3 ligas (usado
    pelos DOIS modos — Python e Excel):
    load_all_matches, get_historico, attach_estilo, save_estilo_db
    clone_formula/fix_range_end (clonagem de fórmulas — só modo Excel)
    mercados_rows_for_game, build_workbook (só modo Excel)
    aplicar_ajuste_mando, aplicar_formula_pro_contra, marcar_estimados,
    sanitizar_v_vazio (só modo Excel), buscar_padroes_liga, montar_aba_padroes
scripts/analise.py        → MODO PYTHON (novo, padrão): aderência/peso/
    recência, Pró/Contra V2 numérico (parametrizável por mult_dp), λ de
    Poisson, parser de critério + P.Plan/P.Comb/Edge/Veredito/Critérios,
    padroes_em_comum, gerar_shortlist, relatorio_dia — ver docstring do
    módulo para o fluxo de uso completo
scripts/ligas.py          → o que MUDA por liga:
    LIGAS = {"copa": ..., "seriea": ..., "serieb": ...}
    league_stats(liga), team_corner_profile(liga, time), corner_matchup(liga, fav, dog, ...),
    player_props(liga, time), estilo_db_path(liga), mando_shrink_k_default(liga),
    output_path_for(liga, sufixo), csv_alias(liga)
templates/Copa_Template_Simplificado.xlsx → template-base (só modo Excel; idêntico p/ as 3 ligas)
data/estilos_selecoes.json / estilos_seriea.json / estilos_serieb.json
    → banco persistente de notas de estilo por liga (cresce a cada sessão)
data/matches/*.csv        → CSVs FootyStats de PARTIDAS (histórico jogo-a-jogo),
    todas as ligas juntas — times promovidos/rebaixados carregam histórico
    dos dois lados automaticamente
data/footystats/seriea/ e /serieb/  → league.csv, teams.csv, teams2.csv,
    players.csv (agregados da temporada; só Série A/B)
docs/PROTOCOLO_BETS_LUCAS.md → manual de decisão (critérios de edge, princípios,
    piso/teto de odd, exemplos reais de erros corrigidos) — ler antes de
    recomendar qualquer entrada, independente da liga
docs/briefing_serieb.md  → contexto específico da Série B (herdado da Copa)
docs/MIGRACAO.md         → o que mudou nesta migração/unificação e o que falta
```

Se o usuário anexar um `Copa_[dia_anterior].xlsx`/`SerieA_[...].xlsx`/
`SerieB_[...].xlsx` mais recente, use-o como `template_path` no lugar do
template desta skill (estrutura é idêntica; só muda o conteúdo). Preferir
sempre o arquivo mais recente que o usuário mandar, já que reflete o estado
real da temporada (banca, princípios ajustados etc. — isso vive no
`PROTOCOLO_BETS_LUCAS.md`, não nesta skill).

## Fluxo de execução

### 1. Descobrir os jogos do dia/rodada
Buscar na web quais partidas da competição acontecem na data pedida (não
assumir — o número de jogos por dia varia). Confirmar nomes EXATOS dos times
como aparecem no FootyStats (`df['home_team_name'].unique()`), não o nome
popular — ver `csv_alias(liga)` em `ligas.py` (Copa tem USMNT/USA, DR
Congo/Congo DR; adicionar novos casos ali se aparecerem). Nomenclaturas
exatas por liga:

**Série A/B (`common_name`):** América Mineiro, Athletic Club, Atlético GO,
Atlético Mineiro, Atlético PR, Avaí, Bahia, Botafogo, Botafogo SP, Bragantino,
CRB, Ceará, Chapecoense, Corinthians, Coritiba, Criciúma, Cruzeiro, Cuiabá,
Fluminense, Fortaleza, Goiás, Grêmio, Internacional, Juventude, Londrina,
Mirassol, Náutico, Novorizontino, Operário PR, Palmeiras, Ponte Preta, Remo,
Santos, São Bernardo, São Paulo, Sport Recife, Vasco da Gama, Vila Nova,
Vitória. Verificar sempre com
`[t for t in df['home_team_name'].unique() if 'termo' in t.lower()]`.

### 2. Carregar liga + histórico
```python
import sys
sys.path.insert(0, "/mnt/skills/user/planilha-liga-dia/scripts")
from planilha_lib import *
from ligas import *

liga = "serieb"                          # ou "seriea" / "copa"
df = load_all_matches()                  # todos os CSVs de partidas (data/matches/*.csv)
hist_A = get_historico("Ceará", df)      # TODOS os jogos completos (mudou de 15 fixos p/ "todos" em 16/07 —
hist_B = get_historico("Athletic Club", df)  # amostra maior reduz risco de padrão frágil, ver Regra 2)
```
Times com poucos jogos → `get_historico` avisa (⚠️); qualificar como amostra
parcial (Regra 2 do protocolo). Times promovidos/rebaixados (Ceará,
Fortaleza, Juventude, Sport...) têm histórico das duas séries automaticamente
porque `data/matches/` inclui os CSVs de Série A e B juntos — mas jogos de
Série A 2025/Copa do Brasil que não estão nesses CSVs não entram; sinalizar
amostra parcial no início da temporada (<15 jogos).

Para Série A/B, calibrar priors da liga ANTES de montar mercados:
```python
liga_stats = league_stats(liga)   # média gols/escanteios/cartões, %Under/Over/BTTS, vantagem de mando
```
`league_stats("copa")` levanta erro — a Copa não tem esse CSV agregado.

### 3. Estilo dos adversários
```python
db = estilo_db_path(liga)               # data/estilos_<liga>.json
attach_estilo(hist_A, estilo_db_path=db)
attach_estilo(hist_B, estilo_db_path=db)
```
Se faltar alguma seleção/time no banco, a função lista quem falta. Preencha
um dict de overrides com sua avaliação (1-5 em cada dimensão — ver critérios
na skill `tabela-comparativa-time/SKILL.md`, seção "Notas de estilo (1-5)"):
```python
NOVOS = {
    "Sweden": ("Organizado, meio-bloco, físico nórdico", 3, 2, 3, 2, 4),
    # texto, bloco_baixo, pressao_alta, transicao, posse, bola_parada
}
attach_estilo(hist_A, estilo_db_path=db, overrides=NOVOS)
save_estilo_db(NOVOS, estilo_db_path=db)   # salva pro banco persistente, próximas sessões reaproveitam
```
**`data/estilos_seriea.json`** e **`data/estilos_serieb.json`** foram
revisados em 23/07/2026 com pesquisa real (técnico atual + estilo tático +
fonte, WebSearch por time) — ver `docs/MIGRACAO.md` para o resumo de quais
times mudaram de técnico e quais ficaram com `confianca: "media"`/`"baixa"`
por falta de citação direta ou por técnico recém-chegado sem jogos ainda
(ex.: Goiás, Mozart Santos anunciado em 22-23/07/2026, zero jogos no comando
até a data — notas necessariamente provisórias). São estimativas de estilo,
não dado objetivo: revisar/corrigir manualmente com `overrides=` +
`save_estilo_db()` sempre que você discordar de uma nota específica, e
reavaliar Goiás (e qualquer outro técnico recém-chegado) assim que houver
3-4 jogos de amostra.

### 4. Enriquecimento por liga — SÓ Série A/B (o que a Copa não tinha)
```python
mu = corner_matchup(liga, "Ceará", "Athletic Club", fav_em_casa=True)
# -> esc_fav_produz, esc_dog_cede, esc_fav_estimado, p5_por_numeros (bool)
# Só considerar Over escanteios do favorito quando p5_por_numeros == True
# (adversário cede acima da média E favorito produz acima da média) —
# Princípio 5 pelos NÚMEROS, não só pelo estilo inferido.

props_A = player_props(liga, "Ceará", top=4)     # chutes/jogo, chutes no gol/90, cartões/90
props_B = player_props(liga, "Athletic Club", top=4)
# Usar o atacante com maior chutes_por_jogo como "X + de 0.5/1.5 chutes no gol".
```
**Cautelas dos dados agregados:** `esc_pro_j_overall` em teams2 pode
representar escanteios TOTAIS do jogo (não só do time) — preferir os splits
`esc_pro_casa/fora` e o lado `esc_contra_*`, que são confiáveis. `players.csv`
reflete o momento do snapshot: cruzar o top de props com a escalação provável
(fontes) antes de usar como âncora.

### 5. Odds e Fontes (julgamento — não pular)
Pesquisar odds reais e análise por jogo. Fontes prioritárias por liga:

- **Copa:** bet365, DraftKings, FanDuel, ESPN, CBS Sports, Yahoo Sports,
  SportsLine, Squawka. Kalshi/Polymarket quando disponível (mais limpo p/
  P.Font por ser independente das odds de sportsbook).
- **Série A/B:** Academia das Apostas Brasil, UmDois Esportes/GE Globo/O
  POVO (contexto/escalações/desfalques), Sofascore/FotMob (xG/forma/H2H),
  Sportingbet/Betano/bet365/Superbet (odds). Kalshi/Polymarket normalmente
  **não** cobrem Brasileirão → P.Font vem de tipsters + modelo Poisson
  próprio, mantendo a independência de P.Mkt.

Para mercados menos comuns não cotados diretamente (Handicap Asiático,
Over/Under 1.5/3.5, 1º Tempo), calibrar um Poisson simples com os λ que
reproduzem a linha de Over/Under 2.5 e o moneyline realmente cotados, e
derivar as demais probabilidades a partir daí.

⚠️ **Isso é um lembrete fácil de esquecer** (já esqueci uma vez, 23/07):
"Over 0.5 gols 1ºT"/"Under 0.5 gols 1ºT" em `analise.py`
(`p_plan`/`avaliar_mercados`) usam `lambda_ft = (la+lb)*0.42` — o MESMO λ do
jogo, sem depender de nenhuma odd externa. Isso significa que **não existe
odd real pra pesquisar nesse mercado** (nem em Handicap Asiático/O-U
1.5/3.5, no fundo) — o "P.Font"/"Odd Mercado" desses mercados no fluxo
original sempre foram o PRÓPRIO P.Plan travestido de odd (dá pra conferir
no arquivo do Lucas: P.Font e P.Mkt de "Over 0.5 gols 1ºT" ficam a menos de
3pp do P.Plan em todo jogo — não é coincidência, é auto-referência). Se for
montar P.Comb/Edge/Critério pra esses mercados, deixar claro pro usuário que
é o modelo comparando com ele mesmo, não uma checagem contra o mercado real
— o valor está em ver o P.Plan isolado, não em fingir que há edge.

Preencher (mesmo formato nas 3 ligas):
```python
jdd_A = dict(estilo_time=..., estilo_adv=..., fav=0.610,  # prob. normalizada
             bb=4, pa=2, tr=4, pos=2, bp=3,               # estilo do ADVERSÁRIO nesta partida
             ataca_fundo="S", contexto="...", obs="...")
jdd_B = dict(...)  # espelho, do ponto de vista do outro time

odds_and_pfont = [("46%", 2.05), ("54%", 1.80), ...]  # 20 tuplas, ver MERCADOS_TEMPLATE_20 em planilha_lib.py
mercados_rows = mercados_rows_for_game("Ceará", "Athletic Club", favorito="A",
                                        odds_and_pfont=odds_and_pfont,
                                        displayA="Ceará", displayB="Athletic")

fontes = dict(placar_modal="1-0 Ceará", p_a="62%", p_empate="25%", p_b="13%",
              consenso="...", melhor_aposta="...", atencao="...")
```
`favorito`: "A" se teamA é o favorito de mercado (controla os textos das
linhas de DC/AH combinadas). **P.Font e Odd sempre número puro (float),
nunca string tipo "0.35 [ESTIMADO]"** — isso quebra as fórmulas de Edge/
P.Comb que somam/multiplicam essas colunas. Quando o valor é estimado (sem
fonte externa real), usar `marcar_estimados(path, game_index,
linhas_estimadas)` para destacar com cor, nunca texto na célula.

### 6. Montar e salvar
```python
games = [dict(teamA="Ceará", teamB="Athletic Club", hist_A=hist_A, hist_B=hist_B,
              jdd_A=jdd_A, jdd_B=jdd_B, mercados_rows=mercados_rows, fontes=fontes),
         # ... um dict por jogo do dia
        ]

output_path = "/mnt/user-data/outputs/" + output_path_for(liga, "13jul")  # -> SerieB_13jul.xlsx
build_workbook(
    games,
    template_path="/mnt/skills/user/planilha-liga-dia/templates/Copa_Template_Simplificado.xlsx",
    # ou o Copa_/SerieA_/SerieB_[dia_anterior].xlsx que o usuário anexou
    output_path=output_path,
    data_jogo="13/07/2026",
)
```
`build_workbook` redimensiona automaticamente as 3 Excel Tables (Times = soma
real dos históricos, Jogos do Dia = 2 linhas/jogo, Mercados = 20 linhas/jogo)
e clona todas as fórmulas com as referências de linha e de range corrigidas.

### 6b. Ajuste de mando no λ — OBRIGATÓRIO na Série A/B, NUNCA na Copa
O λ (Gols Pró/Contra) mistura casa+fora e subestima o mandante. Corrigir com
`aplicar_ajuste_mando` LOGO APÓS `build_workbook` e ANTES do `recalc.py`:
```python
aplicar_ajuste_mando(
    output_path,
    k=mando_shrink_k_default(liga),          # 0.35 ponto de partida (Série B validado; Série A herdado, recalibrar)
    home_teams={"América Mineiro", "Ceará"}, # os MANDANTES do dia
)
```
Chamar com `liga="copa"` (via `mando_shrink_k_default("copa")`) levanta erro
de propósito — torneio neutro não tem mandante real, não fazer esse ajuste
na Copa. `k=1.0` reproduz o comportamento antigo (sem mando) — útil para
comparar com/sem contra o mercado. Não altera fórmula do λ nem o Poisson (só
ajusta a coluna de peso). Validar o efeito por replicação em Python, não por
`data_only` do recalc (AI/Peso dá `#VALUE!` no LibreOffice — limitação
conhecida, não erro do ajuste).

### 6c. Aba Padrões — OBRIGATÓRIO sempre que houver ≥1 jogo (qualquer liga)
Roda LOGO APÓS `aplicar_ajuste_mando` (ou logo após `build_workbook` na
Copa), ANTES do recalc. Cria/substitui a aba "Padrões" com recorrências ≥80%
(gols/cartões/escanteios/chutes, pró e total) nos últimos jogos de cada time,
**filtradas pelo mando que ele efetivamente joga hoje** (time A entra só como
"Casa", time B só como "Fora"; na Copa, mando é sempre "Neutro" pelo
`_comp_name`, então filtrar por isso não teria efeito — ok usar mesmo assim):
```python
montar_aba_padroes(
    output_path,
    games,                                              # mesma lista do build_workbook
    csv_glob="/mnt/skills/user/planilha-liga-dia/data/matches/*seriebmatches*.csv",
    min_pct=0.8,       # % mínimo de recorrência (padrão 80%)
    min_jogos=7,       # amostra mínima por time/mando
)
```
Sem achados para os times do dia, a aba é criada mesmo assim com uma linha
avisando isso — nunca fica ausente sem explicação. Estes achados **não
condicionam por aderência de estilo/favoritismo** (o mercado provavelmente já
precifica) e vêm de amostra de 1 temporada (7-18 jogos): tratar como
candidato a investigar, não como sinal pronto para apostar — a própria função
já grava esse aviso na última linha da aba.

🚨 **Histórico do bug:** esta aba foi esquecida numa entrega inteira em 17/07
porque não estava na sequência documentada, mesmo a função já existindo em
`planilha_lib.py` — não era bug de código, era passo faltando no fluxo
escrito. Tratar como OBRIGATÓRIO, não opcional.

### 7. Recalcular e revisar
```bash
python3 /mnt/skills/public/xlsx/scripts/recalc.py <output_path> 90
```
**Avisos conhecidos** (LibreOffice headless, não erro do template): `#VALUE!`
em `Times!AI`/`AK` (Peso Final) para datas com dia > 12 (interpreta MM/DD em
vez de DD/MM); valores de fallback em `P.Plan` (Mercados) e `Gols Pró/Contra`
(Jogos do Dia) porque `LET`/`POISSON.DIST` só avaliam certo no Excel de
verdade. Sempre avisar o usuário disso ao entregar; **não tentar "corrigir"
a fórmula** — resolve sozinho ao abrir no Excel (locale pt-BR).

Se o `recalc.py` estourar o timeout (LibreOffice pode ser lento pra
inicializar em ambiente novo/frio), rodar de novo com um timeout maior antes
de assumir que é erro — não é um bug do workbook gerado.

### 7b. Fórmula robusta Pró/Contra (POR ÚLTIMO, após o recalc)
```python
aplicar_formula_pro_contra(output_path)
```
Modelo v2 (16/07): média ponderada (`Times!AK`) + desvio-padrão ponderado com
correção de reliability weights + corte unilateral/bilateral parametrizado
em `Parâmetros!B10` (limite unilateral, default 4) e `B11` (multiplicador de
DP, default 2.5) — só `SUMPRODUCT`/`IF`/`IFERROR`/`SQRT`/`ABS`, nunca
`LET`/`FILTER`/`SEQUENCE`/`STDEV.S`/ArrayFormula. Roda depois do recalc
porque o LibreOffice não avalia essas funções corretamente (deixaria
fallback); o Excel resolve ao abrir.

### 8. Sanitizar e apresentar
```python
sanitizar_v_vazio(output_path)
```
Remove tags `<v></v>` vazias que o openpyxl deixa em células de fórmula após
sucessivos load/save — XML inválido que o Excel recusa ("Encontramos um
problema em um conteúdo..."), com reparo automático que às vezes apaga a
fórmula. **Não usa openpyxl** (edita o XML do zip direto), então não
reintroduz o problema. Sempre o ÚLTIMO passo, nada mais toca o arquivo depois.

Depois de rodar, sempre apresentar o arquivo com `present_files` e um resumo
curto: jogo(s) do dia, favoritos, e qualquer aposta que já salte aos olhos
nos critérios (Edge Real / Sinal Externo / Alta Certeza) — lembrando que
esses valores só ficam certos de fato quando abertos no Excel.

## 🚨 ORDEM DE EXECUÇÃO É ESTRITA — sem exceção

```
build_workbook
  → aplicar_ajuste_mando        (pular na Copa — torneio neutro)
  → montar_aba_padroes
  → recalc.py
  → (ajustes de P.Font / marcar_estimados, se houver)
  → aplicar_formula_pro_contra
  → sanitizar_v_vazio
  → present_files                (fim — nada mais toca o arquivo)
```

## Bugs reais encontrados e corrigidos (histórico — por que a ordem acima existe)

1. **Fórmula array dentro de Tabela do Excel.** A versão original usava
   LET+FILTER como ArrayFormula (CSE) para as 12 colunas Pró/Contra, DENTRO
   da Tabela26 (Jogos do Dia). Isso é gatilho conhecido de "Encontramos um
   problema em um conteúdo..." no Excel real (XML tecnicamente válido, só o
   Excel reclama — LibreOffice não acusa nada). **Fix definitivo:** as 12
   colunas usam SUMPRODUCT clássico, nunca mais array formula em lugar
   nenhum do arquivo gerado.
2. **Tags `<v></v>` vazias.** Reabrir/resalvar o workbook várias vezes com
   openpyxl (`build_workbook` → `ajuste_mando` → ... ) deixa essas tags
   vazias em células de fórmula — XML inválido, o Excel às vezes apaga a
   fórmula no reparo automático. `sanitizar_v_vazio()` remove direto no XML
   do zip (não usa openpyxl), por isso é sempre o ÚLTIMO passo.
3. **Referência de outlier tem que ser média SIMPLES**, não ponderada por
   `Times!AK` — ponderar os dois (a referência E o resultado final) pelo
   mesmo peso é circular: o "normal" já nasceria puxado pros jogos de peso
   alto. O peso entra só no cálculo final, sobre o subconjunto já filtrado.
4. **Aba Padrões esquecida de uma entrega inteira** (17/07) por não estar
   documentada na sequência, mesmo a função já existindo — ver seção 6c.
5. **`@` injetado em IF/SE aninhado.** Mesmo sem LET e sem ArrayFormula, o
   Excel injeta `@` (interseção implícita) numa range de dados (ex.
   `Times!$F$2:$F$61`) quando ela aparece "crua" dentro dos dois ramos de um
   `SE()`/`IF()` — troca a range inteira pela célula da mesma linha,
   silenciosamente, zerando indicadores de times com poucos jogos válidos.
   Fix: eliminar o `SE()`/`IF()` da máscara de corte e usar combinação
   ARITMÉTICA (`unilateral*condA + (1-unilateral)*condB`, com `unilateral`
   escalar) — a range de dados só pode aparecer direto dentro de
   `SUMPRODUCT`, nunca dentro de um IF aninhado.
6. **Tokens `_xlfn`:** a única função "nova" usada hoje é `_xlfn.LET` — não
   precisa mais de `_xlfn._xlws.FILTER`/`_xlfn.SEQUENCE`/`_xlfn.STDEV.S`
   desde o modelo v2. Escrever os nomes crus faz o Excel (sobretudo celular)
   não reconhecer a função.

## Diferenças de priors entre ligas (medidas — não copiar cego de uma pra outra)

| Métrica                    | Série A (16/07, 177j) | Série B (12/07) | Copa 2026     |
|-----------------------------|:---:|:---:|:---:|
| Gols/jogo                   | 2.66 | 2.30 | 2.96 |
| Under 2.5 acerta             | ~50% | ~56% | 46% |
| Escanteios/jogo               | 10.02 | 10.4 | — |
| Cartões/jogo                   | 5.11 | 5.37 | — |
| Over 3.5 cartões               | — | 77% | — |
| Ratio gols casa/fora            | 1.396 | 1.255 | neutro (n/a) |
| Vantagem de mando (%)             | 34% | 23% | n/a |

Tabela de acerto por mercado (Escanteios 93% > Cartões 85% > Chutes 78% >
Total gols 54% > BTTS 50% > Combinação 41% > Resultado 33%) vem originalmente
da Copa — usar como prior nas outras ligas, mas reconstruir com bets próprias
a cada ~20 apostas por liga (perfis diferentes: Série B é mais faltosa,
favoritismos mais fracos que seleções).

## Regras que NUNCA mudam (herdadas de `docs/PROTOCOLO_BETS_LUCAS.md`), em qualquer liga
- Verificar odd real na Betano antes de confirmar entrada; não usar odds de
  memória (Regra 1) — sempre pesquisar.
- Sinalizar em vez de inventar quando faltar dado no CSV (Regra 2).
- P.Font reflete julgamento das fontes, não só odds normalizadas replicadas.
- Piso de odd 1.40 / teto 1.80 na Alta Certeza (validados por ROI na Copa;
  tratar como prior a revalidar em Série A/B, não como regra específica de
  uma liga só).
- Máximo 2 apostas por jogo; máximo 47% da banca total em qualquer jogo.
- SKIP quando os dois lados não têm nada a jogar (dead rubber na Copa;
  equivalente na Série A/B = fora da zona de acesso/playoff/rebaixamento).
- Não alterar fórmulas do template — só clonar/redimensionar
  (`build_workbook` já faz isso).
- Princípio 5 (escanteios): Over só quando o adversário FECHA EM BLOCO
  BAIXO real — na Série A/B, conferir `p5_por_numeros` (quem CEDE muitos
  escanteios é o gatilho real, acima do estilo inferido); na Copa, usar o
  banco de estilo (bloco_baixo 1-5) e checar se o "bloco baixo" também não
  tem histórico ofensivo real (ver exemplos DR Congo/Uruguai×Espanha no
  protocolo).

Ver `docs/PROTOCOLO_BETS_LUCAS.md` para os 23 exemplos reais (com custo em
R$ e a regra que cada erro gerou) — ler antes de recomendar qualquer entrada.
