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
def arcade_proxy(arcade_proxy_contract_def, p2p_nfts_weth, balancer):
    proxy = arcade_proxy_contract_def.deploy(p2p_nfts_weth.address, balancer.address)
    p2p_nfts_weth.set_proxy_authorization(proxy, True, sender=p2p_nfts_weth.owner())
    return proxy


def test_initial_state(balancer, arcade_proxy, weth, p2p_nfts_weth, borrower):
    assert arcade_proxy.p2p_lending_nfts() == p2p_nfts_weth.address
    assert arcade_proxy.flash_lender() == balancer.address
    assert p2p_nfts_weth.authorized_proxies(arcade_proxy.address) is True


def _test_pay_loan(arcade_proxy, weth, borrower, owner, wpunk):
    arcade_contract = "0x74241e1A9c021643289476426B9B70229Ab40D53"
    borrower = "0xCffC336E6D019C1aF58257A0b10bf2146a3f42A4"
    loan_id = 6541
    token_id = 7994
    amount = 31356712328767124000
    borrower = "0xCffC336E6D019C1aF58257A0b10bf2146a3f42A4"
    approved = "0x89bc08BA00f135d608bc335f6B33D7a9ABCC98aF"

    weth.transfer(borrower, amount, sender=owner)
    weth.approve(arcade_proxy.address, amount, sender=borrower)
    # weth.approve(arcade_contract, amount, sender=borrower)
    arcade_proxy.pay_arcade_loan(arcade_contract, approved, weth.address, loan_id, amount, sender=borrower)

    assert wpunk.ownerOf(token_id) == borrower


def test_refinance(
    balancer,
    borrower,
    lender,
    lender_key,
    wpunk,
    wpunk_key_hash,
    arcade_proxy,
    now,
    owner,
    p2p_control,
    p2p_nfts_weth,
    weth,
):
    arcade_contract = "0x74241e1A9c021643289476426B9B70229Ab40D53"
    borrower = "0xCffC336E6D019C1aF58257A0b10bf2146a3f42A4"
    loan_id = 6541
    token_id = 7994
    amount = 31356712328767124000
    approved = "0x89bc08BA00f135d608bc335f6B33D7a9ABCC98aF"

    offer = Offer(
        principal=amount,
        interest=amount // 100,
        payment_token=weth.address,
        duration=30 * 86400,
        collection_key_hash=wpunk_key_hash,
        token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=True,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_weth.address)

    weth.transfer(owner, weth.balanceOf(borrower), sender=borrower)  # borrower wallet reset

    weth.transfer(lender, offer.principal, sender=owner)

    assert weth.balanceOf(lender) >= offer.principal

    weth.approve(arcade_proxy.address, amount, sender=borrower)
    weth.approve(p2p_nfts_weth.address, offer.principal, sender=lender)

    wpunk.setApprovalForAll(p2p_nfts_weth.address, True, sender=borrower)

    p2p_control.change_collections_contracts([CollectionContract(wpunk_key_hash, wpunk.address)])

    assert balancer.maxFlashLoan(weth.address) >= amount
    arcade_proxy.refinance_loan(
        arcade_contract,
        approved,
        loan_id,
        amount,
        signed_offer,
        token_id,
        [],
        ZERO_ADDRESS,
        0,
        0,
        ZERO_ADDRESS,
        sender=borrower,
    )

    assert wpunk.ownerOf(token_id) == p2p_nfts_weth.address
    assert weth.balanceOf(borrower) == 0
