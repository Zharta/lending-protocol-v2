from textwrap import dedent

import boa
import pytest
from eth_utils import decode_hex

from ...conftest_base import (
    ZERO_ADDRESS,
    ZERO_BYTES32,
    CollateralStatus,
    Loan,
    Offer,
    Signature,
    SignedOffer,
    compute_loan_hash,
    compute_signed_offer_id,
    deploy_reverts,
    get_last_event,
    sign_offer,
)

FOREVER = 2**256 - 1


@pytest.fixture
def broker():
    return boa.env.generate_address()


@pytest.fixture
def protocol_fee(p2p_nfts_eth):
    fee = p2p_nfts_eth.max_protocol_fee()
    p2p_nfts_eth.set_protocol_fee(fee, sender=p2p_nfts_eth.owner())
    return fee


@pytest.fixture
def offer_bayc(now, lender, lender_key, bayc, broker, p2p_nfts_eth):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=10,
        broker_fee_bps=200,
        broker_address=broker,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
        size=1
    )
    return sign_offer(offer, lender_key, p2p_nfts_eth.address)


@pytest.fixture
def offer_punk(now, lender, lender_key, cryptopunks, broker, p2p_nfts_eth):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=10,
        broker_fee_bps=200,
        broker_address=broker,
        collateral_contract=cryptopunks.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
        size=1
    )
    return sign_offer(offer, lender_key, p2p_nfts_eth.address)


@pytest.fixture
def ongoing_loan_bayc(p2p_nfts_eth, offer_bayc, weth, borrower, lender, bayc, now, protocol_fee):

    offer = offer_bayc.offer
    token_id = offer.collateral_min_token_id
    principal = offer.principal
    origination_fee = offer.origination_fee_amount

    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_eth.address, token_id, sender=borrower)
    weth.deposit(value=principal - origination_fee, sender=lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=lender)

    loan_id = p2p_nfts_eth.create_loan(offer_bayc, token_id, borrower, sender=borrower)

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
        origination_fee_amount=offer.origination_fee_amount,
        broker_fee_bps=offer.broker_fee_bps,
        broker_address=offer.broker_address,
        protocol_fee_bps=p2p_nfts_eth.protocol_fee(),
        pro_rata=offer.pro_rata
    )
    assert compute_loan_hash(loan) == p2p_nfts_eth.loans(loan_id)
    return loan


@pytest.fixture
def ongoing_loan_punk(p2p_nfts_eth, offer_punk, weth, borrower, lender, cryptopunks, now):
    offer = offer_punk.offer
    token_id = offer.collateral_min_token_id
    principal = offer.principal
    origination_fee = offer.origination_fee_amount

    cryptopunks.mint(borrower, token_id)
    cryptopunks.offerPunkForSaleToAddress(token_id, 0, p2p_nfts_eth.address, sender=borrower)
    weth.deposit(value=principal - origination_fee, sender=lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=lender)

    loan_id = p2p_nfts_eth.create_loan(offer_punk, token_id, borrower, sender=borrower)

    loan = Loan(
        id=loan_id,
        amount=offer.principal,
        interest=offer.interest,
        payment_token=offer.payment_token,
        maturity=now + offer.duration,
        start_time=now,
        borrower=borrower,
        lender=lender,
        collateral_contract=cryptopunks.address,
        collateral_token_id=token_id,
        origination_fee_amount=offer.origination_fee_amount,
        broker_fee_bps=offer.broker_fee_bps,
        broker_address=offer.broker_address,
        protocol_fee_bps=p2p_nfts_eth.protocol_fee(),
        pro_rata=offer.pro_rata
    )
    assert compute_loan_hash(loan) == p2p_nfts_eth.loans(loan_id)
    return loan


@pytest.fixture
def ongoing_loan_prorata(p2p_nfts_eth, offer_bayc, weth, borrower, lender, bayc, now, lender_key):

    offer = Offer(**offer_bayc.offer._asdict() | {"pro_rata": True})
    token_id = offer.collateral_min_token_id
    principal = offer.principal
    origination_fee = offer.origination_fee_amount

    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_eth.address, token_id, sender=borrower)
    weth.deposit(value=principal - origination_fee, sender=lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=lender)

    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)
    loan_id = p2p_nfts_eth.create_loan(signed_offer, token_id, borrower, sender=borrower)

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
        origination_fee_amount=offer.origination_fee_amount,
        broker_fee_bps=offer.broker_fee_bps,
        broker_address=offer.broker_address,
        protocol_fee_bps=p2p_nfts_eth.protocol_fee(),
        pro_rata=offer.pro_rata
    )
    assert compute_loan_hash(loan) == p2p_nfts_eth.loans(loan_id)
    return loan


