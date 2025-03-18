import hashlib
import json
import logging
import os
import warnings
from pathlib import Path

import boto3
import click

from ._helpers.deployment import DeploymentManager, Environment

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
warnings.filterwarnings("ignore")


ENV = Environment[os.environ.get("ENV", "local")]
CHAIN = os.environ.get("CHAIN", "nochain")
DYNAMODB = boto3.resource("dynamodb")
P2P_CONFIGS = DYNAMODB.Table(f"p2p-configs-{ENV.name}")
COLLECTIONS = DYNAMODB.Table(f"collections-{ENV.name}")
TRACKED_CONTRACTS = DYNAMODB.Table(f"tracked-contracts-{ENV.name}")
ABI = DYNAMODB.Table(f"abis-{ENV.name}")
KEY_ATTRIBUTES = ["p2p_config_key"]
TRACKED_KEY_ATTRIBUTES = ["contract_key"]
EMPTY_BYTES32 = "00" * 32


def load_abi(filename: str) -> list:
    with open(f"contracts/{filename}", "r") as f:
        return json.load(f)


def abi_key(abi: list) -> str:
    json_dump = json.dumps(abi, sort_keys=True)
    hash = hashlib.sha1(json_dump.encode("utf8"))
    return hash.hexdigest()


def get_abi_map(context, env: Environment, chain: str) -> dict:
    config_file = f"{Path.cwd()}/configs/{env.name}/{chain}/p2p.json"
    with open(config_file, "r") as f:
        config = json.load(f)

    contracts = {
        f"{prefix}.{k}": v for prefix, contracts in config.items() for k, v in contracts.items() if prefix in {"common", "p2p"}
    }
    for k, config in contracts.items():
        contract = context[k].contract
        config["abi"] = contract.contract_type.dict()["abi"]
        config["abi_key"] = abi_key(contract.contract_type.dict()["abi"])

    with open(f"{Path.cwd()}/configs/{env.name}/{chain}/tracking.json", "r") as f:
        tracking_config = json.load(f)
    tracking_contracts = {f"tracking.{k}": v for k, v in tracking_config.items()}
    for config in tracking_contracts.values():
        abi = load_abi(config["abi_file"])
        config["abi"] = abi
        config["abi_key"] = abi_key(abi)

    return contracts | tracking_contracts


def get_p2p_configs(context, env: Environment, chain: str) -> dict:
    config_file = f"{Path.cwd()}/configs/{env.name}/{chain}/p2p.json"
    with open(config_file, "r") as f:
        config = json.load(f)

    p2p_configs = config["p2p"]
    for k, config in p2p_configs.items():
        contract = context[f"p2p.{k}"].contract
        if "abi_key" not in config:
            config["abi_key"] = abi_key(contract.contract_type.dict()["abi"])

    return p2p_configs


def get_traits_roots(context, env: Environment, chain: str) -> dict:  # noqa: ARG001
    config_file = f"{Path.cwd()}/configs/{env.name}/{chain}/p2p.json"
    with open(config_file, "r") as f:
        config = json.load(f)

    configs = config.get("configs", {})
    return configs.get("trait_roots", {})


def get_tracking_configs(context, env: Environment, chain: str) -> dict:  # noqa: ARG001
    with open(f"{Path.cwd()}/configs/{env.name}/{chain}/tracking.json", "r") as f:
        tracking_config = json.load(f)
    tracking_contracts = dict(tracking_config.items())
    for config in tracking_contracts.values():
        abi = load_abi(config["abi_file"])
        config["abi"] = abi
        config["abi_key"] = abi_key(abi)

    return tracking_contracts


