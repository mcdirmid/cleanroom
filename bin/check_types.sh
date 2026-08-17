#!/bin/bash
# check_types.sh - Run pyright on source files

set -e

export PYTHONPATH="$PWD/_main:$PWD:$PYTHONPATH"

exec pyright "$@"