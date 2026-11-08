# ATSC end-to-end build. Stages are cached with stamp files in integration/.stamps/; a stage reruns
# when its inputs change. Logs: integration/logs/make_<stage>.log and make_timings.jsonl.
#
#   make data     restore the S1 database (PostGIS in Docker), load the HIN, context views, S1 report
#   make model    S2 citywide run -> integration/artifacts/$(RUN_ID)/ (backtest, forecast, BIT)
#   make memos    S3 memos for the top $(TOP) City-actionable sites -> $(RUN_ID)/memos/
#   make web      build the frontend and bundle the run (without models/) into the S4 backend
#   make demo     all four, then print the headline results
#   make serve    run the web app on http://127.0.0.1:$(PORT)
#   make test     every test suite, frontend build, Playwright (3 browsers x 2 sizes, axe, load)
#   make clean    drop the database volume, stamps, the run folder, the bundle and the build
#
# Secrets: the s2_reader password is generated into integration/secrets/ (git-ignored); the LLM key
# stays in $(MEMO_ENV), outside the repo, and only site_agent.py reads it.

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := demo

PY        ?= $(CURDIR)/.venv/bin/python
COMPOSE   ?= sudo docker compose
NODE_BIN  ?= $(HOME)/.local/atsc-tools/node-v22.12.0-linux-x64/bin
RUN_ID    ?= s2-citywide-2026-11-08
CONFIG    ?= S2_Risk_Model_Backtest/config/citywide_v1_2022.json
DUMP      ?= dumps/tasc_v1_2022_2026-11-04.sql.gz
HIN_FILE  ?= inputs/hin_mpo_digitized.geojson
HIN_VER   ?= csap_fig3.9_digitized_2026-11-04
MEMO_ENV  ?= $(HOME)/.config/atsc/memo.env
MEMO_MODE ?= api
TOP       ?= 25
PORT      ?= 8000

ifeq ($(strip $(RUN_ID)),)
$(error RUN_ID must not be empty)
endif

S1     := S1_Road_Network_Database
S4     := S4_Web_App
STAGE  := integration/stage.sh
STAMPS := integration/.stamps
ART    := integration/artifacts/$(RUN_ID)
BUNDLE := $(S4)/backend/data/artifacts
SECRET := integration/secrets/s2_password
DB_URL  = postgresql://s2_reader:$$(cat $(CURDIR)/$(SECRET))@localhost:5432/tasc
NODE    = PATH=$(NODE_BIN):$$PATH

