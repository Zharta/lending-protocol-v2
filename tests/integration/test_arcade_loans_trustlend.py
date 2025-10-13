import datetime as dt
import os
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha3_256

import boa
import pytest
from boa.environment import Env
from eth_abi import encode
from eth_account import Account
from eth_account.messages import HexBytes, SignableMessage
from eth_utils import keccak
from hypothesis import given, settings
from hypothesis import strategies as st
from web3 import Web3

from ..conftest_base import ZERO_ADDRESS, CollectionContract, Offer, get_last_event, sign_offer

BPS = 10000

REPAYMENT_CONTRACT = "0x74241e1A9c021643289476426B9B70229Ab40D53"
LOAN_CORE_CONTRACT = "0x89bc08BA00f135d608bc335f6B33D7a9ABCC98aF"


@pytest.fixture(scope="module", autouse=True)
def boa_env_local():
    new_env = Env()
    with boa.swap_env(new_env):
        fork_uri = os.environ["BOA_FORK_RPC_URL"]
        blkid = 23567546
        boa.env.fork(fork_uri, block_identifier=blkid)
        yield


@pytest.fixture(scope="module")
def arcade_contract():
    return boa.load_abi("contracts/auxiliary/ArcadeLoanCore_abi.json", name="ArcadeLoanCore").at(LOAN_CORE_CONTRACT)


@pytest.fixture(scope="module")
def chromie(owner, erc721_contract_def):
    return erc721_contract_def.at("0x059EDD72Cd353dF5106D2B9cC5ab83a52287aC3a")


@pytest.fixture
def chromie_key_hash():
    return sha3_256(b"chromie").digest()


@pytest.fixture(scope="module")
def gazers(owner, erc721_contract_def):
    return erc721_contract_def.at("0xa7d8d9ef8D8Ce8992Df33D8b8CF4Aebabd5bD270")


@pytest.fixture
def gazers_key_hash():
    return sha3_256(b"gazers").digest()


@pytest.fixture(scope="module")
def fidenza(owner, erc721_contract_def):
    return erc721_contract_def.at("0xa7d8d9ef8D8Ce8992Df33D8b8CF4Aebabd5bD270")


@pytest.fixture
def fidenza_key_hash():
    return sha3_256(b"fidenza").digest()


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
def p2p_nfts_usdc(p2p_lending_nfts_contract_def, usdc, delegation_registry, cryptopunks, owner, p2p_control):
    return p2p_lending_nfts_contract_def.deploy(
        usdc, p2p_control, delegation_registry, cryptopunks, 0, 0, owner, BPS, BPS, BPS, BPS
    )


@pytest.fixture
def arcade_proxy_weth(arcade_proxy_contract_def, p2p_nfts_weth, balancer):
    proxy = arcade_proxy_contract_def.deploy(p2p_nfts_weth.address, balancer.address)
    p2p_nfts_weth.set_proxy_authorization(proxy, True, sender=p2p_nfts_weth.owner())
    return proxy


@pytest.fixture
def arcade_proxy_usdc(arcade_proxy_contract_def, p2p_nfts_usdc, balancer):
    proxy = arcade_proxy_contract_def.deploy(p2p_nfts_usdc.address, balancer.address)
    p2p_nfts_usdc.set_proxy_authorization(proxy, True, sender=p2p_nfts_usdc.owner())
    return proxy


def test_initial_state(balancer, arcade_proxy_weth, weth, arcade_proxy_usdc, usdc, p2p_nfts_weth, p2p_nfts_usdc, borrower):
    assert arcade_proxy_weth.p2p_lending_nfts() == p2p_nfts_weth.address
    assert arcade_proxy_weth.flash_lender() == balancer.address
    assert p2p_nfts_weth.authorized_proxies(arcade_proxy_weth.address) is True

    assert arcade_proxy_usdc.p2p_lending_nfts() == p2p_nfts_usdc.address
    assert arcade_proxy_usdc.flash_lender() == balancer.address
    assert p2p_nfts_usdc.authorized_proxies(arcade_proxy_usdc.address) is True


