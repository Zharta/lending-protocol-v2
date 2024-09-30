from textwrap import dedent

import boa
import pytest

from ...conftest_base import (
    ZERO_ADDRESS,
    ZERO_BYTES32,
    CollectionContract,
    Fee,
    FeeAmount,
    FeeType,
    Loan,
    Offer,
    compute_loan_hash,
    compute_signed_offer_id,
    get_last_event,
    get_loan_mutations,
    sign_offer,
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
def borrower_broker_fee(borrower_broker):
    return Fee.borrower_broker(borrower_broker, upfront_amount=15, settlement_bps=300)


@pytest.fixture
def protocol_fees(p2p_nfts_usdc):
    settlement_fee = 1000
    upfront_fee = 11
    p2p_nfts_usdc.set_protocol_fee(upfront_fee, settlement_fee, sender=p2p_nfts_usdc.owner())
    p2p_nfts_usdc.change_protocol_wallet(p2p_nfts_usdc.owner(), sender=p2p_nfts_usdc.owner())
    return settlement_fee


@pytest.fixture
def offer_bayc(now, lender, lender_key, bayc, broker, p2p_nfts_usdc, usdc, bayc_key_hash):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=usdc.address,
        duration=100,
        origination_fee_amount=10,
        broker_upfront_fee_amount=15,
        broker_settlement_fee_bps=200,
        broker_address=broker,
        collection_key_hash=bayc_key_hash,
        token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
        size=1,
    )
    return sign_offer(offer, lender_key, p2p_nfts_usdc.address)


@pytest.fixture
def offer_punk(now, lender, lender_key, cryptopunks, broker, p2p_nfts_usdc, usdc, punks_key_hash):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=usdc.address,
        duration=100,
        origination_fee_amount=10,
        broker_upfront_fee_amount=15,
        broker_settlement_fee_bps=200,
        broker_address=broker,
        collection_key_hash=punks_key_hash,
        token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
        size=1,
    )
    return sign_offer(offer, lender_key, p2p_nfts_usdc.address)


@pytest.fixture
def ongoing_loan_bayc(p2p_nfts_usdc, offer_bayc, usdc, borrower, lender, bayc, now, protocol_fees, borrower_broker_fee):
    offer = offer_bayc.offer
    token_id = offer.token_id
    principal = offer.principal
    origination_fee = offer.origination_fee_amount

    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_usdc.address, token_id, sender=borrower)
    lender_approval = principal - origination_fee + offer.broker_upfront_fee_amount
    usdc.deposit(value=lender_approval, sender=lender)
    usdc.approve(p2p_nfts_usdc.address, lender_approval, sender=lender)

    loan_id = p2p_nfts_usdc.create_loan(
        offer_bayc,
        token_id,
        [],
        borrower,
        borrower_broker_fee.upfront_amount,
        borrower_broker_fee.settlement_bps,
        borrower_broker_fee.wallet,
        sender=borrower,
    )

    loan = Loan(
        id=loan_id,
        offer_id=compute_signed_offer_id(offer_bayc),
        amount=offer.principal,
        interest=offer.interest,
        payment_token=offer.payment_token,
        maturity=now + offer.duration,
        start_time=now,
        borrower=borrower,
        lender=lender,
        collateral_contract=bayc.address,
        collateral_token_id=token_id,
        fees=[Fee.protocol(p2p_nfts_usdc, principal), Fee.origination(offer), Fee.lender_broker(offer), borrower_broker_fee],
        pro_rata=offer.pro_rata,
    )
    assert compute_loan_hash(loan) == p2p_nfts_usdc.loans(loan_id)
    return loan


