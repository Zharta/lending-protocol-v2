from textwrap import dedent

import boa
import pytest
from eth_utils import decode_hex

from ...conftest_base import (
    ZERO_ADDRESS,
    ZERO_BYTES32,
    CollateralStatus,
    Fee,
    FeeAmount,
    FeeType,
    Loan,
    Offer,
    Signature,
    SignedOffer,
    compute_loan_hash,
    compute_signed_offer_id,
    deploy_reverts,
    get_last_event,
    get_loan_mutations,
    sign_offer,
)

FOREVER = 2**256 - 1


def deposit_and_approve(erc20, amount, sender, spender):
    erc20.deposit(value=amount, sender=sender)
    erc20.approve(spender, amount, sender=sender)


@pytest.fixture
def p2p_nfts_proxy(p2p_nfts_eth, p2p_lending_nfts_proxy_contract_def):
    return p2p_lending_nfts_proxy_contract_def.deploy(p2p_nfts_eth.address)


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
def protocol_fee(p2p_nfts_eth):
    settlement_fee = p2p_nfts_eth.max_protocol_settlement_fee()
    upfront_fee = 11
    p2p_nfts_eth.set_protocol_fee(upfront_fee, settlement_fee, sender=p2p_nfts_eth.owner())
    p2p_nfts_eth.change_protocol_wallet(p2p_nfts_eth.owner(), sender=p2p_nfts_eth.owner())
    return Fee.protocol(p2p_nfts_eth, 11)


@pytest.fixture
def offer_bayc(now, lender, lender_key, bayc, broker, p2p_nfts_eth):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=10,
        broker_upfront_fee_amount=15,
        broker_settlement_fee_bps=2000,
        broker_address=broker,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
        size=1,
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
        broker_upfront_fee_amount=15,
        broker_settlement_fee_bps=2000,
        broker_address=broker,
        collateral_contract=cryptopunks.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
        size=1,
    )
    return sign_offer(offer, lender_key, p2p_nfts_eth.address)


@pytest.fixture
def ongoing_loan_bayc(p2p_nfts_eth, offer_bayc, weth, borrower, lender, bayc, now, borrower_broker_fee, protocol_fee):
    offer = offer_bayc.offer
    token_id = offer.collateral_min_token_id
    principal = offer.principal
    origination_fee = offer.origination_fee_amount

    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_eth.address, token_id, sender=borrower)
    lender_approval = principal - origination_fee + offer.broker_upfront_fee_amount
    weth.deposit(value=lender_approval, sender=lender)
    weth.approve(p2p_nfts_eth.address, lender_approval, sender=lender)

    loan_id = p2p_nfts_eth.create_loan(
        offer_bayc,
        token_id,
        borrower,
        borrower_broker_fee.upfront_amount,
        borrower_broker_fee.settlement_bps,
        borrower_broker_fee.wallet,
        sender=borrower,
    )

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
            Fee.protocol(p2p_nfts_eth, principal),
            Fee.origination(offer),
            Fee.lender_broker(offer),
            borrower_broker_fee,
        ],
        pro_rata=offer.pro_rata,
    )
    assert compute_loan_hash(loan) == p2p_nfts_eth.loans(loan_id)
    return loan


@pytest.fixture
def ongoing_loan_punk(p2p_nfts_eth, offer_punk, weth, borrower, lender, cryptopunks, now, borrower_broker_fee):
    offer = offer_punk.offer
    token_id = offer.collateral_min_token_id
    principal = offer.principal
    origination_fee = offer.origination_fee_amount

    cryptopunks.mint(borrower, token_id)
    cryptopunks.offerPunkForSaleToAddress(token_id, 0, p2p_nfts_eth.address, sender=borrower)
    lender_approval = principal - origination_fee + offer.broker_upfront_fee_amount
    weth.deposit(value=lender_approval, sender=lender)
    weth.approve(p2p_nfts_eth.address, lender_approval, sender=lender)

    loan_id = p2p_nfts_eth.create_loan(
        offer_punk,
        token_id,
        borrower,
        borrower_broker_fee.upfront_amount,
        borrower_broker_fee.settlement_bps,
        borrower_broker_fee.wallet,
        sender=borrower,
    )

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
            Fee.protocol(p2p_nfts_eth, principal),
            Fee.origination(offer),
            Fee.lender_broker(offer),
            borrower_broker_fee,
        ],
        pro_rata=offer.pro_rata,
    )
    assert compute_loan_hash(loan) == p2p_nfts_eth.loans(loan_id)
    return loan


