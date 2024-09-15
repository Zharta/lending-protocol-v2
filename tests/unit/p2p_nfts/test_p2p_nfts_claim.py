import boa
import pytest

from ...conftest_base import (
    ZERO_ADDRESS,
    ZERO_BYTES32,
    Fee,
    Loan,
    Offer,
    compute_loan_hash,
    get_last_event,
    get_loan_mutations,
    sign_offer,
)


@pytest.fixture
def p2p_nfts_proxy(p2p_nfts_usdc, p2p_lending_nfts_proxy_contract_def):
    return p2p_lending_nfts_proxy_contract_def.deploy(p2p_nfts_usdc.address)


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
def offer_bayc(now, lender, lender_key, bayc, broker, p2p_nfts_usdc, usdc):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=usdc.address,
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
    return sign_offer(offer, lender_key, p2p_nfts_usdc.address)


@pytest.fixture
def ongoing_loan_bayc(p2p_nfts_usdc, offer_bayc, usdc, borrower, lender, bayc, now, borrower_broker_fee):
    offer = offer_bayc.offer
    token_id = offer.collateral_min_token_id
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
        fees=[Fee.protocol(p2p_nfts_usdc, principal), Fee.origination(offer), Fee.lender_broker(offer), borrower_broker_fee],
        pro_rata=offer.pro_rata,
    )
    assert compute_loan_hash(loan) == p2p_nfts_usdc.loans(loan_id)
    return loan


@pytest.fixture
def offer_punk(now, lender, lender_key, cryptopunks, broker, p2p_nfts_usdc, usdc):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=usdc.address,
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
    return sign_offer(offer, lender_key, p2p_nfts_usdc.address)


@pytest.fixture
def ongoing_loan_punk(p2p_nfts_usdc, offer_punk, usdc, borrower, lender, cryptopunks, now, borrower_broker_fee):
    offer = offer_punk.offer
    token_id = offer.collateral_min_token_id
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
        fees=[Fee.protocol(p2p_nfts_usdc, principal), Fee.origination(offer), Fee.lender_broker(offer), borrower_broker_fee],
        pro_rata=offer.pro_rata,
    )
    assert compute_loan_hash(loan) == p2p_nfts_usdc.loans(loan_id)
    return loan


def test_claim_defaulted_reverts_if_loan_invalid(p2p_nfts_usdc, ongoing_loan_bayc):
    for loan in get_loan_mutations(ongoing_loan_bayc):
        print(f"{loan=}")
        with boa.reverts("invalid loan"):
            p2p_nfts_usdc.claim_defaulted_loan_collateral(loan, sender=ongoing_loan_bayc.borrower)


def test_claim_defaulted_reverts_if_loan_not_defaulted(p2p_nfts_usdc, ongoing_loan_bayc, now):
    time_to_default = ongoing_loan_bayc.maturity - now
    boa.env.time_travel(seconds=time_to_default - 1)

    with boa.reverts("loan not defaulted"):
        p2p_nfts_usdc.claim_defaulted_loan_collateral(ongoing_loan_bayc, sender=ongoing_loan_bayc.lender)


def test_claim_defaulted_reverts_if_not_lender(p2p_nfts_usdc, ongoing_loan_bayc, now, p2p_nfts_proxy):
    time_to_default = ongoing_loan_bayc.maturity - now
    boa.env.time_travel(seconds=time_to_default + 1)

    with boa.reverts("not lender"):
        p2p_nfts_usdc.claim_defaulted_loan_collateral(ongoing_loan_bayc, sender=ongoing_loan_bayc.borrower)

    p2p_nfts_usdc.set_proxy_authorization(p2p_nfts_proxy, True, sender=p2p_nfts_usdc.owner())
    with boa.reverts("not lender"):
        p2p_nfts_proxy.claim_defaulted_loan_collateral(ongoing_loan_bayc, sender=ongoing_loan_bayc.borrower)


def test_claim_defaulted_reverts_with_unauth_proxy(p2p_nfts_usdc, ongoing_loan_bayc, now, usdc, p2p_nfts_proxy):
    time_to_default = ongoing_loan_bayc.maturity - now
    boa.env.time_travel(seconds=time_to_default + 1)

    with boa.reverts("not lender"):
        p2p_nfts_proxy.claim_defaulted_loan_collateral(ongoing_loan_bayc, sender=ongoing_loan_bayc.lender)


def test_claim_defaulted(p2p_nfts_usdc, ongoing_loan_bayc, now, usdc):
    time_to_default = ongoing_loan_bayc.maturity - now

    boa.env.time_travel(seconds=time_to_default + 1)

    p2p_nfts_usdc.claim_defaulted_loan_collateral(ongoing_loan_bayc, sender=ongoing_loan_bayc.lender)

    assert p2p_nfts_usdc.loans(ongoing_loan_bayc.id) == ZERO_BYTES32
    assert boa.env.get_balance(p2p_nfts_usdc.address) == 0


def test_claim_defaulted_works_with_proxy(p2p_nfts_usdc, ongoing_loan_bayc, now, usdc, p2p_nfts_proxy):
    p2p_nfts_usdc.set_proxy_authorization(p2p_nfts_proxy, True, sender=p2p_nfts_usdc.owner())

    time_to_default = ongoing_loan_bayc.maturity - now

    boa.env.time_travel(seconds=time_to_default + 1)

    p2p_nfts_proxy.claim_defaulted_loan_collateral(ongoing_loan_bayc, sender=ongoing_loan_bayc.lender)

    assert p2p_nfts_usdc.loans(ongoing_loan_bayc.id) == ZERO_BYTES32
    assert boa.env.get_balance(p2p_nfts_usdc.address) == 0


def test_claim_defaulted_logs_event(p2p_nfts_usdc, ongoing_loan_bayc, now, usdc):
    time_to_default = ongoing_loan_bayc.maturity - now

    boa.env.time_travel(seconds=time_to_default + 1)

    p2p_nfts_usdc.claim_defaulted_loan_collateral(ongoing_loan_bayc, sender=ongoing_loan_bayc.lender)

    event = get_last_event(p2p_nfts_usdc, "LoanCollateralClaimed")
    assert event.id == ongoing_loan_bayc.id
    assert event.borrower == ongoing_loan_bayc.borrower
    assert event.lender == ongoing_loan_bayc.lender
    assert event.collateral_contract == ongoing_loan_bayc.collateral_contract
    assert event.collateral_token_id == ongoing_loan_bayc.collateral_token_id


def test_claim_defaulted_transfers_collateral_to_lender(p2p_nfts_usdc, ongoing_loan_bayc, now, usdc, bayc):
    time_to_default = ongoing_loan_bayc.maturity - now
    collateral_token_id = ongoing_loan_bayc.collateral_token_id

    boa.env.time_travel(seconds=time_to_default + 1)

    p2p_nfts_usdc.claim_defaulted_loan_collateral(ongoing_loan_bayc, sender=ongoing_loan_bayc.lender)

    assert bayc.ownerOf(collateral_token_id) == ongoing_loan_bayc.lender


def test_claim_defaulted_transfers_collateral_to_lender_punk(p2p_nfts_usdc, ongoing_loan_punk, now, usdc, cryptopunks):
    time_to_default = ongoing_loan_punk.maturity - now
    collateral_token_id = ongoing_loan_punk.collateral_token_id

    boa.env.time_travel(seconds=time_to_default + 1)

    p2p_nfts_usdc.claim_defaulted_loan_collateral(ongoing_loan_punk, sender=ongoing_loan_punk.lender)

    assert cryptopunks.ownerOf(collateral_token_id) == ongoing_loan_punk.lender
