#!/bin/bash
# Task 41 prompt fixed (explicit merge confirmation): rerun it for every model whose saved runs used the old prompt.
cd "$(dirname "$0")"
export TZ=America/Chicago
for m in anthropic/claude-haiku-5.5 deepseek/deepseek-v4.1-flash-1017 openai/gpt-6.1-sol anthropic/claude-sonnet-5.5 anthropic/claude-opus-5.5; do
  safe=${m//\//_}
  old=0
  for r in 1 2 3; do
    f=results/level4/transcripts/${safe}__task41__run$r.json
    if [ ! -f "$f" ] || ! grep -q "explicit confirmation for every merge" "$f"; then old=1; fi
  done
  if [ $old = 1 ]; then
    echo "=== $m task41 redo $(date)"
    python3 -u run_bench.py --models $m --tasks 41 --runs 3 --redo --out results/level4
  else
    echo "=== $m task41 already on new prompt"
  fi
done
echo "=== RERUN41 DONE $(date)"
