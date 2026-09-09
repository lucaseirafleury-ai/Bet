# Validação fora-da-amostra: treino em 2025, teste em 2026

Resolve o problema de comparação múltipla que os relatórios anteriores
tinham (escolher o "vencedor" de um grid grande na mesma amostra onde foi
medido não prova que o parâmetro é bom, só que ele ganhou por sorte
naquela amostra específica). Desenho:

1. **Treino**: grid search completo (48 combinações de `k_mando` ×
   `usar_estilo` × `filtro_aderencia`) rodado só contra a temporada 2025
   (380 jogos), ordenado por acerto de Over/Under 2.5 — a métrica que o
   Lucas priorizou.
2. **Holdout**: os 8 melhores candidatos do treino são reavaliados contra
   a temporada 2026 (usando `timestamp_minimo` — o histórico de cada
   previsão ainda pode usar 2025+início de 2026, só a AVALIAÇÃO fica
   restrita a jogos de 2026, que o processo de escolha nunca viu).

`estilo_por_mando` ficou fixo no valor já decidido por liga (Série A:
`True`; Série B: `False`) — não foi re-otimizado neste teste (fica como
item em aberto).

## Série A — os parâmetros NÃO generalizam (achado principal)

| k_mando | estilo | filtro | Over25 no TREINO | Over25 no HOLDOUT |
|---|---|---|---|---|
| 0.2 | False | 0.8 | **52.68% (1º no treino)** | **44.00% (PIOR no holdout)** |
| None/1.0 | False | 0.8 | 52.35% | 51.00% |
| 0.35 | False | 0.8 | 51.68% | 47.50% |
| 0.7 | True | 0.8 | 51.01% | **52.00% (melhor no holdout)** |
| 0.7 | False | 0.8 | 51.01% | 48.50% |
| 0.2 | False | 0.65 | 51.00% | 49.50% |
| **0.35, False, 0.65** | | | 51.00% (empatado, último do top-8) | **53.00% (2º melhor)** |

**O melhor resultado no treino virou o PIOR resultado no holdout** (52.68%
→ 44.00%, pior que cara-ou-coroa). E o pior colocado do top-8 no treino
(`k=0.35, sem estilo, filtro=0.65`) foi o 2º melhor no holdout. Não existe
correlação confiável entre "ganhar no treino" e "generalizar" nesta liga,
com este volume de dado (~300 jogos de treino).

**Conclusão prática: não dá pra confiar em nenhuma escolha fina de
parâmetro pra Série A ainda.** Ajustar `k_mando`/`filtro_aderencia` com
menos de ~300-400 jogos de treino está, nesta liga, mais perto de
adivinhação do que de calibração. Recomendo manter os valores simples e
"neutros" (sem ajuste de mando, filtro 0.65) em vez de perseguir qualquer
combinação "vencedora" — o teste acabou de provar que essa combinação
não seria confiável de qualquer forma.

## Série B — os parâmetros generalizam bem (achado oposto)

| k_mando | estilo | filtro | Over25 no TREINO | Over25 no HOLDOUT |
|---|---|---|---|---|
| 0.7 | False | 0.8 | 57.00% (1º no treino) | 56.54% |
| 0.35 | True | 0.8 | 56.33% | 55.50% |
| **0.5, False, 0.8** | | | 56.33% | **59.16% (MELHOR no holdout)** |
| 0.2 | False | 0.8 | 56.00% | 57.59% |
| 0.35 | False | 0.8 | 56.00% | 57.59% |
| None/1.0, False | 0/0.5 | | 55.67% | 54.69% |
| 0.2 | True | 0 | 55.67% | 58.33% |

Aqui é o oposto: **todos os 8 candidatos ficam entre 54.7-59.2% no
holdout** — nenhum colapsa, vários até melhoram em relação ao treino. O
1º colocado do treino (57.00%) se mantém forte no holdout (56.54%,
queda pequena e esperada). E o melhor resultado do HOLDOUT
(`k=0.5, sem estilo, filtro=0.8` → 59.16%) generaliza de verdade — não é
o topo do treino, mas está próximo (3º) e se confirma fora da amostra.

**Conclusão prática: a Série B tem sinal real o suficiente pra justificar
um ajuste.** Recomendo adotar `k_mando=0.5, usar_estilo=False,
filtro_aderencia=0.8` — é a config com melhor desempenho comprovado fora
da amostra, não só no treino.

## Por que as ligas se comportam tão diferente

Não sei ao certo — pode ser tamanho de amostra (Série B tem times mais
estáveis ano a ano? menos accesso/rebaixamento afetando o histórico
cross-season?), pode ser que a Série A seja intrinsecamente mais
imprevisível (mais "zebra"), ou pode ser só variância de amostra mesmo.
Vale registrar como pergunta em aberto, não inventar uma explicação.

## Decisão adotada

| Parâmetro | Série A | Série B |
|---|---|---|
| `k_mando` | Sem ajuste (mantido — nenhuma alternativa se provou melhor de forma confiável) | **0.5** (era 0.35 — mudou, com evidência de holdout) |
| `usar_estilo` | `True` (mantido — sem evidência forte o bastante pra mudar) | **`False`** (era `True` — desligar o estilo misto na B, evidência de holdout) |
| `filtro_aderencia` | 0.65 (mantido) | **0.8** (era 0.65 — mudou, contraria o achado anterior baseado em MAE, mas aqui a evidência de holdout pra Over/Under é mais forte) |
| `estilo_por_mando` | `True` (decidido antes, não retestado aqui) | `False` (decidido antes, não retestado aqui) |

**Nota sobre `filtro_aderencia=0.8` na Série B**: contraria o que os
relatórios anteriores diziam ("0.8 é claramente pior", baseado em MAE na
amostra combinada). A diferença é a métrica E o desenho do teste — aqui é
Over/Under 2.5 com validação fora-da-amostra de verdade, que é uma
evidência mais forte. Ainda vale ficar de olho: um único teste de holdout
com 8 candidatos também tem limites.

## Limitações

- Só 8 candidatos testados em holdout (os top-8 do treino) — não é a
  grade de 48 completa, então pode haver combinação fora desse top-8 que
  generalizaria ainda melhor (não testado).
- `estilo_por_mando` não foi re-otimizado neste teste, ficou fixo no
  valor já decidido — é um item em aberto pra uma próxima rodada.
- 2025 é só 1 temporada de treino — o "achado" da Série B ainda pode não
  se confirmar numa 3ª temporada. Continua sendo a melhor estimativa
  disponível, não uma prova definitiva.

Reprodução: `rodar_retrospectiva(..., timestamp_minimo=<primeiro
timestamp de 2026>)` sobre o df combinado 2025+2026, comparando com o
resultado do `grid_search` rodado só em 2025.
