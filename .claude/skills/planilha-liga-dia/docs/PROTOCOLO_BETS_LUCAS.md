# PROTOCOLO_BETS_LUCAS.md
# Manual de Decisão — Apostas Copa 2026
# Atualizado: 03/07/2026 | Baseado em histórico real desta competição

---

## 1. PERFIL DE ANÁLISE E RISCO

**Banca:** ~R$49 | **Unidade:** R$2 | **Casa:** Betano Brasil
**Fase atual:** Round of 32 (mata-mata, jogos únicos)

**Perfil de decisão:**
- Prefere **alta probabilidade sobre alto EV especulativo**
- Evita exposição >47% da banca em um único jogo
- Corrige ativamente quando o analista (Claude) erra — e espera que a correção seja absorvida imediatamente
- Não gosta de volume vazio: menos apostas com mais convicção
- Nunca aceita sugestão que viole princípio previamente acordado, mesmo que pareça fazer sentido contextualmente

**Histórico de banca:**
- R$50 → R$160 (props simples, odds 1.20–1.60) ✅
- R$160 → R$40 (apostas em resultado/combinações, odds 2.00+) ❌
- R$40 → ~R$49 (retomada com props e princípios) ✅

**Lição estrutural:** Odds acima de 1.80 destruíram a banca. O modelo não tem precisão suficiente para essas faixas.

---

## 2. MERCADOS QUE USO

**Prioridade 1 — Props (mais estáveis, menos contexto-dependentes):**
- Escanteios Over/Under X.5 — **93% de acerto histórico**
- Cartões Over/Under X.5 — **85% de acerto**
- Chutes totais Over/Under X.5 — **78% de acerto**
- Chutes a gol Over/Under X.5 — **70% de acerto**

**Prioridade 2 — Mercados condicionais com base sólida:**
- Dupla Chance (DC) — quando P.comb > 65% e odd ≥ 1.40
- Over/Under gols — somente quando há acordo planilha+fontes E contexto Copa confirma
- BTTS Sim/Não — somente quando independente do resultado principal

**Prioridade 3 — Criar Aposta (CA):**
- Favorito vence + Over 1.5 (correlação +92%)
- Favorito vence + Under 3.5 (correlação +84%)
- Favorito vence + BTTS Não (correlação +70%)
- **Regra:** só criar CA quando ambos os componentes têm EV positivo individualmente OU a CA sozinha atinge odd ≥ 1.40

**Mercados de 1°/2° Tempo:**
- Over 0.5 gols 1°T — funciona bem em contexto ofensivo
- Time X marca 1°T — mais preciso que gols totais

---

## 3. MERCADOS QUE EXIGEM CAUTELA

### 🔴 Resultado (Mandante/Empate/Visitante)
**Taxa de acerto histórico: 33%**
- Usar como principal SOMENTE com acordo planilha+fontes forte (Princípio 6)
- Nunca como aposta primária em jogos de classificação ou mata-mata equilibrados
- EV negativo mesmo com P=50% se a odd for 1.50 (EV = 1.50×0.50-1 = -25%)

### 🔴 Over/Under Gols nesta Copa
**Under 2.5 acertou apenas 46% dos jogos da Copa 2026** (vs média histórica de ~52%)
- Média de gols desta Copa: **2.96/jogo**
- Cautela extra em contextos de última rodada ou time precisando de gol
- Under 3.5 é mais conservador e passa melhor pelo contexto Copa

### 🔴 Combinações (3+ eventos)
**Taxa de acerto: 41%** — pior que cara ou coroa
- Cada perna adicionada multiplica o risco sem correlação equivalente
- Máximo 2 eventos correlacionados por CA (mesmo jogo, positivamente correlacionados)

### 🔴 Escanteios com adversário forte
Quando o adversário NÃO joga em bloco baixo:
- Espanha, Alemanha, França, Brasil, Argentina, Portugal, Holanda = NÃO entrar
- Jogo fica end-to-end → poucos escanteios para qualquer lado

### 🟡 Chutes Totais
- O mais volátil dos props
- Depende do ritmo tático do jogo (difícil de prever)
- Só entrar com folga de ±10 chutes acima do threshold

---

## 4. REGRAS QUE CORRIGI AO LONGO DO TEMPO

### Correção 1 — Princípio 5 (Escanteios)
**Erro original:** "Uruguai×Espanha é cena ideal de escanteios — Uruguai pressionando em desespero vs Espanha em bloco."
**Correção:** Espanha NÃO joga em bloco baixo. Mesmo defendendo empate, ela joga com posse dominante. Resultado: jogo de posse vs urgência = poucos escanteios.
**Custo:** -R$8 em 26/06/2026
**Regra corrigida:** Over escanteios SOMENTE quando o adversário FECHA EM BLOCO BAIXO. Não basta precisar vencer — o adversário precisa ser passivo por natureza.

