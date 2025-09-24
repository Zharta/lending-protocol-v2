import json
import sys
from time import sleep

import requests


def get_status_oracle(params):
    """
    Calls the /api/v1/@hyperledger/cactus-plugin-satp-hermes/oracle/execute endpoint
    with the given params as JSON body.

    Args:
        params (dict): The JSON payload to send with the task ID.

    Returns:
        dict: The JSON response from the endpoint.
    """
    url = "http://localhost:4010/api/v1/@hyperledger/cactus-plugin-satp-hermes/oracle/status"
    headers = {"Content-Type": "application/json"}
    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    return response.json()


def get_status(task_id):
    """
    Calls the /api/v1/@hyperledger/cactus-plugin-satp-hermes/oracle/execute endpoint
    with the given file as JSON body.

    Args:
        file_path (str): The path to the JSON file to send.

    Returns:
        dict: The JSON response from the endpoint.
    """

    req_params = {
        "taskID": task_id,
    }

    return get_status_oracle(req_params)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python oracle-evm-check-status.py <TaskID>")
        sys.exit(1)

    task_id = sys.argv[1]

    response = get_status(task_id)
    print("Response:", response)
