# Protocolo de Apostas — Regras Persistentes

Versão inicial, consolidada a partir do que estava espalhado nas skills
`copa-planilha-dia`/`serie-b-planilha-dia` (que citavam um
`briefing_*.md`/`PROTOCOLO_BETS_LUCAS.md` vivendo só em pasta efêmera de
sessão, não versionado). **Este arquivo existe pra parar de se perder entre
sessões — complete/corrija o que estiver incompleto ou desatualizado.**

## Regras que nunca mudam

1. **Não usar odds de memória** — sempre pesquisar odds reais (Betano e
   outras casas) antes de confirmar qualquer entrada.
2. **Sinalizar em vez de inventar** quando faltar dado no CSV/fonte — nunca
   preencher um número plausível sem avisar que é estimativa.
3. **P.Font reflete julgamento qualitativo das fontes**, não é só a odd de
   mercado normalizada — tem que agregar visão de tipsters/analistas.
4. **Não alterar fórmulas do template** — só clonar/redimensionar (hoje
   feito por `planilha_lib.build_workbook`; o motor de pesos em
   `pesos.py`/`excel_writer.py` grava valor calculado, não fórmula nova).
5. Máximo 2 apostas por jogo; mínimo 3 jogos diferentes por dia quando
   houver jogos suficientes.

## Critérios de aposta (faixas de ROI)

- **Alta Certeza**: piso de odd 1.40, teto 1.80. ROI histórico reportado:
  +38.8%, ~89% de acerto (revalidar periodicamente contra resultado real).
- Faixa "Referência" (menor confiança): ROI histórico reportado -41% — ou
  seja, evitar como base de decisão isolada.
- Gestão de banca: máximo 47% da banca por jogo.

## Parâmetros do motor de pesos (ver `metodologia_pesos/pesos.py`)

| Parâmetro | Valor atual | Origem |
|---|---|---|
| Decaimento de recência | 100%/85%/70%/50%/30%/15%/0% em ≤10/20/30/45/90/180/>180 dias | fórmula original do template (Times!AI) — ainda não retestado |
| `k` (encolhimento de mando) — **Série A** | **Nenhum ajuste (k=1.0)**, revisado 24/08/2026 | validado por retrospectiva — ver abaixo. Era 0.35 "no olho" |
| `k` (encolhimento de mando) — **Série B** | **Mantido em 0.35**, confirmado 24/08/2026 | validado por retrospectiva — melhor ou quase melhor nos mercados derivados (ver abaixo) |
| `k` (encolhimento de mando) — Copa | 0.35 | ainda "no olho" — Copa é torneio neutro, sem mando; parâmetro pouco relevante lá |
| `limite_unilateral` (corte outlier) | 4 | testado (3/4/5) na Série A e B, sem diferença mensurável no mercado de gols — ver retrospectivas |
| `multiplicador_dp` (corte outlier) | 2.5 | testado (2/2.5/3) na Série A e B, diferença dentro do ruído — ver retrospectivas |
| Filtro de validade (aderência estilo/favoritismo) | ≥65% nos dois | testado (0/0.5/0.65/0.8) 24/08/2026 — ver "Teste de ablação do estilo" abaixo. Mantido em 65% |

**Primeira rodada de calibração feita em 24/08/2026** contra a Série A
(154 jogos, rodada 24/38) e a Série B (156 jogos, rodada 24/38) — ambas
temporadas ainda em andamento. Relatórios completos:
`docs/retrospectiva_2026-08-24_seriea.md` e
`docs/retrospectiva_2026-08-24_serieb.md`.

**As duas ligas se comportaram DIFERENTE — por isso os parâmetros agora
divergem por liga:**
- **Série A**: o ajuste de mando piorou o modelo de forma consistente nas
  3 métricas (MAE de gols, acerto de Over/Under 2.5, acerto de BTTS) —
  por isso o `k` foi zerado.
- **Série B**: sinal misto — o `k` que minimiza o erro médio de gols
  (0.7) não é o que mais acerta Over/Under 2.5 e BTTS (0.35, o valor já
  em uso, vence ou quase vence nesses dois). Como os mercados derivados
  são mais próximos do que Lucas realmente aposta do que o erro médio de
  gols, mantivemos `k=0.35` na Série B sem mudança.

Tratar as duas como recomendação preliminar (amostra de temporada
parcial, só mercado de gols validado — não cartões/escanteios/chutes).

## Teste de ablação do estilo (24/08/2026)