### Correção 2 — DR Congo não é bloco baixo puro
**Erro:** Inglaterra×DR Congo Over 8.5 escanteios — análise tratou DR Congo como time passivo.
**Correção:** DR Congo 3-1 Uzbekistan = tem capacidade ofensiva real. Times que marcam gols não são "bloco baixo puro". Quando o time defensivo tem histórico ofensivo, o jogo vira mais aberto.
**Custo:** ❌ Red em 01/07/2026
**Regra:** Bloco baixo puro = NZ, Panamá, Jordânia (cederam 0 gols por muito tempo). DR Congo, Gana = não são.

### Correção 3 — Piso de odd 1.40 na Alta Certeza
**Descoberta empírica (estudo retroativo dias 19-27/jun, 41 bets):**
- odd < 1.35 → ROI -8.1%
- odd ≥ 1.35 → ROI +10.3%
- **odd ≥ 1.40 → ROI +38.8% (89% acerto, 8/9 bets)**
- odd ≥ 1.50 → ROI +80.3%
**Regra:** Alta Certeza só aparece na Aba Hoje se odd estimada ≥ 1.40. Abaixo disso, o mercado absorveu toda a margem.

### Correção 4 — Filtro de aposta analisada vs confirmada
**Erro:** Sugerir NZ×Bélgica Over 9.5 escanteios a 2.51 como entrada válida.
**Correção:** Odd 2.51 está acima do piso máximo de 1.80. Uma odd alta NÃO significa valor — significa que o mercado acha improvável. Com EV aparente de +X%, mas odd 2.51, o risco real não justifica.
**Regra:** Verificar sempre se odd real Betano > gatilho E ≤ 1.80. Fora disso, não entra.

### Correção 5 — Concentração de banca
**Erro:** R$25 em um único jogo (Paraguai×Austrália, dia 25/06) com 5 apostas diferentes.
**Custo:** -R$25 quando jogo terminou 0-0 (snoozefest — ambos já sabiam que empate classificava).
**Regra:** Máximo 2 apostas por jogo. Máximo 47% da banca total em qualquer jogo.

### Correção 6 — Princípio 6 em contradições internas das fontes
**Erro:** Japão×Suécia — placar modal das fontes dizia "1-1", aposta sugerida era "Over 2.5". Contradição interna.
**Resultado:** 1-1 (Under 2.5). As fontes tinham a resposta certa no placar modal mas a aposta errada.
**Regra:** Antes de qualquer entrada, verificar se o placar modal das FONTES é consistente com o mercado recomendado. Se "1-1" no placar → Over 2.5 é contradição interna → SKIP.

### Correção 7 — Dead rubbers
**Erro:** Entrar em Senegal×Iraque (ambos eliminados) como "Senegal favorito".
**Regra:** Ambos eliminados = SKIP absoluto. Sem stakes = imprevisível. Qualquer resultado é possível independente da qualidade dos times.

---

## 5. REGRAS PARA NÃO INVENTAR DADOS

1. **Não usar odds memorizadas.** Sempre pesquisar odds reais via web_search antes de preencher APOSTAS_DATA. Odds mudam entre a análise e o jogo.

2. **Não assumir CSV quando não há dados.** Se `csv_n = 0` ou time tem ❌ no check de cobertura → declarar explicitamente "análise parcial" e reduzir stake ou skip.

3. **Não inventar P.fontes.** Se não há fonte externa consultada, P.fontes = P.mercado (igual à odd normalizada). Só declarar P.fontes diferente de P.mercado quando há fonte externa real.

4. **Não normalizar de memória.** Usar sempre a fórmula:
   ```python
   def dec(o): return 1+100/(-o) if o<0 else 1+o/100
   ph, pd, pa = 1/dec(h), 1/dec(d), 1/dec(a)
   s = ph+pd+pa
   norm = (ph/s, pd/s, pa/s)
   ```

5. **Não extrapolar histórico sem alerta.** Se o time histórico jogou em contexto muito diferente (Copa vs qualificatórias, em casa vs fora), sinalizar no OPINIAO.

6. **Não confundir odd modelo com odd Betano.** A odd estimada no APOSTAS_DATA é a nossa estimativa justa. A odd Betano real pode ser diferente. Sempre verificar antes de confirmar entrada.

---

## 6. APOSTA ANALISADA vs APOSTA CONFIRMADA

**Analisada:** aparece na planilha com P.comb calculado, edge estimado, gatilho definido.
**Confirmada:** Lucas verificou a odd real na Betano, odd real > gatilho, odd real ≤ 1.80, e decidiu entrar.