S1_SQL  := $(S1)/sql/05_s2_interface.sql $(S1)/sql/08_hin.sql $(S1)/sql/09_s2_context.sql
S2_SRC  := $(wildcard S2_Risk_Model_Backtest/*.py) $(CONFIG)
S3_SRC  := $(wildcard S3_Countermeasure_Agent/Agent3/*.py) S3_Countermeasure_Agent/Agent3/countermeasure_library.csv
WEB_SRC := $(shell find $(S4)/frontend/src -type f) $(S4)/frontend/package.json $(S4)/frontend/index.html

.PHONY: data model memos web demo serve test clean venv

data: $(STAMPS)/data
model: $(STAMPS)/model
memos: $(STAMPS)/memos
web: $(STAMPS)/web

$(STAMPS) integration/secrets:
	mkdir -p $@

$(SECRET): | integration/secrets
	umask 077; python3 -c "import secrets; print(secrets.token_hex(16))" > $@

venv: $(PY)
$(PY):
	python3 -m venv .venv
	.venv/bin/pip install -q -r $(S1)/requirements.txt -r S2_Risk_Model_Backtest/requirements.txt -r $(S4)/backend/requirements.txt

$(STAMPS)/data: $(S1)/$(DUMP) $(S1)/$(HIN_FILE) $(S1_SQL) $(S1)/ingest.py $(S1)/s1_report.py $(SECRET) | $(STAMPS) $(PY)
	$(STAGE) data 'cd $(S1) \
	  && $(COMPOSE) up -d --wait \
	  && $(COMPOSE) cp $(DUMP) db:/tmp/tasc.sql.gz \
	  && $(COMPOSE) exec -T db sh -c "gunzip -c /tmp/tasc.sql.gz | psql -q -v ON_ERROR_STOP=1 -U tasc -d tasc" \
	  && $(COMPOSE) exec -T db psql -q -v ON_ERROR_STOP=1 -U tasc -d tasc -v s2_password="$$(cat $(CURDIR)/$(SECRET))" < sql/05_s2_interface.sql \
	  && $(PY) ingest.py hin $(HIN_FILE) --version $(HIN_VER) \
	  && $(COMPOSE) exec -T db psql -q -v ON_ERROR_STOP=1 -U tasc -d tasc -v network_version=v1_2022 -v hin_version=$(HIN_VER) \
	       -v hin_buffer_m=30 -v hin_available_as_of=2026-11-04 -v hin_evidence="MPO CSAP Fig. 3.9 digitized 2026-11-04" < sql/08_hin.sql \
	  && $(COMPOSE) exec -T db psql -q -v ON_ERROR_STOP=1 -U tasc -d tasc -v network_version=v1_2022 -v feature_set=backtest_2022 < sql/09_s2_context.sql \
	  && $(PY) s1_report.py --hin-version $(HIN_VER) --out ../integration/artifacts/s1_data_report.json'
	touch $@

$(STAMPS)/model: $(STAMPS)/data $(S2_SRC)
	rm -rf -- "$(CURDIR)/$(ART)"
	$(STAGE) model 'export DATABASE_URL="$(DB_URL)" && $(PY) -m S2_Risk_Model_Backtest.citywide --config $(CONFIG) \
	  --run-id $(RUN_ID) --out-root integration/artifacts > integration/logs/s2_citywide_$(RUN_ID).jsonl; \
	  status=$$?; tail -n 1 integration/logs/s2_citywide_$(RUN_ID).jsonl | cut -c1-300; exit $$status'
	touch $@

$(STAMPS)/memos: $(STAMPS)/model $(S3_SRC)
	rm -rf -- "$(CURDIR)/$(ART)/memos"
	$(STAGE) memos 'export DATABASE_URL="$(DB_URL)" && cd S3_Countermeasure_Agent/Agent3 && $(PY) site_agent.py \
	  --run-dir $(CURDIR)/$(ART) --top $(TOP) --mode $(MEMO_MODE) $(if $(wildcard $(MEMO_ENV)),--env-file $(MEMO_ENV))'
	touch $@

$(STAMPS)/web: $(STAMPS)/memos $(WEB_SRC)
	rm -rf -- "$(CURDIR)/$(BUNDLE)"
	$(STAGE) web 'cd $(S4)/frontend && export $(NODE) && { [ -d node_modules ] || npm ci --no-audit --no-fund; } && npm run build \
	  && cd $(CURDIR) && mkdir -p $(BUNDLE) && rsync -a --exclude models/ $(ART)/ $(BUNDLE)/$(RUN_ID)/ && du -sh $(BUNDLE)/$(RUN_ID)'
	touch $@

demo: web
	@$(PY) integration/summary.py $(ART)
	@tail -n 4 integration/logs/make_timings.jsonl

serve: web
	cd $(S4)/backend && ATSC_ARTIFACTS_DIR=$(CURDIR)/$(BUNDLE) ATSC_FRONTEND_DIST=$(CURDIR)/$(S4)/frontend/dist \
	  $(PY) -m uvicorn app.main:app --host 127.0.0.1 --port $(PORT)

test: | $(PY)
	$(STAGE) test_s1 'cd $(S1) && $(PY) -m unittest discover -s tests'
	$(STAGE) test_s2 '$(if $(wildcard $(SECRET)),export DATABASE_URL="$(DB_URL)" &&) $(PY) -m pytest -q -rs S2_Risk_Model_Backtest/tests'
	$(STAGE) test_s3 'cd S3_Countermeasure_Agent/Agent3 && $(PY) -m pytest -q'
	$(STAGE) test_s4_api 'cd $(S4)/backend && $(PY) -m pytest -q tests'
	$(STAGE) test_s4_build 'cd $(S4)/frontend && export $(NODE) && { [ -d node_modules ] || npm ci --no-audit --no-fund; } && npm run build'
	$(STAGE) test_s4_e2e 'cd $(S4)/e2e && export $(NODE) && { [ -d node_modules ] || npm ci --no-audit --no-fund; } && npx playwright test'

clean:
	-cd $(S1) && $(COMPOSE) down -v
	rm -rf -- "$(CURDIR)/$(STAMPS)" "$(CURDIR)/$(ART)" "$(CURDIR)/$(BUNDLE)" "$(CURDIR)/$(S4)/frontend/dist"
