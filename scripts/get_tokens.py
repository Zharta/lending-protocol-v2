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
TOKENS = DYNAMODB.Table(f"token-symbols-{ENV.name}")


def deserialize_values(item):
    if type(item) is dict:
        return {k: deserialize_values(v) for k, v in item.items()}
    if type(item) is list:
        return [deserialize_values(v) for v in item]
    if type(item) is Decimal:
        return int(item)
    return item


def get_tokens():
    items = []
    response = TOKENS.scan()
    while "LastEvaluatedKey" in response:
        items.extend(deserialize_values(i) for i in response["Items"])
        response = TOKENS.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
    items.extend(deserialize_values(i) for i in response["Items"])
    return items


def store_tokens_config(tokens: list[dict], env: Environment, chain: str):
    config_file = f"{Path.cwd()}/configs/{env.name}/{chain}/tokens.json"
    config = {c["symbol"].lower(): c for c in tokens if c.get("chain") == chain}

    with open(config_file, "w") as f:
        f.write(json.dumps(config, indent=4, sort_keys=True))


@click.command()
def cli():
    print(f"Retrieving tokens configs in {ENV.name} for {CHAIN}")

    tokens = get_tokens()
    store_tokens_config(tokens, ENV, CHAIN)

    print(f"Tokens configs retrieved in {ENV.name} for {CHAIN}")
