.PHONY: help setup test lint format check demo spec-check compose-check containers-up containers-demo containers-down

help:
	@echo "setup             Install locked dependencies"
	@echo "check             Lint, formatting, tests, and Compose validation"
	@echo "demo              Run the fixture-backed local experiment"
	@echo "spec-check        Validate OpenSpec requirements"
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