@pytest.fixture
def ongoing_loan_punk(p2p_nfts_usdc, offer_punk, usdc, borrower, lender, cryptopunks, now, borrower_broker_fee):
    offer = offer_punk.offer
    token_id = offer.token_id
    principal = offer.principal
    origination_fee = offer.origination_fee_amount

    cryptopunks.mint(borrower, token_id)
    cryptopunks.offerPunkForSaleToAddress(token_id, 0, p2p_nfts_usdc.address, sender=borrower)
    lender_approval = principal - origination_fee + offer.broker_upfront_fee_amount
    usdc.deposit(value=lender_approval, sender=lender)
    usdc.approve(p2p_nfts_usdc.address, lender_approval, sender=lender)

    loan_id = p2p_nfts_usdc.create_loan(
        offer_punk,
        token_id,
        [],
        borrower,
        borrower_broker_fee.upfront_amount,
        borrower_broker_fee.settlement_bps,
        borrower_broker_fee.wallet,
        sender=borrower,
    )

    loan = Loan(
        id=loan_id,
        offer_id=compute_signed_offer_id(offer_punk),
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
            Fee.protocol(p2p_nfts_usdc, principal),
            Fee.origination(offer),
            Fee.lender_broker(offer),
            borrower_broker_fee,
        ],
        pro_rata=offer.pro_rata,
    )
    assert compute_loan_hash(loan) == p2p_nfts_usdc.loans(loan_id)
    return loan


@pytest.fixture
def ongoing_loan_prorata(p2p_nfts_usdc, offer_bayc, usdc, borrower, lender, bayc, now, lender_key, borrower_broker_fee):
    offer = Offer(**offer_bayc.offer._asdict() | {"pro_rata": True})
    token_id = offer.token_id
    principal = offer.principal
    origination_fee = offer.origination_fee_amount

    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_usdc.address, token_id, sender=borrower)
    lender_approval = principal - origination_fee + offer.broker_upfront_fee_amount
    usdc.deposit(value=lender_approval, sender=lender)
    usdc.approve(p2p_nfts_usdc.address, lender_approval, sender=lender)

    signed_offer = sign_offer(offer, lender_key, p2p_nfts_usdc.address)
    loan_id = p2p_nfts_usdc.create_loan(
        signed_offer,
        token_id,
        [],
        borrower,
        borrower_broker_fee.upfront_amount,
        borrower_broker_fee.settlement_bps,
        borrower_broker_fee.wallet,
        sender=borrower,
    )

    loan = Loan(
        id=loan_id,
        offer_id=compute_signed_offer_id(signed_offer),
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
            Fee.protocol(p2p_nfts_usdc, principal),
            Fee.origination(offer),
            Fee.lender_broker(offer),
            borrower_broker_fee,
        ],
        pro_rata=offer.pro_rata,
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


def test_settle_loan_reverts_if_loan_already_settled(p2p_nfts_usdc, ongoing_loan_bayc, usdc, now):
    loan = ongoing_loan_bayc
    interest = loan.interest
    borrower_broker_fee = loan.calc_borrower_broker_settlement_fee(now)
    amount_to_settle = loan.amount + interest + borrower_broker_fee

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    with boa.reverts("invalid loan"):
        usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
        p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)


def test_settle_loan_reverts_if_funds_not_approved(p2p_nfts_usdc, ongoing_loan_bayc, usdc, now):
    interest = ongoing_loan_bayc.interest
    borrower_broker_fee = ongoing_loan_bayc.calc_borrower_broker_settlement_fee(now)
    amount_to_settle = ongoing_loan_bayc.amount + interest + borrower_broker_fee

    with boa.reverts():
        usdc.approve(p2p_nfts_usdc.address, amount_to_settle - 1, sender=ongoing_loan_bayc.borrower)
        p2p_nfts_usdc.settle_loan(ongoing_loan_bayc, sender=ongoing_loan_bayc.borrower)


def test_settle_loan_prorata_reverts_if_funds_not_approved(p2p_nfts_usdc, ongoing_loan_prorata, usdc, now):
    loan = ongoing_loan_prorata
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    interest = loan.interest * actual_duration // loan_duration
    borrower_broker_fee = loan.calc_borrower_broker_settlement_fee(now)
    amount_to_settle = loan.amount + interest + borrower_broker_fee

    boa.env.time_travel(seconds=actual_duration)
    with boa.reverts():
        usdc.approve(p2p_nfts_usdc.address, amount_to_settle - 1, sender=loan.borrower)
        p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)