**Nunca recomendar como "entrar" sem que o usuário tenha verificado a odd real.**

Formato correto de saída ao recomendar:
```
✅ ENTRA se odd Betano ≥ [GATILHO]
🟡 Break-even se odd Betano = [1/P.comb]
❌ Sem valor se odd Betano < [1/P.comb]
```

Nunca dizer "entra a 1.40" sem que Lucas tenha confirmado que a Betano está oferecendo isso.

---

## 7. REGRAS PARA ANÁLISE PRÉ-JOGO

### Passo 1 — Verificar contexto de classificação
- Ambos eliminados → SKIP
- Um eliminado, outro classificado → verificar se o classificado tem razão para poupar
- Ambos classificados lutando por posição → jogo real, entrar normalmente
- Mata-mata → under 2.5 tem suporte contextual extra (cautela defensiva)

### Passo 2 — Verificar cobertura CSV
```python
n = len(comp[(comp['home_team_name']==time)|(comp['away_team_name']==time)])
# ✅ ≥10 jogos | ⚠️ 5-9 jogos | ❌ <5 jogos
```
- ❌ zero → stakes mínimos, análise só por fontes externas

### Passo 3 — Normalizar odds e calcular P.mercado
Sempre com a fórmula. Nunca de cabeça.

### Passo 4 — Preencher P.fontes
Buscar: Yahoo Sports Betting, CBS Sports, DraftKings, ESPN.
Query: `"[TeamA] [TeamB] World Cup 2026 prediction best bet"`
Extrair: narrativa, placar modal, melhor aposta sugerida.

### Passo 5 — Aplicar Princípio 6
- Planilha e fontes concordam na direção? → continua
- Fontes internamente consistentes? (placar modal bate com aposta) → continua
- Padrão Copa confirma? (média 2.96 gols → cautela Under 2.5) → ajustar

### Passo 6 — Aplicar Princípio 5 (escanteios)
Verificar ANTES de incluir qualquer Over escanteios:
- O adversário fechará em bloco baixo? (NZ, Panamá, Jordânia = sim; Alemanha, França, Espanha = NÃO)
- O adversário tem histórico de marcar gols mesmo sendo inferior? (DR Congo 3-1 Uzbekistan = não é passivo)

### Passo 7 — Verificar piso e correlação
- Alta Certeza: odd estimada ≥ 1.40
- CA: dois mercados do mesmo jogo com correlação positiva
- Princípio 1: apostas no mesmo jogo são independentes?

---

## 8. REGRAS PARA ANÁLISE LIVE

> ⚠️ Esta seção é baseada em contexto e não em dados históricos validados.

### Gol marcado pelo favorito (1-0 no 30min)
- Under 2.5 mantido? → verificar se adversário vai se abrir (mais gols vêm)
- Over escanteios? → aumenta (adversário pressiona para empatar)
- DC do favorito → provavelmente já passou do gatilho. Skip.

### Favorito perdendo (0-1 no 30min)
- Resultado/DC favorito: odd sobe → verificar se novo gatilho cria valor real
- Over gols: favorito vai atacar = mais gols prováveis
- Escanteios: favorito pressionando = mais escanteios

### 0-0 no intervalo
- Under 2.5 mantido se jogo fechado e nenhum lado criou muito
- BTTS Não mantido se um dos lados tem ataque fraco
- Over gols pode subir de valor (menos gols no 1°T = mais pressão no 2°T)

### Red card no 1°T
- Equipe com 10 homens: fechar em bloco → Over escanteios do adversário sobe
- Under gols: equipe menor pode conseguir 0-0 ou 0-1
- BTTS Não: time com 10 homens dificilmente marca

---

## 9. REGRAS POR MERCADO ESPECÍFICO

### Handicap Asiático (AH)
- Só entrar quando P.real > 55% e contexto forte de dominância
- AH -1.5 = favorito vence por 2+ gols → exige P ≥ 60% e contexto de goleada esperada
- AH -0.5 = favorito vence (equivale a resultado) → preferir resultado direto ou DC
- Preencher no RESULTADOS como "verificar" — o script não avalia automaticamente

### Over/Under Gols
- Over 1.5: enter quando P ≥ 68% e odd ≥ 1.35 (break-even com P=74%)
- Over 2.5: entrar quando ambas as equipes são ofensivas E Copa confirma (não usar em mata-mata se contexto for cauteloso)
- Under 2.5: cautela — apenas 46% de acerto nesta Copa
- Under 3.5: mais seguro, 62% de acerto. Usar em mata-mata defensivo

