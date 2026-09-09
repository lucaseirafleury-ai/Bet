# Teste de ablação — o estilo de jogo está ajudando o modelo?

Pergunta do Lucas: as retrospectivas de mando (Série A/B, 24/08/2026)
sempre rodaram com o filtro/peso de aderência de estilo ativo (≥65% nos
dois). Este teste isola a contribuição do estilo, comparando
`usar_estilo=True` (padrão) vs `usar_estilo=False` (força
`aderência_estilo=1.0` em todo jogo histórico — `peso_final` vira só
`aderência_favoritismo × peso_recência`), variando também o limiar do
filtro (`filtro_aderencia` = 0, 0.5, 0.65, 0.8).

**Desenho do teste**: as duas condições usam EXATAMENTE o mesmo conjunto
de jogos avaliados e o mesmo histórico disponível (o cálculo de estilo
roda dos dois jeitos, só o resultado é ignorado quando `usar_estilo=False`)
— isola só o efeito do peso/filtro, não a disponibilidade de dado.
`k_mando` fixo no valor já validado por liga (Série A: nenhum ajuste;
Série B: 0.35). Mesmo escopo das retrospectivas anteriores: só mercado de
gols.

## Resultado — diferença (SEM estilo − COM estilo), pareado por filtro

| Filtro | Série A: ΔMAE | Série A: ΔOver2.5 | Série A: ΔBTTS | Série B: ΔMAE | Série B: ΔOver2.5 | Série B: ΔBTTS |
|---|---|---|---|---|---|---|
| 0 (sem filtro) | −0.0006 | 0.000 | −0.006 | −0.0022 | 0.000 | 0.000 |
| 0.5 | −0.0006 | 0.000 | −0.006 | −0.0022 | 0.000 | 0.000 |
| **0.65 (atual)** | **+0.0016** | **+0.006** | **−0.006** | **−0.0012** | **0.000** | **0.000** |
| 0.8 (estrito) | **−0.0288** | **+0.065** | +0.013 | −0.0046 | 0.000 | +0.006 |

(Δ negativo em MAE ou positivo em Over/BTTS = tirar o estilo melhorou;
valores próximos de zero = estilo é indiferente nessa configuração.)

## Conclusão

**No filtro atual (65%), o estilo é essencialmente indiferente** — as
diferenças com/sem estilo são da ordem de 0.001-0.002 de MAE e 0-0.6
pontos percentuais de acerto, dentro do ruído de uma amostra de ~155
jogos. Isso vale nas duas ligas.

**Em filtro mais estrito (80%), o estilo ATRAPALHA** — principalmente na
Série A (MAE piora 0.029, acerto de Over/Under 2.5 cai 6.5pp quando o
filtro de estilo real está ativo). Faz sentido: em 80% de exigência,
sobra pouco histórico válido por jogo, e esse histórico fica mais sujeito
a ruído do que a um filtro mais frouxo.

**Interpretação**: não é evidência de que "estilo nunca importa" — é
evidência de que **os proxies atuais de estilo** (`estilo.py`, calculados
dos últimos 5 jogos) não estão discriminando qualidade de adversário de um
jeito que ajude a prever gols, pelo menos nesta amostra. Isso é consistente
com a ressalva já documentada em `estilo.py`/`protocolo.md`: só 2 das 5
dimensões (Posse, Bloco Baixo) têm dado direto no CSV; as outras 3
(Pressão Alta, Transição, Bola Parada) são proxies mais fracos — pode ser
que o ruído deles esteja anulando o sinal das 2 dimensões boas.

## Recomendação (preliminar)

- **Manter `filtro_aderencia=0.65`** — não há motivo pra trocar (a
  diferença entre 0/0.5/0.65 é desprezível), mas também não há evidência
  de que 65% seja "o número certo" — só que não atrapalha.
- **Não usar `filtro_aderencia=0.8`** — piora mensuravelmente na Série A.
- **Não desligar o estilo** (risco maior que benefício comprovado: nos
  filtros usuais ele é neutro, não prejudicial) — mas também não tratar
  como um pilar comprovado do modelo. É candidato a revisão se/quando os
  proxies de Pressão Alta/Transição/Bola Parada forem melhorados (dado
  mais rico) ou se o filtro/peso for reformulado.
- Vale reavaliar esse teste quando a retrospectiva cobrir outros mercados
  (cartões, escanteios) — é possível que o estilo importe mais em
  mercados onde ele foi originalmente pensado (ex.: escanteios, que o
  protocolo já liga a "Princípio 5" de estilo/números).

## Limitações

Mesmas das retrospectivas anteriores: amostra de temporada parcial (~155
jogos por liga, rodada 24/38), só mercado de gols, proxies de estilo
documentados como mais fracos em 3 das 5 dimensões.

Reprodução: `metodologia_pesos/retrospectiva.py`, `grid_search()` com
`grade = dict(k_mando=[<valor validado da liga>], usar_estilo=[True, False], filtro_aderencia=[0, 0.5, 0.65, 0.8])`.
