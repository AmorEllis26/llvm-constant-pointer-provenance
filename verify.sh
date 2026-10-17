#!/bin/sh
set -eu
if [ "$#" -ne 4 ]; then
  echo "Usage: $0 BASE_BUILD V3_BUILD LLVM_SOURCE LD_LLD" >&2
  exit 2
fi
exec "${PYTHON:-python3}" "$(dirname "$0")/verify.py" --base "$1" --v3 "$2" --source "$3" --linker "$4"