### Dupla Chance (DC)
- Entrar quando P.comb ≥ 65% E odd Betano ≥ 1.40
- Se odd DC < 1.40 → combinar com Over/Under via CA para melhorar a odd

### Cartões
- Over 3.5 cartões: entrar em jogos físicos/decisivos com árbitro rígido
- Over 0.5 cartões 1°T: funciona em jogos de alta intensidade no início
- **85% de acerto** — segundo mercado mais confiável

### Escanteios
- Over X.5: SOMENTE favorito dominante vs bloco baixo real
- Bloco baixo = time que cede domínio territorial por necessidade ou estilo
- **NÃO é**: Espanha, Alemanha, França (jogam com posse)
- **É**: NZ, Panamá, Jordânia, Cabo Verde
- Times ofensivos de segunda linha (DR Congo, Gana): verificar histórico de gols antes de classificar como "passivo"
- **93% de acerto quando Princípio 5 é corretamente aplicado**

### BTTS Sim/Não
- Só entrar quando não correlacionado com resultado principal
- BTTS Não: entrar quando favorito tem clean sheet histórico E adversário tem pouco ataque
- BTTS Sim: entrar em jogos abertos onde ambas têm dados de gol no CSV
- Evitar BTTS Sim em mata-mata (defensivos por natureza)

---

## 10. ESTRUTURA DA PLANILHA/OUTPUT

### Aba Hoje — 4 tabelas em ordem de prioridade:

**🎯 Edge Real** (roxa) — PRIORIDADE MÁXIMA
- Critério: P.plan > P.font > P.mkt, todos > 60%
- Ineficiência real: planilha enxerga algo que mercado subestima
- ROI validado: +11.6% (71% acerto)
- Ação: entrar sempre, qualquer odd acima de 1.20

**📡 Sinal Externo** (laranja)
- Critério: P.font > P.mkt, P > 60%, planilha não contradiz (≥ P.mkt × 0.90)
- ROI validado: +7.3% (71% acerto)
- Ação: entrar em 100% dos casos sem filtro de odd mínima

**✅ Alta Certeza** (azul) — ODD ≥ 1.40 OBRIGATÓRIO
- Critério: P.comb > 65%, gatilho ≤ 1.80, **odd estimada ≥ 1.40**
- ROI validado: +38.8% (89% acerto) com piso 1.40
- Ação: entrar quando odd Betano real ≥ 1.40

**📊 Referência** (verde escuro)
- Critério: P.comb > 55%, edge > 10%
- ROI histórico: -41.7%
- Ação: NÃO entrar automaticamente. Só análise.

### 11 colunas da Aba Hoje:
```
Jogo | Aposta | P.Plan | P.Font | P.Mkt | P.Comb | Edge | Gatilho | Odd(input) | Veredito | Stake
```

### Combinações automáticas (CA):
O sistema gera automaticamente para cada jogo com favorito identificado:
- CA: [Fav] + Over 1.5 (fator condicional 0.92)
- CA: [Fav] + Over 2.5 (fator 0.76)
- CA: [Fav] + Under 3.5 (fator 0.84)
- CA: [Fav] + BTTS Não (fator 0.70)

### Arquivo de dados (dados_Xjun.py):
Estrutura obrigatória:
```python
ESTILO = {"TeamA": ("Descrição", bb, pa, tr, posse, bp), ...}
PERFIL_ALVO = {"TeamA": dict(nome="TeamB", fav="XX%", estilo="...", notas=[...]), ...}
JOGOS = [("TeamA", "TeamB", "DD/MM HH:MM ET", "Cidade"), ...]
OPINIAO = {("TeamA","TeamB"): "Análise com princípios aplicados", ...}
FONTES_DATA = {("TeamA","TeamB"): dict(narrativa="", placar_modal="", ...), ...}
APOSTAS_DATA = {("TeamA","TeamB"): [("Mercado","Tipo","chave",p_fon,odd,p_plan), ...], ...}
BETS_1418 = {("TeamA","TeamB"): [("Mercado","Tipo","chave",p,odd,p_ov,"nota"), ...], ...}
TIMES = [...]; SHEET_NAMES = {...}; ARBITROS_JOGOS = [...]; CSV_ALIAS = {}
OUTPUT_PATH = "/mnt/user-data/outputs/Copa_Xjun.xlsx"
```

---

## 11. CHECKLIST ANTES DE RECOMENDAR UMA APOSTA