def test_settle_loan(p2p_nfts_usdc, ongoing_loan_bayc, usdc, now):
    loan = ongoing_loan_bayc
    interest = loan.interest
    borrower_broker_fee = loan.calc_borrower_broker_settlement_fee(now)
    amount_to_settle = loan.amount + interest + borrower_broker_fee

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    assert p2p_nfts_usdc.loans(loan.id) == ZERO_BYTES32
    assert usdc.balanceOf(p2p_nfts_usdc.address) == 0


def test_settle_loan_decreases_offer_count(p2p_nfts_usdc, ongoing_loan_bayc, usdc):
    loan = ongoing_loan_bayc
    interest = loan.interest
    borrower_broker_fee_amount = interest * loan.get_borrower_broker_fee().settlement_bps // 10000
    amount_to_settle = loan.amount + interest + borrower_broker_fee_amount

    offer_count_before = p2p_nfts_usdc.offer_count(ongoing_loan_bayc.offer_id)
    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    assert p2p_nfts_usdc.offer_count(ongoing_loan_bayc.offer_id) == offer_count_before - 1


def test_settle_loan_logs_event(p2p_nfts_usdc, ongoing_loan_bayc, usdc, now):
    loan = ongoing_loan_bayc
    interest = loan.interest
    protocol_fee_amount = interest * loan.get_protocol_fee().settlement_bps // 10000
    lender_broker_fee_amount = interest * loan.get_lender_broker_fee().settlement_bps // 10000
    borrower_broker_fee_amount = interest * loan.get_borrower_broker_fee().settlement_bps // 10000
    amount_to_settle = loan.amount + interest + borrower_broker_fee_amount

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


@pytest.mark.slow
@pytest.mark.parametrize("protocol_upfront_fee", [0, 3])
@pytest.mark.parametrize("protocol_settlement_fee", [0, 100])
@pytest.mark.parametrize("borrower_broker_upfront_fee", [0, 5])
@pytest.mark.parametrize("borrower_broker_settlement_fee", [0, 200])
@pytest.mark.parametrize("lender_broker_upfront_fee", [0, 7])
@pytest.mark.parametrize("lender_broker_settlement_fee", [0, 300])
@pytest.mark.parametrize("origination_fee", [0, 10])
def test_settle_loan_logs_fees(
    bayc,
    bayc_key_hash,
    borrower,
    lender,
    lender_key,
    now,
    offer_bayc,
    p2p_nfts_usdc,
    usdc,
    protocol_upfront_fee,
    protocol_settlement_fee,
    borrower_broker_upfront_fee,
    borrower_broker_settlement_fee,
    lender_broker_upfront_fee,
    lender_broker_settlement_fee,
    origination_fee,
):
    token_id = 1
    principal = 1000
    lender_broker = (
        boa.env.generate_address("lender_broker")
        if lender_broker_upfront_fee or lender_broker_settlement_fee
        else ZERO_ADDRESS
    )
    borrower_broker = (
        boa.env.generate_address("borrower_broker")
        if borrower_broker_upfront_fee or borrower_broker_settlement_fee
        else ZERO_ADDRESS
    )
    offer = Offer(
        principal=principal,
        interest=100,
        payment_token=usdc.address,
        duration=100,
        origination_fee_amount=origination_fee,
        broker_upfront_fee_amount=lender_broker_upfront_fee,
        broker_settlement_fee_bps=lender_broker_settlement_fee,
        broker_address=lender_broker,
        collection_key_hash=bayc_key_hash,
        token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
        size=1,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_usdc.address)

    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_usdc.address, token_id, sender=borrower)
    usdc.approve(p2p_nfts_usdc.address, principal - origination_fee + offer.broker_upfront_fee_amount, sender=lender)

    p2p_nfts_usdc.set_protocol_fee(protocol_upfront_fee, protocol_settlement_fee, sender=p2p_nfts_usdc.owner())
    p2p_nfts_usdc.change_protocol_wallet(p2p_nfts_usdc.owner(), sender=p2p_nfts_usdc.owner())

    loan_id = p2p_nfts_usdc.create_loan(
        signed_offer,
        token_id,
        [],
        borrower,
        borrower_broker_upfront_fee,
        borrower_broker_settlement_fee,
        borrower_broker,
        sender=borrower,
    )

    loan = Loan(
        id=loan_id,
        offer_id=compute_signed_offer_id(signed_offer),
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
            Fee.protocol(p2p_nfts_usdc, principal),
            Fee.origination(offer),
            Fee.lender_broker(offer),
            Fee.borrower_broker(borrower_broker, borrower_broker_upfront_fee, borrower_broker_settlement_fee),
        ],
        pro_rata=offer.pro_rata,
    )
    assert compute_loan_hash(loan) == p2p_nfts_usdc.loans(loan_id)

    interest = loan.interest
    protocol_fee_amount = interest * loan.get_protocol_fee().settlement_bps // 10000
    lender_broker_fee_amount = interest * loan.get_lender_broker_fee().settlement_bps // 10000
    borrower_broker_fee_amount = interest * loan.get_borrower_broker_fee().settlement_bps // 10000
    amount_to_settle = loan.amount + interest + borrower_broker_fee_amount

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


