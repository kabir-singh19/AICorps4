#!/usr/bin/env bash
# Run one make stage: tee its output to integration/logs/make_<stage>.log and append a timing
# record to integration/logs/make_timings.jsonl. Exits with the command's status.
set -uo pipefail
stage=$1; shift
logs="$(cd "$(dirname "$0")" && pwd)/logs"
mkdir -p "$logs"
start=$(date +%s.%N)
echo "== $stage: $(date -Is)" | tee "$logs/make_$stage.log"
bash -eo pipefail -c "$*" 2>&1 | tee -a "$logs/make_$stage.log"
status=${PIPESTATUS[0]}
end=$(date +%s.%N)
secs=$(python3 -c "print(round($end - $start, 1))")
printf '{"stage": "%s", "started": "%s", "seconds": %s, "exit": %s}\n' "$stage" "$(date -Is -d "@${start%.*}")" "$secs" "$status" >> "$logs/make_timings.jsonl"
echo "== $stage: exit $status after ${secs}s" | tee -a "$logs/make_$stage.log"
# Retention (EVP 3.2.3.2.2): logs are kept 90 days, then removed (same rule as `atsc logs prune`).
find "$logs" -type f -mtime +90 -delete
exit "$status"
