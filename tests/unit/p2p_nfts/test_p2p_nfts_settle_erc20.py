from textwrap import dedent

import boa
import pytest
from eth_utils import decode_hex

from ...conftest_base import (
    ZERO_ADDRESS,
    ZERO_BYTES32,
    CollateralStatus,
    Fee,
    FeeType,
    FeeAmount,
    Loan,
    Offer,
    Signature,
    SignedOffer,
    compute_loan_hash,
    compute_signed_offer_id,
    deploy_reverts,
    get_last_event,
    sign_offer,
    get_loan_mutations,
)

FOREVER = 2**256 - 1


@pytest.fixture(autouse=True)
def lender_funds(lender, usdc):
    usdc.mint(lender, 10**12)


@pytest.fixture(autouse=True)
def borrower_funds(borrower, usdc):
    usdc.mint(borrower, 10**12)


@pytest.fixture
def broker():
    return boa.env.generate_address()


@pytest.fixture
def borrower_broker():
    return boa.env.generate_address()


@pytest.fixture
def borrower_broker_fee():
    return 300


@pytest.fixture
def protocol_fee(p2p_nfts_usdc):
    fee = p2p_nfts_usdc.max_protocol_fee()
    p2p_nfts_usdc.set_protocol_fee(fee, sender=p2p_nfts_usdc.owner())
    return fee


@pytest.fixture
def offer_bayc(now, lender, lender_key, bayc, broker, p2p_nfts_usdc, usdc):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=usdc.address,
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
    return sign_offer(offer, lender_key, p2p_nfts_usdc.address)


@pytest.fixture
def offer_punk(now, lender, lender_key, cryptopunks, broker, p2p_nfts_usdc, usdc):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=usdc.address,
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
    return sign_offer(offer, lender_key, p2p_nfts_usdc.address)


@pytest.fixture
def ongoing_loan_bayc(p2p_nfts_usdc, offer_bayc, usdc, borrower, lender, bayc, now, protocol_fee, borrower_broker, borrower_broker_fee):

    offer = offer_bayc.offer
    token_id = offer.collateral_min_token_id
    principal = offer.principal
    origination_fee = offer.origination_fee_amount

    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_usdc.address, token_id, sender=borrower)
    usdc.deposit(value=principal - origination_fee, sender=lender)
    usdc.approve(p2p_nfts_usdc.address, principal, sender=lender)

    loan_id = p2p_nfts_usdc.create_loan(offer_bayc, token_id, borrower, borrower_broker_fee, borrower_broker, sender=borrower)

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
        fees=[
            Fee(FeeType.PROTOCOL, 0, p2p_nfts_usdc.protocol_fee(), p2p_nfts_usdc.protocol_wallet()),
            Fee(FeeType.ORIGINATION, offer.origination_fee_amount, 0, lender),
            Fee(FeeType.LENDER_BROKER, 0, offer.broker_fee_bps, offer.broker_address),
            Fee(FeeType.BORROWER_BROKER, 0, borrower_broker_fee, borrower_broker),
        ],
        pro_rata=offer.pro_rata
    )
    assert compute_loan_hash(loan) == p2p_nfts_usdc.loans(loan_id)
    return loan


@pytest.fixture
def ongoing_loan_punk(p2p_nfts_usdc, offer_punk, usdc, borrower, lender, cryptopunks, now, borrower_broker, borrower_broker_fee):
    offer = offer_punk.offer
    token_id = offer.collateral_min_token_id
    principal = offer.principal
    origination_fee = offer.origination_fee_amount

    cryptopunks.mint(borrower, token_id)
    cryptopunks.offerPunkForSaleToAddress(token_id, 0, p2p_nfts_usdc.address, sender=borrower)
    usdc.deposit(value=principal - origination_fee, sender=lender)
    usdc.approve(p2p_nfts_usdc.address, principal, sender=lender)

    loan_id = p2p_nfts_usdc.create_loan(offer_punk, token_id, borrower, borrower_broker_fee, borrower_broker, sender=borrower)

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
        fees=[
            Fee(FeeType.PROTOCOL, 0, p2p_nfts_usdc.protocol_fee(), p2p_nfts_usdc.protocol_wallet()),
            Fee(FeeType.ORIGINATION, offer.origination_fee_amount, 0, lender),
            Fee(FeeType.LENDER_BROKER, 0, offer.broker_fee_bps, offer.broker_address),
            Fee(FeeType.BORROWER_BROKER, 0, borrower_broker_fee, borrower_broker),
        ],
        pro_rata=offer.pro_rata
    )
    assert compute_loan_hash(loan) == p2p_nfts_usdc.loans(loan_id)
    return loan