def test_settle_loan_doesnt_transfer_excess_amount_from_borrower(p2p_nfts_usdc, ongoing_loan_bayc, usdc, now):
    interest = ongoing_loan_bayc.interest
    borrower_broker_fee = ongoing_loan_bayc.calc_borrower_broker_settlement_fee(now)
    amount_to_settle = ongoing_loan_bayc.amount + interest + borrower_broker_fee
    initial_borrower_balance = usdc.balanceOf(ongoing_loan_bayc.borrower)

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle + 1, sender=ongoing_loan_bayc.borrower)
    p2p_nfts_usdc.settle_loan(ongoing_loan_bayc, sender=ongoing_loan_bayc.borrower)
    assert usdc.balanceOf(p2p_nfts_usdc.address) == 0
    assert usdc.balanceOf(ongoing_loan_bayc.borrower) == initial_borrower_balance - amount_to_settle


def test_settle_loan_transfers_collateral_to_borrower_erc721(p2p_nfts_usdc, ongoing_loan_bayc, usdc, bayc, now):
    loan = ongoing_loan_bayc
    borrower_broker_fee = loan.calc_borrower_broker_settlement_fee(now)
    amount_to_settle = loan.amount + loan.interest + borrower_broker_fee

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    assert bayc.ownerOf(loan.collateral_token_id) == loan.borrower


def test_settle_loan_transfers_collateral_to_borrower_punks(p2p_nfts_usdc, ongoing_loan_punk, usdc, cryptopunks, now):
    loan = ongoing_loan_punk
    borrower_broker_fee = loan.calc_borrower_broker_settlement_fee(now)
    amount_to_settle = loan.amount + loan.interest + borrower_broker_fee

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    assert cryptopunks.ownerOf(loan.collateral_token_id) == loan.borrower


def test_settle_loan_pays_lender(p2p_nfts_usdc, ongoing_loan_bayc, usdc, now):
    loan = ongoing_loan_bayc
    interest = loan.interest
    protocol_fee_amount = interest * loan.get_protocol_fee().settlement_bps // 10000
    lender_broker_fee_amount = interest * loan.get_lender_broker_fee().settlement_bps // 10000
    borrower_broker_fee_amount = interest * loan.get_borrower_broker_fee().settlement_bps // 10000
    amount_to_settle = loan.amount + interest + borrower_broker_fee_amount
    amount_to_receive = loan.amount + interest - protocol_fee_amount - lender_broker_fee_amount
    initial_lender_balance = usdc.balanceOf(loan.lender)

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    assert usdc.balanceOf(loan.lender) == initial_lender_balance + amount_to_receive


