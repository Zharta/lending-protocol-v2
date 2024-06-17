# ruff: noqa: T201

import os

import web3
from ape import convert

from scripts.deployment import DeploymentManager, Environment

ENV = Environment[os.environ.get("ENV", "local")]


def inject_poa(w3):
    w3.middleware_onion.inject(web3.middleware.geth_poa_middleware, layer=0)
    return w3


def transfer(w3, wallet, val=10**60):
    b = w3.eth.coinbase
    w3.eth.send_transaction({"from": b, "to": wallet, "value": val})
    print(f"new balance: {w3.eth.get_balance(wallet)}")


def propose_owner(dm, from_wallet, to_wallet):
    contracts = [c for c in dm.context.contracts.values() if hasattr(c.contract, "proposeOwner")]
    dm.owner.set_autosign(True)
    for i, c in enumerate(contracts):
        c.contract.proposeOwner(to_wallet, sender=from_wallet, gas_price=convert("28 gwei", int))
        print(f"Signed contract {i + 1} out of {len(contracts)}")


def claim_ownership(dm, wallet):
    contracts = [c for c in dm.context.contracts.values() if hasattr(c.contract, "claimOwnership")]
    dm.owner.set_autosign(True)
    for i, c in enumerate(contracts):
        c.contract.claimOwnership(sender=wallet, gas_price=convert("28 gwei", int))
        print(f"Signed contract {i + 1} out of {len(contracts)}")


def ape_init_extras():
    dm = DeploymentManager(ENV)

    globals()["dm"] = dm
    globals()["owner"] = dm.owner
    for k, v in dm.context.contracts.items():
        globals()[k.replace(".", "_").replace("-", "_")] = v.contract
        print(k.replace(".", "_"), v.contract)
    for k, v in dm.context.config.items():
        globals()[k.replace(".", "_").replace("-", "_")] = v
