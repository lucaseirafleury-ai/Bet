#!/bin/bash
set -uo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

if ! command -v pip3 >/dev/null 2>&1 && ! command -v pip >/dev/null 2>&1; then
  echo "session-start.sh: pip não encontrado, pulando instalação de dependências." >&2
  exit 0
fi

PIP_CMD=$(command -v pip3 || command -v pip)

"$PIP_CMD" install -q -r "$CLAUDE_PROJECT_DIR/metodologia_pesos/requirements.txt" \
  || echo "session-start.sh: pip install falhou, seguindo mesmo assim (sessão pode instalar manualmente se precisar)." >&2

exit 0
