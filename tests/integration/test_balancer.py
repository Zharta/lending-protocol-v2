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
def eip3156_proxy_contract_def():
    return boa.load_partial("contracts/EIP3156Flash.vy")


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
def balancer(boa_env):
    return boa.load_abi("contracts/auxiliary/BalancerFlashLoanProvider.json", name="Balancer").at(
        "0x4EAF187ad4cE325bF6C84070b51c2f7224A51321"
    )


@pytest.fixture
def balancer_proxy(eip3156_proxy_contract_def, p2p_nfts_usdc, balancer):
    return eip3156_proxy_contract_def.deploy(p2p_nfts_usdc.address, balancer.address)


def test_initial_state(balancer, balancer_proxy, usdc, p2p_nfts_usdc, borrower):
    assert balancer_proxy.flash_lender() == balancer.address
    assert balancer_proxy.p2p_lending_nfts() == p2p_nfts_usdc.address

    max_flash_loan = balancer.maxFlashLoan(usdc.address)
    assert max_flash_loan > 0
    assert balancer.flashFee(usdc.address, max_flash_loan) == 0


def test_balancer_flash_loan(balancer, balancer_proxy, usdc, p2p_nfts_usdc, borrower, debug_precompile, owner):
    amount = balancer.maxFlashLoan(usdc.address)
    usdc.transfer(owner, usdc.balanceOf(borrower), sender=borrower)  # reset balance
    balancer_proxy.flash_loan(amount, sender=borrower)
    assert usdc.balanceOf(borrower) == 0
