#!/usr/bin/env bash
# Run fairscape-evidence over every example dir; record outcome + key counters.
# Usage: ./run_grader.sh   (writes results/<slug>/ and results/summary.tsv)
set -u
cd "$(dirname "$0")"
GRADER_ROOT=../..
mkdir -p results
for d in */; do
  slug="${d%/}"
  [ "$slug" = results ] && continue
  [ -e "$slug/ro-crate-metadata.json" ] || continue
  out="results/$slug"
  mkdir -p "$out"
  (cd "$GRADER_ROOT" && python3 -m aireadiness_evidence.cli \
      "examples/outside_examples/$slug" -o "examples/outside_examples/$out" \
      --no-network --json-only) > "$out/stdout.txt" 2> "$out/stderr.txt"
  printf '  %-32s exit %s\n' "$slug" "$?"
done

python3 summarize.py > results/summary.tsv
column -t -s $'\t' results/summary.tsv
