# Varredura de filtro-mineração — checklist e rotina semanal

Lucas pediu (27/08/2026) pra revisitar TODAS as análises antigas de
amostra grande que não ficaram positivas (ou ficaram fracas), aplicando
a mesma técnica que funcionou pro Over 2.5-Sbo: separar as apostas
simuladas em green/red e procurar uma característica que filtre,
sempre checando ano a ano e nunca aceitando subgrupo com `n<15`.

**Rodam manualmente (já feitos, 27/08/2026)**:
- [x] Favoritismo (1x2) no Over 2.5-Sbo — sinal real, não empilhado com
  o teto de odd. `docs/retrospectiva_filtro_favoritismo_over25_2026-08-27.md`
- [x] 1x2 "casa" Série B — confirmado morto, filtro não resgata.
  `docs/retrospectiva_filtro_casa_serieb_2026-08-27.md`
- [x] 1x2 casa Série A — ruído, filtro não ajuda.
  `docs/retrospectiva_filtro_1x2_ruido_2026-08-27.md`
- [x] mandante_dc Série B — ruído, filtro não ajuda. Mesmo doc acima.

**Restam 24 candidatos**, priorizados: primeiro os que NÃO são
correlacionados com o Over Série A (diversificação real), depois os
que são (Over 1.5/3.5/4.5 e Under, mesma família de gols do Over 2.5 —
correlação 0,88-0,96 já medida, valor esperado menor).

## Método (reaproveitar sempre, sem inventar de novo)

Ver os 4 relatórios já feitos (link acima) como referência de formato.
Pra cada candidato desta lista:

1. **Rodar o backtest** com `retrospectiva.rodar_retrospectiva` +
   `simular_apostas`, usando os parâmetros já documentados no relatório
   antigo referenciado na tabela abaixo (não regrid do zero — reaproveitar
   o que já foi achado). Dado: 100% Sportmonks, bookmaker bet365
   (`sportmonks_adapter.carregar_liga_sportmonks`, default), mesmo
   `n_historico=15, min_jogos_historico=8, min_jogos_estilo=5` padrão do
   projeto, salvo se o relatório antigo especificar outro.
2. **Enriquecer as apostas simuladas** com as mesmas 7 features padrão
   (`odd`, `edge`, `prob_modelo_<mercado>`, `prob_mercado_<mercado>`,
   `gf_pred`, `ga_pred`, `gf_pred - ga_pred`) cruzando `(jogo, data)` de
   volta no `rel["jogos"]` completo (mesmo padrão dos 4 já feitos).
3. **Cortar pela mediana cada feature**, calcular `n`/acerto/ROI (lucro
   com `stake=1` consistente — CUIDADO, já teve um bug real de stake
   inconsistente nessa conta, ver `docs/retrospectiva_filtro_over25_green_red_2026-08-27.md`,
   seção "Correção" — sempre `lucro = sum((odd-1) se venceu senão -1)`,
   `ROI = lucro/n`, nunca dividir por um stake diferente do usado no
   lucro) e o detalhamento ano a ano (2024/2025/2026, os únicos anos
   disponíveis no Sportmonks).
4. **Só reportar como "candidato" um corte que tenha os 3 anos
   positivos** (mesmo padrão dos 4 já feitos) — nunca um agregado sem
   checagem ano a ano. Se nenhum corte passar nisso (bem provável pra
   maioria destes, já que muitos partem de amostra sistematicamente
   negativa), documentar como "testado, filtro não ajuda" — resultado
   negativo é resultado, mesma disciplina do projeto inteiro.
5. **Documentar em novo** `docs/retrospectiva_filtro_<nome>_<data>.md`
   (mesmo formato dos 4 já feitos), **atualizar o README.md** (novo
   item numerado, seguindo o último), **marcar o item como feito nesta
   checklist** (trocar `[ ]` por `[x]`, linkar o doc novo).
6. `pytest metodologia_pesos/` (não deve haver regressão — isso é só
   análise, sem mudança de produção) + commit + push pra
   `claude/campeonato-brasileiro-analysis-sb5ilb`.

## Regra da rotina semanal

**Rodar os PRÓXIMOS 3 itens não marcados (`[ ]`) do topo da lista pra
baixo**, um por semana (quartas-feiras), pra não consumir o limite
semanal de uma vez. Se algum candidato realmente achar um filtro
promissor (3 anos positivos, `n≥15`/ano), reportar isso destacado —
não é decisão automática de produção, fica documentado esperando o
Lucas decidir (mesmo padrão do teto de odd do Over 2.5). Não enviar
mensagem proativa se nada de especial for achado (resultado negativo
é esperado pra maioria) — só documentar e seguir. Se algo promissor
for achado, aí sim vale destacar claramente no fim da execução.

## Lista priorizada (24 restantes)

### Grupo 1 — não correlacionados com Over Série A (prioridade alta)

- [ ] Escanteios Série A — params/motor em `docs/retrospectiva_escanteios_cartoes_2026-08-27.md`
  (aviso: já testado com viés sistemático negativo forte, z=-2,38; baixa
  chance de achar filtro, mas testar mesmo assim por completude)
- [ ] Escanteios Série B — mesmo doc acima (z=-2,80)
- [ ] Favorito DC Série A — params em `docs/retrospectiva_favorito_dc_2026-08-25.md`
  (ROI -6% a -17% sozinho, sistemático)
- [ ] Favorito DC Série B — mesmo doc (ROI -3% a -4%)
- [ ] 1x2 "empate" Série A — grid em `docs/retrospectiva_1x2_dc_2026-08-25.md`
- [ ] 1x2 "fora" Série A — mesmo doc
- [ ] 1x2 "visitante_dc" Série A — mesmo doc (z chegou a -1,2/-1,6 no grid original)
- [ ] 1x2 "empate" Série B — mesmo doc + `docs/retrospectiva_1x2_dc_novos_eixos_2026-08-25.md`
- [ ] 1x2 "fora" Série B — mesmo par de docs (z=-2,36/-2,47 pro par fora/visitante_dc)
- [ ] 1x2 "visitante_dc" Série B — mesmo par de docs

### Grupo 2 — correlacionados com Over Série A (prioridade baixa, mesma família de gols)

- [ ] Over 1.5 Série A — params em `docs/retrospectiva_over_1_5_3_5_4_5_2026-08-25.md`
- [ ] Over 1.5 Série B — mesmo doc
- [ ] Over 3.5 Série A — mesmo doc
- [ ] Over 3.5 Série B — mesmo doc
- [ ] Over 4.5 Série A — mesmo doc
- [ ] Over 4.5 Série B — mesmo doc
- [ ] Under 1.5 Série A — odd real em `docs/retrospectiva_under_odds_reais_2026-08-27.md`
- [ ] Under 1.5 Série B — mesmo doc
- [ ] Under 2.5 Série A — mesmo doc
- [ ] Under 2.5 Série B — mesmo doc
- [ ] Under 3.5 Série A — mesmo doc
- [ ] Under 3.5 Série B — mesmo doc
- [ ] Under 4.5 Série A — mesmo doc
- [ ] Under 4.5 Série B — mesmo doc

## Quando a lista acabar

Depois do último item marcado `[x]`, a rotina deve avisar o Lucas (só
nesse caso, é uma exceção à regra de "não notificar") que a varredura
completa terminou, com um resumo de quantos candidatos novos foram
achados (provavelmente poucos ou nenhum, dado o padrão já visto) — e
então desativar a própria rotina (`update_trigger` com `enabled=false`,
ou avisar o Lucas pra desativar).
