.PHONY: help setup test lint format check demo spec-check compose-check containers-up containers-demo containers-down

help:
	@echo "setup             Install locked dependencies"
	@echo "check             Lint, formatting, tests, and Compose validation"
	@echo "demo              Run the fixture-backed local experiment"
	@echo "dashboard         Serve the local activity dashboard on port 8765"
	@echo "dashboard-demo    Run an experiment through that persistent gateway"
	@echo "history-check     Verify canonical history integrity"
	@echo "spec-check        Validate OpenSpec requirements"
	@echo "review-capacity-demo  Run the fixed numerical A/B/C comparison"
	@echo "review-capacity-figures  Refresh learning graphics from REPORT=path/to/report.json"
	@echo "fixture-admission-create  Queue two fixture tasks in isolated local state"
	@echo "fixture-admission-advance/status/reconcile  Inspect or advance BATCH=id"
	@echo "fixture-admission-run-status  Inspect RUN=id before a decision"
	@echo "fixture-admission-decide  Decide RUN=id DIGEST=hash DECISION=approve|reject"
	@echo "containers-up     Start the container gateway and database"
	@echo "containers-demo   Run isolated one-shot workers"
	@echo "containers-down   Stop services and retain database volumes"

setup:
	uv sync --locked

test:
	uv run --locked pytest

lint:
	uv run --locked ruff check .
	uv run --locked ruff format --check .

format:
	uv run --locked ruff format .
	uv run --locked ruff check --fix .

compose-check:
	docker compose config --quiet

check: lint test compose-check

demo:
	uv run --locked systems-lab demo

spec-check:
	OPENSPEC_TELEMETRY=0 openspec validate --all --strict

containers-up:
	uv run --locked systems-lab init
	docker compose up --build -d --wait gateway

containers-demo:
	uv run --locked systems-lab --gateway http://127.0.0.1:8765 run --executor docker

containers-down:
	docker compose down

.PHONY: dashboard dashboard-demo history-check

dashboard:
	uv run --locked systems-lab dashboard

dashboard-demo:
	uv run --locked systems-lab --gateway http://127.0.0.1:8765 demo

history-check:
	uv run --locked systems-lab history-verify

.PHONY: review-capacity-demo review-capacity-figures

review-capacity-demo:
	uv run --locked systems-lab experiment review-capacity --scenario experiments/review-capacity/scenario.json

review-capacity-figures:
	@test -n "$(REPORT)" || (echo "Usage: make review-capacity-figures REPORT=path/to/report.json" >&2; exit 2)
	uv run --no-project --with matplotlib==3.11.2 python docs/graphics/render_review_capacity.py "$(REPORT)"

FIXTURE_LAB_ROOT ?= $(CURDIR)/.lab/fixture-admission
.PHONY: fixture-admission-create fixture-admission-status fixture-admission-advance fixture-admission-reconcile fixture-admission-run-status fixture-admission-decide

fixture-admission-create:
	LAB_ROOT="$(FIXTURE_LAB_ROOT)" uv run --locked systems-lab batch create

fixture-admission-status fixture-admission-advance fixture-admission-reconcile:
	@test -n "$(BATCH)" || (echo "BATCH=id is required" >&2; exit 2)
	LAB_ROOT="$(FIXTURE_LAB_ROOT)" uv run --locked systems-lab batch $(patsubst fixture-admission-%,%,$@) "$(BATCH)"

fixture-admission-run-status:
	@test -n "$(RUN)" || (echo "RUN=id is required" >&2; exit 2)
	LAB_ROOT="$(FIXTURE_LAB_ROOT)" uv run --locked systems-lab status "$(RUN)"

fixture-admission-decide:
	@test -n "$(RUN)" && test -n "$(DIGEST)" && test -n "$(DECISION)" || (echo "RUN=id DIGEST=hash DECISION=approve|reject are required" >&2; exit 2)
	LAB_ROOT="$(FIXTURE_LAB_ROOT)" uv run --locked systems-lab decide "$(RUN)" --digest "$(DIGEST)" "--$(DECISION)"

.PHONY: telemetry-up telemetry-down

telemetry-up:
	uv run --locked systems-lab init
	OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://otel-collector:4318/v1/traces docker compose --profile observability up --build -d --wait gateway otel-collector

telemetry-down:
	docker compose --profile observability down
