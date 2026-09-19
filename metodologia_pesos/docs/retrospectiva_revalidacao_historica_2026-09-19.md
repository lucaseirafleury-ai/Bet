# Revalidação sobre o histórico profundo (2026-09-19)

Os 3 critérios em produção foram calibrados olhando **2024-2026**. Com o
add-on de Historical Data temos odds desde ~2018 — então **2018-2023 é
fora-da-amostra genuíno**: seis anos que nunca participaram de nenhuma
escolha de parâmetro, casa de aposta, limiar ou filtro.

Nenhum holdout ou reamostragem é tão forte quanto dado que o processo
nunca viu. Se o edge sobrevive aqui, é o argumento mais sólido que este
projeto pode ter; se some, o critério era ajuste ao período de calibração.

**Ressalva honesta**: mercado antigo era menos eficiente. Um edge maior em
2018-2020 pode refletir mercado mais frouxo, não superioridade do modelo —
por isso o ano a ano está completo abaixo, não só o agregado.

## BTTS

| Período | n | acerto | ROI | z |
|---|---|---|---|---|
| **Fora da amostra (2018-2023)** | 360 | 47% | -4.7% | -0.87 |
| Calibração (2024-2026) | 221 | 61% | +22.0% | +3.33 |
| Tudo | 581 | 52% | +5.5% | +1.30 |

Ano a ano:

| Ano | n | acerto | ROI | z |
|---|---|---|---|---|
| 2017 · | 45 | 36% | -30.6% | -2.16 |
| 2018 · | 7 | 29% | -40.7% | -1.06 |
| 2019 · | 65 | 42% | -12.7% | -0.97 |
| 2020 · | 41 | 59% | +21.7% | +1.32 |
| 2021 · | 67 | 48% | -3.9% | -0.31 |
| 2022 · | 48 | 52% | +7.6% | +0.50 |
| 2023 · | 87 | 49% | -2.3% | -0.22 |
| 2024 | 81 | 63% | +27.7% | +2.51 |
| 2025 | 77 | 51% | +3.2% | +0.27 |
| 2026 | 63 | 71% | +37.7% | +3.37 |

`·` = fora da amostra

## Over 2.5

| Período | n | acerto | ROI | z |
|---|---|---|---|---|
| **Fora da amostra (2018-2023)** | 84 | 48% | -1.3% | -0.11 |
| Calibração (2024-2026) | 86 | 59% | +24.8% | +2.19 |
| Tudo | 170 | 54% | +11.9% | +1.47 |

Ano a ano:

| Ano | n | acerto | ROI | z |
|---|---|---|---|---|
| 2019 · | 16 | 56% | +9.5% | +0.38 |
| 2020 · | 13 | 46% | +1.1% | +0.03 |
| 2021 · | 9 | 44% | -4.7% | -0.12 |
| 2022 · | 2 | 50% | +1.0% | +0.01 |
| 2023 · | 44 | 45% | -5.3% | -0.34 |
| 2024 | 25 | 64% | +36.6% | +1.74 |
| 2025 | 33 | 52% | +8.9% | +0.47 |
| 2026 | 28 | 64% | +32.9% | +1.71 |

`·` = fora da amostra

## Cartões+Árbitro

| Período | n | acerto | ROI | z |
|---|---|---|---|---|
| **Fora da amostra (2018-2023)** | 0 | — | — | — |
| Calibração (2024-2026) | 439 | 57% | +5.4% | +1.22 |
| Tudo | 439 | 57% | +5.4% | +1.22 |

Ano a ano:

| Ano | n | acerto | ROI | z |
|---|---|---|---|---|
| 2024 | 155 | 57% | +4.7% | +0.63 |
| 2025 | 158 | 57% | +5.4% | +0.73 |
| 2026 | 126 | 58% | +6.2% | +0.77 |

`·` = fora da amostra


---

## Veredito

O padrão é o mesmo nos dois critérios de gols: **edge forte no período de
calibração, ausente fora dele**. BTTS rende +22,0% em 2024-2026 e −4,7%
nos sete anos anteriores (n=360, amostra sólida — não é ruído). Over 2.5
repete: +24,8% dentro, −1,3% fora.

### Explicações alternativas testadas e descartadas

| Hipótese | Teste | Resultado |
|---|---|---|
| Odds antigas são de fechamento (mais afiadas) | Margem do book por ano | Estável: 1x2 5,5-6,8%, BTTS 6,8-7,3%. Antigas têm margem **maior** — mercado mais frouxo, mais fácil de bater |
| Dado de entrada pior nas temporadas antigas | Cobertura de estatística por ano | Antigas são **mais limpas** (0% faltando) que as recentes (1-3%) |
| Amostra pequena fora da amostra | n | BTTS n=360 em 7 anos |
| Mercado ficou mais eficiente com o tempo | Direção do efeito | Preveria edge **maior** no passado; observamos o oposto |

Nenhuma sobrevive. O que resta é a explicação mais simples: **o edge medido
em 2024-2026 é artefato de seleção**. Os parâmetros foram escolhidos
varrendo dezenas de configurações nesse mesmo período — exatamente o
processo que produz z alto sem edge real.

Vale lembrar que o mercado mais frouxo do passado torna o resultado pior,
não melhor: um edge genuíno deveria aparecer com mais folga em 2017-2021,
não sumir.

### Cartões+Árbitro

Não é testável fora da amostra: odds de cartões na Série B só existem de
2024 em diante. Mas há um sinal independente na mesma direção — com o
histórico de árbitro mais profundo (média sobre 4.462 jogos em vez de
1.040), o ROI no MESMO período 2024-2026 caiu de **+15,1% (z=+2,47) para
+5,4% (z=+1,22)**. O número anterior era inflado por médias de árbitro
estimadas com amostra fina.

### O que isso significa na prática

Os 3 critérios em produção não têm, hoje, evidência de edge que sobreviva
a dado que o processo de escolha nunca viu. O ledger real (11 green / 3
red) é n=14 — pequeno demais para distinguir sorte de vantagem, e ainda
por cima dentro do mesmo período de calibração.

### Caminho construtivo

Agora existe dado para fazer certo o que antes era impossível: calibrar em
2017-2022 e validar em 2023-2026, com o processo de escolha cego ao
período de validação. Um critério que passe nesse desenho vale muito mais
que os três atuais juntos.
