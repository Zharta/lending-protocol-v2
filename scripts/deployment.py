# ruff: noqa: ERA001

import logging
import os
import warnings

import click
from ape import convert
from ape.cli import ConnectedProviderCommand
from rich import print

from ._helpers.deployment import DeploymentManager, Environment

ENV = Environment[os.environ.get("ENV", "local")]

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
warnings.filterwarnings("ignore")


def gas_cost(context):  # noqa: ARG001
    return {"gas_price": convert("10 gwei", int)}


@click.command(cls=ConnectedProviderCommand)
def cli(network):
    print(f"Connected to {network}")

    dm = DeploymentManager(ENV)
    dm.context.gas_func = gas_cost

    changes = set()
    # changes |= {
    #     # "configs.max_penalty_fee_weth",
    #     # "eth-grails.loans",
    #     # "common.nftx_marketplace_zap",
    # }

    dm.deploy(changes, dryrun=True)

    print("Done")
