#!/bin/bash
# Resumable: finished runs are skipped, so this can be restarted any time.
cd "$(dirname "$0")"
export TZ=America/Chicago
for m in deepseek/deepseek-v4.1-flash-1017 anthropic/claude-haiku-5.5 openai/gpt-6.1-sol anthropic/claude-sonnet-5.5 anthropic/claude-opus-5.5; do
  echo "=== $m level2 $(date)"
  python3 -u run_bench.py --models $m --suite multiturn --runs 4 --out results/level2-extra
  echo "=== $m level3 $(date)"
  python3 -u run_bench.py --models $m --tasks 25 29 30 31 32 33 34 35 36 37 38 --runs 5 --out results/level3-final
  echo "=== $m level5 $(date)"
  python3 -u run_bench.py --models $m --suite level5 --runs 5 --out results/level5
done
for m in openai/gpt-6.1-sol anthropic/claude-sonnet-5.5 anthropic/claude-opus-5.5; do
  echo "=== $m level4 $(date)"
  python3 -u run_bench.py --models $m --suite level4 --runs 3 --out results/level4
done
echo "=== ALL DONE $(date)"
