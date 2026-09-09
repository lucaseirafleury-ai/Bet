# Under com odd aproximada — resultado é viés da fórmula, não edge real

## Contexto

O CSV da FootyStats só traz odd real do lado **Over** pras linhas de
gols (`odds_ft_over15/25/35/45`) — nenhuma coluna de odd de Under.
Lucas pediu pra construir uma odd aproximada de Under a partir da odd
de Over, pra poder testar esse lado do mercado.

Implementado em `pesos.odd_e_prob_under_aproximada(odd_over)`: pega o
complemento bruto da probabilidade implícita do Over
(`1 - 1/odd_over`), sem remover a margem da casa dos dois lados (não
temos a odd real de Under pra normalizar de verdade, como fazemos com
BTTS via `probabilidade_implicita_2vias`). **Isso já era esperado, e
foi documentado na própria função antes de rodar qualquer teste, pra
ficar otimista** — a margem inteira "sobra" pro lado Over calculado,
nenhuma é descontada do lado Under.

Testado nos 4 mercados (Under 1.5/2.5/3.5/4.5), 3 limiares de edge (0%,
5%, 8%), nas duas ligas, período completo 2023-2026, mesmos parâmetros
do combo campeão de Over 2.5.

## Resultado — positivo em TODAS as 24 combinações testadas

| Liga | Mercado | edge=0% | edge=5% | edge=8% |
|---|---|---|---|---|
| Série A | Under 1.5 | n=935, ROI+6,0%, z=1,05 | n=808, +6,6%, z=1,07 | n=711, +10,1%, z=1,52 |
| Série A | Under 2.5 | n=911, +3,9%, z=1,22 | n=790, +0,7%, z=0,20 | n=709, +3,0%, z=0,83 |
| Série A | Under 3.5 | n=922, +14,0%, z=2,45 | n=793, +14,3%, z=2,17 | n=673, +15,6%, z=2,03 |
| Série A | Under 4.5 | n=959, +10,1%, z=1,90 | n=736, +11,8%, z=1,71 | n=472, +15,9%, z=1,49 |
| Série B | Under 1.5 | n=962, +13,3%, z=2,67 | n=835, +14,7%, z=2,75 | n=759, +13,6%, z=2,44 |
| Série B | Under 2.5 | n=941, +6,6%, z=2,40 | n=832, +7,3%, z=2,50 | n=765, +6,9%, z=2,28 |
| Série B | Under 3.5 | n=952, +6,8%, z=4,35 | n=813, +7,1%, z=4,24 | n=694, +7,9%, z=4,40 |
| Série B | Under 4.5 | n=1000, +5,4%, z=6,18 | n=767, +5,7%, z=5,81 | n=441, +5,3%, z=3,83 |

**24 de 24 combinações deram ROI positivo.** Isso NUNCA aconteceu em
nenhum teste anterior desta sessão (nem no melhor achado, o combo de
Over 2.5, que só é positivo naquele mercado específico). Alguns
z-scores (Série B Under 3.5/4.5: z=4,4 e z=6,2) são ordens de grandeza
maiores que qualquer resultado já visto no projeto — inclusive maiores
que o que seria razoável esperar de qualquer edge real contra um
mercado líquido como Over/Under gols do Brasileirão.

## Por que isso é viés da aproximação, não descoberta

Um z-score alto normalmente indica que um resultado é consistente
demais pra ser sorte. Mas essa lógica assume que a fonte de "erro"
entre o modelo e o mercado é ruído aleatório em torno de uma edge real.
Aqui não é isso: **a odd de Under usada não é uma odd de mercado — é
uma fórmula determinística aplicada à odd de Over, com viés
sistemático conhecido e documentado ANTES do teste rodar** (a odd sai
sempre um pouco alta demais, nunca baixa demais). Um viés sistemático
constante gera exatamente esse padrão: ROI sempre positivo, variância
pequena (porque o viés é quase fixo, não aleatório), logo z-score
inflado — sem nenhuma relação com vantagem real de aposta. O z-score
alto aqui mede a CONSISTÊNCIA DO VIÉS DA FÓRMULA, não uma vantagem
genuína contra casas de aposta reais.

Reforça isso: nenhuma casa de aposta real deixaria uma ineficiência de
+5% a +16% de ROI aberta simultaneamente em TODAS as linhas de
Over/Under gols, nas duas ligas, por 4 anos seguidos — mercado de gols
é um dos mais líquidos e arbitrados que existe. Se fosse edge real,
teria sido arbitrada há muito tempo.

## Recomendação — não usar para apostar

- **Não adotar nenhum critério de Under como critério de aposta.** Os
  números acima não representam vantagem real — são o artefato
  esperado da aproximação.
- Continua valendo o critério de Over 2.5 já documentado
  (`docs/retrospectiva_grid_completo_2026-08-25.md`), que usa odd REAL
  de mercado, não aproximada.
- **Para testar Under de verdade**, é necessário conseguir uma fonte de
  dado com a odd REAL do lado Under (não existe no CSV atual da
  FootyStats) — sem isso, qualquer "resultado" desse lado do mercado
  deve ser tratado como não confiável, por mais atraente que o número
  pareça.

## O que fica no código

A função `pesos.odd_e_prob_under_aproximada` e os mercados
`under15/25/35/45` em `retrospectiva._MERCADOS_SIMULAVEIS` continuam
disponíveis no motor (com a ressalva de viés documentada na docstring)
— úteis como ferramenta de exploração/diagnóstico, não como fonte de
critério de aposta.

Reprodução: `metodologia_pesos/retrospectiva.py`
(`rodar_retrospectiva`/`simular_apostas`, mercados `under15/25/35/45`),
script de orquestração ad-hoc (não versionado).