def test_refinance_10278(
    balancer,
    borrower,
    lender,
    lender_key,
    chromie,
    chromie_key_hash,
    arcade_proxy_usdc,
    now,
    owner,
    p2p_control,
    p2p_nfts_usdc,
    usdc,
    arcade_contract,
):
    borrower = "0x40d775827365Ae4d54cBC08A1A1c4f586b2C1D0A"
    loan_id = 10278
    token_id = 402
    principal = 6250000000
    interest = 226027397
    amount = principal + interest
    payment_token = usdc

    _check_loan_terms(arcade_contract, loan_id, principal, interest)

    offer, signed_offer = _create_offer(amount, token_id, chromie_key_hash, lender, lender_key, usdc, p2p_nfts_usdc)

    payment_token.transfer(owner, payment_token.balanceOf(borrower), sender=borrower)  # borrower wallet reset

    payment_token.transfer(lender, offer.principal, sender=owner)

    assert payment_token.balanceOf(lender) >= offer.principal

    payment_token.approve(arcade_proxy_usdc.address, amount, sender=borrower)
    payment_token.approve(p2p_nfts_usdc.address, offer.principal, sender=lender)

    chromie.setApprovalForAll(p2p_nfts_usdc.address, True, sender=borrower)

    p2p_control.change_collections_contracts([CollectionContract(chromie_key_hash, chromie.address)])
    _refinance_loan(arcade_proxy_usdc, loan_id, amount, signed_offer, token_id, borrower)

    assert chromie.ownerOf(token_id) == p2p_nfts_usdc.address
    assert payment_token.balanceOf(borrower) == 0


def test_refinance_10281(
    balancer,
    borrower,
    lender,
    lender_key,
    chromie,
    chromie_key_hash,
    arcade_proxy_usdc,
    now,
    owner,
    p2p_control,
    p2p_nfts_usdc,
    usdc,
    arcade_contract,
):
    borrower = "0x40d775827365Ae4d54cBC08A1A1c4f586b2C1D0A"
    loan_id = 10281
    token_id = 8952
    principal = 6250000000
    interest = 226027397
    amount = principal + interest
    payment_token = usdc

    _check_loan_terms(arcade_contract, loan_id, principal, interest)

    offer, signed_offer = _create_offer(amount, token_id, chromie_key_hash, lender, lender_key, usdc, p2p_nfts_usdc)

    payment_token.transfer(owner, payment_token.balanceOf(borrower), sender=borrower)  # borrower wallet reset
    payment_token.transfer(lender, offer.principal, sender=owner)
    assert payment_token.balanceOf(lender) >= offer.principal

    payment_token.approve(arcade_proxy_usdc.address, amount, sender=borrower)
    payment_token.approve(p2p_nfts_usdc.address, offer.principal, sender=lender)

    chromie.setApprovalForAll(p2p_nfts_usdc.address, True, sender=borrower)

    p2p_control.change_collections_contracts([CollectionContract(chromie_key_hash, chromie.address)])
    _refinance_loan(arcade_proxy_usdc, loan_id, amount, signed_offer, token_id, borrower)

    assert chromie.ownerOf(token_id) == p2p_nfts_usdc.address
    assert payment_token.balanceOf(borrower) == 0