@pytest.fixture
def ongoing_loan_prorata(p2p_nfts_usdc, offer_bayc, usdc, borrower, lender, bayc, now, lender_key, borrower_broker, borrower_broker_fee):

    offer = Offer(**offer_bayc.offer._asdict() | {"pro_rata": True})
    token_id = offer.collateral_min_token_id
    principal = offer.principal
    origination_fee = offer.origination_fee_amount

    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_usdc.address, token_id, sender=borrower)
    usdc.deposit(value=principal - origination_fee, sender=lender)
    usdc.approve(p2p_nfts_usdc.address, principal, sender=lender)

    signed_offer = sign_offer(offer, lender_key, p2p_nfts_usdc.address)
    loan_id = p2p_nfts_usdc.create_loan(signed_offer, token_id, borrower, borrower_broker_fee, borrower_broker, sender=borrower)

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
        fees=[
            Fee(FeeType.PROTOCOL, 0, p2p_nfts_usdc.protocol_fee(), p2p_nfts_usdc.protocol_wallet()),
            Fee(FeeType.ORIGINATION, offer.origination_fee_amount, 0, lender),
            Fee(FeeType.LENDER_BROKER, 0, offer.broker_fee_bps, offer.broker_address),
            Fee(FeeType.BORROWER_BROKER, 0, borrower_broker_fee, borrower_broker),
        ],
        pro_rata=offer.pro_rata
    )
    assert compute_loan_hash(loan) == p2p_nfts_usdc.loans(loan_id)
    return loan


def test_settle_loan_reverts_if_loan_invalid(p2p_nfts_usdc, ongoing_loan_bayc):

    for loan in get_loan_mutations(ongoing_loan_bayc):
        print(f"{loan=}")
        with boa.reverts("invalid loan"):
            p2p_nfts_usdc.settle_loan(loan, sender=ongoing_loan_bayc.borrower)


def test_settle_loan_reverts_if_loan_defaulted(p2p_nfts_usdc, ongoing_loan_bayc, now):
    time_to_default = ongoing_loan_bayc.maturity - now
    boa.env.time_travel(seconds=time_to_default + 1)

    with boa.reverts("loan defaulted"):
        p2p_nfts_usdc.settle_loan(ongoing_loan_bayc, sender=ongoing_loan_bayc.borrower)


def test_settle_loan_reverts_if_loan_already_settled(p2p_nfts_usdc, ongoing_loan_bayc, usdc):
    loan = ongoing_loan_bayc
    interest = loan.interest
    amount_to_settle = loan.amount + interest

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    with boa.reverts("invalid loan"):
        usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
        p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)


def test_settle_loan_reverts_if_funds_not_approved(p2p_nfts_usdc, ongoing_loan_bayc, usdc):
    interest = ongoing_loan_bayc.interest
    amount_to_settle = ongoing_loan_bayc.amount + interest

    with boa.reverts():
        usdc.approve(p2p_nfts_usdc.address, amount_to_settle - 1, sender=ongoing_loan_bayc.borrower)
        p2p_nfts_usdc.settle_loan(ongoing_loan_bayc, sender=ongoing_loan_bayc.borrower)


def test_settle_loan_prorata_reverts_if_funds_not_approved(p2p_nfts_usdc, ongoing_loan_prorata, usdc):
    loan = ongoing_loan_prorata
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    amount_to_settle = amount + interest

    boa.env.time_travel(seconds=actual_duration)
    with boa.reverts():
        usdc.approve(p2p_nfts_usdc.address, amount_to_settle - 1, sender=loan.borrower)
        p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)


def test_settle_loan(p2p_nfts_usdc, ongoing_loan_bayc, usdc):
    loan = ongoing_loan_bayc
    interest = loan.interest
    amount_to_settle = loan.amount + interest

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    assert p2p_nfts_usdc.loans(loan.id) == ZERO_BYTES32
    assert usdc.balanceOf(p2p_nfts_usdc.address) == 0


