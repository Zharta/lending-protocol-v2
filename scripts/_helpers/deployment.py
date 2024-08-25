# ruff: noqa: ERA001 PTH123 FURB103

import json
import logging
import os
import warnings
from enum import Enum
from pathlib import Path
from typing import Any

from ape import accounts

from . import contracts as contracts_module
from .basetypes import (
    ContractConfig,
    DeploymentContext,
    Environment,
)
from .dependency import DependencyManager

ENV = Environment[os.environ.get("ENV", "local")]

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
warnings.filterwarnings("ignore")


class Context(Enum):
    DEPLOYMENT = "deployment"
    CONSOLE = "console"


def load_contracts(env: Environment) -> list[ContractConfig]:
    config_file = Path.cwd() / "configs" / env.name / "p2p.json"
    with config_file.open(encoding="utf8") as f:
        config = json.load(f)

    return [
        contracts_module.__dict__[c["contract"]](
            key=f"{scope}.{name}", address=c.get("address"), abi_key=c.get("abi_key"), **c.get("properties", {})
        )
        for scope in ["common", "p2p"]
        for name, c in config[scope].items()
    ]


def store_contracts(env: Environment, contracts: list[ContractConfig]):
    config_file = Path.cwd() / "configs" / env.name / "p2p.json"
    with config_file.open(encoding="utf8") as f:
        config = json.load(f)

    contracts_dict = {c.key: c for c in contracts}
    for scope in ["common", "p2p"]:
        for name, c in config[scope].items():
            key = f"{scope}.{name}"
            if key in contracts_dict:
                c["address"] = contracts_dict[key].address()
                if contracts_dict[key].abi_key:
                    c["abi_key"] = contracts_dict[key].abi_key
                if contracts_dict[key].version:
                    c["version"] = contracts_dict[key].version
            properties = c.get("properties", {})
            addresses = c.get("properties_addresses", {})
            for prop_key, prop_val in properties.items():
                if prop_key.endswith("_key"):
                    addresses[prop_key[:-4]] = contracts_dict[prop_val].address()
            c["properties_addresses"] = addresses

    with open(config_file, "w", encoding="locale") as f:
        f.write(json.dumps(config, indent=4, sort_keys=True))


def load_nft_contracts(env: Environment) -> list[ContractConfig]:
    config_file = Path.cwd() / "configs" / env.name / "collections.json"
    with config_file.open(encoding="utf8") as f:
        config = json.load(f)

    return [
        contracts_module.__dict__[c.get("contract_def", "ERC721")](
            key=key,
            address=c.get("contract_address"),
            abi_key=c.get("abi_key"),
        )
        for key, c in config.items()
    ]


def load_configs(env: Environment) -> dict:
    config_file = Path.cwd() / "configs" / env.name / "p2p.json"
    with config_file.open(encoding="utf8") as f:
        config = json.load(f)

    _configs = config.get("configs", {})
    return {f"configs.{k}": v for k, v in _configs.items()}


class DeploymentManager:
    def __init__(self, env: Environment, context: Context = Context.DEPLOYMENT):
        self.env = env
        match env:
            case Environment.local:
                self.owner = accounts.test_accounts[0]
            case Environment.dev:
                self.owner = accounts.load("devacc")
            case Environment.int:
                self.owner = accounts.load("intacc")
            case Environment.prod:
                self.owner = accounts.load("prodacc")
        self.context = DeploymentContext(self._get_contracts(context), self.env, self.owner, self._get_configs())

    def _get_contracts(self, context: Context) -> dict[str, ContractConfig]:
        contracts = load_contracts(self.env)
        nfts = load_nft_contracts(self.env)
        all_contracts = contracts + nfts

        # always deploy everything in local
        if self.env == Environment.local and context == Context.DEPLOYMENT:
            for contract in all_contracts:
                contract.contract = None

        return {c.key: c for c in all_contracts}

    def _get_configs(self) -> dict[str, Any]:
        return load_configs(self.env)

    def _save_state(self):
        store_contracts(self.env, list(self.context.contracts.values()))

    def deploy(self, changes: set[str], *, dryrun=False, save_state=True):
        self.owner.set_autosign(True) if self.env != Environment.local else None
        self.context.dryrun = dryrun
        dependency_manager = DependencyManager(self.context, changes)
        contracts_to_deploy = dependency_manager.build_contract_deploy_set()
        dependencies_tx = dependency_manager.build_transaction_set()

        for contract in contracts_to_deploy:
            if contract.deployable(self.context):
                contract.deploy(self.context)

        if save_state and not dryrun:
            self._save_state()

        for dependency_tx in dependencies_tx:
            dependency_tx(self.context)

        if save_state and not dryrun:
            self._save_state()

    def deploy_all(self, *, dryrun=False, save_state=True):
        self.deploy(self.context.contract.keys(), dryrun=dryrun, save_state=save_state)
