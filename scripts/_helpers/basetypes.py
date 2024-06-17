# ruff: noqa: PLR6301, ARG002

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ape.contracts.base import ContractContainer, ContractInstance
from ape_accounts.accounts import KeyfileAccount
from rich import print as rprint
from rich.markup import escape

Environment = Enum("Environment", ["local", "dev", "int", "prod"])


def abi_key(abi: list) -> str:
    json_dump = json.dumps(abi, sort_keys=True)
    _hash = hashlib.sha1(json_dump.encode("utf8"))
    return _hash.hexdigest()


@dataclass
class DeploymentContext:
    contracts: dict[str, Any]
    env: Environment
    owner: KeyfileAccount
    config: dict[str, Any] = field(default_factory=dict)
    gas_func: Callable | None = None
    dryrun: bool = False

    def __getitem__(self, key):
        if key in self.contracts:
            return self.contracts[key]
        return self.config[key]

    def __contains__(self, key):
        return key in self.contracts or key in self.config

    def keys(self):
        return self.contracts.keys() | self.config.keys()

    def gas_options(self):
        return self.gas_func(self) if self.gas_func is not None else {}


@dataclass
class ContractConfig:
    key: str
    contract: ContractInstance | None
    container: ContractContainer | None
    deployment_deps: set[str] = field(default_factory=set)
    config_deps: dict[str, Callable] = field(default_factory=dict)
    deployment_args: list[Any] = field(default_factory=list)
    abi_key: str | None = None
    version: str | None = None

    nft: bool = False

    def deployable(self, context: DeploymentContext) -> bool:
        return True

    def deployment_dependencies(self, context: DeploymentContext) -> set[str]:
        return self.deployment_deps

    def deployment_args_values(self, context: DeploymentContext) -> list[Any]:
        values = [context[c] if c in context else c for c in self.deployment_args]  # noqa: SIM401
        return [v.contract if isinstance(v, ContractConfig) else v for v in values]

    def deployment_args_repr(self, context: DeploymentContext) -> list[Any]:
        return [f"[blue]{escape(c)}[/blue]" if c in context else c for c in self.deployment_args]

    def deployment_options(self, context: DeploymentContext) -> dict[str, Any]:
        return {"sender": context.owner} | context.gas_options()

    def config_dependencies(self, context: DeploymentContext) -> dict[str, Callable]:
        return self.config_deps

    def address(self):
        return self.contract.address if self.contract else None

    def container_name(self):
        return self.container.contract_type.name if self.container else None

    def __str__(self):
        return self.key

    def __repr__(self):
        return f"Contract[key={self.key}, contract={self.contract}, container_name={self.container_name()}]"

    def load_contract(self, address: str):
        self.contract = self.container.at(address)

    def deploy(self, context: DeploymentContext):
        if self.contract is not None:
            rprint(
                f"[dark_orange bold]WARNING[/]: Deployment will override contract [blue bold]{self.key}[/] at {self.contract}"
            )
        if not self.deployable(context):
            raise Exception(f"Cant deploy contract {self} in current context")  # noqa: TRY002
        print_args = self.deployment_args_repr(context)
        kwargs = self.deployment_options(context)
        kwargs_str = ", ".join(f"{k}={v}" for k, v in kwargs.items())
        rprint(
            f"Deploying [blue]{self.key}[/blue] <- {self.container_name()}.deploy({', '.join(str(a) for a in print_args)}, {kwargs_str})"  # noqa: E501
        )

        if not context.dryrun:
            deploy_args = self.container.constructor.encode_input(*self.deployment_args_values(context))
            rprint(f"Deployment args for [blue]{self.key}[/]: [bright_black]{deploy_args.hex()}[/]")

            self.contract = self.container.deploy(*self.deployment_args_values(context), **kwargs)
            self.abi_key = abi_key(self.contract.contract_type.dict()["abi"])


@dataclass
class MinimalProxy(ContractConfig):
    impl: str = ""
    factory_func: str = "create_proxy"

    def deploy(self, context: DeploymentContext):
        if self.contract is not None:
            rprint(
                f"[dark_orange bold]WARNING[/dark_orange bold]: Deployment will override contract [blue bold]{self.key}[/blue bold] at {self.contract}"  # noqa: E501
            )
        if not self.deployable(context):
            raise Exception(f"Cant deploy contract {self} in current context")  # noqa: TRY002
        impl_contract = context[self.impl].contract
        print_args = self.deployment_args_repr(context)
        kwargs = self.deployment_options(context)
        kwargs_str = ",".join(f"{k}={v}" for k, v in kwargs.items())
        rprint(
            f"Deploying Proxy [blue]{self.key}[/blue] <- {self.impl}.{self.factory_func}({', '.join(str(a) for a in print_args)}, {kwargs_str})"  # noqa: E501
        )

        if not context.dryrun:
            tx = impl_contract.invoke_transaction(self.factory_func, *self.deployment_args_values(context), **kwargs)
            self.contract = self.container.at(tx.return_value)
            self.abi_key = abi_key(self.contract.contract_type.dict()["abi"])