def test_settle_loan_logs_event(p2p_nfts_usdc, ongoing_loan_bayc, usdc):
    loan = ongoing_loan_bayc
    interest = loan.interest
    protocol_fee_amount = interest * loan.get_protocol_fee().interest_bps // 10000
    lender_broker_fee_amount = interest * loan.get_lender_broker_fee().interest_bps // 10000
    borrower_broker_fee_amount = interest * loan.get_borrower_broker_fee().interest_bps // 10000
    amount_to_settle = loan.amount + interest

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    event = get_last_event(p2p_nfts_usdc, "LoanPaid")
    assert event.id == loan.id
    assert event.borrower == loan.borrower
    assert event.lender == loan.lender
    assert event.payment_token == loan.payment_token
    assert event.paid_principal == loan.amount
    assert event.paid_interest == interest
    assert event.paid_settlement_fees == [
        FeeAmount(FeeType.PROTOCOL, protocol_fee_amount, p2p_nfts_usdc.protocol_wallet()),
        FeeAmount(FeeType.LENDER_BROKER, lender_broker_fee_amount, loan.get_lender_broker_fee().wallet),
        FeeAmount(FeeType.BORROWER_BROKER, borrower_broker_fee_amount, loan.get_borrower_broker_fee().wallet),
    ]


@pytest.mark.parametrize("protocol_fee", [0, 100])
@pytest.mark.parametrize("borrower_broker_fee", [0, 200])
@pytest.mark.parametrize("lender_broker_fee", [0, 300])
@pytest.mark.parametrize("origination_fee", [0, 10])
def test_settle_loan_logs_fees(
    bayc,
    borrower,
    lender,
    lender_key,
    now,
    offer_bayc,
    p2p_nfts_usdc,
    usdc,
    protocol_fee,
    borrower_broker_fee,
    lender_broker_fee,
    origination_fee
):

    token_id = 1
    principal = 1000
    lender_broker = boa.env.generate_address("lender_broker") if lender_broker_fee > 0 else ZERO_ADDRESS
    borrower_broker = boa.env.generate_address("borrower_broker") if borrower_broker_fee > 0 else ZERO_ADDRESS
    offer = Offer(
        principal=principal,
        interest=100,
        payment_token=usdc.address,
        duration=100,
        origination_fee_amount=origination_fee,
        broker_fee_bps=lender_broker_fee,
        broker_address=lender_broker,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
        size=1
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_usdc.address)

    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_usdc.address, token_id, sender=borrower)
    usdc.approve(p2p_nfts_usdc.address, principal - origination_fee, sender=lender)

    p2p_nfts_usdc.set_protocol_fee(protocol_fee, sender=p2p_nfts_usdc.owner())
    p2p_nfts_usdc.change_protocol_wallet(p2p_nfts_usdc.owner(), sender=p2p_nfts_usdc.owner())

    loan_id = p2p_nfts_usdc.create_loan(signed_offer, token_id, borrower, borrower_broker_fee, borrower_broker, sender=borrower)

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
        fees=[
            Fee(FeeType.PROTOCOL, 0, p2p_nfts_usdc.protocol_fee(), p2p_nfts_usdc.protocol_wallet()),
            Fee(FeeType.ORIGINATION, offer.origination_fee_amount, 0, lender),
            Fee(FeeType.LENDER_BROKER, 0, offer.broker_fee_bps, offer.broker_address),
            Fee(FeeType.BORROWER_BROKER, 0, borrower_broker_fee, borrower_broker),
        ],
        pro_rata=offer.pro_rata
    )
    assert compute_loan_hash(loan) == p2p_nfts_usdc.loans(loan_id)

    interest = loan.interest
    protocol_fee_amount = interest * loan.get_protocol_fee().interest_bps // 10000
    lender_broker_fee_amount = interest * loan.get_lender_broker_fee().interest_bps // 10000
    borrower_broker_fee_amount = interest * loan.get_borrower_broker_fee().interest_bps // 10000
    amount_to_settle = loan.amount + interest

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    event = get_last_event(p2p_nfts_usdc, "LoanPaid")
    assert event.id == loan.id
    assert event.borrower == loan.borrower
    assert event.lender == loan.lender
    assert event.payment_token == loan.payment_token
    assert event.paid_principal == loan.amount
    assert event.paid_interest == interest

    paid_fees = [
        FeeAmount(FeeType.PROTOCOL, protocol_fee_amount, p2p_nfts_usdc.protocol_wallet()),
        FeeAmount(FeeType.LENDER_BROKER, lender_broker_fee_amount, loan.get_lender_broker_fee().wallet),
        FeeAmount(FeeType.BORROWER_BROKER, borrower_broker_fee_amount, loan.get_borrower_broker_fee().wallet),
    ]
    assert event.paid_settlement_fees == [f for f in paid_fees if f.amount > 0]


