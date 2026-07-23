#!/usr/bin/env bash
# Sincroniza as skills versionadas neste repo (.claude/skills/<nome>) para
# ~/.claude/skills/<nome>, para ficarem disponíveis em qualquer sessão do
# Claude Code, não só quando este repo está aberto.
#
# O repo é a fonte da verdade: cada skill é espelhada (rsync --delete) para
# o destino, mas só a própria pasta da skill é tocada — skills de outra
# origem em ~/.claude/skills (docx, pdf, pptx, etc.) não são afetadas.
#
# Uso:
#   scripts/deploy_skills.sh              # deploy de todas as skills do repo
#   scripts/deploy_skills.sh planilha-liga-dia   # só uma skill específica
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_ROOT="$REPO_DIR/.claude/skills"
DST_ROOT="$HOME/.claude/skills"

if [ ! -d "$SRC_ROOT" ]; then
  echo "Nada em $SRC_ROOT — nenhuma skill versionada neste repo." >&2
  exit 1
fi

mkdir -p "$DST_ROOT"

if [ "$#" -gt 0 ]; then
  names=("$@")
else
  names=()
  for d in "$SRC_ROOT"/*/; do
    names+=("$(basename "$d")")
  done
fi

for name in "${names[@]}"; do
  src="$SRC_ROOT/$name"
  dst="$DST_ROOT/$name"
  if [ ! -d "$src" ]; then
    echo "Aviso: $src não existe, pulando." >&2
    continue
  fi
  # Sem dependência de rsync (nem sempre disponível): espelha a pasta inteira
  # (remove o destino antigo e copia de novo), só a pasta desta skill é
  # tocada em ~/.claude/skills.
  rm -rf "$dst"
  cp -a "$src" "$dst"
  find "$dst" -name '__pycache__' -type d -prune -exec rm -rf {} +
  find "$dst" -name '*.pyc' -delete
  echo "deploy: $name -> $dst"
done
