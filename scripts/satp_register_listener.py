import logging
import os
import warnings

import click
import requests
from rich import print

from ._helpers.deployment import DeploymentManager, Environment

ENV = Environment[os.environ.get("ENV", "local")]
CHAIN = os.environ.get("CHAIN", "nochain")


logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
warnings.filterwarnings("ignore")


def gas_cost(context):  # noqa: ARG001
    return {}


def register_oracle(params):
    """
    Calls the /api/v1/@hyperledger/cactus-plugin-satp-hermes/oracle/register endpoint
    with the given params as JSON body.

    Args:
        params (dict): The JSON payload to send.

    Returns:
        dict: The JSON response from the endpoint.
    """
    url = "http://localhost:4010/api/v1/@hyperledger/cactus-plugin-satp-hermes/oracle/register"
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json=params, headers=headers)
    response.raise_for_status()
    return response.json()


def register_read(source_contract_type, destination_contract_type, source_contract_address, destination_contract_address):
    """
    Calls the /api/v1/@hyperledger/cactus-plugin-satp-hermes/oracle/register" endpoint
    with the given file as JSON body.

    Returns:
        dict: The JSON response from the endpoint.
    """

    req_params = {
        "sourceNetworkId": {"id": "Sepolia", "ledgerType": "ETHEREUM"},
        "sourceContract": {
            "contractName": source_contract_type.name,
            "contractAbi": source_contract_type.dict()["abi"],
            "contractAddress": source_contract_address,
        },
        "destinationNetworkId": {"id": "Curtis", "ledgerType": "ETHEREUM"},
        "destinationContract": {
            "contractAbi": destination_contract_type.dict()["abi"],
            "contractName": destination_contract_type.name,
            "contractBytecode": destination_contract_type.dict().get("runtimeBytecode"),
            "contractAddress": destination_contract_address,
            "methodName": "sendFunds",
            # not needed because we will write the data read from the source contract
            # we can still pass it but it will overwrite the data read from the source contract
        },
        "listeningOptions": {
            "eventSignature": "LoanCreated(bytes32,uint256,uint256,address,uint256,uint256,address,address,address,uint256,(uint256,uint256,uint256,address)[],bool,bytes32,bytes32,address)",  # noqa: E501
            # since the event signature contains mutliple parameters, we need to specify which one we want to use
            "filterParams": ["borrower", "amount"],
        },
        "taskMode": "EVENT_LISTENING",
        "taskType": "READ_AND_UPDATE",
    }

    return register_oracle(req_params)


# @click.command(cls=ConnectedProviderCommand)
@click.command
def cli():
    dm_zethereum = DeploymentManager(ENV, "sepolia")
    dm_zapechain = DeploymentManager(ENV, "curtis")

    source_contract = dm_zethereum.context.contracts["p2p.ape_test"].contract
    destination_contract = dm_zapechain.context.contracts["common.lending_pool_wape"].contract

    read_response = register_read(
        source_contract.contract_type,
        destination_contract.contract_type,
        source_contract.address,
        destination_contract.address,
    )
    print("Response:", read_response)

    print(f"Task ID: {read_response['taskID']}")

    print("Done")
