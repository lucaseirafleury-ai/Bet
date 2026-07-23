# BRIEFING — Sistema de Apostas Brasileirão Série B 2026
# Lucas | Adaptado do sistema Copa 2026 | Atualizado: 12/07/2026
# Para qualquer nova sessão iniciar com contexto completo

---

## 1. IDENTIDADE DO SISTEMA

**Objetivo:** Análise de apostas por rodada da Série B 2026 com edge real.
**Banca:** ~R$49 (atualizar após cada rodada)
**Unidade:** 1u = R$2
**Casa:** Betano Brasil
**Formato:** Pontos corridos, 38 rodadas, 20 clubes. Ida/volta com mando invertido.
**O que está em jogo:** 2 primeiros sobem direto à Série A 2027; 3º–6º disputam
playoff (cruzamento olímpico) por mais 2 vagas; 4 últimos caem à Série C.

### O que muda vs. Copa (mata-mata) — importante
- **Não há dead rubber "clássico"** (ambos eliminados) até o fim da temporada,
  MAS existe o equivalente: **jogo sem stakes** = dois times já sem chance de
  acesso, playoff nem rebaixamento (isso só aparece nas rodadas finais). Até lá,
  quase todo jogo tem contexto (Z-4, G-4, playoff). **SKIP** continua valendo
  quando os dois lados não têm nada a jogar.
- **Mando de campo importa muito** (na Copa era neutro). Times de Série B têm
  desempenho casa/fora bem distinto — o `get_historico` já traz `Casa/Fora`
  real, não força "Neutro". Favoritismo do mandante costuma ser inflado.
- **Menos análise externa quantitativa** que a Copa. As fontes-fonte mudam
  (ver seção 12). Kalshi/Polymarket normalmente **não** cobrem Série B →
  P.Font vem de tipsters/casas + julgamento, com o cuidado da Regra de
  independência (não derivar P.Font só das odds da mesma casa).
- **Média de gols mais baixa** que a Copa 2026 (a Copa teve 2.96/jogo). A Série
  B tende a jogos mais truncados, com muito **1-0 e 1-1**. Under 2.5 volta a
  ter suporte estrutural — mas **validar por rodada**, não assumir.

---

## 2. ARQUITETURA DO SISTEMA (skill copa-planilha-dia serve p/ Série B)

A skill `copa-planilha-dia` foi generalizada e **funciona para a Série B**:
- `planilha_lib.py` já mapeia os CSVs `brazilseriea*` e `brazilserieb*`
  (competição "Brasileirão Série A/B 2026", mando Casa/Fora real).
- Fluxo idêntico: descobrir jogos da rodada → `get_historico()` →
  `attach_estilo()` → pesquisar odds/contexto → `mercados_rows_for_game()` →
  `build_workbook()` → `recalc.py`.
- Banco de estilos `data/estilos_selecoes.json` agora inclui as **20 equipes
  da Série B 2026** (notas 1-5 salvas em 12/07). Revisar quando um time mudar
  claramente de perfil (troca de técnico, reforços).

### Nome do arquivo de saída
`SerieB_Xjul.xlsx` (em vez de `Copa_Xjul.xlsx`). Estrutura idêntica: 4 abas
(Times / Jogos do Dia / Mercados / Fontes) + Critérios + Parâmetros.

### Dados-fonte (CSVs FootyStats em `/mnt/project/`)
```
brazilserieamatches2026to2026stats.csv   → Série A (para times que caíram/subiram)
brazilseriebmatches2026to2026stats.csv   → Série B 2026 (fonte principal)
```
Obs.: alguns times (Ceará, Fortaleza, Juventude, Sport) têm também jogos de
**Série A 2025 / Copa do Brasil** que NÃO estão nesses CSVs — o histórico
disponível é só o da Série B 2026 corrente. Sinalizar amostra parcial no
início da temporada (poucas rodadas jogadas = <15 jogos).

---

## 3. CRITÉRIOS DE CLASSIFICAÇÃO (iguais — rodam na aba Mercados)

Mesma lógica da Copa, mesma coluna "Critérios":

### 🎯 Edge Real — P.Plan > P.Font > P.Mkt, todos > 60% → entrar sempre
### 📡 Sinal Externo — P.Font > P.Mkt, P > 60%, planilha não contradiz → entrar
### ✅ Alta Certeza — P.Comb > 65%, **odd ≥ 1.40**, gatilho ≤ 1.80 → entrar se odd real ≥ 1.40
### 📊 Referência — P.Comb > 55%, edge > 10% → NÃO entrar (só análise)

Piso de odd 1.40 e teto 1.80 **continuam valendo** — foram validados por ROI,
não são específicos da Copa.

---

## 4. OS PRINCÍPIOS — reinterpretados para Série B

### Princípio 1 — Correlação intra-jogo → **inalterado**
### Princípio 2 — Alinhamento com a tese → **inalterado**
### Princípio 3 — Cruzar com histórico (poucos jogos = reduzir stake) → **inalterado**
### Princípio 4 — Diversificação → **máx. 2 apostas/jogo**; numa rodada com
   vários jogos, mín. 3 jogos diferentes. Em dia de 1-2 jogos só (fim de
   rodada), aceitar menos, mas nunca concentrar >47% da banca num jogo.
