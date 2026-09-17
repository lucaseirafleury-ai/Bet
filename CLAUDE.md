# Instruções do projeto

## Como trabalhar

### Sinalizar quando vale trocar para o Opus

Antes de rodar algo, avalie se o Opus entregaria resultado melhor que o Sonnet
e **avise o usuário antes de começar**, para ele trocar o modelo se quiser.

Vale sinalizar em: decisão de arquitetura com trade-off não óbvio, raciocínio
estatístico delicado (escolher piso de confirmação, julgar se um resultado é
edge ou ruído), diagnóstico de causa raiz complexa, e código onde o risco é de
*completude* — esquecer um caminho alternativo que lê o mesmo dado.

Não precisa perguntar para: rodar script que já existe, atualizar config, git,
checar API, conferir contagem. Siga direto.

### Usar todos os núcleos em processo de CPU

Sempre que for rodar processamento pesado de CPU, **paralelize usando todos os
núcleos disponíveis** (`nproc`) em vez de rodar sequencialmente. Verifique
núcleos e memória livre antes, e confira que o consumo por processo cabe.

Escolha o eixo de paralelização que **não duplica trabalho compartilhado**. No
estudo das ligas, por exemplo, o eixo certo é o alvo (independentes entre si) e
não a liga — a descoberta no Brasil é compartilhada entre as ligas e seria
refeita em cada processo.

Antes de disparar processos em paralelo, confira se algum deles **escreve em
arquivo compartilhado**. `buscar_sportmonks.buscar()` grava no checkpoint
quando encontra fixture nova; vários processos gravando no mesmo arquivo o
corrompem. Consolide com uma execução sequencial antes, e faça backup.

### Validar durante a execução, não só no fim

Execuções longas já produziram bugs descobertos só no fim. Em toda execução
longa:

1. **Output incremental** — nunca `| tail` nem buffer que esconda o progresso
   até o fim (use `python3 -u`).
2. **Monitor cobrindo erro E progresso** — silêncio não é sucesso; um processo
   travado é indistinguível de um saudável se o filtro só vigia o caminho feliz.
3. **Validar o primeiro lote** antes de deixar o resto rodar — conferir se os
   dados fazem sentido (contagens batendo, valores em faixa plausível, campos
   preenchidos), não só se o script não quebrou.
4. **Parar ao primeiro sinal estranho** e investigar, em vez de anotar e seguir.

Verificações que já pegaram bug real neste projeto: monotonicidade de
estatística acumulada (nunca pode diminuir ao longo do jogo), `snapshots ==
jogos_com_resultado × 6`, e conferir que nomes de função/símbolos externos
existem antes de rodar (`bs.juntar` não existia — a função é `mesclar`).

## Estrutura

- `ligas_live_app/` — painel ao vivo (Flask), roda no Render
- `pesquisa_gols/` — pipeline de pesquisa que gera `ligas_live_app/regras_sinais.json`

## Git e deploy

- Desenvolvimento: `claude/football-goal-probability-analysis-4nc14e`
- Produção: `claude/executar-iniciar-pasta-v42hg8` (o Render faz deploy automático)

Para levar algo a produção: confira `/api/status` e `/api/insights` em
https://painel-sinais-ligas.onrender.com para garantir que não há jogo ao vivo,
faça cherry-pick dos arquivos específicos (`git checkout <branch-trabalho> --
<arquivos>`), valide sintaxe/JSON, commit, push, e volte para o branch de
trabalho. Nunca copie o branch inteiro.

## Dados

Odds ao vivo via Sportmonks só trazem **bet365** (verificado em milhares de
linhas nas 5 ligas). Outras casas aparecem no catálogo mas não no feed do nosso
plano. Mercado de chutes existe só **pré-jogo** — a bet365 congela a linha ~1min
após o apito e nunca reprecifica, em liga nenhuma.
