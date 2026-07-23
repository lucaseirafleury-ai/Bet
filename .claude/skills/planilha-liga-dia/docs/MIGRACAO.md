# Migração do sistema de apostas (Claude Project → Claude Code)

Migrado em 23/07/2026 a partir de um export (.zip) do Claude Project onde o
sistema rodava antes. Registro do que mudou e do que precisa de atenção.

## O que mudou (otimização)

As 3 skills antigas (`copa-planilha-dia`, `serie-a-planilha-dia`,
`serie-b-planilha-dia`) foram unificadas nesta única skill
`planilha-liga-dia`, parametrizada por `liga` ("copa" | "seriea" | "serieb"):

- `scripts/planilha_lib.py` — motor 100% compartilhado (histórico, clonagem
  de fórmulas, `build_workbook`, ajuste de mando, fórmula Pró/Contra robusta,
  `aplicar_formula_pro_contra`, `marcar_estimados`, `sanitizar_v_vazio`).
  Antes esse arquivo existia em 3 cópias idênticas (uma por skill); agora é
  uma só. `aplicar_ajuste_mando`/`aplicar_formula_pro_contra`/
  `marcar_estimados`/`sanitizar_v_vazio` também foram promovidos pra cá
  (antes viviam duplicados em `seriea_lib.py`/`serieb_lib.py`, apesar de não
  terem NENHUMA lógica específica de liga).
- `scripts/ligas.py` — substitui `seriea_lib.py` + `serieb_lib.py` (que eram
  98% idênticos) por um único módulo com um registro `LIGAS = {...}` por
  competição (CSVs agregados, banco de estilos, se é torneio neutro, prefixo
  de arquivo). Funções (`league_stats`, `team_corner_profile`,
  `corner_matchup`, `player_props`, `estilo_db_path`,
  `mando_shrink_k_default`) agora recebem `liga` como parâmetro.
- Guard-rails novos que não existiam antes: chamar `league_stats("copa")` ou
  `mando_shrink_k_default("copa")` levanta erro explícito (Copa é torneio de
  seleções neutro, sem CSVs agregados de liga/jogador nem mandante real) —
  antes isso só "funcionava" porque a Copa nunca teve um `copa_lib.py`
  chamando essas funções; agora está explícito no código.
- `data/matches/` — pasta única com os CSVs de PARTIDAS de Série A e B juntos
  (antes cada skill lia de `/mnt/project/*.csv`, um diretório de conhecimento
  do Project que misturava tudo). Times promovidos/rebaixados continuam
  carregando histórico dos dois lados porque o glob padrão inclui ambos.
- `data/footystats/<liga>/` — CSVs agregados de liga/time/jogador, exclusivos
  de Série A/B (a Copa não tinha esse enriquecimento).
- Deploy: fonte de verdade é este repo (`.claude/skills/planilha-liga-dia`);
  `scripts/deploy_skills.sh` (raiz do repo) sincroniza para
  `~/.claude/skills/planilha-liga-dia` para ficar disponível em qualquer
  sessão, não só quando este repo está aberto.

## ⚠️ Perda de dados identificada no export (parcialmente recuperada)

O arquivo `serie-b-planilha-dia/estilos_serieb.json` dentro do .zip recebido
**não continha JSON** — continha uma cópia do texto do `SKILL.md` da mesma
pasta (import/export trocou o conteúdo dos dois arquivos). O mesmo aconteceu
num segundo arquivo enviado separadamente com o mesmo nome, o que sugere que
a troca já existia na origem (Project do chat), não só no .zip.

Em 23/07/2026, Lucas recuperou o conteúdo colando o texto diretamente de uma
mensagem do Project (sem precisar baixar o arquivo pelo celular) e
`data/estilos_serieb.json` foi atualizado com os 20 times reais.

Essa versão recuperada tinha `"confianca": "baixa"` em TODOS os 20 times, com
o texto `"[Derivado de dados FootyStats 2026, sem scouting manual]"` em cada
entrada — ou seja, era um banco gerado só por estatística agregada, **não** o
banco com pesquisa qualitativa que o `SKILL.md` original da Série B descrevia
como "notas salvas em 12/07".

### Pesquisa qualitativa real (23/07/2026)

A pedido de Lucas ("é possível você fazer com base em fontes fortes?"), os
dois bancos foram revisados com pesquisa real (WebSearch por time, técnico
atual + estilo tático + fonte citada):

- **`estilos_seriea.json` — concluído.** Verificado time a time: 7 times
  tinham técnico desatualizado no banco antigo e foram reescritos (Cruzeiro:
  Tite→Artur Jorge; Corinthians: Dorival→Diniz; Vasco: Diniz→Renato Gaúcho;
  Remo: Osório→Léo Condé; Chapecoense: Dal Pozzo→Rafael Lacerda; Santos:
  Cuca confirmado mas com pesquisa tática real pela primeira vez; São Paulo:
  Crespo→Roger Machado→Dorival Júnior). Outros 4 mantiveram o técnico mas
  ganharam fonte/citação mais forte (Grêmio, Atlético PR, Coritiba,
  Bragantino). Os 9 restantes já estavam corretos e só foram confirmados.
  Nenhum time ficou em confiança baixa — os 8 em "media" (Vitória, Flamengo,
  Cruzeiro, Grêmio, Atlético PR, Remo, Santos, Chapecoense) têm identidade
  tática indireta (análise de jornalista/discurso de apresentação) em vez de
  citação direta e consistente do próprio técnico.
