# Arquivo das 3 ligas nórdicas (Allsvenskan, Superettan, 1. Division)

## Por que isto existe

Os dados brutos de cada liga (`dados/.checkpoint_<id>.json`) são
`gitignored` de propósito — são cache/checkpoint reconstruível a partir da
API da Sportmonks, e ficam grandes demais pra versionar rotineiramente.

Mas em 16/09/2026 o usuário decidiu **cancelar a assinatura Sportmonks das
3 ligas nórdicas** (Allsvenskan/573, Superettan/579, 1. Division/447) pra
liberar os 3 slots do plano e testar outras ligas. Cancelar a assinatura
não é o problema — os dados JÁ BUSCADOS continuam bons; o problema é que
sem a assinatura **não dá mais pra rebuscar** se o container for reciclado
e o cache local (gitignored, nunca sincronizado) se perder. Isso quase
aconteceu de verdade nesta mesma sessão: um teste mal isolado sobrescreveu
`.checkpoint_573.json` com dado fake, e só foi recuperável porque a
assinatura ainda estava ativa pra rebuscar.

Por isso este arquivo é congelado aqui, **comprimido e commitado no git**
(portanto no GitHub, fora do container) — o único lugar realmente durável
que este projeto tem. Sem assinatura ativa, isto deixa de ser
"recuperável a qualquer momento" e passa a ser **a única cópia que existe**.

## Por que essas 3 ligas importam mesmo sem assinatura ativa

As regras brasileiras (Série A/B) usam tripla confirmação: uma condição só
vira regra publicada se sobreviver a TRÊS processos de descoberta
independentes —

1. **herdado**: descoberta na Allsvenskan → confirmada em Série A/B (é
   isto que depende dos dados deste arquivo)
2. nativo A→B: descoberta na Série A → confirmada na Série B
3. nativo B→A: descoberta na Série B → confirmada na Série A

Medido por backtest de odds reais (3.876 jogos): confirmação=1 origem deu
ROI −12,3%, =2 origens −8,1%, só =3 origens deu positivo (+5,6%). Ou seja,
a via "herdado" — a que precisa destes dados nórdicos — é o que sustenta o
piso de 3 confirmações. Sem ela, o piso vira 2, e o histórico mostra que
2 origens não é suficiente pra ter edge real.

Analisado em 16/09/2026: das 810 famílias de condições brasileiras
candidatas, 173 têm as três origens (viram as 80 regras publicadas hoje);
outras 227 têm só as duas nativas. Perder a via herdada não mata a tripla
confirmação: as 173 famílias de hoje já têm as duas nativas também, então
sobreviveriam. O que se perde é a capacidade de **gerar novas** famílias
com tripla confirmação daqui pra frente — a via herdada para de produzir
candidatos novos assim que os dados aqui pararem de ser atualizados.

## O que tem aqui

Estado capturado em 16/09/2026, rótulos na versão 2 (fonte `statistics`,
não `trends` — ver commit `dd73fab` na branch de trabalho, correção do
desalinhamento treino-vs-apuração).

| arquivo | liga | jogos | com resultado | snapshots |
|---|---|---|---|---|
| `checkpoint_573_allsvenskan.json.gz` | Allsvenskan (573) | 720 | 644 | 3.864 |
| `checkpoint_579_superettan.json.gz` | Superettan (579) | 720 | 665 | 3.990 |
| `checkpoint_447_1_divisao.json.gz` | 1. Division (447) | 728 | 656 | 3.936 |

Checksums SHA-256 do JSON **descomprimido** (conferir depois de restaurar,
ver `restaurar.py`):

```
2be2dd3f33bd143eab3aee492ce9946bb3568abe5cf1ffe27ed4ccc512316e8f  checkpoint_573.json
ff48d7dc71bab0d01786990812a923864d5fcc814908cd8527c67a20cce409e7  checkpoint_579.json
521209388e9067d986aed433151723d24c56aea138da0c45e655680aaecad19c  checkpoint_447.json
```

## Como restaurar

```bash
cd pesquisa_gols
python3 dados/arquivo_nordicas/restaurar.py
```

Descomprime os 3 arquivos de volta pra `dados/.checkpoint_<id>.json`,
confere o checksum de cada um contra a tabela acima, e recusa sobrescrever
sem `--forcar` se já existir um checkpoint ali (pra nunca perder um estado
mais recente por engano).

## O que fazer se cancelar a assinatura de verdade

Este arquivo continua permitindo:
- Rodar `gerar_regras_sinais.py` (a via "herdado" volta a funcionar a
  partir do estado congelado aqui, mesmo sem API).
- Auditar/reproduzir os números da tripla confirmação.

Este arquivo NÃO permite:
- Descobrir novas condições nórdicas depois de 16/09/2026 (os dados não
  se atualizam mais sem assinatura).
- Confirmar candidatos brasileiros novos contra jogos nórdicos futuros.

Se mais tarde a assinatura for reativada (mesma liga ou outra 3ª via
independente do Brasil), `buscar_multiliga.py` detecta e rebusca sozinho
— não precisa mexer neste arquivo.
