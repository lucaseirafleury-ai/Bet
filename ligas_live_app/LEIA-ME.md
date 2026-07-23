# Painel de Sinais — Ligas Nórdicas/Bálticas

Sistema de análise pré-live + monitoramento ao vivo para Superettan, Allsvenskan,
A Lyga, 1. Lyga e 1. Division, usando a API da Sportmonks.

## 1. Configuração inicial (só uma vez)

1. Abra `config.py` e cole seu token da Sportmonks em `SPORTMONKS_TOKEN`.
2. Se quiser trocar alguma liga, ajuste o dicionário `LIGAS_MONITORADAS`
   (precisa bater com as 5 ligas selecionadas no seu plano Sportmonks).

## 2. Como rodar

Dê **duplo clique em `INICIAR.bat`**.

Isso vai:
- Instalar as dependências automaticamente (só na primeira vez demora um pouco)
- Abrir o painel no navegador em `http://127.0.0.1:5000`

## 3. Como usar o painel

**Botão "Rodar análise pré-live"**
Roda a Fase 1: busca os próximos jogos das 5 ligas, monta o perfil de cada time
(médias dos últimos jogos) e calcula:
- Placar modal (Poisson)
- Favorito de posse, pressão e xG_proxy

Os cartões aparecem na coluna do meio. Rode isso de manhã, antes das rodadas do dia.

**Botão "Iniciar monitoramento ao vivo"**
Roda a Fase 2 em segundo plano: a cada 60 segundos, verifica os jogos ao vivo
das 5 ligas e compara o que está acontecendo com o que foi previsto na Fase 1.

Isso alimenta dois lugares diferentes do painel:

- **"Jogos ao vivo agora"** (coluna do meio) — painel permanente, sem limiar,
  atualizado a cada ciclo. Mostra por time: xG_proxy acumulado, divergência
  xG × gols reais, pressão, escanteios, cartões e eficiência de finalização
  (chutes no alvo / chutes totais).
- **"Sinais ao vivo"** (coluna da direita) — só os eventos que cruzaram um
  limiar de desvio, cobrindo 4 frentes: ritmo de gols, ritmo de escanteios,
  ritmo de cartões, e pressão/xG_proxy (esse último só dispara quando as
  últimas 3 leituras confirmam uma tendência consistente — evita alertar em
  cima de um pico isolado de 1 minuto).

Deixe rodando durante os jogos. Clique em "Parar monitoramento" quando acabar
a rodada (ou simplesmente feche a janela do INICIAR.bat).

## 4. Ajustar o comportamento

Tudo fica em `config.py`:

| Parâmetro | O que controla |
|---|---|
| `DIAS_A_FRENTE` | quantos dias pra frente a Fase 1 busca jogos |
| `JOGOS_HISTORICO_PERFIL` | quantos jogos recentes usa pra montar o perfil de um time |
| `MINUTO_MINIMO_ALERTA` | a partir de que minuto o monitor pode gerar sinal |
| `LIMIAR_DELTA_PRESSAO` / `LIMIAR_DELTA_XG` | quão grande o desvio de pressão/xG precisa ser pra virar sinal |
| `LIMIAR_DELTA_GOLS` / `LIMIAR_DELTA_ESCANTEIROS` / `LIMIAR_DELTA_CARTOES` | idem, para cada mercado |
| `LIMIAR_DIVERGENCIA_XG_GOLS` | diferença (em "gols") entre xG_proxy acumulado e gols reais para virar sinal |
| `JANELA_MOMENTUM` | quantas leituras recentes usa pra confirmar tendência (padrão: 3) |
| `MIN_LEITURAS_CONSISTENTES` | de quantas dessas leituras precisa concordar na direção (padrão: 2) |
| `INTERVALO_POLLING_SEGUNDOS` | de quanto em quanto tempo o monitor checa os jogos ao vivo |

## 5. Observações importantes

- **A precisão da fórmula de xG_proxy e Pressão é aproximada** — baseada em
  chutes/posse/dangerous attacks, não é um xG real de fornecedor especializado.
  Sirva como sinal direcional, não como probabilidade calibrada.
- **A qualidade do perfil pré-live depende do histórico disponível.** Times com
  poucos jogos na base (início de temporada, promovidos) terão perfis menos
  confiáveis — o sistema usa valores-padrão razoáveis nesses casos, mas vale
  checar `jogos_considerados` no relatório antes de confiar 100%.
- Este sistema **não envia dado nenhum pra fora da sua máquina** — tudo roda
  localmente, os arquivos de dados ficam em `data/`.
- Se a Sportmonks mudar o nome de algum campo de estatística (ex: "Shots On Goal"
  virar outra coisa), ajuste as constantes `CAMPO_*` no topo de `xg_pressure.py`.

