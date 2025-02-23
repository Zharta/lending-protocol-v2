import json
import logging
import os
import warnings
from decimal import Decimal
from pathlib import Path

import boto3
import click

from ._helpers.deployment import Environment

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
warnings.filterwarnings("ignore")


ENV = Environment[os.environ.get("ENV", "local")]
CHAIN = os.environ.get("CHAIN")
DYNAMODB = boto3.resource("dynamodb")
COLLECTIONS = DYNAMODB.Table(f"collections-{ENV.name}")


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
        response = COLLECTIONS.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
    collection_items.extend(deserialize_values(i) for i in response["Items"])
    return collection_items


def store_collections_config(collections: list[dict], env: Environment, chain: str):
    config_file = f"{Path.cwd()}/configs/{env.name}/{chain}/collections.json"
    config = {c["collection_key"]: c for c in collections if c.get("chain") == chain}

    with open(config_file, "w") as f:
        f.write(json.dumps(config, indent=4, sort_keys=True))


@click.command()
def cli():
    print(f"Retrieving collection configs in {ENV.name} for {CHAIN}")

    collections = get_collections()
    store_collections_config(collections, ENV, CHAIN)

    print(f"Collections configs retrieved in {ENV.name} for {CHAIN}")