def test_refinance_10276(
    balancer,
    borrower,
    lender,
    lender_key,
    chromie,
    chromie_key_hash,
    arcade_proxy_usdc,
    now,
    owner,
    p2p_control,
    p2p_nfts_usdc,
    usdc,
    arcade_contract,
):
    borrower = "0x40d775827365Ae4d54cBC08A1A1c4f586b2C1D0A"
    loan_id = 10276
    token_id = 5934
    principal = 8000000000
    interest = 289315068
    amount = principal + interest
    payment_token = usdc

    _check_loan_terms(arcade_contract, loan_id, principal, interest)
    offer, signed_offer = _create_offer(amount, token_id, chromie_key_hash, lender, lender_key, usdc, p2p_nfts_usdc)

    payment_token.transfer(owner, payment_token.balanceOf(borrower), sender=borrower)  # borrower wallet reset
    payment_token.transfer(lender, offer.principal, sender=owner)
    assert payment_token.balanceOf(lender) >= offer.principal

    payment_token.approve(arcade_proxy_usdc.address, amount, sender=borrower)
    payment_token.approve(p2p_nfts_usdc.address, offer.principal, sender=lender)

    chromie.setApprovalForAll(p2p_nfts_usdc.address, True, sender=borrower)

    p2p_control.change_collections_contracts([CollectionContract(chromie_key_hash, chromie.address)])
    _refinance_loan(arcade_proxy_usdc, loan_id, amount, signed_offer, token_id, borrower)

    assert chromie.ownerOf(token_id) == p2p_nfts_usdc.address
    assert payment_token.balanceOf(borrower) == 0


def test_refinance_10277(
    balancer,
    borrower,
    lender,
    lender_key,
    chromie,
    chromie_key_hash,
    arcade_proxy_usdc,
    now,
    owner,
    p2p_control,
    p2p_nfts_usdc,
    usdc,
    arcade_contract,
):
    borrower = "0x40d775827365Ae4d54cBC08A1A1c4f586b2C1D0A"
    loan_id = 10277
    token_id = 2129
    principal = 6250000000
    interest = 226027397
    amount = principal + interest
    payment_token = usdc

    _check_loan_terms(arcade_contract, loan_id, principal, interest)
    offer, signed_offer = _create_offer(amount, token_id, chromie_key_hash, lender, lender_key, usdc, p2p_nfts_usdc)

    payment_token.transfer(owner, payment_token.balanceOf(borrower), sender=borrower)  # borrower wallet reset
    payment_token.transfer(lender, offer.principal, sender=owner)

    assert payment_token.balanceOf(lender) >= offer.principal

    payment_token.approve(arcade_proxy_usdc.address, amount, sender=borrower)
    payment_token.approve(p2p_nfts_usdc.address, offer.principal, sender=lender)

    chromie.setApprovalForAll(p2p_nfts_usdc.address, True, sender=borrower)

    p2p_control.change_collections_contracts([CollectionContract(chromie_key_hash, chromie.address)])
    _refinance_loan(arcade_proxy_usdc, loan_id, amount, signed_offer, token_id, borrower)

    assert chromie.ownerOf(token_id) == p2p_nfts_usdc.address
    assert payment_token.balanceOf(borrower) == 0


def test_refinance_10279(
    balancer,
    borrower,
    lender,
    lender_key,
    chromie,
    chromie_key_hash,
    arcade_proxy_usdc,
    now,
    owner,
    p2p_control,
    p2p_nfts_usdc,
    usdc,
    arcade_contract,
):
    borrower = "0x40d775827365Ae4d54cBC08A1A1c4f586b2C1D0A"
    loan_id = 10279
    token_id = 7868
    principal = 6250000000
    interest = 226027397
    amount = principal + interest
    payment_token = usdc

    _check_loan_terms(arcade_contract, loan_id, principal, interest)
    offer, signed_offer = _create_offer(amount, token_id, chromie_key_hash, lender, lender_key, usdc, p2p_nfts_usdc)

    payment_token.transfer(owner, payment_token.balanceOf(borrower), sender=borrower)  # borrower wallet reset
    payment_token.transfer(lender, offer.principal, sender=owner)
    assert payment_token.balanceOf(lender) >= offer.principal

    payment_token.approve(arcade_proxy_usdc.address, amount, sender=borrower)
    payment_token.approve(p2p_nfts_usdc.address, offer.principal, sender=lender)

    chromie.setApprovalForAll(p2p_nfts_usdc.address, True, sender=borrower)

    p2p_control.change_collections_contracts([CollectionContract(chromie_key_hash, chromie.address)])
    _refinance_loan(arcade_proxy_usdc, loan_id, amount, signed_offer, token_id, borrower)

    assert chromie.ownerOf(token_id) == p2p_nfts_usdc.address
    assert payment_token.balanceOf(borrower) == 0