### Princípio 5 — ESCANTEIOS ⚠️ (o mais sensível ao contexto)
   Continua: Over escanteios **só** favorito dominante vs. **bloco baixo real**.
   Na Série B os "blocos baixos reais" são times como Operário PR, Juventude,
   Avaí, São Bernardo, Atlético-GO (defensivos por estilo). **NÃO** entrar
   quando o favorito é um time de posse enfrentando outro que também sobe
   (jogo end-to-end). Cuidado: favoritismos na B são mais fracos que na Copa —
   um "favorito" a 45% não domina como uma seleção a 70%.
### Princípio 6 — ACORDO PLANILHA + FONTES → **inalterado** (o mais validado)
### Princípio 7 — Não entrar quando mercado já precificou (odd < gatilho) → **inalterado**

---

## 5. CRIAR APOSTA — fatores de correlação (revisar na Série B)
Mesmos fatores da Copa como ponto de partida (Fav+O1.5≈92%, Fav+U3.5≈84%,
Fav+BTTSNão≈70%). **Recalibrar** após ~20 bets de Série B — a média de gols
mais baixa tende a **subir** P(Under 3.5 | fav vence) e P(BTTS Não | fav vence).

---

## 6. PADRÕES SÉRIE B 2026 (preencher com dados reais ao longo da temporada)

- Média de gols: **[medir]** — provisoriamente assumir ~2.3–2.5/jogo (mais baixa que Copa).
- Placares modais esperados: **1-0** e **1-1** dominantes (padrão de 2ª divisão).
- Mando pesa: mandante leva vantagem estrutural maior que em torneio neutro.
- Under 2.5 e BTTS Não: com suporte estrutural, mas **validar rodada a rodada**.
- Melhor defesa até rodada 17: **Juventude** (8 gols sofridos em 17 jogos).

*(Substituir por números medidos dos CSVs assim que houver amostra suficiente.)*

---

## 7. TAXA DE ACERTO POR MERCADO — herdada da Copa (revalidar na B)
Os pesos históricos (Escanteios 93% > Cartões 85% > Chutes 78% > Total gols 54%
> BTTS 50% > Combinação 41% > Resultado 33%) vêm da Copa. Servem como
**prior**, mas a Série B pode ter perfil diferente (mais cartões — jogo mais
faltoso; escanteios menos previsíveis por favoritismos fracos). **Reconstruir a
tabela** com as próprias bets da Série B a cada 20 apostas.

---

## 8. NOMENCLATURAS CSV (Série B) — nomes exatos no FootyStats
```
América Mineiro   (não "América-MG")
Athletic Club     (não "Athletic-MG")
Atlético GO       Avaí   Botafogo SP   CRB   Ceará   Criciúma   Cuiabá
Fortaleza   Goiás   Juventude   Londrina   Novorizontino   Náutico
Operário PR   Ponte Preta   Sport Recife   São Bernardo   Vila Nova
```
Verificar sempre com:
```python
[t for t in df['home_team_name'].unique() if 'termo' in t.lower()]
```

---

## 9. REGRAS QUE NÃO MUDAM (herdadas do protocolo)
- Verificar odd real na Betano antes de confirmar entrada.
- Não usar odds de memória — sempre pesquisar (Regra 1).
- Sinalizar em vez de inventar quando faltar dado no CSV (Regra 2).
- P.Font reflete julgamento das fontes, não só odds normalizadas.
- Piso 1.40 / teto 1.80 na Alta Certeza.
- Máx. 2 apostas por jogo; máx. 47% da banca por jogo.
- SKIP quando os dois lados não têm nada a jogar (equivalente ao dead rubber).

---

## 10. HISTÓRICO DE BANCA
(herdado; atualizar com resultados da Série B)

| Período | Evento | Banca |
|---|---|---|
| Copa 2026 | Fim do ciclo Copa | ~R$49 |
| 13/07 | 1º dia Série B (AME×LON, CEA×ATH) | ? |

---

## 11. UPDATES POR RODADA
*(uma linha por rodada: data | resultados | banca | aprendizado)*

| Data | Jogos | Banca | Aprendizado |
|---|---|---|---|
| 13/07 (R17) | América-MG×Londrina, Ceará×Athletic | ? | Migração do sistema Copa→Série B; mando volta a contar |

---

## 12. FONTES DE PESQUISA — Série B (substituem as da Copa)
Prioridade para Série B:
1. **Academia das Apostas Brasil** — stats e tips detalhados de Série B
2. **UmDois Esportes / GE Globo / O POVO** — contexto, escalações, desfalques
3. **Sofascore / FotMob** — xG, forma, H2H, confirmação de sede/horário
4. **Sportingbet / Betano / bet365 / Superbet** — odds de referência
5. **PredictZ / WinDrawWin / Academia** — probabilidades de modelo

⚠️ Kalshi/Polymarket em geral **não** cobrem Série B → P.Font vem de
tipsters + modelo próprio (Poisson calibrado), mantendo a independência
de P.Mkt (Regra do protocolo).

---

## 13. PROMPT PADRÃO PARA NOVA SESSÃO
```
Leia o briefing em /mnt/user-data/outputs/briefing_serieb.md antes de qualquer ação.
Leia /mnt/skills/user/copa-planilha-dia/SKILL.md para o fluxo completo.

Tarefa: Gere a planilha da Série B do dia [DATA].
```
A skill cobre descoberta dos jogos, histórico, estilo (banco já tem os 20
times da B), odds e montagem. Intervir só se a skill sinalizar (⚠️) dado
faltante.
