from textwrap import dedent

import boa
import pytest
from eth_utils import decode_hex

from ...conftest_base import (
    ZERO_ADDRESS,
    CollateralStatus,
    Fee,
    FeeType,
    Loan,
    Offer,
    Signature,
    SignedOffer,
    compute_loan_hash,
    compute_signed_offer_id,
    deploy_reverts,
    get_last_event,
    replace_namedtuple_field,
    sign_offer,
)

FOREVER = 2**256 - 1


@pytest.fixture
def p2p_nfts_proxy(p2p_nfts_eth, p2p_lending_nfts_proxy_contract_def):
    return p2p_lending_nfts_proxy_contract_def.deploy(p2p_nfts_eth.address)


def test_create_loan_reverts_if_offer_not_signed_by_lender(p2p_nfts_eth, borrower, now, lender, borrower_key):
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=ZERO_ADDRESS,
        collateral_min_token_id=1,
        collateral_max_token_id=1,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, borrower_key, p2p_nfts_eth.address)

    with boa.reverts("offer not signed by lender"):
        p2p_nfts_eth.create_loan(signed_offer, 1, ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower)


def test_create_loan_reverts_if_offer_has_invalid_signature(p2p_nfts_eth, borrower, now, lender, lender_key):
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=ZERO_ADDRESS,
        collateral_min_token_id=1,
        collateral_max_token_id=1,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
        size=1,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    invalid_offers = [
        replace_namedtuple_field(offer, principal=offer.principal + 1),
        replace_namedtuple_field(offer, interest=offer.interest + 1),
        replace_namedtuple_field(offer, payment_token=boa.env.generate_address("random")),
        replace_namedtuple_field(offer, duration=offer.duration + 1),
        replace_namedtuple_field(offer, origination_fee_amount=offer.origination_fee_amount + 1),
        replace_namedtuple_field(offer, broker_upfront_fee_amount=offer.broker_upfront_fee_amount + 1),
        replace_namedtuple_field(offer, broker_settlement_fee_bps=offer.broker_settlement_fee_bps + 1),
        replace_namedtuple_field(offer, broker_address=boa.env.generate_address("random")),
        replace_namedtuple_field(offer, collateral_contract=boa.env.generate_address("random")),
        replace_namedtuple_field(offer, collateral_min_token_id=offer.collateral_min_token_id + 1),
        replace_namedtuple_field(offer, collateral_max_token_id=offer.collateral_max_token_id + 1),
        replace_namedtuple_field(offer, expiration=offer.expiration + 1),
        replace_namedtuple_field(offer, lender=boa.env.generate_address("random")),
        replace_namedtuple_field(offer, pro_rata=not offer.pro_rata),
        replace_namedtuple_field(offer, size=offer.size + 1),
    ]

    for invalid_offer in invalid_offers:
        print(f"{invalid_offer=}")
        with boa.reverts("offer not signed by lender"):
            p2p_nfts_eth.create_loan(
                SignedOffer(invalid_offer, signed_offer.signature), 1, ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower
            )


def test_create_loan_reverts_if_offer_expired(p2p_nfts_eth, borrower, now, lender, lender_key, bayc):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    with boa.reverts("offer expired"):
        p2p_nfts_eth.create_loan(signed_offer, token_id, ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower)


def test_create_loan_reverts_if_payment_token_invalid(p2p_nfts_eth, borrower, now, lender, lender_key, bayc):
    token_id = 1
    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_eth.address, token_id, sender=borrower)
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=boa.env.generate_address("random"),
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    with boa.reverts("invalid payment token"):
        p2p_nfts_eth.create_loan(signed_offer, token_id, ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower)


def test_create_loan_reverts_if_collateral_locked(p2p_nfts_eth, p2p_control, borrower, now, lender, lender_key, bayc):
    token_id = 1
    broker = boa.env.generate_address("broker")
    bayc.mint(borrower, token_id)

    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    p2p_control.add_broker_lock(bayc.address, token_id, broker, now + 100, sender=borrower)

    with boa.reverts("collateral locked"):
        p2p_nfts_eth.create_loan(signed_offer, token_id, ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower)


def test_create_loan_reverts_if_collateral_not_whitelisted(p2p_nfts_eth, p2p_control, borrower, now, lender, lender_key, bayc):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    p2p_control.change_whitelisted_collections([(bayc.address, False)], sender=p2p_control.owner())

    with boa.reverts("collateral not whitelisted"):
        p2p_nfts_eth.create_loan(signed_offer, token_id, ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower)


def test_create_loan_reverts_if_token_id_below_offer_range(p2p_nfts_eth, borrower, now, lender, lender_key, bayc):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id + 1,
        collateral_max_token_id=token_id + 1,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    with boa.reverts("tokenid below offer range"):
        p2p_nfts_eth.create_loan(signed_offer, token_id, ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower)


def test_create_loan_reverts_if_token_id_above_offer_range(p2p_nfts_eth, borrower, now, lender, lender_key, bayc):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id - 1,
        collateral_max_token_id=token_id - 1,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    with boa.reverts("tokenid above offer range"):
        p2p_nfts_eth.create_loan(signed_offer, token_id, ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower)


