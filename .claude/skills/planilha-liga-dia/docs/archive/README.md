# Archive

`converte_sumproduct.py` — utilitário avulso usado em 16/07 para converter,
já com a planilha pronta, as fórmulas antigas de Gols/Cartões/Escanteios/
Chutes Pró-Contra (LET+FILTER+SEQUENCE+STDEV.S, que quebravam no Excel
mobile) para SUMPRODUCT clássico.

Superado pelo modelo v2 embutido em `aplicar_formula_pro_contra()`
(`scripts/planilha_lib.py`), que já gera direto as fórmulas SUMPRODUCT
(média e desvio-padrão ponderados, corte unilateral/bilateral parametrizado
via `Parâmetros!B10/B11`) — não há mais fórmula LET/FILTER/SEQUENCE/STDEV.S
para converter. Mantido só como referência histórica de como o problema foi
diagnosticado; não faz parte do fluxo da skill.
