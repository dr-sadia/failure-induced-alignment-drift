#!/bin/zsh
# Read the Z.AI credential without echo or shell-history exposure, run one
# suite stage, and clear the credential when this process exits.

set +x
set -u

typeset ZAI_API_KEY=""

cleanup() {
  unset ZAI_API_KEY
}
trap cleanup EXIT HUP INT TERM

read -r -s "ZAI_API_KEY?Z.AI key: "
print

if (( ${#ZAI_API_KEY} < 8 )); then
  print -u2 "The credential was empty or too short. No API calls were made."
  exit 2
fi

script_dir=${0:A:h}
ZAI_API_KEY="$ZAI_API_KEY" python3 "$script_dir/run_suite.py" "$@"
status=$?
exit $status
