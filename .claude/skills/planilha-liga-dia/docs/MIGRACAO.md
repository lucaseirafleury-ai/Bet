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

**Mas atenção:** essa versão recuperada tem `"confianca": "baixa"` em TODOS
os 20 times, com o texto `"[Derivado de dados FootyStats 2026, sem scouting
manual]"` em cada entrada — ou seja, é um banco gerado só por estatística
agregada (posse, escanteios/jogo, gols sofridos/jogo, faltas/jogo), **não** o
banco com pesquisa qualitativa (técnico, estilo tático observado) que o
`SKILL.md` original da Série B descrevia como "notas salvas em 12/07". Tratar
como o mesmo tipo de rascunho que já existia para a Série A: válido para
destravar `attach_estilo` (nenhum time falta mais), mas revisar/completar com
julgamento qualitativo antes de confiar nele para o Princípio 5 — a coluna
`tr` (transição), em particular, tende a ser a mais fraca desse tipo de
derivação puramente estatística (mesmo problema já visto na Série A).

O banco da Série A (`estilos_seriea.json`, 20 times) veio íntegro no export —
mas o próprio `SKILL.md` da Série A já sinalizava que é um RASCUNHO gerado só
por estatística, sem validação qualitativa do Lucas (ver seção "PENDÊNCIAS"
no SKILL.md unificado) — mesmo caveat do banco da Série B agora.

## O que NÃO foi migrado (não estava no export)

- CSVs de partidas da Copa do Mundo 2026 (worldcup/friendlies/qualifiers) —
  o ciclo da Copa já tinha terminado antes deste export ("Fim do ciclo Copa",
  banca ~R$49) e o .zip só trouxe dados de Série A/B. A liga `"copa"` está
  configurada em `ligas.py` mas sem CSVs de partida em `data/matches/` — se
  for reativada, adicionar os CSVs e revisar `CSV_ALIAS`/`_comp_name` em
  `planilha_lib.py`.
- `briefing_copa.md` (mencionado no `SKILL.md` da Copa, nunca existiu neste
  export nem no ambiente anterior).