def test_settle_loan_reverts_if_loan_invalid(p2p_nfts_eth, ongoing_loan_bayc):
    invalid_loans = [
        Loan(**ongoing_loan_bayc._asdict() | {"id": ZERO_BYTES32}),
        Loan(**ongoing_loan_bayc._asdict() | {"amount": ongoing_loan_bayc.amount + 1}),
        Loan(**ongoing_loan_bayc._asdict() | {"interest": ongoing_loan_bayc.interest + 1}),
        Loan(**ongoing_loan_bayc._asdict() | {"payment_token": p2p_nfts_eth.address}),
        Loan(**ongoing_loan_bayc._asdict() | {"maturity": ongoing_loan_bayc.maturity - 1}),
        Loan(**ongoing_loan_bayc._asdict() | {"start_time": ongoing_loan_bayc.start_time - 1}),
        Loan(**ongoing_loan_bayc._asdict() | {"borrower": p2p_nfts_eth.address}),
        Loan(**ongoing_loan_bayc._asdict() | {"lender": p2p_nfts_eth.address}),
        Loan(**ongoing_loan_bayc._asdict() | {"collateral_contract": p2p_nfts_eth.address}),
        Loan(**ongoing_loan_bayc._asdict() | {"collateral_token_id": ongoing_loan_bayc.collateral_token_id + 1}),
        Loan(**ongoing_loan_bayc._asdict() | {"origination_fee_amount": ongoing_loan_bayc.origination_fee_amount + 1}),
        Loan(**ongoing_loan_bayc._asdict() | {"broker_fee_bps": ongoing_loan_bayc.broker_fee_bps + 1}),
        Loan(**ongoing_loan_bayc._asdict() | {"broker_address": p2p_nfts_eth.address}),
        Loan(**ongoing_loan_bayc._asdict() | {"protocol_fee_bps": ongoing_loan_bayc.protocol_fee_bps + 1}),
        Loan(**ongoing_loan_bayc._asdict() | {"pro_rata": not ongoing_loan_bayc.pro_rata})
    ]

    for loan in invalid_loans:
        print(f"{loan=}")
        with boa.reverts("invalid loan"):
            p2p_nfts_eth.settle_loan(loan, sender=ongoing_loan_bayc.borrower)


def test_settle_loan_reverts_if_loan_defaulted(p2p_nfts_eth, ongoing_loan_bayc, now):
    time_to_default = ongoing_loan_bayc.maturity - now
    boa.env.time_travel(seconds=time_to_default + 1)

    with boa.reverts("loan defaulted"):
        p2p_nfts_eth.settle_loan(ongoing_loan_bayc, sender=ongoing_loan_bayc.borrower)


def test_settle_loan_reverts_if_loan_already_settled(p2p_nfts_eth, ongoing_loan_bayc):
    loan = ongoing_loan_bayc
    interest = loan.interest
    amount_to_settle = loan.amount + interest

    p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)

    with boa.reverts("invalid loan"):
        p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)


def test_settle_loan_reverts_if_funds_not_sent(p2p_nfts_eth, ongoing_loan_bayc, weth):
    interest = ongoing_loan_bayc.interest
    amount_to_settle = ongoing_loan_bayc.amount + interest

    with boa.reverts("invalid sent value"):
        p2p_nfts_eth.settle_loan(ongoing_loan_bayc, sender=ongoing_loan_bayc.borrower, value=amount_to_settle - 1)


def test_settle_loan_prorata_reverts_if_funds_not_sent(p2p_nfts_eth, ongoing_loan_prorata, weth):
    loan = ongoing_loan_prorata
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    amount_to_settle = amount + interest

    boa.env.time_travel(seconds=actual_duration)
    with boa.reverts("invalid sent value"):
        p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle - 1)


def test_settle_loan(p2p_nfts_eth, ongoing_loan_bayc, weth):
    loan = ongoing_loan_bayc
    interest = loan.interest
    amount_to_settle = loan.amount + interest

    p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)

    assert p2p_nfts_eth.loans(loan.id) == ZERO_BYTES32
    assert boa.env.get_balance(p2p_nfts_eth.address) == 0


def test_settle_loan_logs_event(p2p_nfts_eth, ongoing_loan_bayc, weth):
    loan = ongoing_loan_bayc
    interest = loan.interest
    protocol_fee_amount = interest * loan.protocol_fee_bps // 10000
    broker_fee_amount = interest * loan.broker_fee_bps // 10000
    amount_to_settle = loan.amount + interest

    p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)

    event = get_last_event(p2p_nfts_eth, "LoanPaid")
    assert event.id == loan.id
    assert event.borrower == loan.borrower
    assert event.lender == loan.lender
    assert event.payment_token == loan.payment_token
    assert event.paid_principal == loan.amount
    assert event.paid_interest == interest
    assert event.paid_protocol_fees == protocol_fee_amount
    assert event.paid_broker_fees == broker_fee_amount


def test_settle_loan_transfers_excess_amount_to_borrower(p2p_nfts_eth, ongoing_loan_bayc, weth):
    interest = ongoing_loan_bayc.interest
    amount_to_settle = ongoing_loan_bayc.amount + interest
    initial_borrower_balance = boa.env.get_balance(ongoing_loan_bayc.borrower)

    p2p_nfts_eth.settle_loan(ongoing_loan_bayc, sender=ongoing_loan_bayc.borrower, value=amount_to_settle + 1)
    assert boa.env.get_balance(p2p_nfts_eth.address) == 0
    assert boa.env.get_balance(ongoing_loan_bayc.borrower) == initial_borrower_balance - amount_to_settle