def test_settle_loan_doesnt_transfer_excess_amount_from_borrower(p2p_nfts_usdc, ongoing_loan_bayc, usdc):
    interest = ongoing_loan_bayc.interest
    amount_to_settle = ongoing_loan_bayc.amount + interest
    initial_borrower_balance = usdc.balanceOf(ongoing_loan_bayc.borrower)

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle + 1, sender=ongoing_loan_bayc.borrower)
    p2p_nfts_usdc.settle_loan(ongoing_loan_bayc, sender=ongoing_loan_bayc.borrower)
    assert usdc.balanceOf(p2p_nfts_usdc.address) == 0
    assert usdc.balanceOf(ongoing_loan_bayc.borrower) == initial_borrower_balance - amount_to_settle


def test_settle_loan_transfers_collateral_to_borrower_erc721(p2p_nfts_usdc, ongoing_loan_bayc, usdc, bayc):
    loan = ongoing_loan_bayc
    amount_to_settle = loan.amount + loan.interest

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    assert bayc.ownerOf(loan.collateral_token_id) == loan.borrower


def test_settle_loan_transfers_collateral_to_borrower_punks(p2p_nfts_usdc, ongoing_loan_punk, usdc, cryptopunks):
    loan = ongoing_loan_punk
    amount_to_settle = loan.amount + loan.interest

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    assert cryptopunks.ownerOf(loan.collateral_token_id) == loan.borrower


def test_settle_loan_pays_lender(p2p_nfts_usdc, ongoing_loan_bayc, usdc):
    loan = ongoing_loan_bayc
    interest = loan.interest
    protocol_fee_amount = interest * loan.get_protocol_fee().interest_bps // 10000
    lender_broker_fee_amount = interest * loan.get_lender_broker_fee().interest_bps // 10000
    borrower_broker_fee_amount = interest * loan.get_borrower_broker_fee().interest_bps // 10000
    amount_to_settle = loan.amount + interest
    amount_to_receive = loan.amount + interest - protocol_fee_amount - lender_broker_fee_amount - borrower_broker_fee_amount
    initial_lender_balance = usdc.balanceOf(loan.lender)

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    assert usdc.balanceOf(loan.lender) == initial_lender_balance + amount_to_receive


def test_settle_loan_pays_lender_broker_fees(p2p_nfts_usdc, ongoing_loan_bayc, usdc):
    loan = ongoing_loan_bayc
    interest = loan.interest
    lender_broker_fee_amount = interest * loan.get_lender_broker_fee().interest_bps // 10000
    lender_broker = loan.get_lender_broker_fee().wallet
    amount_to_settle = loan.amount + interest
    initial_broker_balance = usdc.balanceOf(lender_broker)

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    assert usdc.balanceOf(lender_broker) == initial_broker_balance + lender_broker_fee_amount


def test_settle_loan_pays_borrower_broker_fees(p2p_nfts_usdc, ongoing_loan_bayc, usdc):
    loan = ongoing_loan_bayc
    interest = loan.interest
    borrower_broker_fee_amount = interest * loan.get_borrower_broker_fee().interest_bps // 10000
    borrower_broker = loan.get_borrower_broker_fee().wallet
    amount_to_settle = loan.amount + interest
    initial_broker_balance = usdc.balanceOf(borrower_broker)

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    assert usdc.balanceOf(borrower_broker) == initial_broker_balance + borrower_broker_fee_amount


def test_settle_loan_pays_protocol_fees(p2p_nfts_usdc, ongoing_loan_bayc, usdc):
    loan = ongoing_loan_bayc
    interest = loan.interest
    protocol_fee_amount = interest * loan.get_protocol_fee().interest_bps // 10000
    amount_to_settle = loan.amount + interest
    initial_protocol_wallet_balance = usdc.balanceOf(p2p_nfts_usdc.protocol_wallet())

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    assert usdc.balanceOf(p2p_nfts_usdc.protocol_wallet()) == initial_protocol_wallet_balance + protocol_fee_amount