def test_create_loan_reverts_if_offer_is_revoked(p2p_nfts_eth, borrower, now, lender, lender_key, bayc):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    p2p_nfts_eth.revoke_offer(signed_offer, sender=lender)

    with boa.reverts("offer revoked"):
        p2p_nfts_eth.create_loan(signed_offer, token_id, ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower)


def test_create_loan_reverts_if_offer_exceeds_count(p2p_nfts_eth, borrower, now, lender, lender_key, bayc):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id - 1,
        collateral_max_token_id=token_id + 1,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
        size=0,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    with boa.reverts("offer fully utilized"):
        p2p_nfts_eth.create_loan(signed_offer, token_id, ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower)


def test_create_loan_reverts_if_origination_fee_exceeds_principal(p2p_nfts_eth, borrower, now, lender, lender_key, bayc):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=1001,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    with boa.reverts("origination fee gt principal"):
        p2p_nfts_eth.create_loan(signed_offer, token_id, ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower)


def test_create_loan_reverts_if_broker_fee_without_address(p2p_nfts_eth, borrower, now, lender, lender_key, bayc):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=15,
        broker_settlement_fee_bps=100,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    with boa.reverts("broker fee without address"):
        p2p_nfts_eth.create_loan(signed_offer, token_id, ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower)