@pytest.fixture
def ongoing_loan_prorata(
    p2p_nfts_eth,
    offer_bayc,
    weth,
    borrower,
    lender,
    bayc,
    now,
    lender_key,
    borrower_broker_fee,
    protocol_fee,
):
    offer = Offer(**offer_bayc.offer._asdict() | {"pro_rata": True})
    token_id = offer.collateral_min_token_id
    principal = offer.principal
    origination_fee = offer.origination_fee_amount

    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_eth.address, token_id, sender=borrower)
    lender_approval = principal - origination_fee + offer.broker_upfront_fee_amount
    weth.deposit(value=lender_approval, sender=lender)
    weth.approve(p2p_nfts_eth.address, lender_approval, sender=lender)

    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)
    loan_id = p2p_nfts_eth.create_loan(
        signed_offer,
        token_id,
        borrower,
        borrower_broker_fee.upfront_amount,
        borrower_broker_fee.settlement_bps,
        borrower_broker_fee.wallet,
        sender=borrower,
    )

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
            Fee.protocol(p2p_nfts_eth, principal),
            Fee.origination(offer),
            Fee.lender_broker(offer),
            borrower_broker_fee,
        ],
        pro_rata=offer.pro_rata,
    )
    assert compute_loan_hash(loan) == p2p_nfts_eth.loans(loan_id)
    return loan


def test_settle_loan_reverts_if_loan_invalid(p2p_nfts_eth, ongoing_loan_bayc):
    for loan in get_loan_mutations(ongoing_loan_bayc):
        print(f"{loan=}")
        with boa.reverts("invalid loan"):
            p2p_nfts_eth.settle_loan(loan, sender=ongoing_loan_bayc.borrower)


def test_settle_loan_reverts_if_loan_defaulted(p2p_nfts_eth, ongoing_loan_bayc, now):
    time_to_default = ongoing_loan_bayc.maturity - now
    boa.env.time_travel(seconds=time_to_default + 1)

    with boa.reverts("loan defaulted"):
        p2p_nfts_eth.settle_loan(ongoing_loan_bayc, sender=ongoing_loan_bayc.borrower)


def test_settle_loan_reverts_if_not_borrower(p2p_nfts_eth, ongoing_loan_bayc):
    loan = ongoing_loan_bayc
    interest = loan.interest
    amount_to_settle = loan.amount + interest
    random = boa.env.generate_address("random")
    boa.env.set_balance(random, amount_to_settle)

    with boa.reverts("not borrower"):
        p2p_nfts_eth.settle_loan(loan, sender=random, value=amount_to_settle)


def test_settle_loan_reverts_if_proxy_not_auth(p2p_nfts_eth, ongoing_loan_bayc, p2p_nfts_proxy):
    loan = ongoing_loan_bayc
    interest = loan.interest
    amount_to_settle = loan.amount + interest

    p2p_nfts_eth.set_proxy_authorization(p2p_nfts_proxy, False, sender=p2p_nfts_eth.owner())
    with boa.reverts("not borrower"):
        p2p_nfts_proxy.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)


def test_settle_loan_reverts_if_loan_already_settled(p2p_nfts_eth, ongoing_loan_bayc):
    loan = ongoing_loan_bayc
    interest = loan.interest
    amount_to_settle = loan.amount + interest

    p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)

    with boa.reverts("invalid loan"):
        p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)


