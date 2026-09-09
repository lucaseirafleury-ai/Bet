"""Script pareado do xlwings para o botão "Run main" do Excel.

Convenção do xlwings: este arquivo precisa ter o MESMO NOME (sem
extensão) e ficar na MESMA PASTA que `SerieA_testes_visuais.xlsx`. Ao
clicar em "Run main" na aba xlwings do Excel, o Excel roda
`python SerieA_testes_visuais.py`, que conecta na planilha aberta
(`xw.Book.caller()`), lê os parâmetros da aba Parâmetros, recalcula o
modelo (mesmo motor de `retrospectiva.py`) e reescreve o arquivo inteiro
— sem precisar fechar o Excel manualmente nem rodar nada no terminal.

Setup (uma vez só) — ver `docs/planilha_botao_recalcular.md` pro passo a
passo completo:
    pip install xlwings pandas openpyxl
    xlwings addin install

Por que fecha e reabre o arquivo (em vez de só atualizar células): a aba
Jogos é reconstruída do zero a cada recálculo (o número de jogos pode
mudar dependendo dos parâmetros, ex. `n_historico`) — reaproveita 100%
da lógica já testada de `gerar_planilha_testes.py` (mesmas funções que
o gerador de linha de comando usa), em vez de reimplementar a escrita
célula a célula de um jeito novo e não testado.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import xlwings as xw

from gerar_planilha_testes import (
    _CHAVES_PARAMS,
    _valor_param,
    carregar_jogos_seriea,
    computar_jogos,
    gerar_workbook,
)

_LINHA_PRIMEIRO_PARAM = 3
_dfs_cache = {}


def _ler_parametros_da_planilha(sheet_params):
    valores = {}
    for i, chave in enumerate(_CHAVES_PARAMS):
        r = _LINHA_PRIMEIRO_PARAM + i
        nome_celula = sheet_params.range((r, 1)).value
        if nome_celula != chave:
            raise ValueError(
                f"Layout inesperado na aba Parâmetros: linha {r} tem '{nome_celula}', "
                f"esperava '{chave}'. Não reordene/apague linhas dessa aba."
            )
        valores[chave] = _valor_param(chave, sheet_params.range((r, 3)).value)
    return valores


def main():
    book = xw.Book.caller()
    caminho = book.fullname
    app = book.app

    params = _ler_parametros_da_planilha(book.sheets["Parâmetros"])
    print(f"Recalculando com os parâmetros: {params}")

    if "seriea" not in _dfs_cache:
        _dfs_cache["seriea"] = carregar_jogos_seriea()
    jogos = computar_jogos(params, df=_dfs_cache["seriea"])

    # fecha antes de reescrever (o arquivo não pode estar aberto/travado
    # pelo Excel enquanto o openpyxl grava por cima) e reabre depois —
    # seguro aqui porque este script roda como processo Python à parte
    # (chamado pelo botão "Run main"), não como VBA dentro do próprio
    # arquivo, então fechar o livro não interrompe a execução.
    book.close()
    gerar_workbook(caminho, params, jogos)
    novo = app.books.open(caminho)
    novo.sheets["Jogos"].activate()
    print(f"Recalculado e reaberto: {caminho}")


if __name__ == "__main__":
    xw.Book("SerieA_testes_visuais.xlsx").set_mock_caller()
    main()
