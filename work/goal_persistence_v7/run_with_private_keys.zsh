#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="${0:A:h}"

read -rs "OPENAI_API_KEY?OpenAI API key (hidden): "
print
read -rs "ZAI_API_KEY?Z.AI API key (hidden): "
print

export OPENAI_API_KEY ZAI_API_KEY
trap 'unset OPENAI_API_KEY ZAI_API_KEY' EXIT INT TERM

python3 "$SCRIPT_DIR/run_experiment.py" "$@"