def test_settle_loan_reverts_if_funds_not_sent(p2p_nfts_eth, ongoing_loan_bayc):
    interest = ongoing_loan_bayc.interest
    amount_to_settle = ongoing_loan_bayc.amount + interest

    with boa.reverts("invalid sent value"):
        p2p_nfts_eth.settle_loan(ongoing_loan_bayc, sender=ongoing_loan_bayc.borrower, value=amount_to_settle - 1)


def test_settle_loan_prorata_reverts_if_funds_not_sent(p2p_nfts_eth, ongoing_loan_prorata):
    loan = ongoing_loan_prorata
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    amount_to_settle = amount + interest

    boa.env.time_travel(seconds=actual_duration)
    with boa.reverts("invalid sent value"):
        p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle - 1)


def test_settle_loan(p2p_nfts_eth, ongoing_loan_bayc):
    loan = ongoing_loan_bayc
    interest = loan.interest
    amount_to_settle = loan.amount + interest

    p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)

    assert p2p_nfts_eth.loans(loan.id) == ZERO_BYTES32
    assert boa.env.get_balance(p2p_nfts_eth.address) == 0


def test_settle_loan_logs_event(p2p_nfts_eth, ongoing_loan_bayc):
    loan = ongoing_loan_bayc
    interest = loan.interest
    protocol_fee_amount = interest * loan.get_protocol_fee().settlement_bps // 10000
    lender_broker_fee_amount = interest * loan.get_lender_broker_fee().settlement_bps // 10000
    borrower_broker_fee_amount = interest * loan.get_borrower_broker_fee().settlement_bps // 10000
    amount_to_settle = loan.amount + interest

    p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)

    event = get_last_event(p2p_nfts_eth, "LoanPaid")
    assert event.id == loan.id
    assert event.borrower == loan.borrower
    assert event.lender == loan.lender
    assert event.payment_token == loan.payment_token
    assert event.paid_principal == loan.amount
    assert event.paid_interest == interest
    assert event.paid_settlement_fees == [
        FeeAmount(FeeType.PROTOCOL, protocol_fee_amount, p2p_nfts_eth.protocol_wallet()),
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
    borrower,
    lender,
    lender_key,
    now,
    p2p_nfts_eth,
    weth,
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
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=origination_fee,
        broker_upfront_fee_amount=lender_broker_upfront_fee,
        broker_settlement_fee_bps=lender_broker_settlement_fee,
        broker_address=lender_broker,
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
    deposit_and_approve(weth, principal - origination_fee + offer.broker_upfront_fee_amount, lender, p2p_nfts_eth.address)

    p2p_nfts_eth.set_protocol_fee(protocol_upfront_fee, protocol_settlement_fee, sender=p2p_nfts_eth.owner())
    p2p_nfts_eth.change_protocol_wallet(p2p_nfts_eth.owner(), sender=p2p_nfts_eth.owner())

    loan_id = p2p_nfts_eth.create_loan(
        signed_offer,
        token_id,
        borrower,
        borrower_broker_upfront_fee,
        borrower_broker_settlement_fee,
        borrower_broker,
        sender=borrower,
    )

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
            Fee.protocol(p2p_nfts_eth, principal),
            Fee.origination(offer),
            Fee.lender_broker(offer),
            Fee.borrower_broker(borrower_broker, borrower_broker_upfront_fee, borrower_broker_settlement_fee),
        ],
        pro_rata=offer.pro_rata,
    )
    assert compute_loan_hash(loan) == p2p_nfts_eth.loans(loan_id)

    interest = loan.interest
    protocol_fee_amount = interest * loan.get_protocol_fee().settlement_bps // 10000
    lender_broker_fee_amount = interest * loan.get_lender_broker_fee().settlement_bps // 10000
    borrower_broker_fee_amount = interest * loan.get_borrower_broker_fee().settlement_bps // 10000
    amount_to_settle = loan.amount + interest

    p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)

    event = get_last_event(p2p_nfts_eth, "LoanPaid")
    assert event.id == loan.id
    assert event.borrower == loan.borrower
    assert event.lender == loan.lender
    assert event.payment_token == loan.payment_token
    assert event.paid_principal == loan.amount
    assert event.paid_interest == interest

    paid_fees = [
        FeeAmount(FeeType.PROTOCOL, protocol_fee_amount, p2p_nfts_eth.protocol_wallet()),
        FeeAmount(FeeType.LENDER_BROKER, lender_broker_fee_amount, loan.get_lender_broker_fee().wallet),
        FeeAmount(FeeType.BORROWER_BROKER, borrower_broker_fee_amount, loan.get_borrower_broker_fee().wallet),
    ]
    assert event.paid_settlement_fees == [f for f in paid_fees if f.amount > 0]


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
    protocol_fee_amount = interest * loan.get_protocol_fee().settlement_bps // 10000
    lender_broker_fee_amount = interest * loan.get_lender_broker_fee().settlement_bps // 10000
    borrower_broker_fee_amount = interest * loan.get_borrower_broker_fee().settlement_bps // 10000
    amount_to_settle = loan.amount + interest
    amount_to_receive = loan.amount + interest - protocol_fee_amount - lender_broker_fee_amount - borrower_broker_fee_amount
    initial_lender_balance = boa.env.get_balance(loan.lender)

    p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)

    assert boa.env.get_balance(loan.lender) == initial_lender_balance + amount_to_receive