def test_settle_loan_pays_lender_broker_fees(p2p_nfts_usdc, ongoing_loan_bayc, usdc, now):
    loan = ongoing_loan_bayc
    interest = loan.interest
    lender_broker_fee_amount = interest * loan.get_lender_broker_fee().settlement_bps // 10000
    lender_broker = loan.get_lender_broker_fee().wallet
    borrower_broker_fee = loan.calc_borrower_broker_settlement_fee(now)
    amount_to_settle = loan.amount + interest + borrower_broker_fee
    initial_broker_balance = usdc.balanceOf(lender_broker)

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    assert usdc.balanceOf(lender_broker) == initial_broker_balance + lender_broker_fee_amount


def test_settle_loan_pays_borrower_broker_fees(p2p_nfts_usdc, ongoing_loan_bayc, usdc):
    loan = ongoing_loan_bayc
    interest = loan.interest
    borrower_broker_fee_amount = interest * loan.get_borrower_broker_fee().settlement_bps // 10000
    borrower_broker = loan.get_borrower_broker_fee().wallet
    amount_to_settle = loan.amount + interest + borrower_broker_fee_amount
    initial_broker_balance = usdc.balanceOf(borrower_broker)

    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    assert usdc.balanceOf(borrower_broker) == initial_broker_balance + borrower_broker_fee_amount


def test_settle_loan_pays_protocol_fees(p2p_nfts_usdc, ongoing_loan_bayc, usdc, now):
    loan = ongoing_loan_bayc
    interest = loan.interest
    protocol_fee_amount = interest * loan.get_protocol_fee().settlement_bps // 10000
    borrower_broker_fee = loan.calc_borrower_broker_settlement_fee(now)
    amount_to_settle = loan.amount + interest + borrower_broker_fee
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
    interest * loan.get_protocol_fee().settlement_bps // 10000
    lender_broker_fee_amount = interest * loan.get_lender_broker_fee().settlement_bps // 10000
    borrower_broker_fee_amount = interest * loan.get_borrower_broker_fee().settlement_bps // 10000
    amount_to_settle = amount + interest + borrower_broker_fee_amount

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
    protocol_fee_amount = interest * loan.get_protocol_fee().settlement_bps // 10000
    lender_broker_fee_amount = interest * loan.get_lender_broker_fee().settlement_bps // 10000
    borrower_broker_fee_amount = interest * loan.get_borrower_broker_fee().settlement_bps // 10000
    amount_to_settle = amount + interest + borrower_broker_fee_amount
    amount_to_receive = amount + interest - protocol_fee_amount - lender_broker_fee_amount
    initial_lender_balance = usdc.balanceOf(loan.lender)

    boa.env.time_travel(seconds=actual_duration)
    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    assert usdc.balanceOf(loan.lender) == initial_lender_balance + amount_to_receive


def test_settle_loan_prorata_pays_lender_broker_fees(p2p_nfts_usdc, ongoing_loan_prorata, usdc, now):
    loan = ongoing_loan_prorata
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    interest = loan.interest * actual_duration // loan_duration
    broker_fee_amount = interest * loan.get_lender_broker_fee().settlement_bps // 10000
    broker_address = loan.get_lender_broker_fee().wallet
    borrower_broker_fee = loan.calc_borrower_broker_settlement_fee(now + actual_duration)
    amount_to_settle = loan.amount + interest + borrower_broker_fee
    initial_broker_balance = usdc.balanceOf(broker_address)

    boa.env.time_travel(seconds=actual_duration)
    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    assert usdc.balanceOf(broker_address) == initial_broker_balance + broker_fee_amount


def test_settle_loan_prorata_pays_borrower_broker_fees(p2p_nfts_usdc, ongoing_loan_prorata, usdc, now):
    loan = ongoing_loan_prorata
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    interest = loan.interest * actual_duration // loan_duration
    broker_fee_amount = interest * loan.get_borrower_broker_fee().settlement_bps // 10000
    broker_address = loan.get_borrower_broker_fee().wallet
    borrower_broker_fee = loan.calc_borrower_broker_settlement_fee(now + actual_duration)
    amount_to_settle = loan.amount + interest + borrower_broker_fee
    initial_broker_balance = usdc.balanceOf(broker_address)

    boa.env.time_travel(seconds=actual_duration)
    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    assert usdc.balanceOf(broker_address) == initial_broker_balance + broker_fee_amount


