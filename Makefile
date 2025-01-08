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

integration-tests:
	${VENV}/bin/pytest tests/integration

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
	$(VENV)/bin/ruff check --select I --fix .
	$(VENV)/bin/ruff format tests scripts

%-local: export ENV=local
%-dev: export ENV=dev
%-int: export ENV=int
%-prod: export ENV=prod

%-zethereum %-zapechain: export ENV=dev
%-sepolia %-curtis: export ENV=int
%-ethereum %-apechain: export ENV=prod

%-local: export CHAIN=foundry
%-zethereum: export CHAIN=zethereum
%-zapechain: export CHAIN=zapechain
%-sepolia: export CHAIN=sepolia
%-curtis: export CHAIN=curtis
%-ethereum: export CHAIN=ethereum
%-apechain: export CHAIN=apechain

%-local: export NETWORK=ethereum:local:foundry
%-zethereum: export NETWORK=ethereum:local:https://network.dev.zharta.io/dev1/
%-zapechain: export NETWORK=ethereum:local:https://network.dev.zharta.io/dev2/
%-sepolia: export NETWORK=ethereum:sepolia:alchemy
%-curtis: export NETWORK=apechain:curtis:https://curtis.rpc.caldera.xyz/http
%-ethereum: export NETWORK=ethereum:mainnet:alchemy
%-apechain: export NETWORK=apechain:apechain:alchemy

add-account:
	${VENV}/bin/ape accounts import $(alias)

compile:
	rm -rf .build/*
	${VENV}/bin/ape compile

console-local console-zethereum console-zapechain console-sepolia console-curtis console-ethereum console-apechain:
	${VENV}/bin/ape console --network ${NETWORK} # --verbosity DEBUG

deploy-local deploy-zethereum deploy-zapechain deploy-sepolia deploy-curtis deploy-ethereum deploy-apechain:
	${VENV}/bin/ape run -I deployment --network ${NETWORK}

publish-zethereum publish-zapechain publish-sepolia publish-curtis publish-ethereum publish-apechain:
	${VENV}/bin/ape run publish

get-metadata-zethereum get-metadata-zapechain get-metadata-sepolia get-metadata-curtis get-metadata-ethereum get-metadata-apechain:
	${VENV}/bin/ape run get_collections
	${VENV}/bin/ape run get_tokens
