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
| Decaimento de recência | 100%/85%/70%/50%/30%/15%/0% em ≤10/20/30/45/90/180/>180 dias | fórmula original do template (Times!AI) |
| `k` (encolhimento de mando) | 0.35 | escolhido "no olho", validado por inspeção de resultado em `SerieA_16jul_6.xlsx` |
| `limite_unilateral` (corte outlier) | 4 | escolhido "no olho" |
| `multiplicador_dp` (corte outlier) | 2.5 | escolhido "no olho" |
| Filtro de validade (aderência estilo/favoritismo) | ≥65% nos dois | fórmula original do template (Times!O2 etc.) |

**Nenhum desses parâmetros foi calibrado estatisticamente contra resultado
real ainda** — é o principal item da etapa de calibração (ver
`metodologia_pesos/README.md`, seção "o que ainda falta").

## Ligas cobertas hoje

- **Copa 2026**: torneio neutro, sem mando de campo.
- **Série B 2026**: mando de campo conta, média de gols mais baixa
  (2.3/jogo), liga mais faltosa (5.37 cartões/jogo), tem props de jogador.
- **Série A**: reaproveita a mesma fórmula/parâmetros da Série B (não
  validada separadamente ainda) — banco de estilo próprio ainda não existe.

## TODO (preencher com Lucas)

- [ ] Completar critérios de ROI por faixa de odd (só temos "Alta Certeza"
      e "Referência" documentados — havia mais faixas mencionadas em
      sessões anteriores que não foram recuperadas nesta consolidação).
- [ ] Confirmar se as regras "não usar odds de memória" / "máx 47% da
      banca" valem igual pra Série A ou se há ajuste por liga.
- [ ] Definir de onde vem `Tips_telegram.xlsx` de forma acessível a
      qualquer sessão (hoje só existe localmente no Windows do Lucas).