def test_settle_loan_prorata_pays_protocol_fees(p2p_nfts_usdc, ongoing_loan_prorata, usdc, now):
    loan = ongoing_loan_prorata
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    interest = loan.interest * actual_duration // loan_duration
    protocol_fee_amount = interest * loan.get_protocol_fee().settlement_bps // 10000
    borrower_broker_fee = loan.calc_borrower_broker_settlement_fee(now + actual_duration)
    amount_to_settle = loan.amount + interest + borrower_broker_fee
    initial_protocol_wallet_balance = usdc.balanceOf(p2p_nfts_usdc.protocol_wallet())

    boa.env.time_travel(seconds=actual_duration)
    usdc.approve(p2p_nfts_usdc.address, amount_to_settle, sender=loan.borrower)
    p2p_nfts_usdc.settle_loan(loan, sender=loan.borrower)

    assert usdc.balanceOf(p2p_nfts_usdc.protocol_wallet()) == initial_protocol_wallet_balance + protocol_fee_amount


def test_settle_loan_creates_pending_transfer_on_erc20_transfer_fail(
    p2p_lending_nfts_contract_def,
    p2p_control,
    weth,
    bayc,
    bayc_key_hash,
    delegation_registry,
    cryptopunks,
    owner,
    borrower,
    lender,
    lender_key,
    now,
):
    failing_erc20_code = dedent("""

            @external
            def transfer(_to : address, _value : uint256) -> bool:
                return False

            @external
            def transferFrom(_from : address, _to : address, _value : uint256) -> bool:
                return True

            """)
    erc20 = boa.loads(failing_erc20_code)
    p2p_nfts_erc20 = p2p_lending_nfts_contract_def.deploy(
        erc20, p2p_control, delegation_registry, cryptopunks, 0, 0, owner, 0, 0, 0, 0
    )
    p2p_control.change_collections_contracts([CollectionContract(bayc_key_hash, bayc.address)])

    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=erc20.address,
        duration=100,
        origination_fee_amount=10,
        broker_upfront_fee_amount=0,
        broker_settlement_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collection_key_hash=bayc_key_hash,
        token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
        size=1,
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_erc20.address)

    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_erc20.address, token_id, sender=borrower)

    loan_id = p2p_nfts_erc20.create_loan(signed_offer, token_id, [], borrower, 0, 0, ZERO_ADDRESS, sender=borrower)
    loan = Loan(
        id=loan_id,
        offer_id=compute_signed_offer_id(signed_offer),
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
            Fee.protocol(p2p_nfts_erc20, offer.principal),
            Fee.origination(offer),
            Fee.lender_broker(offer),
            Fee.borrower_broker(ZERO_ADDRESS),
        ],
        pro_rata=offer.pro_rata,
    )
    assert compute_loan_hash(loan) == p2p_nfts_erc20.loans(loan_id)

    p2p_nfts_erc20.settle_loan(loan, sender=loan.borrower)

    assert p2p_nfts_erc20.pending_transfers(lender) == loan.amount + loan.interest


def test_claim_pending_transactions(p2p_nfts_usdc, usdc):
    user = boa.env.generate_address()
    value = 10**6

    p2p_nfts_usdc.eval(f"self.pending_transfers[{user}] = {value}")
    boa.env.set_balance(p2p_nfts_usdc.address, value)
    usdc.deposit(value=value, sender=p2p_nfts_usdc.address)

    assert usdc.balanceOf(user) == 0
    assert p2p_nfts_usdc.pending_transfers(user) == value

    p2p_nfts_usdc.claim_pending_transfers(sender=user)

    assert usdc.balanceOf(user) == value
    assert p2p_nfts_usdc.pending_transfers(user) == 0

    with boa.reverts("no pending transfers"):
        p2p_nfts_usdc.claim_pending_transfers(sender=user)
