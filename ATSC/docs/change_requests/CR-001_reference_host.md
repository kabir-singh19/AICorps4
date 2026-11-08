# CR-001: Reference test host

**Status:** proposed by the team leader, 8 Nov 2026. Needs sponsor and City approval (FSR change rule).

**Requirement affected:** FSR 3.2.2.1 Hosting Footprint; ICD 3.3 Mounting Locations (Raspberry Pi 5 named as the reference test host).

**Change:** the team will not use a Raspberry Pi 5. The reference host is one x86-64 Linux machine running Docker, with every container held to the ICD Table 2 caps (proxy 0.25 vCPU / 0.25 GB, web 0.25 / 0.25 GB, api 0.5 / 1 GB, worker 2 / 3.5 GB, db 1 / 2 GB). The caps, not the hardware, define the footprint: 4 vCPU, 7 GB RAM in total.

**Why:** no Pi 5 is available to the team. The caps reproduce the FSR footprint on any host.

**Verification (ECEN 404):** `deploy/worker.sh` runs training under the worker caps and writes wall time and peak memory to `integration/logs/worker_resources.txt`. A full capped run has not been completed yet; run `s2-citywide-v1.1-2026-11-08` used all 8 cores of the host (753 s). The db container runs with `cpus: 1.0`, `mem_limit: 2g`.

**Not affected:** amd64 is the only image architecture built; an arm64 build is no longer required.
