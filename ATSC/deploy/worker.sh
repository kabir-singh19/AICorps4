#!/usr/bin/env bash
# Run a command in the batch worker container under the ICD Table 2 caps (2 vCPU, 3.5 GB RAM,
# no swap beyond the cap). The repo is mounted at /atsc; DATABASE_URL is passed through.
# GNU time writes the wall time and peak memory to integration/logs/worker_resources.txt.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
sudo docker build -q -t atsc-worker -f "$root/deploy/worker.Dockerfile" "$root" >/dev/null
exec sudo docker run --rm --cpus 2 --memory 3584m --memory-swap 3584m --network host \
  -e "DATABASE_URL=${DATABASE_URL:-}" -e PYTHONUNBUFFERED=1 -u "$(id -u):$(id -g)" -v "$root:/atsc" -w "/atsc${WORKDIR_IN_REPO:-}" \
  -e HOME=/tmp atsc-worker /usr/bin/time -v -o /atsc/integration/logs/worker_resources.txt "$@"
