# Convenções deste projeto

## Desempenho

**Trabalho de CPU usa todos os núcleos.** Backtest, grid search e qualquer
varredura de parâmetros são CPU puro e cada combinação é independente —
paralelizar com `multiprocessing.Pool(os.cpu_count())`. Referência real:
um grid de 192 combinações levava ~2,5h single-thread; com 4 núcleos cai
para ~40min. Padrão em `grid_ligas_novas.py` (`_init_worker` carrega o
DataFrame uma vez por processo, em vez de serializar o df a cada tarefa).

**Exceção: chamadas à API do Sportmonks ficam sequenciais.** A API tem
rate limit (já retornou 429 em uso intenso) — paralelizar a puxada de
dado troca tempo por erro. Sequencial ali é proposital.

**Trabalho longo roda em background com checkpoint.** O container pode ser
reciclado; salvar parcial a cada etapa concluída (ver `grid_ligas_novas.py`)
para que uma interrupção custe no máximo uma etapa.

## Disciplina estatística (não negociável)

A régua para adotar qualquer critério:
1. `z >= ~2` no período completo;
2. positivo em **todos** os anos isoladamente (um ano negativo derruba);
3. `n >= 15` em treino e holdout;
4. o holdout confirma a **magnitude** do treino, não só o sinal.

Falhou em um dos quatro: não vira critério — no máximo "pista para
monitorar". Resultado negativo é resultado e fica documentado igual: o
histórico de descartes impede repetir teste.

Sempre reportar ano a ano, nunca só o agregado. Sempre comparar o modelo
contra **odd real de mercado** — modelo contra ele mesmo mede precisão,
não vantagem. Em grid grande, lembrar que o melhor z de treino é quase
sempre sorte: a coluna que vale é o holdout.

## Dados

- Dado bruto (`data/sportmonks_*/fixtures.jsonl`) fica **fora do git** —
  é grande e reconstituível via `pull_hist.py`.
- `SPORTMONKS_TOKEN` só por variável de ambiente. Nunca em commit, log ou
  documentação.
- Profundidade útil do plano (medido em 19/09/2026, com Historical Data):
  odds a partir de ~2018, estatística + árbitro a partir de ~2015, nada
  antes. Anos sem odd ainda servem para a média histórica dos árbitros.

## Rotinas

O painel roda 3x/dia (11h/15h/19h UTC) via sessão persistente com acesso
de push ao repo. Scripts que **sobrescrevem** `fixtures.jsonl` devem rodar
fora dessas janelas.
