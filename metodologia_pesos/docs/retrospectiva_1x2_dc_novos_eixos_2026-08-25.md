# 1x2/DC com n_historico + filtros separados — confirma que não há nada de novo

## Contexto

Depois do grid completo em 1x2/DC não achar nada de defensável (Série A
sem sinal; Série B "casa" com z alto mas deteriorando ano a ano —
`docs/retrospectiva_1x2_dc_2026-08-25.md`), Lucas perguntou se já
tínhamos testado variar `n_historico` e separar
`filtro_estilo`/`filtro_favoritismo` nesses mercados, do jeito que fez
diferença real no BTTS. Resposta: não tínhamos testado — fizemos agora.

Grid: `n_historico ∈ {10,15,20} × filtro_estilo ∈ {0,0.5,0.65,0.8} ×
filtro_favoritismo ∈ {0,0.5,0.65,0.8}` (48 combinações), aplicado a
`casa`/`mandante_dc` na Série B (onde tinha aparecido sinal) e aos 5
mercados na Série A (por completude). Rodado em paralelo (4 processos,
usando os 4 núcleos do ambiente) pra acelerar — mesma disciplina de
sempre, com checagem ano a ano obrigatória em qualquer candidato com
z alto.

## Resultado — confirma a decisão anterior, não muda nada

**Série B "casa"**: o melhor candidato do grid novo (`n_hist=15,
filtro_estilo=0.8, filtro_favoritismo=0/0.5, edge=0%`) dá z=+2,78
(ligeiramente melhor que o z=+2,71 anterior) — **mas com o MESMO padrão
de deterioração**: 2023 +37,8%, 2024 +33,5%, 2025 +5,2%, 2026 **−8,9%**.
Testando TODA a vizinhança de `n_historico`/filtros, o padrão se repete
de forma idêntica em praticamente todos os candidatos do topo — a
tendência de queda não é sensível a nenhum desses parâmetros. Isso
confirma que o problema é genuinamente temporal (mercado arbitrado ou
regime mudou), não uma questão de calibração fina que os novos eixos
pudessem destravar.

**Série B "mandante_dc"**: nenhum candidato passa de z=+0,09 (ruído) —
pior ainda que "casa" sozinho (esperado, já que empate dilui o sinal).

**Série A (todos os 5 mercados)**: nenhuma combinação de
`n_historico`/filtros produz sinal positivo defensável.
`visitante_dc`/`fora` continuam negativos (visitante_dc chega a
z=−2,36/−2,47 — desvantagem estatisticamente relevante, não uma
oportunidade, já que não temos como "apostar contra" um mercado nesta
infraestrutura). `empate`/`mandante_dc`/`casa` seguem em torno de zero
ou levemente negativos.

## Recomendação — nenhuma mudança

**Mantém a decisão anterior: não usar nenhum mercado de 1x2/Dupla
Chance de lado fixo pra apostar**, nas duas ligas. Os dois eixos novos
(janela de histórico, filtros separados) que tinham revelado um
candidato genuinamente melhor no BTTS não têm o mesmo efeito aqui —
faz sentido, porque o problema de 1x2/DC não era de calibração (que
esses eixos poderiam corrigir), era de tendência temporal (que nenhum
parâmetro de corte de amostra consegue reverter).

Continuam valendo só os dois critérios já validados: Over 2.5 e BTTS
na Série A.

## Limitações

- Mesma ressalva de sempre: 4 anos de dado.
- Não testamos combinar 1x2/DC com `k_mando`/`usar_estilo` fora dos
  valores-base escolhidos (`k=0.5` pras duas ligas) — improvável mudar
  o quadro dado que o problema é temporal, não foi testado por
  completude máxima.

Reprodução: `metodologia_pesos/retrospectiva.py`
(`_probabilidades_1x2_e_dc`, mercados `casa/empate/fora/mandante_dc/visitante_dc`),
scripts de orquestração ad-hoc paralelos (não versionados).
