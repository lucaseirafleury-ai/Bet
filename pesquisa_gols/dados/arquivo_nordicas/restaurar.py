"""
Restaura os 3 checkpoints nórdicos arquivados (ver README.md nesta pasta)
de volta pra dados/.checkpoint_<id>.json, onde buscar_sportmonks.py e
gerar_regras_sinais.py esperam encontrá-los.

Por padrão RECUSA sobrescrever um checkpoint que já existir em dados/ —
um checkpoint mais recente (rebuscado da API depois deste arquivo ter sido
criado) não deve ser silenciosamente substituído pela versão congelada.
Use --forcar só se tiver certeza de que quer voltar a este estado.

Uso:
    python3 dados/arquivo_nordicas/restaurar.py
    python3 dados/arquivo_nordicas/restaurar.py --forcar
"""
import gzip
import hashlib
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
DADOS_DIR = os.path.dirname(AQUI)

ARQUIVOS = [
    ("checkpoint_573_allsvenskan.json.gz", 573,
     "2be2dd3f33bd143eab3aee492ce9946bb3568abe5cf1ffe27ed4ccc512316e8f"),
    ("checkpoint_579_superettan.json.gz", 579,
     "ff48d7dc71bab0d01786990812a923864d5fcc814908cd8527c67a20cce409e7"),
    ("checkpoint_447_1_divisao.json.gz", 447,
     "521209388e9067d986aed433151723d24c56aea138da0c45e655680aaecad19c"),
]


def main():
    forcar = "--forcar" in sys.argv
    for nome_gz, league_id, checksum_esperado in ARQUIVOS:
        origem = os.path.join(AQUI, nome_gz)
        destino = os.path.join(DADOS_DIR, f".checkpoint_{league_id}.json")

        if os.path.exists(destino) and not forcar:
            print(f"[pulando] {destino} já existe — rode com --forcar pra sobrescrever "
                  f"(pode ser um checkpoint mais recente que o arquivado)")
            continue

        with gzip.open(origem, "rb") as f:
            conteudo = f.read()

        checksum_real = hashlib.sha256(conteudo).hexdigest()
        if checksum_real != checksum_esperado:
            print(f"[ERRO] checksum de {nome_gz} não bate!")
            print(f"  esperado: {checksum_esperado}")
            print(f"  obtido:   {checksum_real}")
            print("  NÃO restaurando este arquivo — o .gz pode estar corrompido.")
            continue

        with open(destino, "wb") as f:
            f.write(conteudo)
        print(f"[OK] {destino} restaurado ({len(conteudo)} bytes, checksum confere)")


if __name__ == "__main__":
    main()