def test_refinance_10282(
    balancer,
    borrower,
    lender,
    lender_key,
    bayc,
    bayc_key_hash,
    arcade_proxy_usdc,
    now,
    owner,
    p2p_control,
    p2p_nfts_usdc,
    usdc,
    arcade_contract,
):
    borrower = "0x40d775827365Ae4d54cBC08A1A1c4f586b2C1D0A"
    loan_id = 10282
    token_id = 8219
    principal = 22000000000
    interest = 795616438
    amount = principal + interest
    payment_token = usdc

    _check_loan_terms(arcade_contract, loan_id, principal, interest)
    offer, signed_offer = _create_offer(amount, token_id, bayc_key_hash, lender, lender_key, usdc, p2p_nfts_usdc)

    payment_token.transfer(owner, payment_token.balanceOf(borrower), sender=borrower)  # borrower wallet reset
    payment_token.transfer(lender, offer.principal, sender=owner)
    assert payment_token.balanceOf(lender) >= offer.principal

    payment_token.approve(arcade_proxy_usdc.address, amount, sender=borrower)
    payment_token.approve(p2p_nfts_usdc.address, offer.principal, sender=lender)

    bayc.setApprovalForAll(p2p_nfts_usdc.address, True, sender=borrower)

    p2p_control.change_collections_contracts([CollectionContract(bayc_key_hash, bayc.address)])
    _refinance_loan(arcade_proxy_usdc, loan_id, amount, signed_offer, token_id, borrower)

    assert bayc.ownerOf(token_id) == p2p_nfts_usdc.address
    assert payment_token.balanceOf(borrower) == 0


def test_refinance_10413(
    balancer,
    borrower,
    lender,
    lender_key,
    fidenza,
    fidenza_key_hash,
    arcade_proxy_usdc,
    now,
    owner,
    p2p_control,
    p2p_nfts_usdc,
    usdc,
    arcade_contract,
):
    borrower = "0x40d775827365Ae4d54cBC08A1A1c4f586b2C1D0A"
    loan_id = 10413
    token_id = 78000255
    principal = 50000000000
    interest = 1541095890
    amount = principal + interest
    payment_token = usdc

    _check_loan_terms(arcade_contract, loan_id, principal, interest)
    offer, signed_offer = _create_offer(amount, token_id, fidenza_key_hash, lender, lender_key, usdc, p2p_nfts_usdc)

    payment_token.transfer(owner, payment_token.balanceOf(borrower), sender=borrower)  # borrower wallet reset
    payment_token.transfer(lender, offer.principal, sender=owner)
    assert payment_token.balanceOf(lender) >= offer.principal

    payment_token.approve(arcade_proxy_usdc.address, amount, sender=borrower)
    payment_token.approve(p2p_nfts_usdc.address, offer.principal, sender=lender)

    fidenza.setApprovalForAll(p2p_nfts_usdc.address, True, sender=borrower)

    p2p_control.change_collections_contracts([CollectionContract(fidenza_key_hash, fidenza.address)])
    _refinance_loan(arcade_proxy_usdc, loan_id, amount, signed_offer, token_id, borrower)

    assert fidenza.ownerOf(token_id) == p2p_nfts_usdc.address
    assert payment_token.balanceOf(borrower) == 0


