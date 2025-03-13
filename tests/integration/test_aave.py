import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

import boa
import pytest
from eth_abi import encode
from eth_account import Account
from eth_account.messages import HexBytes, SignableMessage
from eth_utils import keccak
from hypothesis import given, settings
from hypothesis import strategies as st
from web3 import Web3

from ..conftest_base import ZERO_ADDRESS, CollectionContract, get_last_event


@pytest.fixture
def aave_proxy_contract_def():
    return boa.load_partial("contracts/AaveFlash.vy")


@pytest.fixture
def p2p_control(p2p_lending_control_contract_def, owner, cryptopunks, bayc, bayc_key_hash, punks_key_hash):
    p2p_control = p2p_lending_control_contract_def.deploy()
    p2p_control.change_collections_contracts([CollectionContract(bayc_key_hash, bayc.address)])
    return p2p_control


@pytest.fixture
def p2p_nfts_usdc(p2p_lending_nfts_contract_def, usdc, delegation_registry, cryptopunks, owner, p2p_control):
    return p2p_lending_nfts_contract_def.deploy(
        usdc, p2p_control, delegation_registry, cryptopunks, 0, 0, owner, 10000, 10000, 10000, 10000
    )


@pytest.fixture
def aave_proxy(aave_proxy_contract_def, p2p_nfts_usdc):
    aave_pool_address_provider = "0x2f39d218133AFaB8F2B819B1066c7E434Ad94E9e"
    return aave_proxy_contract_def.deploy(p2p_nfts_usdc.address, aave_pool_address_provider)


@pytest.fixture
def aave(boa_env):
    return boa.load_abi("contracts/auxiliary/AavePoolv3_abi.json", name="AavePoolv3").at(
        "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"
    )


def test_initial_state(aave, aave_proxy, usdc, p2p_nfts_usdc, borrower):
    assert aave_proxy.POOL() == aave.address
    assert aave_proxy.ADDRESSES_PROVIDER() == aave.ADDRESSES_PROVIDER()


def test_aave_flash_loan(aave, aave_proxy, usdc, p2p_nfts_usdc, borrower, owner):
    amount = int(1000 * 1e6)
    usdc.transfer(borrower, amount, sender=owner)
    assert usdc.balanceOf(borrower) >= amount
    usdc.approve(aave_proxy.address, amount, sender=borrower)  # for premium, TODO: change provider
    aave_proxy.flash_loan(amount, sender=borrower)