def update_p2p_config(p2p_config_key: str, p2p_config: dict):
    indexed_attrs = list(enumerate(p2p_config.items()))
    p2p_config["p2p_config_key"] = p2p_config_key
    update_expr = ", ".join(f"{k}=:v{i}" for i, (k, v) in indexed_attrs if k not in KEY_ATTRIBUTES)
    values = {f":v{i}": v for i, (k, v) in indexed_attrs if k not in KEY_ATTRIBUTES}
    P2P_CONFIGS.update_item(
        Key={"p2p_config_key": p2p_config_key}, UpdateExpression=f"SET {update_expr}", ExpressionAttributeValues=values
    )


def update_tracking_config(config_key: str, config: dict):
    config = {k: v for k, v in config.items() if k != "abi"}
    indexed_attrs = list(enumerate(config.items()))
    config["contract_key"] = config_key
    update_expr = ", ".join(f"#k{i}=:v{i}" for i, (k, v) in indexed_attrs if k not in TRACKED_KEY_ATTRIBUTES)
    names = {f"#k{i}": k for i, (k, v) in indexed_attrs if k not in TRACKED_KEY_ATTRIBUTES}
    values = {f":v{i}": v for i, (k, v) in indexed_attrs if k not in TRACKED_KEY_ATTRIBUTES}
    TRACKED_CONTRACTS.update_item(
        Key={"contract_key": config_key},
        UpdateExpression=f"SET {update_expr}",
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )


def update_collection_trait_root(collection_key: str, root: str):
    COLLECTIONS.update_item(
        Key={"collection_key": collection_key}, UpdateExpression="SET traits_root=:v", ExpressionAttributeValues={":v": root}
    )


def update_collection_p2p_whitelisted(collection_key: str, *, whitelisted: bool):
    COLLECTIONS.update_item(
        Key={"collection_key": collection_key},
        UpdateExpression="SET p2p_whitelisted=:v",
        ExpressionAttributeValues={":v": whitelisted},
    )


def update_abi(abi_key: str, abi: list[dict]):
    ABI.update_item(Key={"abi_key": abi_key}, UpdateExpression="SET abi=:v", ExpressionAttributeValues={":v": abi})


@click.command()
def cli():  # noqa: C901
    dm = DeploymentManager(ENV, CHAIN)

    print(f"Updating p2p configs in {ENV.name} for {CHAIN}")

    abis = get_abi_map(dm.context, dm.env, dm.chain)
    for contract_key, config in abis.items():
        abi_key = config["abi_key"]
        print(f"adding abi {contract_key=} {abi_key=}")
        update_abi(abi_key, config["abi"])

    p2p_configs = get_p2p_configs(dm.context, dm.env, dm.chain)
    for data in p2p_configs.values():
        data["chain"] = CHAIN

    tracking_configs = get_tracking_configs(dm.context, dm.env, dm.chain)
    for data in tracking_configs.values():
        data["chain"] = CHAIN

    for k, v in tracking_configs.items():
        print(f"updating tracking config {k} {v['name']}")
        update_tracking_config(k, v)

    for k, v in p2p_configs.items():
        properties_abis = {}
        for prop, prop_val in v.get("properties", {}).items():
            if prop_val in abis:
                properties_abis[prop] = abis[prop_val]["abi_key"]
            elif prop_val in dm.context and dm.context[prop_val].abi_key:
                properties_abis[prop] = dm.context[prop_val].abi_key
        v["properties_abis"] = properties_abis

        abi_key = v["abi_key"]
        print(f"updating p2p config {k} {abi_key=}")
        update_p2p_config(k, v)

    trait_roots = get_traits_roots(dm.context, dm.env, dm.chain)
    for collection, root in trait_roots.items():
        print(f"updating trait root {collection=} {root=}")
        update_collection_trait_root(collection, root)

    for collection, root in trait_roots.items():
        whitelisted = root != EMPTY_BYTES32
        print(f"updating whitelisted {collection=} {whitelisted=}")
        update_collection_p2p_whitelisted(collection, whitelisted=whitelisted)

    print(f"P2P configs updated in {ENV.name} for {CHAIN}")
