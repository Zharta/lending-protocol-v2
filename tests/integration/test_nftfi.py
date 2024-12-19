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

from ..conftest_base import ZERO_ADDRESS, CollectionContract, Offer, get_last_event, sign_offer

BPS = 10000


@pytest.fixture
def p2p_control(p2p_lending_control_contract_def, owner, cryptopunks, bayc, bayc_key_hash, punks_key_hash):
    p2p_control = p2p_lending_control_contract_def.deploy()
    p2p_control.change_collections_contracts([CollectionContract(bayc_key_hash, bayc.address)])
    return p2p_control


@pytest.fixture
def p2p_nfts_weth(p2p_lending_nfts_contract_def, weth, delegation_registry, cryptopunks, owner, p2p_control):
    return p2p_lending_nfts_contract_def.deploy(
        weth, p2p_control, delegation_registry, cryptopunks, 0, 0, owner, BPS, BPS, BPS, BPS
    )


@pytest.fixture
def balancer(boa_env):
    return boa.load_abi("contracts/auxiliary/BalancerFlashLoanProvider.json", name="Balancer").at(
        "0x4EAF187ad4cE325bF6C84070b51c2f7224A51321"
    )


@pytest.fixture
def nftfi_proxy(nftfi_proxy_contract_def, p2p_nfts_weth, balancer):
    aave_pool_address_provider = "0x2f39d218133AFaB8F2B819B1066c7E434Ad94E9e"
    proxy = nftfi_proxy_contract_def.deploy(p2p_nfts_weth.address, aave_pool_address_provider, balancer.address)
    p2p_nfts_weth.set_proxy_authorization(proxy, True, sender=p2p_nfts_weth.owner())
    return proxy


@pytest.fixture
def aave(boa_env):
    return boa.load_abi("contracts/auxiliary/AavePoolv3_abi.json", name="AavePoolv3").at(
        "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"
    )


def test_initial_state(aave, nftfi_proxy, weth, p2p_nfts_weth, borrower):
    assert nftfi_proxy.POOL() == aave.address
    assert nftfi_proxy.ADDRESSES_PROVIDER() == aave.ADDRESSES_PROVIDER()


def test_pay_loan(nftfi_proxy, weth, borrower, owner, mayc):
    nftfi_contract = "0x9F10D706D789e4c76A1a6434cd1A9841c875C0A6"
    borrower = "0x47cf584925b637B1023f63b6141f795cBaA1AE79"
    # lender = "0xa317566d1eb36cee30cb923f7575bfb7c168032e"
    loan_id = 915
    token_id = 3350
    amount = 3094932000000000000
    approved = "0x6730697f33d6D2490029b32899E7865c0d902Ca0"

    weth.transfer(nftfi_proxy.address, amount, sender=owner)
    # weth.approve(nftfi_contract, amount, sender=borrower)
    nftfi_proxy.pay_nftfi_loan(nftfi_contract, approved, weth.address, loan_id, amount, sender=borrower)

    assert mayc.ownerOf(token_id) == borrower


def test_refinance(
    aave,
    borrower,
    debug_precompile,
    lender,
    lender_key,
    mayc,
    mayc_key_hash,
    nftfi_proxy,
    now,
    owner,
    p2p_control,
    p2p_nfts_weth,
    weth,
):
    nftfi_contract = "0x9F10D706D789e4c76A1a6434cd1A9841c875C0A6"
    borrower = "0x47cf584925b637B1023f63b6141f795cBaA1AE79"
    loan_id = 915
    token_id = 3350
    amount = 3094932000000000000
    flash_loan_fee = amount * 5 // BPS  # TODO: change provider
    approved = "0x6730697f33d6D2490029b32899E7865c0d902Ca0"

    offer = Offer(
        principal=amount,
        interest=amount // 100,
        payment_token=weth.address,
        duration=30 * 86400,
        collection_key_hash=mayc_key_hash,
        token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=True,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_weth.address)

    weth.transfer(borrower, flash_loan_fee, sender=owner)
    weth.transfer(lender, offer.principal, sender=owner)

    assert weth.balanceOf(borrower) >= flash_loan_fee
    assert weth.balanceOf(lender) >= offer.principal

    weth.approve(nftfi_proxy.address, amount + flash_loan_fee, sender=borrower)
    weth.approve(p2p_nfts_weth.address, offer.principal, sender=lender)

    # mayc.approve(nftfi_proxy.address, token_id, sender=borrower)
    mayc.setApprovalForAll(p2p_nfts_weth.address, True, sender=borrower)

    p2p_control.change_collections_contracts([CollectionContract(mayc_key_hash, mayc.address)])

    nftfi_proxy.refinance_loan(nftfi_contract, approved, loan_id, amount, signed_offer, token_id, sender=borrower)

    assert mayc.ownerOf(token_id) == p2p_nfts_weth.address
    assert weth.balanceOf(borrower) == 0


def test_refinance_balancer(
    balancer,
    borrower,
    debug_precompile,
    lender,
    lender_key,
    mayc,
    mayc_key_hash,
    nftfi_proxy,
    now,
    owner,
    p2p_control,
    p2p_nfts_weth,
    weth,
):
    nftfi_contract = "0x9F10D706D789e4c76A1a6434cd1A9841c875C0A6"
    borrower = "0x47cf584925b637B1023f63b6141f795cBaA1AE79"
    loan_id = 915
    token_id = 3350
    amount = 3094932000000000000
    approved = "0x6730697f33d6D2490029b32899E7865c0d902Ca0"

    offer = Offer(
        principal=amount,
        interest=amount // 100,
        payment_token=weth.address,
        duration=30 * 86400,
        collection_key_hash=mayc_key_hash,
        token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=True,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_weth.address)

    weth.transfer(lender, offer.principal, sender=owner)

    assert weth.balanceOf(lender) >= offer.principal

    weth.approve(nftfi_proxy.address, amount, sender=borrower)
    weth.approve(p2p_nfts_weth.address, offer.principal, sender=lender)

    # mayc.approve(nftfi_proxy.address, token_id, sender=borrower)
    mayc.setApprovalForAll(p2p_nfts_weth.address, True, sender=borrower)

    p2p_control.change_collections_contracts([CollectionContract(mayc_key_hash, mayc.address)])

    nftfi_proxy.refinance_loan_balancer(nftfi_contract, approved, loan_id, amount, signed_offer, token_id, sender=borrower)

    assert mayc.ownerOf(token_id) == p2p_nfts_weth.address
    assert weth.balanceOf(borrower) == 0
