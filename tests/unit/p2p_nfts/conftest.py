from textwrap import dedent

import boa
import pytest
from eth_utils import decode_hex

from ...conftest_base import ZERO_ADDRESS, WhitelistRecord


@pytest.fixture(scope="module")
def max_lock_expiration():
    return 2 * 86400


@pytest.fixture(scope="module")
def max_protocol_fee():
    return 500


@pytest.fixture(scope="module")
def bayc(erc721_contract_def, owner):
    return erc721_contract_def.deploy()


@pytest.fixture(scope="module")
def p2p_control(p2p_lending_control_contract_def, cryptopunks, bayc, max_lock_expiration, owner):
    p2p_control = p2p_lending_control_contract_def.deploy(cryptopunks, max_lock_expiration)
    p2p_control.change_whitelisted_collections([WhitelistRecord(cryptopunks.address, True)])
    p2p_control.change_whitelisted_collections([WhitelistRecord(bayc.address, True)])
    return p2p_control


@pytest.fixture(scope="module")
def usdc(weth9_contract_def, owner):
    return weth9_contract_def.deploy("USDC", "USDC", 9, 10**20)


@pytest.fixture
def delegation_registry(delegation_registry_contract_def, owner):
    return delegation_registry_contract_def.deploy()


@pytest.fixture
def p2p_nfts_eth(
    p2p_lending_nfts_contract_def,
    max_lock_expiration,
    weth,
    delegation_registry,
    cryptopunks,
    p2p_control,
    max_protocol_fee,
    owner,
):
    return p2p_lending_nfts_contract_def.deploy(
        ZERO_ADDRESS,
        max_protocol_fee,
        delegation_registry,
        weth,
        cryptopunks,
        p2p_control
    )


@pytest.fixture
def p2p_nfts_usdc(
    p2p_lending_nfts_contract_def,
    max_lock_expiration,
    usdc,
    weth,
    delegation_registry,
    cryptopunks,
    p2p_control,
    max_protocol_fee,
    owner,
):
    return p2p_lending_nfts_contract_def.deploy(
        usdc,
        max_protocol_fee,
        delegation_registry,
        weth,
        cryptopunks,
        p2p_control
    )


@pytest.fixture(scope="module")
def now():
    return boa.eval("block.timestamp")