def test_settle_loan_transfers_collateral_to_borrower_erc721(p2p_nfts_eth, ongoing_loan_bayc, weth, bayc):
    loan = ongoing_loan_bayc
    amount_to_settle = loan.amount + loan.interest

    p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)

    assert bayc.ownerOf(loan.collateral_token_id) == loan.borrower


def test_settle_loan_transfers_collateral_to_borrower_punks(p2p_nfts_eth, ongoing_loan_punk, weth, cryptopunks):
    loan = ongoing_loan_punk
    amount_to_settle = loan.amount + loan.interest

    p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)

    assert cryptopunks.ownerOf(loan.collateral_token_id) == loan.borrower


def test_settle_loan_pays_lender(p2p_nfts_eth, ongoing_loan_bayc, weth):
    loan = ongoing_loan_bayc
    interest = loan.interest
    protocol_fee_amount = interest * loan.protocol_fee_bps // 10000
    broker_fee_amount = interest * loan.broker_fee_bps // 10000
    amount_to_settle = loan.amount + interest
    amount_to_receive = loan.amount + interest - protocol_fee_amount - broker_fee_amount
    initial_lender_balance = boa.env.get_balance(loan.lender)

    p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)

    assert boa.env.get_balance(loan.lender) == initial_lender_balance + amount_to_receive


def test_settle_loan_pays_broker_fees(p2p_nfts_eth, ongoing_loan_bayc, weth):
    loan = ongoing_loan_bayc
    interest = loan.interest
    broker_fee_amount = interest * loan.broker_fee_bps // 10000
    amount_to_settle = loan.amount + interest
    initial_broker_balance = boa.env.get_balance(loan.broker_address)

    p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)

    assert boa.env.get_balance(loan.broker_address) == initial_broker_balance + broker_fee_amount


def test_settle_loan_pays_protocol_fees(p2p_nfts_eth, ongoing_loan_bayc, weth):
    loan = ongoing_loan_bayc
    interest = loan.interest
    protocol_fee_amount = interest * loan.protocol_fee_bps // 10000
    amount_to_settle = loan.amount + interest
    initial_protocol_wallet_balance = boa.env.get_balance(p2p_nfts_eth.protocol_wallet())

    p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)

    assert boa.env.get_balance(p2p_nfts_eth.protocol_wallet()) == initial_protocol_wallet_balance + protocol_fee_amount


def test_settle_loan_prorata_logs_event(p2p_nfts_eth, ongoing_loan_prorata, weth):
    loan = ongoing_loan_prorata
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    protocol_fee_amount = interest * loan.protocol_fee_bps // 10000
    broker_fee_amount = interest * loan.broker_fee_bps // 10000
    amount_to_settle = amount + interest

    print(f"{amount_to_settle=}")
    boa.env.time_travel(seconds=actual_duration)
    p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)

    event = get_last_event(p2p_nfts_eth, "LoanPaid")
    assert event.id == loan.id
    assert event.borrower == loan.borrower
    assert event.lender == loan.lender
    assert event.payment_token == loan.payment_token
    assert event.paid_principal == amount
    assert event.paid_interest == interest
    assert event.paid_protocol_fees == protocol_fee_amount
    assert event.paid_broker_fees == broker_fee_amount


def test_settle_loan_prorata_pays_lender(p2p_nfts_eth, ongoing_loan_prorata, weth):
    loan = ongoing_loan_prorata
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    protocol_fee_amount = interest * loan.protocol_fee_bps // 10000
    broker_fee_amount = interest * loan.broker_fee_bps // 10000
    amount_to_settle = amount + interest
    amount_to_receive = amount + interest - protocol_fee_amount - broker_fee_amount
    initial_lender_balance = boa.env.get_balance(loan.lender)

    boa.env.time_travel(seconds=actual_duration)
    p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)

    assert boa.env.get_balance(loan.lender) == initial_lender_balance + amount_to_receive


def test_settle_loan_prorata_pays_broker_fees(p2p_nfts_eth, ongoing_loan_prorata, weth):
    loan = ongoing_loan_prorata
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    broker_fee_amount = interest * loan.broker_fee_bps // 10000
    amount_to_settle = amount + interest
    initial_broker_balance = boa.env.get_balance(loan.broker_address)

    boa.env.time_travel(seconds=actual_duration)
    p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)

    assert boa.env.get_balance(loan.broker_address) == initial_broker_balance + broker_fee_amount


def test_settle_loan_prorata_pays_protocol_fees(p2p_nfts_eth, ongoing_loan_prorata, weth):
    loan = ongoing_loan_prorata
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    protocol_fee_amount = interest * loan.protocol_fee_bps // 10000
    amount_to_settle = amount + interest
    initial_protocol_wallet_balance = boa.env.get_balance(p2p_nfts_eth.protocol_wallet())

    boa.env.time_travel(seconds=actual_duration)
    p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)

    assert boa.env.get_balance(p2p_nfts_eth.protocol_wallet()) == initial_protocol_wallet_balance + protocol_fee_amount