## 7. Backtest histórico (validar o modelo sem esperar jogos futuros)

Roda direto no terminal, sem precisar do painel:

```powershell
python backtest.py
```

O que ele faz:
- Pega os jogos já finalizados das 5 ligas nos últimos 45 dias (ajustável em
  `DIAS_HISTORICO` dentro do arquivo)
- Para cada jogo, reconstrói — usando o recurso `trends` da Sportmonks — como
  as estatísticas estavam nos minutos 15, 30, 45, 60 e 75
- Recalcula o que o modelo teria mostrado naquele momento (com e sem o ajuste
  dinâmico de xG/pressão) e compara com o resultado final real
- Gera `data/backtest_resultados.csv` — uma linha por (jogo, checkpoint)

No fim, imprime um resumo:
```
Probabilidade média dada ao resultado real, SEM ajuste: XX.X%
Probabilidade média dada ao resultado real, COM ajuste: XX.X%
Ajuste melhorou a leitura em XX.X% dos casos
```

Se "COM ajuste" for consistentemente maior que "SEM ajuste", o ajuste dinâmico
de xG/pressão está agregando valor real. Se for igual ou pior, os pesos
(`PESO_XG`, `PESO_PRESSAO` em `live_poisson.py`) provavelmente precisam ser
recalibrados — ou até zerados, se o ajuste estiver atrapalhando mais que ajudando.

**Duas limitações que este backtest ainda tem, e que valem sua atenção:**

1. **Cobertura de `trends` não é garantida em todas as ligas.** Se um jogo vier
   com "[sem trends]" no terminal, significa que a Sportmonks não tem essa
   granularidade pra aquela liga/partida específica — nesse caso o jogo é pulado.
2. **Identificação do tipo "Gol" nos eventos não foi validada em teste real.**
   Se aparecer o aviso "[aviso] type_id de gol não identificado", o placar parcial
   reconstruído está usando o placar final como aproximação (menos preciso que
   reconstruir o placar real minuto a minuto). Se isso acontecer, me avise o nome
   exato que aparecer nos types da sua conta, que ajusto a lista de candidatos em
   `identificar_type_id_gol()` dentro de `backtest.py`.

## 9. Modelo calibrado de Over/Under (validado fora da amostra, POR LIGA)

O mercado **Over/Under 2.5 gols** usa um modelo diferente do resto, calibrado com
569 jogos / 2.845 snapshots das 5 ligas (validação cronológica fora da amostra,
sem vazamento entre snapshots do mesmo jogo). **Cada liga tem seus próprios
coeficientes** — testamos e confirmamos que aplicar o mesmo coeficiente pra
todas reduziria a precisão:

| Liga | Métrica incremental | Melhora real? |
|---|---|---|
| Allsvenskan | Chutes totais por 15min | Sim (+1,12% MAE / +2,98% Poisson) |
| 1. Lyga | Chutes para fora por 15min | Sim, mas pequena (+0,46% / +1,87%) |
| 1. Division | Ataques por 15min | Sim, mas pequena (+1,52% / +1,38%) |
| A Lyga | — | Nenhuma métrica ajudou — usa "somente minuto" |
| Superettan | — | Nenhuma métrica ajudou — usa "somente minuto" |

No painel, o nome do mercado mostra **"✓ calibrado"** quando esse modelo está
ativo (sempre está, pras 5 ligas — mesmo A Lyga/Superettan usam a versão
"somente minuto" calibrada, que é matematicamente equivalente e mais segura
que o ajuste heurístico genérico).

**Achado relevante que vale lembrar**: chutes no alvo (SOT) — a métrica que
melhor explica gols já acontecidos — **não ajudou em nenhuma das 5 ligas** a
prever gols futuros. Isso reforça que "o que já aconteceu" e "o que ainda vai
acontecer" são perguntas diferentes, com respostas diferentes.

Vitória casa/empate/fora e BTTS continuam usando a lógica anterior (ajuste
heurístico por xG/pressão, por time) — testamos versões calibradas por time
separado e não funcionaram (ver histórico de decisões no chat), então não
foram substituídas.

Os coeficientes ficam em `MODELOS_CALIBRADOS_POR_LIGA`, dentro de
`live_poisson.py`, caso precise ajustar no futuro.

## 10. Estrutura de arquivos

```
config.py              → configurações centrais
sportmonks_client.py    → chamadas à API
poisson_model.py        → cálculo do placar modal
xg_pressure.py          → cálculo de xG_proxy e Pressão (compartilhado)
prelive_analysis.py     → Fase 1
live_monitor.py         → Fase 2
app.py                  → servidor local + dashboard
templates/dashboard.html
static/style.css
static/app.js
data/                   → arquivos gerados (JSON), criados automaticamente
```
