from textwrap import dedent

import boa
import pytest
from eth_utils import decode_hex

from ...conftest_base import ZERO_ADDRESS, WhitelistRecord


@pytest.fixture(scope="module")
def max_lock_expiration():
    return 2 * 86400


@pytest.fixture
def bayc(erc721_contract_def, owner):
    return erc721_contract_def.deploy()


@pytest.fixture
def usdc(weth9_contract_def, owner):
    return weth9_contract_def.deploy("USDC", "USDC", 9, 10**20)


@pytest.fixture
def delegation_registry(delegation_registry_contract_def, owner):
    return delegation_registry_contract_def.deploy()


@pytest.fixture
def p2p_nfts_usdc(p2p_lending_nfts_contract_def, max_lock_expiration, usdc, delegation_registry, bayc, cryptopunks, owner):
    contract = p2p_lending_nfts_contract_def.deploy(usdc, delegation_registry, cryptopunks, 0, 0, owner)
    contract.change_whitelisted_collections([WhitelistRecord(cryptopunks.address, True), WhitelistRecord(bayc.address, True)])
    return contract


@pytest.fixture
def now():
    return boa.eval("block.timestamp")
