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
| `k` (encolhimento de mando) — Série B/Copa | 0.35 | ainda "no olho" — Série B não testada separadamente ainda |
| `limite_unilateral` (corte outlier) | 4 | testado (3/4/5) na Série A, sem diferença mensurável no mercado de gols — ver retrospectiva |
| `multiplicador_dp` (corte outlier) | 2.5 | testado (2/2.5/3) na Série A, diferença dentro do ruído — ver retrospectiva |
| Filtro de validade (aderência estilo/favoritismo) | ≥65% nos dois | fórmula original do template (Times!O2 etc.) — ainda não retestado |

**Primeira rodada de calibração feita em 24/08/2026** contra 154 jogos da
Série A 2026 (rodada 24/38, temporada ainda em andamento) — ver
`metodologia_pesos/docs/retrospectiva_2026-08-24_seriea.md` para o
relatório completo. Achado principal: **o ajuste de mando piorou o modelo
nesta base** (quanto mais forte o encolhimento, pior o MAE de gols e o
acerto de Over/Under 2.5 e BTTS, de forma consistente) — por isso o `k` da
Série A foi zerado acima. É uma amostra parcial de uma única liga/
temporada e só valida o mercado de gols (não cartões/escanteios/chutes) —
tratar como preliminar, não como validação definitiva. Falta rodar a
mesma retrospectiva pra Série B assim que os CSVs chegarem, e não assumir
que o mesmo resultado vale lá (a Série B tem mando de campo mais forte,
~23%, segundo `serie-b-planilha-dia/SKILL.md`).

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
- **Série A**: dados reais em `data/footystats_seriea/` (league/teams/
  teams2/players/matches, subidos 24/08/2026, rodada 24/38 em andamento).
  Único dos três com uma primeira calibração retrospectiva feita (ver
  acima) — `k` de mando revisado pra Série A especificamente.

## TODO (preencher com Lucas)

- [ ] Completar critérios de ROI por faixa de odd (só temos "Alta Certeza"
      e "Referência" documentados — havia mais faixas mencionadas em
      sessões anteriores que não foram recuperadas nesta consolidação).
- [ ] Confirmar se as regras "não usar odds de memória" / "máx 47% da
      banca" valem igual pra Série A ou se há ajuste por liga.
- [x] Rodar `retrospectiva.rodar_retrospectiva`/`grid_search` com os CSVs
      reais da Série A (24/08/2026) — ver relatório e resultado acima.
- [ ] Rodar a mesma retrospectiva pra Série B assim que os CSVs chegarem
      (não assumir que o `k=1.0` da Série A vale lá também).
- [ ] Estender `retrospectiva.py` pra validar os outros 10 indicadores
      Pró/Contra (cartões, escanteios, chutes, chutes no gol, gols 1T) —
      hoje só gols foi validado.
- [ ] Confirmar a decisão de zerar o `k` de mando da Série A com o Lucas
      antes de aplicar de vez nas planilhas reais (é recomendação
      preliminar, amostra de temporada parcial).
- [ ] Re-rodar a retrospectiva da Série A quando a temporada estiver mais
      avançada (mais jogos = amostra melhor).