def test_settle_loan_prorata_logs_event(p2p_nfts_usdc, ongoing_loan_prorata, usdc):
    loan = ongoing_loan_prorata
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    protocol_fee_amount = interest * loan.get_protocol_fee().interest_bps // 10000
    lender_broker_fee_amount = interest * loan.get_lender_broker_fee().interest_bps // 10000
    borrower_broker_fee_amount = interest * loan.get_borrower_broker_fee().interest_bps // 10000
    amount_to_settle = amount + interest

    print(f"{amount_to_settle=}")
    boa.env.time_travel(seconds=actual_duration)
    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    event = get_last_event(p2p_nfts_usdc, "LoanPaid")
    assert event.id == loan.id
    assert event.borrower == loan.borrower
    assert event.lender == loan.lender
    assert event.payment_token == loan.payment_token
    assert event.paid_principal == amount
    assert event.paid_interest == interest
    assert event.paid_settlement_fees == [
        # FeeAmount(FeeType.PROTOCOL, protocol_fee_amount, p2p_nfts_usdc.protocol_wallet()),
        FeeAmount(FeeType.LENDER_BROKER, lender_broker_fee_amount, loan.get_lender_broker_fee().wallet),
        FeeAmount(FeeType.BORROWER_BROKER, borrower_broker_fee_amount, loan.get_borrower_broker_fee().wallet),
    ]


def test_settle_loan_prorata_pays_lender(p2p_nfts_usdc, ongoing_loan_prorata, usdc):
    loan = ongoing_loan_prorata
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    protocol_fee_amount = interest * loan.get_protocol_fee().interest_bps // 10000
    lender_broker_fee_amount = interest * loan.get_lender_broker_fee().interest_bps // 10000
    borrower_broker_fee_amount = interest * loan.get_borrower_broker_fee().interest_bps // 10000
    amount_to_settle = amount + interest
    amount_to_receive = amount + interest - protocol_fee_amount - lender_broker_fee_amount - borrower_broker_fee_amount
    initial_lender_balance = usdc.balanceOf(loan.lender)

    boa.env.time_travel(seconds=actual_duration)
    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    assert usdc.balanceOf(loan.lender) == initial_lender_balance + amount_to_receive


def test_settle_loan_prorata_pays_lender_broker_fees(p2p_nfts_usdc, ongoing_loan_prorata, usdc):
    loan = ongoing_loan_prorata
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    broker_fee_amount = interest * loan.get_lender_broker_fee().interest_bps // 10000
    broker_address = loan.get_lender_broker_fee().wallet
    amount_to_settle = amount + interest
    initial_broker_balance = usdc.balanceOf(broker_address)

    boa.env.time_travel(seconds=actual_duration)
    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    assert usdc.balanceOf(broker_address) == initial_broker_balance + broker_fee_amount


def test_settle_loan_prorata_pays_borrower_broker_fees(p2p_nfts_usdc, ongoing_loan_prorata, usdc):
    loan = ongoing_loan_prorata
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    broker_fee_amount = interest * loan.get_borrower_broker_fee().interest_bps // 10000
    broker_address = loan.get_borrower_broker_fee().wallet
    amount_to_settle = amount + interest
    initial_broker_balance = usdc.balanceOf(broker_address)

    boa.env.time_travel(seconds=actual_duration)
    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    assert usdc.balanceOf(broker_address) == initial_broker_balance + broker_fee_amount


def test_settle_loan_prorata_pays_protocol_fees(p2p_nfts_usdc, ongoing_loan_prorata, usdc):
    loan = ongoing_loan_prorata
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    protocol_fee_amount = interest * loan.get_protocol_fee().interest_bps // 10000
    amount_to_settle = amount + interest
    initial_protocol_wallet_balance = usdc.balanceOf(p2p_nfts_usdc.protocol_wallet())

    boa.env.time_travel(seconds=actual_duration)
    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    assert usdc.balanceOf(p2p_nfts_usdc.protocol_wallet()) == initial_protocol_wallet_balance + protocol_fee_amount


def test_settle_loan_reverts_if_native_payment_for_erc20(p2p_nfts_usdc, ongoing_loan_bayc):
    with boa.reverts("native payment not allowed"):
        p2p_nfts_usdc.settle_loan(ongoing_loan_bayc, value=1)