def test_settle_loan_pays_lender_broker_fees(p2p_nfts_eth, ongoing_loan_bayc, weth):
    loan = ongoing_loan_bayc
    interest = loan.interest
    lender_broker_fee_amount = interest * loan.get_lender_broker_fee().settlement_bps // 10000
    lender_broker = loan.get_lender_broker_fee().wallet
    amount_to_settle = loan.amount + interest
    initial_broker_balance = boa.env.get_balance(lender_broker)

    p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)

    assert boa.env.get_balance(lender_broker) == initial_broker_balance + lender_broker_fee_amount


def test_settle_loan_pays_borrower_broker_fees(p2p_nfts_eth, ongoing_loan_bayc, weth):
    loan = ongoing_loan_bayc
    interest = loan.interest
    borrower_broker_fee_amount = interest * loan.get_borrower_broker_fee().settlement_bps // 10000
    borrower_broker = loan.get_borrower_broker_fee().wallet
    amount_to_settle = loan.amount + interest
    initial_broker_balance = boa.env.get_balance(borrower_broker)

    p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)

    assert boa.env.get_balance(borrower_broker) == initial_broker_balance + borrower_broker_fee_amount


def test_settle_loan_pays_protocol_fees(p2p_nfts_eth, ongoing_loan_bayc, weth):
    loan = ongoing_loan_bayc
    interest = loan.interest
    protocol_fee_amount = interest * loan.get_protocol_fee().settlement_bps // 10000
    amount_to_settle = loan.amount + interest
    initial_protocol_wallet_balance = boa.env.get_balance(p2p_nfts_eth.protocol_wallet())

    p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)

    assert boa.env.get_balance(p2p_nfts_eth.protocol_wallet()) == initial_protocol_wallet_balance + protocol_fee_amount


def test_settle_loan_works_with_proxy(p2p_nfts_eth, ongoing_loan_bayc, weth, p2p_nfts_proxy):
    loan = ongoing_loan_bayc
    interest = loan.interest
    protocol_fee_amount = interest * loan.get_protocol_fee().settlement_bps // 10000
    amount_to_settle = loan.amount + interest
    initial_protocol_wallet_balance = boa.env.get_balance(p2p_nfts_eth.protocol_wallet())

    p2p_nfts_eth.set_proxy_authorization(p2p_nfts_proxy, True, sender=p2p_nfts_eth.owner())
    p2p_nfts_proxy.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)

    assert boa.env.get_balance(p2p_nfts_eth.protocol_wallet()) == initial_protocol_wallet_balance + protocol_fee_amount


