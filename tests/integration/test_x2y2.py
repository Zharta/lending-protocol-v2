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
def x2y2_proxy(x2y2_proxy_contract_def, p2p_nfts_weth, balancer):
    proxy = x2y2_proxy_contract_def.deploy(p2p_nfts_weth.address, balancer.address)
    p2p_nfts_weth.set_proxy_authorization(proxy, True, sender=p2p_nfts_weth.owner())
    return proxy


def test_initial_state(balancer, x2y2_proxy, weth, p2p_nfts_weth, borrower):
    assert x2y2_proxy.p2p_lending_nfts() == p2p_nfts_weth.address
    assert x2y2_proxy.flash_lender() == balancer.address
    assert p2p_nfts_weth.authorized_proxies(x2y2_proxy.address) is True


def _test_pay_loan(x2y2_proxy, weth, borrower, owner, captainz):
    x2y2_contract = "0xB81965DdFdDA3923f292a47A1be83ba3A36B5133"
    borrower = "0x5b4485cD1528b11c40a1e098F918026865DB2807"
    loan_id = 50899
    token_id = 9712
    amount = 1714672700000000000 + 1630300000000000
    approved = "0xeF887e8b1C06209F59E8Ae55D0e625C937344376"

    weth.transfer(borrower, amount, sender=owner)
    weth.approve(x2y2_proxy.address, amount, sender=borrower)

    x2y2_proxy.pay_x2y2_loan(x2y2_contract, approved, weth.address, loan_id, amount, sender=borrower)

    assert captainz.ownerOf(token_id) == borrower


def test_refinance(
    balancer,
    borrower,
    debug_precompile,
    lender,
    lender_key,
    captainz,
    captainz_key_hash,
    x2y2_proxy,
    now,
    owner,
    p2p_control,
    p2p_nfts_weth,
    weth,
):
    x2y2_contract = "0xB81965DdFdDA3923f292a47A1be83ba3A36B5133"
    borrower = "0x5b4485cD1528b11c40a1e098F918026865DB2807"
    loan_id = 50899
    token_id = 9712
    amount = 1714672700000000000 + 1630300000000000
    approved = "0xeF887e8b1C06209F59E8Ae55D0e625C937344376"

    offer = Offer(
        principal=amount,
        interest=amount // 100,
        payment_token=weth.address,
        duration=30 * 86400,
        collection_key_hash=captainz_key_hash,
        token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=True,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_weth.address)

    weth.transfer(owner, weth.balanceOf(borrower), sender=borrower)  # borrower wallet reset

    weth.transfer(lender, offer.principal, sender=owner)

    assert weth.balanceOf(lender) >= offer.principal

    weth.approve(x2y2_proxy.address, amount, sender=borrower)
    weth.approve(p2p_nfts_weth.address, offer.principal, sender=lender)

    captainz.setApprovalForAll(p2p_nfts_weth.address, True, sender=borrower)

    p2p_control.change_collections_contracts([CollectionContract(captainz_key_hash, captainz.address)])

    assert balancer.maxFlashLoan(weth.address) >= amount
    x2y2_proxy.refinance_loan(
        x2y2_contract, approved, loan_id, amount, signed_offer, token_id, [], ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower
    )

    assert captainz.ownerOf(token_id) == p2p_nfts_weth.address
    assert weth.balanceOf(borrower) == 0
