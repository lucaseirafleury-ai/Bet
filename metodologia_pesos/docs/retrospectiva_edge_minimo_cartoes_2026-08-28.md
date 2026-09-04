# Retrospectiva — edge mínimo pro Cartões+Árbitro (28/08/2026)

## Contexto

Lucas notou (durante a depuração do bug de linha do Goiás) que
Cartões+Árbitro é o único dos 3 critérios de produção sem edge mínimo
(`LIMIAR_EDGE_CARTOES = 0.0` — BTTS usa 5%, Over 2.5 usa 8%). A entrada
corrigida do Goiás ficou com edge de só 3,08%, bem mais fina que o
normal desses outros critérios, o que levantou a pergunta: será que
apostas de edge muito fino estão diluindo o resultado desse critério?

**Importante deixar claro antes dos números**: `LIMIAR_EDGE_CARTOES=0.0`
não foi um esquecimento — foi a configuração usada em TODA a validação
que deu o z=+2,01/ROI+9,4% documentado hoje (`docs/protocolo.md`).
Testar um piso agora é a mesma disciplina de sempre: nunca mudar
produção sem revalidar primeiro.

## Método

Reaproveitei o backtest de produção completo (mesma função que
`checar_decaimento._checagem_cartoes_arbitro` usa —
`rodar_retrospectiva` + `media_arbitro_walk_forward` +
`linha_mais_liquida`/`odd_media_na_linha` + `simular_aposta_linha`),
capturando o `edge` de cada aposta simulada (campo novo, adicionado em
`cartoes_arbitro.simular_aposta_linha` nesta mesma sessão — antes não
era exposto). n=386 (bate com o já documentado). Cortei por faixa de
edge e por corte mínimo, sempre checando ano a ano (2024/2025/2026) —
nunca aceitar um agregado sem ver os 3 anos.

## Resultado

**Por faixa** (não cumulativo):

| Edge | n | acerto | ROI | z |
|---|---|---|---|---|
| 0-2% | 43 | 53,5% | −3,5% | −0,25 |
| 2-5% | 56 | 58,9% | +9,3% | +0,75 |
| 5-10% | 76 | 52,6% | −2,1% | −0,20 |
| 10-20% | 122 | 64,8% | +18,0% | **+2,26** |
| 20%+ | 89 | 60,7% | +13,7% | +1,40 |

As apostas de edge abaixo de 10% (n=175, quase metade da amostra) são,
juntas, essencialmente ruído (ROI+1,2%, z=+0,17) — e o pior bloco
individual (5-10%) chega a ser NEGATIVO. As de edge 10%+ (n=211) são
consistentemente melhores.

**Por corte mínimo** (cumulativo, `edge >= corte`), testando pontos
redondos ao redor do platô:

| Corte | n | ROI | z | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| ≥3% | 319 | +9,6% | +1,87 | +32,1% | +4,6% | +11,8% |
| ≥5% | 287 | +11,3% | +2,10 | +32,1% | +7,0% | +12,4% |
| ≥8% | 237 | +13,6% | +2,31 | +34,7% | +10,0% | +13,4% |
| **≥10%** | **211** | **+16,2%** | **+2,62** | **+48,9%** | **+11,5%** | **+14,7%** |
| ≥12% | 180 | +12,0% | +1,76 | +45,3% | +7,8% | +9,8% |
| ≥15% | 146 | +9,3% | +1,22 | +41,7% | +0,9% | +11,0% |

**≥10% é o pico**: melhora sobre o baseline (z=+2,02→+2,62, ROI
+9,4%→+16,2%), amostra ainda saudável (n=211, mais da metade da
original), e **os 3 anos positivos** (2024 z=+2,73, 2025 z=+1,28, 2026
z=+1,56) — passa a mesma barra "sem ano negativo" usada pros outros
critérios. Cortes vizinhos (8%, 12%) também melhoram sobre o baseline
— não é um pico isolado por acaso, é um platô (3%→10% sobe de forma
consistente, depois de 10% degrada) — mas ≥10% é claramente o melhor
ponto testado.

## Limitações (mesma disciplina de sempre)

- **Risco de comparação múltipla**: testei 6 cortes redondos — bem
  menos que a busca extensa feita pro Over 2.5, mas ainda é uma busca
  na mesma amostra que gerou o critério original. Não é validação
  fora-da-amostra.
- **2024 é pequeno em toda faixa** (n=19-24) — o z alto de 2024 em
  quase todo corte testado é parcialmente amostra pequena, não só
  sinal forte. 2025/2026 (n maiores) são a leitura mais confiável.
- Cortar edge reduz o VOLUME de apostas (211 de 386, ~55%) — Lucas
  precisa decidir se topa menos entradas por resultado melhor.

## Recomendação

Corte de edge mínimo em **10%** pro Cartões+Árbitro é um candidato
real e defensável (mesma barra "sem ano negativo" dos outros
critérios, melhora clara sobre o baseline, não é um pico isolado). Não
apliquei a produção nesta rodada — decisão de adotar (ou não, ou testar
outro valor) é do Lucas, mesmo padrão de todo o projeto.