1. **P.comb ≥ 65%?** (Alta Certeza) → se não, é Referência (não entrar)
2. **Odd estimada ≥ 1.40?** (piso empírico) → se não, a odd não paga o risco
3. **Gatilho ≤ 1.80?** (range válido) → se >1.80, stake não justificado
4. **Princípio 6:** Planilha e fontes apontam na mesma direção? → se não: SKIP
5. **Princípio 6b:** Fontes internamente consistentes? (placar modal bate com aposta) → se não: SKIP
6. **Princípio 5 (se escanteios):** Adversário fecha em bloco baixo REAL? → se não: SKIP
7. **Princípio 1:** Apostas no mesmo jogo são independentes entre si?
8. **Princípio 4:** Máximo 2 apostas por jogo? Mínimo 3 jogos diferentes?
9. **Dead rubber?** Ambos eliminados → SKIP absoluto
10. **Sem dados CSV?** Time com ❌ → stakes mínimos ou skip
11. **Copa 2026 padrão confirma?** Under 2.5 só 46% → cautela extra
12. **A recomendação está como "verificar odd real antes de entrar"?** → sempre incluir essa nota

---

## 12. CHECKLIST ANTES DE PREENCHER A PLANILHA

1. **CSV disponível e atualizado?** Verificar com `glob.glob(CSVS)` e contar jogos por time
2. **Odds pesquisadas via web?** Não usar odds memorizadas
3. **Normalização feita com fórmula?** Não fazer de cabeça
4. **P.fontes tem fonte real?** Se não há fonte consultada, P.fontes = P.mercado
5. **APOSTAS_DATA com pelo menos resultado, Under, Over, BTTS, DC por jogo?**
6. **BETS_1418 com nota e break-even?** `Break-even = round(1/p_fontes, 2)`
7. **ARBITROS_JOGOS preenchido?** Mesmo que com "A confirmar"
8. **CSV_ALIAS correto?** Verificar nomes divergentes (ex: "DR Congo" → "Congo DR")
9. **OUTPUT_PATH correto?** `/mnt/user-data/outputs/Copa_Xjun.xlsx`
10. **Após gerar:** rodar recalc.py para resolver fórmulas Excel
11. **Princípios 5 e 6 verificados** em cada OPINIAO antes de sugerir props

---

## 13. EXEMPLOS REAIS EXTRAÍDOS DESTE HISTÓRICO

### Exemplo 1 — Escanteios válido ✅
**Jogo:** Nova Zelândia × Bélgica (26/06/2026)
**Entrada original:** "NZ×Bélgica Over 9.5 escanteios — Bélgica precisa vencer vs NZ bloco baixo. Cenário ideal."
**Análise correta:** NZ fecha em bloco baixo por necessidade. Bélgica com De Bruyne, Lukaku pressionando. Princípio 5 ✅ perfeitamente aplicado.
**Decisão correta:** ENTRAR
**Resultado:** ✅ Green
**Erro a evitar:** Confundir este cenário com Uruguai×Espanha (que foi classificado erroneamente como "ideal").

---

### Exemplo 2 — Escanteios inválido ❌
**Jogo:** Uruguai × Espanha (26/06/2026)
**Entrada original:** "Uruguai×Espanha Over 9.5 escanteios — Uruguai pressionando em desespero vs Espanha em bloco. Cenário ideal."
**Erro:** Espanha NÃO joga em bloco baixo. Mesmo defendendo empate, joga com posse dominante (toque curto, Xavi style).
**Decisão correta:** SKIP — Princípio 5 violado
**Resultado:** ❌ Red — Custo: -R$8
**Correção do analista após erro:** "Errei. Violei o princípio que você pediu para registrar. O único escanteios válido hoje era NZ×Bélgica."
**Regra consolidada:** Over escanteios só quando adversário FECHA EM BLOCO BAIXO. Espanha, Alemanha, França, Brasil, Argentina, Portugal, Holanda = NÃO fecham.

---

### Exemplo 3 — DR Congo não é bloco baixo puro ❌
**Jogo:** Inglaterra × DR Congo (01/07/2026)
**Entrada:** Over 8.5 escanteios — Inglaterra dominante vs time defensivo.
**Erro:** DR Congo 3-1 Uzbekistan = tem capacidade ofensiva real. Não é time puramente passivo.
**Resultado:** ❌ Red — DR Congo marcou (2-1), jogo ficou mais aberto que o esperado.
**Lição:** Time que marca gols não é bloco baixo puro. Verificar SEMPRE o histórico ofensivo antes de classificar como passivo.

---

### Exemplo 4 — Princípio 6 validado empiricamente ✅
**Dia:** 25/06/2026 — 6 jogos
**Resultado da validação:**

