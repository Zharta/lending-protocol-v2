from functools import wraps
from typing import Any

from rich import print
from rich.markup import escape

from .basetypes import ContractConfig, DeploymentContext


def check_owner(f):
    @wraps(f)
    def wrapper(self, context, *args, **kwargs):
        if not hasattr(self, "__is_deployer_owner"):
            self.__is_deployer_owner = is_deployer_owner(context, self.key)
        return f(self, context, *args, **kwargs)

    return wrapper


def check_different(getter: str, value_property: Any):
    def check_if_needed(f):
        @wraps(f)
        def wrapper(self, context, *args, **kwargs):
            value = getattr(self, value_property)
            expected_value = context[value] if value in context else value  # noqa: SIM401
            if isinstance(expected_value, ContractConfig):
                expected_value = expected_value.address()
            if not is_config_needed(context, self.key, getter, expected_value):
                return lambda *_: None
            return f(self, context, *args, **kwargs)

        return wrapper

    return check_if_needed


def is_deployer_owner(context: DeploymentContext, contract: str) -> bool:
    if not context[contract].address():
        return True
    owner = execute_read(context, contract, "owner")
    if owner != context.owner:
        print(f"[dark_orange bold]WARNING[/] Contract [blue]{escape(contract)}[/] owner is {owner}, expected {context.owner}")
        return False
    return True


def is_config_needed(context: DeploymentContext, contract: str, func: str, new_value: Any) -> bool:
    if context.dryrun:
        return True
    current_value = execute_read(context, contract, func)
    if current_value == new_value:
        print(f"Contract [blue]{escape(contract)}[/] {func} is already {new_value}, skipping update")
        return False
    return True


def execute_read(context: DeploymentContext, contract: str, func: str, *args, options=None):
    contract_instance = context.contracts[contract].contract
    args_repr = [f"[blue]{escape(c)}[/blue]" if c in context else c for c in args]
    print(f"Calling [blue]{escape(contract)}[/blue].{func}({', '.join(args_repr)})", end=" ")

    args_values = [context[c] if c in context else c for c in args]  # noqa: SIM401
    args_values = [v.address() if isinstance(v, ContractConfig) else v for v in args_values]

    result = contract_instance.call_view_method(func, *args_values, **(options or {}))
    print(f"= {result}")
    return result


def execute(context: DeploymentContext, contract: str, func: str, *args, options=None):
    args_repr = [f"[blue]{escape(c)}[/blue]" if c in context else str(c) for c in args]
    print(f"Executing [blue]{escape(contract)}[/blue].{func}({', '.join(args_repr)})")
    if not context.dryrun:
        contract_instance = context.contracts[contract].contract
        function = getattr(contract_instance, func)
        args_values = [context[c] if c in context else c for c in args]  # noqa: SIM401
        args_values = [v.address() if isinstance(v, ContractConfig) else v for v in args_values]
        try:
            function(*args_values, **({"sender": context.owner} | context.gas_options() | (options or {})))
        except Exception as e:
            print(f"[bold red]Error executing {contract}.{func} with arguments {args_values}: {e}")
