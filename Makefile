.PHONY: venv install install-dev test run clean interfaces docs

VENV?=./.venv
PYTHON=${VENV}/bin/python3

CONTRACTS := $(shell find contracts -depth 1 -name '*.vy')
NATSPEC := $(patsubst contracts/%, natspec/%, $(CONTRACTS:%.vy=%.json))
PATH := ${VENV}/bin:${PATH}

vpath %.vy ./contracts

$(VENV):
	if ! command -v uv > /dev/null; then python -m pip install -U uv; fi
	uv venv $(VENV)

install: ${VENV} requirements.txt
	uv pip sync requirements.txt

install-dev: $(VENV) requirements-dev.txt
	uv pip sync requirements-dev.txt
	$(VENV)/bin/pre-commit install

requirements.txt: pyproject.toml
	uv pip compile -o requirements.txt pyproject.toml

requirements-dev.txt: pyproject.toml
	uv pip compile -o requirements-dev.txt --extra dev pyproject.toml

test: ${VENV}
	${VENV}/bin/pytest tests/unit -n auto --dist loadscope

coverage:
	${VENV}/bin/coverage run -m pytest tests/unit --runslow
	${VENV}/bin/coverage report

branch-coverage:
	${VENV}/bin/coverage run --branch -m pytest tests/unit --runslow
	${VENV}/bin/coverage report

unit-tests:
	${VENV}/bin/pytest tests/unit --runslow -n auto --dist loadscope

gas:
	${VENV}/bin/pytest tests/unit --gas-profile

interfaces:
	${VENV}/bin/python scripts/build_interfaces.py contracts/*.vy

docs: $(NATSPEC)

natspec/%.json: %.vy
	${VENV}/bin/vyper -f userdoc,devdoc $< > $@

clean:
	rm -rf ${VENV} .cache .build __pycache__ **/__pycache__

lint:
	$(VENV)/bin/ruff check .

format:
	$(VENV)/bin/ruff format scripts tests
	$(VENV)/bin/ruff check --select I --fix

%-local: export ENV=local
%-dev: export ENV=dev
%-int: export ENV=int
%-prod: export ENV=prod

add-account:
	${VENV}/bin/ape accounts import $(alias)

compile:
	rm -rf .build/*
	${VENV}/bin/ape compile

console-local:
	${VENV}/bin/ape console --network ethereum:local:foundry

deploy-local:
	${VENV}/bin/ape run -I deployment --network ethereum:local:foundry

console-dev:
	${VENV}/bin/ape console --network https://network.dev.zharta.io

deploy-dev:
	${VENV}/bin/ape run -I deployment --network https://network.dev.zharta.io

console-int:
	${VENV}/bin/ape console --network ethereum:sepolia:alchemy

deploy-int:
	${VENV}/bin/ape run -I deployment --network ethereum:sepolia:alchemy

console-prod:
	${VENV}/bin/ape console --network ethereum:mainnet:alchemy

deploy-prod: compile
	${VENV}/bin/ape run -I deployment --network ethereum:mainnet:alchemy

publish-dev publish-int publish-prod:
	${VENV}/bin/ape run publish

get-collections-dev get-collections-int get-collections-prod:
	${VENV}/bin/ape run get_collections