Pergunta: o filtro/peso de aderência de estilo (≥65% nos dois, multiplica
em `peso_final`) está realmente ajudando a prever gols, ou é peso morto?
Testado isolando o efeito do estilo (`pesos.calcular_pesos_historico(usar_estilo=False)`)
contra o comportamento padrão, nas duas ligas, variando o limiar do
filtro — ver `docs/retrospectiva_estilo_2026-08-24.md` para o relatório
completo.

**Achado: no filtro atual (65%), o estilo é essencialmente indiferente**
(diferença de ~0.001-0.002 de MAE e 0-0.6pp de acerto, dentro do ruído) —
nas duas ligas. **Em filtro estrito (80%), o estilo ATRAPALHA**
(principalmente Série A: MAE piora 0.029, acerto de Over/Under 2.5 cai
6.5pp). Interpretação: não é que "estilo não importa" — é que os proxies
atuais (3 das 5 dimensões são proxies mais fracos, ver seção abaixo) não
estão discriminando bem o suficiente pra fazer diferença nesta amostra.
**Decisão**: manter `filtro_aderencia=0.65` (sem motivo pra trocar) e
manter o estilo ativado (não prejudica no filtro usual, só em 80%) — mas
não tratar como pilar comprovado do modelo até os proxies melhorarem ou o
teste for refeito nos outros mercados (cartões/escanteios).

## Notas de estilo — agora automáticas (últimos 5 jogos)

Desde a consolidação em `estilo.py`, as 5 notas de estilo por time
(Bloco Baixo, Pressão Alta, Transição, Posse, Bola Parada) deixaram de ser
julgamento qualitativo e passaram a ser calculadas a partir dos últimos 5
jogos de cada time, com parâmetros pré-definidos e documentados no próprio
arquivo. Duas dimensões (Posse, Bloco Baixo) usam dado direto do CSV do
FootyStats; as outras três (Pressão Alta, Transição, Bola Parada) usam
proxies estatísticos mais fracos (não há métrica direta de pressão/
transição/bola parada no CSV padrão) — sinalizar essa diferença de
confiança sempre que relevante. O banco JSON (`data/estilos_*.json`) virou
um cache sobrescrito a cada sessão, não mais editado à mão.

## Ligas cobertas hoje

- **Copa 2026**: torneio neutro, sem mando de campo.
- **Série B 2026**: mando de campo conta, média de gols mais baixa
  (2.3/jogo), liga mais faltosa (5.37 cartões/jogo), tem props de jogador.
  Dados reais em `data/footystats_serieb/`, calibração feita 24/08/2026
  (ver acima) — `k=0.35` mantido.
- **Série A**: dados reais em `data/footystats_seriea/` (league/teams/
  teams2/players/matches, subidos 24/08/2026, rodada 24/38 em andamento).
  Calibração feita 24/08/2026 (ver acima) — `k` de mando zerado.

## TODO (preencher com Lucas)

- [ ] Completar critérios de ROI por faixa de odd (só temos "Alta Certeza"
      e "Referência" documentados — havia mais faixas mencionadas em
      sessões anteriores que não foram recuperadas nesta consolidação).
- [ ] Confirmar se as regras "não usar odds de memória" / "máx 47% da
      banca" valem igual pra Série A ou se há ajuste por liga.
- [x] Rodar `retrospectiva.rodar_retrospectiva`/`grid_search` com os CSVs
      reais da Série A (24/08/2026) — ver relatório e resultado acima.
- [x] Rodar a mesma retrospectiva pra Série B (24/08/2026) — sinal misto,
      `k=0.35` mantido (ver relatório acima). Confirmado: não dava pra
      assumir que o achado da Série A valeria lá.
- [x] Teste de ablação do estilo (24/08/2026) — filtro de 65% mantido,
      estilo é indiferente nesse nível, atrapalha em 80% (ver acima).
- [ ] Estender `retrospectiva.py` pra validar os outros 10 indicadores
      Pró/Contra (cartões, escanteios, chutes, chutes no gol, gols 1T) —
      hoje só gols foi validado, nas duas ligas. Vale reavaliar o teste de
      ablação do estilo nesses mercados também (pode importar mais em
      escanteios, ligado ao "Princípio 5" do protocolo antigo).
- [ ] Confirmar com Lucas a decisão de zerar o `k` de mando da Série A
      antes de aplicar de vez nas planilhas reais (é recomendação
      preliminar, amostra de temporada parcial).
- [ ] Re-rodar as duas retrospectivas quando as temporadas estiverem mais
      avançadas (mais jogos = amostra melhor, principalmente pra
      desempatar o sinal misto da Série B).