| Jogo | Acordo P6? | Resultado |
|---|---|---|
| CIV×Curaçao | ✅ Planilha e fontes concordam | ✅ 2-0 CIV Green |
| Par×Aus | ✅ Ambas Under 2.5 | ✅ 0-0 Under Green |
| Tur×EUA | ✅ Over 2.5, BTTS Sim | ✅ 3-2 Over/BTTS Green |
| Tun×Ned | ❌ Planilha dizia 2-4 gols Holanda, fontes diziam Under 2.5 | ❌ 3-1 → planilha estava certa |
| ECU×ALE | ❌ Contradição interna | ❌ Resultado misto |
| Jpn×Swe | ❌ Placar modal 1-1 mas aposta sugerida Over 2.5 | ❌ 1-1 → Under teria ganho |

**Conclusão:** 3 jogos COM acordo → 3/3 acertos. 3 jogos SEM acordo → análise inútil.

---

### Exemplo 5 — Contradição interna nas fontes ❌
**Jogo:** Japão × Suécia (25/06/2026)
**Entrada original:** Over 2.5 gols — "Suécia precisa atacar + Japão no contra."
**Erro:** O próprio placar modal das fontes dizia "1-1". Over 2.5 só ganha no 2-1, 2-2, etc. — os placares MENOS prováveis segundo a própria análise.
**Resultado:** 1-1. Under 2.5 teria ganho.
**Regra:** Se o placar modal das fontes aponta para Under mas a aposta sugerida é Over — SKIP. Há contradição interna.

---

### Exemplo 6 — Concentração de banca ❌
**Dia:** 25/06/2026
**Erro:** R$25 em 5 apostas no jogo Paraguai×Austrália (47% da banca no mesmo jogo)
**Resultado:** Jogo terminou 0-0 (snoozefest — ambos sabiam que empate classificava). Perda total de -R$25.
**Contexto perdido:** A análise não capturou que, dependendo do outro jogo do grupo, empate poderia classificar os dois. O contexto estava incompleto.
**Regra:** Máximo 2 apostas por jogo. A concentração foi o maior erro estrutural — independente de qualquer análise.

---

### Exemplo 7 — Piso de odd 1.40 descoberto retroativamente ✅
**Contexto:** Estudo retroativo de 41 bets da Alta Certeza (dias 19-27/jun)
**Descoberta:**

| Piso de odd | Bets | Taxa | ROI |
|---|---|---|---|
| Sem filtro | 41 | 68% | **-8.1%** |
| ≥ 1.35 | 20 | 75% | +10.3% |
| **≥ 1.40** | **9** | **89%** | **+38.8%** |
| ≥ 1.50 | 3 | 100% | +80.3% |

**Decisão:** Implementar odd ≥ 1.40 como piso obrigatório para Alta Certeza.
**Motivo:** Abaixo de 1.40 o mercado já absorveu toda a margem. 68% de acerto com odd 1.25 dá ROI negativo.

---

### Exemplo 8 — Criar Aposta resolvendo o problema do piso ✅
**Jogo:** Canada × South Africa (28/06/2026)
**Problema:** Canadá DC @ 1.20 (< 1.40 piso) + Under 3.5 @ 1.30 (< 1.40 piso) → ambas abaixo do piso
**Solução CA:** Canadá DC + Under 3.5 = **@ 1.56** — acima do piso
**Cálculo:** P(Under 3.5 | Canadá DC) = 0.93 (se Canadá vence/empata, jogo controlado = poucos gols)
**P.CA = 0.78 × 0.93 = 73%** | EV = 1.56 × 0.73 - 1 = **+13.9%** ✅
**Resultado:** ✅ Green — Canada 1-0 South Africa
**Lição:** CA transforma dois mercados abaixo do piso em entrada com valor real.

---

### Exemplo 9 — Resumo vs Fontes: confiar nos dados ❌
**Jogo:** Tunísia × Holanda (25/06/2026)
**Situação:** Resumo projetava Holanda 2-4 gols. Fontes narrativas sugeriam Under 2.5 ("jogo morno, Holanda poupando").
**Erro:** Seguimos a narrativa das fontes (Under 2.5) contra os dados do Resumo (Holanda 2-4 gols).
**Resultado:** 3-1 — Over 2.5 ✅, Under 2.5 ❌
**Regra:** Quando dados e narrativa contradizem, confiar nos dados. A narrativa "Holanda poupando" era menos confiável que o histórico de gols da Holanda.

---

### Exemplo 10 — Dead rubber SKIP obrigatório ✅
**Jogo:** Senegal × Iraque (26/06/2026)
**Status:** Ambos eliminados. Nenhum tem nada a ganhar.
**Análise:** "Senegal favorito pela qualidade individual."
**Decisão correta:** SKIP — contexto zero, resultado imprevisível.
**Regra permanente:** Dois times eliminados = skip total. Mesmo que um seja tecnicamente superior.

---