def test_settle_loan_prorata_logs_event(p2p_nfts_eth, ongoing_loan_prorata, weth):
    loan = ongoing_loan_prorata
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    protocol_fee_amount = interest * loan.get_protocol_fee().settlement_bps // 10000
    lender_broker_fee_amount = interest * loan.get_lender_broker_fee().settlement_bps // 10000
    borrower_broker_fee_amount = interest * loan.get_borrower_broker_fee().settlement_bps // 10000
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
    assert event.paid_settlement_fees == [
        FeeAmount(FeeType.PROTOCOL, protocol_fee_amount, p2p_nfts_eth.protocol_wallet()),
        FeeAmount(FeeType.LENDER_BROKER, lender_broker_fee_amount, loan.get_lender_broker_fee().wallet),
        FeeAmount(FeeType.BORROWER_BROKER, borrower_broker_fee_amount, loan.get_borrower_broker_fee().wallet),
    ]


def test_settle_loan_prorata_pays_lender(p2p_nfts_eth, ongoing_loan_prorata, weth):
    loan = ongoing_loan_prorata
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    protocol_fee_amount = interest * loan.get_protocol_fee().settlement_bps // 10000
    lender_broker_fee_amount = interest * loan.get_lender_broker_fee().settlement_bps // 10000
    borrower_broker_fee_amount = interest * loan.get_borrower_broker_fee().settlement_bps // 10000
    amount_to_settle = amount + interest
    amount_to_receive = amount + interest - protocol_fee_amount - lender_broker_fee_amount - borrower_broker_fee_amount
    initial_lender_balance = boa.env.get_balance(loan.lender)

    boa.env.time_travel(seconds=actual_duration)
    p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)

    assert boa.env.get_balance(loan.lender) == initial_lender_balance + amount_to_receive


def test_settle_loan_prorata_pays_lender_broker_fees(p2p_nfts_eth, ongoing_loan_prorata, weth):
    loan = ongoing_loan_prorata
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    broker_fee_amount = interest * loan.get_lender_broker_fee().settlement_bps // 10000
    broker_address = loan.get_lender_broker_fee().wallet
    amount_to_settle = amount + interest
    initial_broker_balance = boa.env.get_balance(broker_address)

    boa.env.time_travel(seconds=actual_duration)
    p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)

    assert boa.env.get_balance(broker_address) == initial_broker_balance + broker_fee_amount


def test_settle_loan_prorata_pays_borrower_broker_fees(p2p_nfts_eth, ongoing_loan_prorata, weth):
    loan = ongoing_loan_prorata
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    broker_fee_amount = interest * loan.get_borrower_broker_fee().settlement_bps // 10000
    broker_address = loan.get_borrower_broker_fee().wallet
    amount_to_settle = amount + interest
    initial_broker_balance = boa.env.get_balance(broker_address)

    boa.env.time_travel(seconds=actual_duration)
    p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)

    assert boa.env.get_balance(broker_address) == initial_broker_balance + broker_fee_amount


def test_settle_loan_prorata_pays_protocol_fees(p2p_nfts_eth, ongoing_loan_prorata, weth):
    loan = ongoing_loan_prorata
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    protocol_fee_amount = interest * loan.get_protocol_fee().settlement_bps // 10000
    amount_to_settle = amount + interest
    initial_protocol_wallet_balance = boa.env.get_balance(p2p_nfts_eth.protocol_wallet())

    boa.env.time_travel(seconds=actual_duration)
    p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)

    assert boa.env.get_balance(p2p_nfts_eth.protocol_wallet()) == initial_protocol_wallet_balance + protocol_fee_amount
