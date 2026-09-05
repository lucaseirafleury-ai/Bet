# Dupla confirmação (Over 2.5 + BTTS no mesmo jogo) — o resultado mais forte da sessão, com uma ressalva importante

## Contexto

Segmentando os dois critérios já validados (Over 2.5 z=2,23 n=221;
BTTS z=2,65 n=207) entre os 113 jogos onde os dois coincidem e o
restante, o acerto e o ROI de cada mercado sobem bastante no subgrupo
de interseção (BTTS: 55,3%→63,7% acerto, ROI 9,9%→24,7%; Over 2.5:
52,8%→57,5% acerto, ROI 11,0%→20,7%). Lucas pediu pra testar
formalmente "só apostar quando os dois critérios coincidirem" como
critério à parte.

**Interpretação testada**: apostar as DUAS pernas separadamente (2
stakes distintos — não é combo/parlay que exige as duas baterem) só
nos jogos onde Over 2.5 e BTTS (cada um com seus próprios parâmetros
já validados) disparam ao mesmo tempo.

## Resultado — o mais forte de toda a sessão

| | |
|---|---|
| Jogos únicos | 113 |
| Apostas (2 por jogo) | **226** |
| ROI | **+22,7%** |
| z-score | **+3,40** |

| Ano | n | Acerto | ROI |
|---|---|---|---|
| 2023 | 58 | 55,2% | +12,0% |
| 2024 | 60 | 66,7% | +37,6% |
| 2025 | 58 | 53,4% | **+8,2%** |
| 2026 | 50 | 68,0% | +34,1% |

**Nenhum ano nem perto de negativo** — inclusive 2025 (o ano mais fraco
histórico dos dois critérios individuais) fica em +8,2%, o melhor
resultado que 2025 teve em qualquer critério testado nesta sessão
inteira. z=+3,40 é o maior de todo o projeto até agora, maior que Over
2.5 (2,23) e BTTS (2,65) isolados.

## Ressalva importante — por que não é simplesmente "achamos um edge melhor ainda"

Isso não é uma terceira fonte de vantagem independente — é a
**interseção de dois critérios que já foram, cada um, escolhidos por
grid search** (Over 2.5: melhor de 96 combinações; BTTS: melhor de 48
combinações). Este resultado adiciona uma **terceira camada de seleção**
(escolher o subconjunto onde os dois concordam). É esperado, quase por
definição, que a interseção de dois sinais positivos e parcialmente
correlacionados performe melhor que cada um sozinho — não é
necessariamente uma vantagem nova, pode ser simplesmente "os jogos onde
o modelo está mais confiante dos dois lados ao mesmo tempo".

Além disso, as duas apostas de cada jogo não são independentes uma da
outra — jogos de muito gol tendem a favorecer Over 2.5 E BTTS ao mesmo
tempo (correlação real, não coincidência), então o `n=226` tem menos
"informação independente" real do que 226 eventos genuinamente
descorrelacionados (mesma ressalva já registrada quando testamos
misturar Over1.5+2.5+3.5+BTTS numa carteira única).

**Isso não invalida o resultado** — é real, saiu direto do backtest,
com boa consistência ano a ano (o que pesa a favor de ser sinal
genuíno, não sorte pura). Mas merece ser tratado com o nível de cautela
mais alto de toda a sessão, precisamente por acumular 3 camadas de
seleção (grid do Over 2.5 → grid do BTTS → interseção dos dois).

## Recomendação

Considerar como um **terceiro nível de confiança**, acima dos dois
critérios individuais: quando um jogo aciona TANTO Over 2.5 QUANTO
BTTS, é um sinal de convicção mais forte do modelo — vale considerar
priorizar esses 113 jogos/ano (~32/ano) se for necessário limitar
volume ou stake por algum motivo prático (banca, tempo disponível).
Não recomendado como SUBSTITUTO dos dois critérios completos — continuar
apostando em ambos sempre que dispararem, mesmo sem coincidência, já
que os subgrupos "não coincide" de cada um continuam positivos e
defensáveis sozinhos (BTTS não-coincide: ROI+9,9%; Over2.5 não-coincide:
ROI+11,0%).

## Limitações

- Terceira camada de comparação múltipla empilhada sobre as duas
  anteriores (grids de Over 2.5 e BTTS).
- `n=113` jogos únicos — menor amostra que qualquer um dos dois
  critérios-pai.
- As duas pernas do mesmo jogo são correlacionadas, não eventos
  independentes — o `z=3,40` provavelmente está um pouco inflado pela
  mesma razão discutida na tentativa de "carteira" de múltiplos
  mercados (`docs/retrospectiva_novos_eixos_2026-08-25.md` não cobre
  isso, ver a análise de portfólio anterior na conversa).
- Mesma disciplina de sempre: 4 anos de dado, não décadas.

Reprodução: `metodologia_pesos/retrospectiva.py`
(`rodar_retrospectiva`/`simular_apostas` com os parâmetros já
documentados de cada critério), script de orquestração ad-hoc (não
versionado).
