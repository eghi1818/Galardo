# GALARDO Makefile - developer command interface (Blueprint §5)
# Python stdlib implementation; no external services required.

PY      ?= python3
API_PORT ?= 8090
TARGET_ORIGIN ?= http://127.0.0.1:8095
BACKEND := backend
TESTPORT ?= 18088

.PHONY: help dev-up dev-down seed-lab test test-integration scenario-validate run-local clean

help:
	@echo "GALARDO - authorized resilience testing platform (MVP)"
	@echo "  make dev-up              start lab target + API + dashboard (foreground)"
	@echo "  make seed-lab            (auto on boot) reset & reseed lab data"
	@echo "  make test                integration test suite (ephemeral ports, isolated data)"
	@echo "  make scenario-validate FILE=tests/fixtures/health-smoke.yaml"
	@echo "  make clean               remove local state (data/)"

dev-up:
	cd $(BACKEND) && $(PY) run_local.py

dev-down:
	@pkill -f "run_local.py" || true
	@echo "stopped (or not running)"

seed-lab:
	@echo "Lab data is seeded automatically on API boot (api.seed_lab)."
	@echo "To force a clean reseed: rm -rf data && make dev-up"

test:
	cd tests && GALARDO_TARGET_ORIGIN=http://127.0.0.1:$(TESTPORT) $(PY) tests_integration.py

scenario-validate:
	@cd $(BACKEND) && $(PY) -c "\
import sys, json; sys.path.insert(0, '.');\
import api as _a, os; _a.seed_lab();\
from scenario import parse_scenario_yaml, ScenarioError;\
from policy import effective_policy, resolve_scenario_layers, validate_against_policy;\
import db;\
targets = {t['name']: t for t in db.list('targets')};\
yaml_text = open('$(FILE)').read();\
try:\n\
    norm = parse_scenario_yaml(yaml_text, targets);\
    tgt = db.get('targets', norm['target_id']);\
    layers = resolve_scenario_layers(db, norm, engagement_id=tgt.get('engagement_id'));\
    eff, _ = effective_policy(layers);\
    errs = validate_against_policy({'max_rps': norm['profile']['max_rps'], 'max_vus': norm['profile']['virtual_users'], 'max_duration_sec': norm['profile']['duration_seconds'], 'paths': norm['request_paths']}, eff, tgt);\
    if errs: print(json.dumps({'valid': False, 'errors': errs}, indent=1)); sys.exit(1);\
    print(json.dumps({'valid': True, 'scenario_hash': norm['scenario_sha256'], 'effective_limits': {'max_rps': eff['max_rps'], 'max_vus': eff['max_vus'], 'max_duration_sec': eff['max_duration_sec']}}, indent=1))\
except ScenarioError as e:\n\
    print(json.dumps({'valid': False, 'errors': e.errors}, indent=1)); sys.exit(1)"

clean:
	rm -rf data
	@echo "local state removed"

run-local: dev-up

# --- GALARDO demo (Goal 2 + Goal 3 end-to-end) ---
demo:
	python3 tools/galardo_demo.py
