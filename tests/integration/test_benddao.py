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
def benddao_proxy(benddao_proxy_contract_def, p2p_nfts_weth, balancer):
    proxy = benddao_proxy_contract_def.deploy(p2p_nfts_weth.address, balancer.address)
    p2p_nfts_weth.set_proxy_authorization(proxy, True, sender=p2p_nfts_weth.owner())
    return proxy


def test_initial_state(balancer, benddao_proxy, weth, p2p_nfts_weth, borrower):
    assert benddao_proxy.p2p_lending_nfts() == p2p_nfts_weth.address
    assert benddao_proxy.flash_lender() == balancer.address
    assert p2p_nfts_weth.authorized_proxies(benddao_proxy.address) is True


def test_pay_loan(benddao_proxy, weth, borrower, owner, koda):
    benddao_contract = "0x70b97A0da65C15dfb0FFA02aEE6FA36e507C2762"
    borrower = "0xFb71960563af69888eb10182711cD69dDD01dbF7"
    token_id = 9851
    amount = 670300000000000000 + 5436224997180424
    approved = benddao_contract

    weth.transfer(borrower, amount, sender=owner)
    weth.approve(benddao_proxy.address, amount, sender=borrower)
    # weth.approve(benddao_contract, amount, sender=borrower)
    benddao_proxy.pay_benddao_loan(benddao_contract, approved, weth.address, koda.address, token_id, amount, sender=borrower)

    assert koda.ownerOf(token_id) == borrower


def test_refinance(
    balancer,
    borrower,
    debug_precompile,
    lender,
    lender_key,
    koda,
    koda_key_hash,
    benddao_proxy,
    now,
    owner,
    p2p_control,
    p2p_nfts_weth,
    weth,
):
    benddao_contract = "0x70b97A0da65C15dfb0FFA02aEE6FA36e507C2762"
    borrower = "0xFb71960563af69888eb10182711cD69dDD01dbF7"
    token_id = 9851
    amount = 670300000000000000 + 5436224997180424
    approved = benddao_contract

    offer = Offer(
        principal=amount,
        interest=amount // 100,
        payment_token=weth.address,
        duration=30 * 86400,
        collection_key_hash=koda_key_hash,
        token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=True,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_weth.address)

    weth.transfer(owner, weth.balanceOf(borrower), sender=borrower)  # borrower wallet reset

    weth.transfer(lender, offer.principal, sender=owner)

    assert weth.balanceOf(lender) >= offer.principal

    weth.approve(benddao_proxy.address, amount, sender=borrower)
    weth.approve(p2p_nfts_weth.address, offer.principal, sender=lender)

    koda.setApprovalForAll(p2p_nfts_weth.address, True, sender=borrower)

    p2p_control.change_collections_contracts([CollectionContract(koda_key_hash, koda.address)])

    assert balancer.maxFlashLoan(weth.address) >= amount
    benddao_proxy.refinance_loan(benddao_contract, approved, koda.address, amount, signed_offer, token_id, sender=borrower)

    assert koda.ownerOf(token_id) == p2p_nfts_weth.address
    assert weth.balanceOf(borrower) == 0