### Exemplo 11 — Paraguai×Austrália: ignorar o Resumo ❌
**Jogo:** Paraguai × Austrália (25/06/2026)
**O Resumo dizia:** "Paraguai 1 gol, Austrália 1 gol — jogo tático e truncado. Apostas: Empate, Under 2.5."
**Decisão errada:** Apostamos em Over 1.5, Over 3.5 cartões, Austrália marca 1°T — ignorando o que o Resumo disse.
**Resultado:** 0-0. Under 2.5 ✅, Empate ✅. Tudo que o Resumo apontou foi certo.
**Lição:** Quando o Resumo aponta Under e Empate de forma consistente, confiar. Nosso viés contextual ("ambos precisam de gol") estava errado.

---

### Exemplo 12 — Sinal Externo funciona sem piso de odd ✅
**Jogo:** Suíça × Argélia (02/07/2026)
**Mercado:** Suíça DC + Over 1.5 @ 1.70 (CA)
**Análise:** P.font(70%) > P.mkt(66%) → Sinal Externo. Argélia em alta confiança vai atacar.
**Nota:** Suíça DC @ 1.27 sozinha (< 1.40) — não entra. Over 1.5 @ 1.37 (< 1.40) — não entra. CA @ 1.70 → ENTRA.
**EV = 1.70 × 0.66 - 1 = +12%**
**Decisão:** ENTRAR via CA

---

### Exemplo 13 — Correlação intra-jogo viola Princípio 1 ❌
**Entrada errada:** Portugal DC + Empate @ X.XX no mesmo jogo
**Erro:** Portugal DC cobre "Portugal vence OU empata". Empate isolado é subconjunto do DC.
**Resultado se Portugal vencer:** DC ✅ + Empate ❌ → redundância que desperdiça stake
**Resultado se empatar:** DC ✅ + Empate ✅ → aparente diversificação mas apostas correlacionadas
**Regra:** Nunca apostar DC e Empate do mesmo jogo. São apostas correlacionadas que violam Princípio 1.

---

### Exemplo 14 — Props vs Resultado: diferença de taxa de acerto 📊
**Dado empírico (histórico Copa 2026, 88 apostas validadas):**

| Mercado | Taxa de acerto |
|---|---|
| Escanteios | **93%** |
| Cartões | **85%** |
| Chutes | **78%** |
| Total gols | 54% |
| BTTS | 50% |
| Combinação | 41% |
| Resultado | **33%** |

**Conclusão prática:** Escanteios e cartões são mundos diferentes do resultado. Não tratar como equivalentes.

---

### Exemplo 15 — Odd abaixo do gatilho = sem edge ❌
**Caso:** NZ×Bélgica Chutes 25.5 @ 1.29 (gatilho modelo: 1.66)
**Análise:** Edge aparente = -14.9%
**Decisão correta:** SKIP — Betano já precificou completamente. Entrar aqui é apostar na certeza, não no valor.
**Regra:** odd Betano < gatilho = sem edge, independente de quão alta seja a probabilidade percebida.

---

### Exemplo 16 — Argentina × Cabo Verde: Princípio 5 aplicado corretamente ✅
**Jogo:** Argentina × Cabo Verde (03/07/2026)
**Contexto:** Cabo Verde cedeu 27 chutes vs Espanha sem sofrer gol — bloco baixo PURO.
**Diferença vs DR Congo:** Cabo Verde não tem histórico ofensivo significativo. É genuinamente passivo.
**Decisão:** Over escanteios Argentina + Argentina -1.5 AH = entradas válidas pelo Princípio 5
**Raciocínio:** Argentina pressiona constantemente vs time que se fecha = cantos em sequência.

---

### Exemplo 17 — Mbappé 1+ chutes como "evento quase certo" em CA ✅
**Contexto:** Lucas reportou green ao adicionar "Mbappé 1+ chute" em uma CA com odd melhor.
**Princípio:** P(evento quase certo ≈ 97%) em CA amplifica edge sem reduzir probabilidade significativamente.
**Fórmula:** CA base @ 1.62 × Mbappé chute @ 1.10 = **1.78** com P ≈ 73% × 97% = **70.8%**
**EV = 1.78 × 0.708 - 1 = +26%** (vs +13% da CA original)
**Regra:** Adicionar evento quase certo (P>95%) em CA com EV positivo amplifica o edge. Em CA com EV negativo, piora.

---