def test_refinance_10318(
    balancer,
    borrower,
    lender,
    lender_key,
    gazers,
    gazers_key_hash,
    arcade_proxy_usdc,
    now,
    owner,
    p2p_control,
    p2p_nfts_usdc,
    usdc,
    arcade_contract,
):
    borrower = "0x40d775827365Ae4d54cBC08A1A1c4f586b2C1D0A"
    loan_id = 10318
    token_id = 215000919
    principal = 8600000000
    interest = 233260273
    amount = principal + interest
    payment_token = usdc

    _check_loan_terms(arcade_contract, loan_id, principal, interest)
    offer, signed_offer = _create_offer(amount, token_id, gazers_key_hash, lender, lender_key, usdc, p2p_nfts_usdc)

    payment_token.transfer(owner, payment_token.balanceOf(borrower), sender=borrower)  # borrower wallet reset
    payment_token.transfer(lender, offer.principal, sender=owner)
    assert payment_token.balanceOf(lender) >= offer.principal

    payment_token.approve(arcade_proxy_usdc.address, amount, sender=borrower)
    payment_token.approve(p2p_nfts_usdc.address, offer.principal, sender=lender)

    gazers.setApprovalForAll(p2p_nfts_usdc.address, True, sender=borrower)

    p2p_control.change_collections_contracts([CollectionContract(gazers_key_hash, gazers.address)])
    _refinance_loan(arcade_proxy_usdc, loan_id, amount, signed_offer, token_id, borrower)

    assert gazers.ownerOf(token_id) == p2p_nfts_usdc.address
    assert payment_token.balanceOf(borrower) == 0


def test_refinance_10319(
    balancer,
    borrower,
    lender,
    lender_key,
    gazers,
    gazers_key_hash,
    arcade_proxy_usdc,
    now,
    owner,
    p2p_control,
    p2p_nfts_usdc,
    usdc,
    arcade_contract,
):
    borrower = "0x40d775827365Ae4d54cBC08A1A1c4f586b2C1D0A"
    loan_id = 10319
    token_id = 215000023
    principal = 8600000000
    interest = 233260273
    amount = principal + interest
    payment_token = usdc

    _check_loan_terms(arcade_contract, loan_id, principal, interest)
    offer, signed_offer = _create_offer(amount, token_id, gazers_key_hash, lender, lender_key, usdc, p2p_nfts_usdc)

    payment_token.transfer(owner, payment_token.balanceOf(borrower), sender=borrower)  # borrower wallet reset

    payment_token.transfer(lender, offer.principal, sender=owner)

    assert payment_token.balanceOf(lender) >= offer.principal

    payment_token.approve(arcade_proxy_usdc.address, amount, sender=borrower)
    payment_token.approve(p2p_nfts_usdc.address, offer.principal, sender=lender)

    gazers.setApprovalForAll(p2p_nfts_usdc.address, True, sender=borrower)

    p2p_control.change_collections_contracts([CollectionContract(gazers_key_hash, gazers.address)])

    _refinance_loan(arcade_proxy_usdc, loan_id, amount, signed_offer, token_id, borrower)

    assert gazers.ownerOf(token_id) == p2p_nfts_usdc.address
    assert payment_token.balanceOf(borrower) == 0


def _check_loan_terms(arcade_contract, loan_id, principal, interest):
    arcade_loan = arcade_contract.getLoan(loan_id)
    assert arcade_loan.state == 1  # active
    assert arcade_loan.terms.principal == principal
    _interest_amount = arcade_contract.getInterestAmount(principal, arcade_loan.terms.proratedInterestRate)
    assert _interest_amount == interest


def _create_offer(amount, token_id, collection_key_hash, lender, lender_key, erc20, p2p_contract, interest=0):
    _now = boa.eval("block.timestamp")
    offer = Offer(
        principal=amount,
        interest=interest,
        payment_token=p2p_contract.payment_token(),
        duration=30 * 86400,
        collection_key_hash=collection_key_hash,
        token_id=token_id,
        expiration=_now + 100,
        lender=lender,
        pro_rata=True,
    )
    return offer, sign_offer(offer, lender_key, p2p_contract.address)


def _refinance_loan(proxy, loan_id, amount, signed_offer, token_id, borrower):
    proxy.refinance_loan(
        REPAYMENT_CONTRACT,
        LOAN_CORE_CONTRACT,
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