def test_create_loan_reverts_if_collateral_not_approved_erc721(p2p_nfts_eth, borrower, now, lender, lender_key, bayc, weth):
    token_id = 1
    principal = 1000
    offer = Offer(
        principal=principal,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    with boa.reverts():  # not owned
        p2p_nfts_eth.create_loan(signed_offer, token_id, ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower)

    bayc.mint(borrower, token_id)
    with boa.reverts("transfer is not approved"):
        p2p_nfts_eth.create_loan(signed_offer, token_id, ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower)


def test_create_loan_reverts_if_collateral_not_approved_punks(p2p_nfts_eth, borrower, now, lender, lender_key, cryptopunks):
    token_id = 1
    principal = 1000
    offer = Offer(
        principal=principal,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=cryptopunks.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    with boa.reverts():  # not owned
        p2p_nfts_eth.create_loan(signed_offer, token_id, ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower)

    cryptopunks.mint(borrower, token_id)
    with boa.reverts("transfer is not approved"):
        p2p_nfts_eth.create_loan(signed_offer, token_id, ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower)


def test_create_loan_reverts_if_lender_funds_not_approved(p2p_nfts_eth, borrower, now, lender, lender_key, bayc, weth):
    token_id = 1
    principal = 1000
    offer = Offer(
        principal=principal,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_eth.address, token_id, sender=borrower)
    weth.deposit(value=principal, sender=lender)

    with boa.reverts():
        p2p_nfts_eth.create_loan(signed_offer, token_id, ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower)


def test_create_loan(p2p_nfts_eth, borrower, now, lender, lender_key, bayc, weth):
    token_id = 1
    principal = 1000
    offer = Offer(
        principal=principal,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_eth.address, token_id, sender=borrower)
    weth.deposit(value=principal, sender=lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=lender)
    loan_id = p2p_nfts_eth.create_loan(signed_offer, token_id, ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower)

    loan = Loan(
        id=loan_id,
        amount=offer.principal,
        interest=offer.interest,
        payment_token=offer.payment_token,
        maturity=now + offer.duration,
        start_time=now,
        borrower=borrower,
        lender=lender,
        collateral_contract=bayc.address,
        collateral_token_id=token_id,
        fees=[Fee.protocol(p2p_nfts_eth), Fee.origination(offer), Fee.lender_broker(offer), Fee.borrower_broker(ZERO_ADDRESS)],
        pro_rata=offer.pro_rata,
    )
    assert compute_loan_hash(loan) == p2p_nfts_eth.loans(loan_id)


def test_create_loan_logs_event(p2p_nfts_eth, borrower, now, lender, lender_key, bayc, weth):
    token_id = 1
    principal = 1000
    offer = Offer(
        principal=principal,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_eth.address, token_id, sender=borrower)
    weth.deposit(value=principal, sender=lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=lender)
    loan_id = p2p_nfts_eth.create_loan(signed_offer, token_id, ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower)

    event = get_last_event(p2p_nfts_eth, "LoanCreated")
    assert event.id == loan_id
    assert event.amount == offer.principal
    assert event.interest == offer.interest
    assert event.payment_token == offer.payment_token
    assert event.maturity == now + offer.duration
    assert event.start_time == now
    assert event.borrower == borrower
    assert event.lender == lender
    assert event.collateral_contract == bayc.address
    assert event.collateral_token_id == token_id
    assert event.fees == [
        Fee.protocol(p2p_nfts_eth),
        Fee.origination(offer),
        Fee.lender_broker(offer),
        Fee.borrower_broker(ZERO_ADDRESS),
    ]
    assert event.pro_rata == offer.pro_rata


def test_create_loan_succeeds_if_broker_matches_lock(p2p_nfts_eth, p2p_control, borrower, now, lender, lender_key, bayc, weth):
    token_id = 1
    principal = 1000
    broker = boa.env.generate_address("broker")
    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_eth.address, token_id, sender=borrower)
    weth.deposit(value=principal, sender=lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=lender)

    offer = Offer(
        principal=principal,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=broker,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    p2p_control.add_broker_lock(bayc.address, token_id, broker, now + 100, sender=borrower)
    p2p_nfts_eth.create_loan(signed_offer, token_id, ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower)

    collateral_status = CollateralStatus.from_tuple(p2p_control.get_collateral_status(bayc.address, token_id))
    assert collateral_status.broker_lock.expiration > now
    assert collateral_status.whitelisted


def test_create_loan_creates_delegation(p2p_nfts_eth, borrower, now, lender, lender_key, bayc, weth, delegation_registry):
    token_id = 1
    principal = 1000
    delegate = boa.env.generate_address("delegate")
    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_eth.address, token_id, sender=borrower)
    weth.deposit(value=principal, sender=lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=lender)

    offer = Offer(
        principal=principal,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    p2p_nfts_eth.create_loan(signed_offer, token_id, delegate, 0, 0, ZERO_ADDRESS, sender=borrower)

    assert delegation_registry.checkDelegateForERC721(delegate, p2p_nfts_eth.address, bayc.address, token_id, b"")


def test_create_loan_transfers_collateral_to_escrow(p2p_nfts_eth, borrower, now, lender, lender_key, bayc, weth):
    token_id = 1
    principal = 1000
    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_eth.address, token_id, sender=borrower)
    weth.deposit(value=principal, sender=lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=lender)

    offer = Offer(
        principal=principal,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    p2p_nfts_eth.create_loan(signed_offer, token_id, ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower)

    assert bayc.ownerOf(token_id) == p2p_nfts_eth.address


def test_create_loan_transfers_principal_to_borrower(p2p_nfts_eth, borrower, now, lender, lender_key, bayc, weth):
    token_id = 1
    principal = 1000
    origination_fee = 100
    initial_borrower_balance = boa.env.get_balance(borrower)
    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_eth.address, token_id, sender=borrower)
    weth.deposit(value=principal, sender=lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=lender)

    offer = Offer(
        principal=principal,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=origination_fee,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    p2p_nfts_eth.create_loan(signed_offer, token_id, ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower)

    assert boa.env.get_balance(borrower) == initial_borrower_balance + principal - origination_fee


def test_create_loan_transfers_origination_fee_to_lender(p2p_nfts_eth, borrower, now, lender, lender_key, bayc, weth):
    token_id = 1
    principal = 1000
    origination_fee = 100
    initial_lender_balance = boa.env.get_balance(lender)

    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_eth.address, token_id, sender=borrower)
    weth.deposit(value=principal - origination_fee, sender=lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=lender)

    offer = Offer(
        principal=principal,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=origination_fee,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    p2p_nfts_eth.create_loan(signed_offer, token_id, ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower)

    assert boa.env.get_balance(lender) == initial_lender_balance - principal + origination_fee


def test_create_loan_updates_offer_usage_count(p2p_nfts_eth, borrower, now, lender, lender_key, bayc, weth):
    token_id = 1
    principal = 1000
    offer = Offer(
        principal=principal,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
        size=1,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_eth.address, token_id, sender=borrower)
    weth.deposit(value=principal, sender=lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=lender)
    p2p_nfts_eth.create_loan(signed_offer, token_id, ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower)

    assert p2p_nfts_eth.offer_count(compute_signed_offer_id(signed_offer)) == 1


def test_create_loan_works_with_proxy(p2p_nfts_eth, borrower, now, lender, lender_key, bayc, weth, p2p_nfts_proxy):
    token_id = 1
    principal = 1000
    offer = Offer(
        principal=principal,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_eth.address, token_id, sender=borrower)
    weth.deposit(value=principal, sender=lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=lender)
    p2p_nfts_eth.set_proxy_authorization(p2p_nfts_proxy, True, sender=p2p_nfts_eth.owner())

    loan_id = p2p_nfts_proxy.create_loan(signed_offer, token_id, ZERO_ADDRESS, 0, 0, ZERO_ADDRESS, sender=borrower)

    loan = Loan(
        id=loan_id,
        amount=offer.principal,
        interest=offer.interest,
        payment_token=offer.payment_token,
        maturity=now + offer.duration,
        start_time=now,
        borrower=borrower,
        lender=lender,
        collateral_contract=bayc.address,
        collateral_token_id=token_id,
        fees=[Fee.protocol(p2p_nfts_eth), Fee.origination(offer), Fee.lender_broker(offer), Fee.borrower_broker(ZERO_ADDRESS)],
        pro_rata=offer.pro_rata,
    )
    assert compute_loan_hash(loan) == p2p_nfts_eth.loans(loan_id)