- **`estilos_serieb.json` — concluído.** Banco reescrito do zero (não havia
  nenhuma pesquisa qualitativa prévia para reaproveitar — uma primeira
  tentativa esbarrou no limite de sessão da API antes de escrever qualquer
  coisa, sem dano ao arquivo; a segunda tentativa completou os 20 times
  salvando em lotes). Resultado: 8 confiança alta, 11 media, 1 baixa (Goiás —
  Mozart Santos anunciado em 22-23/07/2026, zero jogos no comando até a data,
  notas necessariamente provisórias; reavaliar com 3-4 jogos de amostra).
  Times com amostra rasa por troca de técnico recentíssima (Ponte Preta,
  Sport Recife) ou fonte mais genérica (CRB, Botafogo SP, Operário PR) ficaram
  em "media" — considerar revisão manual prioritária nesses. Vários técnicos
  trocaram de posição entre si dentro da própria Série B em 2026 (Roger
  Silva: América-MG → Sport → Atlético GO; Daniel Paulista: Goiás → Ceará;
  Mozart: Ceará → Goiás; Umberto Louzer: Vila Nova → América Mineiro) —
  confirmado o posicionamento de cada um em 23/07/2026, mas essa liga está
  trocando comando com frequência incomum; reconferir se aparecer notícia
  mais recente.

Mesmo pesquisado, este é um banco de **estimativas de estilo, não um dado
objetivo** — é normal e esperado revisar/corrigir manualmente quando o
próprio Lucas discordar de uma nota específica (ver o mecanismo de
`overrides=` + `save_estilo_db()` no `SKILL.md`, o mesmo usado pra correções
pontuais desde a Copa).

## Modo Python sem Excel (`scripts/analise.py`, 23/07/2026)

Lucas descreveu o pós-processamento manual que fazia toda vez que recebia a
planilha: filtrar Mercados por P.Comb ≥ 65%, trocar `Parâmetros!B11`
(multiplicador do desvio-padrão) de 2.5 para 1.25 e descartar quem caísse
abaixo de 65% no P.Plan reavaliado, cortar odd de mercado > 2.0, e cruzar a
aba Padrões dos dois times procurando recorrências em comum (stake 1.0). Ele
pediu pra isso ficar mais fácil, "às vezes até sem planilha" — a planilha
Excel continua útil só para reformular parâmetros visualmente, não para o
consumo diário.

Resposta: `scripts/analise.py` reimplementa TODA a matemática do template em
Python puro (sem abrir Excel/LibreOffice):
- Aderência de estilo/favoritismo e peso por recência (`Times!AG/AH/AI/AK`).
- A fórmula Pró/Contra V2 (média/desvio-padrão ponderados + corte
  unilateral/bilateral), agora com `mult_dp` como parâmetro de função em vez
  de uma célula que precisa ser editada e reaberta no Excel.
- λ_A/λ_B e o parser de critério que gera P.Plan via Poisson bivariado
  (reverse-engineered lendo a fórmula LET real do template — `Mercados!F`),
  cobrindo BTTS, Over/Under gols, Resultado/DC, Handicap Asiático, mercados
  de 1º tempo e combinações (CA) com multiplicador.
- P.Comb (= P.Plan×45% + P.Font×55%), Edge, Veredito e as 4 categorias do
  protocolo (Edge Real/Sinal Externo/Alta Certeza/Referência) — confirmado
  que essas fórmulas do template já batem exatamente com
  `PROTOCOLO_BETS_LUCAS.md`.
- `gerar_shortlist()`/`relatorio_dia()` automatizam o pós-processamento
  manual inteiro (os 3 filtros + padrões em comum) numa chamada só.

Validação: só foi possível validar por CONSISTÊNCIA INTERNA
(`scripts/test_analise.py` — Poisson normalizado, Over/Under 2.5
complementares, Vence/Empate/Vence somando 1, DC = Vence+Empate, simetria
quando λ_A=λ_B, handicap mais exigente que resultado seco, BTTS
complementar, multiplicador de CA aplicado exato, e o corte de outlier
realmente reagindo a `mult_dp`), rodado com dados reais de Ceará x Athletic
Club (Série B) sem erros. **Não foi cross-validado abrindo a planilha de
verdade no Excel** — o `recalc.py`/LibreOffice trava neste ambiente (mesmo
problema de `javaldx`/Java já registrado acima, independente deste código).
Recomendação: na primeira vez que Lucas for usar de verdade, gerar também a
versão Excel do mesmo jogo e comparar os números antes de confiar 100% no
modo Python.

## O que NÃO foi migrado (não estava no export)

- CSVs de partidas da Copa do Mundo 2026 (worldcup/friendlies/qualifiers) —
  o ciclo da Copa já tinha terminado antes deste export ("Fim do ciclo Copa",
  banca ~R$49) e o .zip só trouxe dados de Série A/B. A liga `"copa"` está
  configurada em `ligas.py` mas sem CSVs de partida em `data/matches/` — se
  for reativada, adicionar os CSVs e revisar `CSV_ALIAS`/`_comp_name` em
  `planilha_lib.py`.
- `briefing_copa.md` (mencionado no `SKILL.md` da Copa, nunca existiu neste
  export nem no ambiente anterior).