### Exemplo 18 — Quando a planilha diverge muito do mercado ⚠️
**Jogo:** Canadá × África do Sul (28/06/2026)
**Situação:** Planilha calculou P(África do Sul vence) = 51% (histórico defensivo). Mercado dizia 18%.
**Aba Hoje:** VAZIA — todas as 4 tabelas sem entradas.
**Análise:** Divergência de 33 pontos percentuais = modelo não tem edge aqui.
**Decisão:** Não usar a Aba Hoje. Usar análise contextual pura: CA Canadá DC + Under 3.5 @ 1.56 (identificada manualmente).
**Regra:** Quando Aba Hoje está vazia, não significa que não há aposta — pode significar que o modelo diverge do mercado. Analisar manualmente pelo Mercados.

---

### Exemplo 19 — ROI por grupo de critério (validação retroativa) 📊
**Estudo:** Dias 19-27/jun, 88 apostas com resultado

| Grupo | Bets | Taxa | ROI |
|---|---|---|---|
| 🎯 Edge Real | 7 | 71% | **+11.6%** |
| 📡 Sinal Externo | 22 | 71% | **+7.3%** |
| ✅ Alta Certeza (odd≥1.40) | 9 | 89% | **+38.8%** |
| 📊 Referência | 3 | 33% | -41.7% |

**Conclusão:** Referência = nunca entrar. Edge Real = entrar sempre que aparecer. Alta Certeza com piso = o mercado mais lucrativo.

---

### Exemplo 20 — Portugal × Croácia: empate subestimado nas fontes ⚠️
**Jogo:** Portugal × Croácia (02/07/2026)
**Situação:** P.fontes(empate) = 26.7% (mesma que mercado). Mas analistas externos diziam "draw is underpriced" — Croácia tem 5 empates nos últimos 8 mata-matas.
**Erro de preenchimento:** P.fontes foi preenchida igual ao mercado, então o sistema não capturou o sinal externo.
**Correção:** Quando analistas externos dizem que o mercado subestima um evento, P.fontes deveria refletir isso (35-40%) para capturar o Sinal Externo.
**Regra:** Ao preencher P.fontes, refletir o julgamento qualitativo das fontes, não apenas replicar as odds normalizadas. Se a fonte diz "underpriced", aumentar P.fontes acima de P.mercado.

---

### Exemplo 21 — Análise de edge real: quando o sistema detecta ineficiência 🎯
**Cenário hipotético baseado no sistema:**
P.plan=72%, P.font=68%, P.mkt=62% → P.plan > P.font > P.mkt, todos > 60% → **🎯 Edge Real**
**Interpretação:** O modelo histórico (planilha) enxerga algo que o mercado e até as fontes subestimam. É o sinal mais forte do sistema.
**Regra:** Quando Edge Real aparece, entrar independente da odd estar "baixa". O edge vem da divergência com o mercado, não da odd absoluta.

---

### Exemplo 22 — Bélgica × Senegal: contexto desconsiderado ⚠️
**Jogo:** Bélgica × Senegal (01/07/2026, R32)
**Situação:** Odds: BEL 43.6% / Draw 30.3% / SEN 26.1%. Yahoo analista preferia Senegal para avançar.
**Princípio 6:** Fontes externas contradiziam as odds (Senegal era "mais experiente e confiável"). P.fontes(Senegal) deveria ter sido ~35%, criando Sinal Externo.
**Regra:** Em jogos equilibrados onde analistas externos divergem das odds — e têm argumento sólido — P.fontes deve refletir essa divergência, não apenas replicar as odds.

---

### Exemplo 23 — Over/Under em último jogo de grupo com eliminado ❌
**Padrão descoberto:** Times que precisam de gol para classificar se lançam ao ataque.
- Bósnia 3-1 (dia 24), Marrocos 4-2 (dia 24), Brasil 3-0 (dia 24) = todos Under 2.5 falhou
- Paraguai 0-0 Austrália = Over 1.5 falhou (empate classificava os dois)
**Regra:** Última rodada de grupo com contexto de empate serve para ambos → Under + Empate. Times com necessidade de gol → Over + BTTS. Verificar SEMPRE qual cenário serve para cada time.

---

## NOTAS FINAIS

**O que nunca mudar:**
- Verificar odd real na Betano antes de confirmar entrada
- Princípio 6 como filtro obrigatório
- Piso 1.40 na Alta Certeza
- SKIP em dead rubbers
- Máximo 2 apostas por jogo

**O que reavaliar periodicamente:**
- Piso de 1.40 após ~30 novas bets do mata-mata
- Taxa de acerto por mercado (atualizar a cada 20 bets)
- Fatores de correlação das CAs (validar empiricamente)

**Fontes de pesquisa prioritárias:**
1. Yahoo Sports Betting — melhor análise quantitativa
2. CBS Sports — previsões detalhadas
3. DraftKings Network — foco em totais e props
4. FanDuel — odds de referência
5. Bleacher Report — contexto atualizado
