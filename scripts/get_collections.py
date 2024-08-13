import json
import logging
import os
import warnings
from pathlib import Path

import boto3
import click
from decimal import Decimal
from ._helpers.deployment import Environment

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
warnings.filterwarnings("ignore")


ENV = Environment[os.environ.get("ENV", "local")]
DYNAMODB = boto3.resource("dynamodb")
COLLECTIONS = DYNAMODB.Table(f"collections-{ENV.name}")
ABI = DYNAMODB.Table(f"abis-{ENV.name}")
KEY_ATTRIBUTES = ["p2p_config_key"]


def deserialize_values(item):
    if type(item) is dict:
        return {k: deserialize_values(v) for k, v in item.items()}
    if type(item) is list:
        return [deserialize_values(v) for v in item]
    if type(item) is Decimal:
        return int(item)
    return item


def get_collections():
    collection_items = []
    response = COLLECTIONS.scan()
    while "LastEvaluatedKey" in response:
        collection_items.extend(deserialize_values(i) for i in response["Items"])
        response = COLLECTIONS.scan()
    collection_items.extend(deserialize_values(i) for i in response["Items"])
    return collection_items


def store_collections_config(collections: list[dict], env: Environment):
    config_file = f"{Path.cwd()}/configs/{env.name}/collections.json"
    config = {c["collection_key"]: c for c in collections}

    with open(config_file, "w") as f:
        f.write(json.dumps(config, indent=4, sort_keys=True))


def update_p2p_config(p2p_config_key: str, p2p_config: dict):
    indexed_attrs = list(enumerate(p2p_config.items()))
    p2p_config["p2p_config_key"] = p2p_config_key
    update_expr = ", ".join(f"{k}=:v{i}" for i, (k, v) in indexed_attrs if k not in KEY_ATTRIBUTES)
    values = {f":v{i}": v for i, (k, v) in indexed_attrs if k not in KEY_ATTRIBUTES}
    P2P_CONFIGS.update_item(
        Key={"p2p_config_key": p2p_config_key}, UpdateExpression=f"SET {update_expr}", ExpressionAttributeValues=values
    )


def update_abi(abi_key: str, abi: list[dict]):
    ABI.update_item(Key={"abi_key": abi_key}, UpdateExpression="SET abi=:v", ExpressionAttributeValues={":v": abi})


@click.command()
def cli():

    print(f"Retrieving collection configs in {ENV.name}")

    collections = get_collections()
    store_collections_config(collections, ENV)

    print(f"Collections configs retrieved in {ENV.name}")

