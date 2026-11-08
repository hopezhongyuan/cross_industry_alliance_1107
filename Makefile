ROOT := $(CURDIR)
PY := $(ROOT)/backend/.venv/bin/python
NPM ?= npm

.PHONY: install dev migrate test lint format check schema schema-check audit verify frontend-install frontend-check

install:
	python3 -m venv backend/.venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r backend/requirements-dev.txt

dev:
	cd backend && $(PY) manage.py runserver

migrate:
	cd backend && $(PY) manage.py migrate

test:
	cd backend && $(PY) -m pytest --cov=apps --cov-report=term-missing --cov-fail-under=85

lint:
	cd backend && $(PY) -m ruff check . && $(PY) -m ruff format --check .

format:
	cd backend && $(PY) -m ruff format .

check:
	cd backend && $(PY) manage.py check
	cd backend && $(PY) manage.py makemigrations --check --dry-run

schema:
	cd backend && $(PY) manage.py spectacular --file $(ROOT)/contracts/openapi.yaml --validate

schema-check:
	cd backend && $(PY) manage.py spectacular --file /tmp/alliance-openapi.yaml --validate
	diff -u $(ROOT)/contracts/openapi.yaml /tmp/alliance-openapi.yaml

contract-check:
	$(PY) scripts/validate_contract.py

audit:
	cd backend && $(PY) manage.py audit_ledger

verify: lint check schema-check contract-check test
	@echo "verify passed"

frontend-install:
	cd frontend/admin-pc && $(NPM) ci
	cd frontend/miniapp && $(NPM) ci

frontend-check:
	cd frontend/admin-pc && $(NPM) run gen:api && $(NPM) run typecheck && $(NPM) run build
	cd frontend/miniapp && $(NPM) run build:h5
	@echo "frontend check passed"
